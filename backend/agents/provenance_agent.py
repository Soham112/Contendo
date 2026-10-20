"""Provenance classifier (step 3.3): whose material a source is.

Two independent structured Haiku calls (samples) per part of the source, run
in parallel (one part unless the text is longer than
utils.provenance_spans.MAX_PART_CHARS). Each labels the text user_authored or
external and names the paragraphs with the other label; code turns that into
offsets and decides whether the result is confident enough to apply without
asking the user.

Confident means, for every part: both samples answered, they give every
paragraph the same label, neither was uncertain, every evidence quote is in
the text, each gave some evidence, and every paragraph number and source fact
cited exists. The API gives no probabilities, and a wrong reading can be well
quoted (evals/baselines/2026-10-19-provenance-v1.md, tc-p03), so agreement
between samples is the check on the reading itself. When the samples disagree,
a paragraph either calls external is external (the safe side). Measured on
labelled sources before anything reads the result (CODEBASE.md "Step 3 data layer").

Called at ingest (agents/ingestion_agent.py) and by scripts/backfill_authorship.py;
nothing reads the result yet. user_stated and system_inferred are set by rule,
never here.
"""
import contextvars
import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from functools import lru_cache

from pydantic import BaseModel, Field, create_model

from agents.provenance_prompt import SYSTEM_PROMPT, AuthorContext, SourceFacts, user_message
from llm.client import HAIKU, StructuredOutputError, complete_structured
from llm.pricing import call_cost
from config.niches import SEGMENT_BUSINESS, get_niche
from memory.account_store import get_account
from memory.experience_store import experience_nodes_to_context_string, get_experience_nodes
from memory.profile_store import load_profile
from utils.business_notes import profile_note
from utils.provenance_spans import Paragraph, merge_runs, paragraphs, parts

logger = logging.getLogger(__name__)

# Bump when SYSTEM_PROMPT, the schema, the confidence rule or the model changes
# (stored with every result in sources.authorship_detail).
# 2: provider_author fact, byline / interview / evidence rules, two samples.
# 3: source_facts_used offers only the facts that have a value (reading_schema).
# 4: signed_by, checked against the user's name and the labels (v3 baseline: tc-p07).
CLASSIFIER = ("provenance_agent", "4")

# Independent readings per part; the result is confident only when they agree.
SAMPLES = 2

# How much of the source's opening later parts see, for context.
OPENING_CHARS = 1_500

Label = Literal["user_authored", "external"]
FactName = Literal["title", "input_type", "source_type", "provider_author"]


class ProvenanceReading(BaseModel):
    reasoning: str = Field(description="Who is speaking and whose experience the text describes; written before the label")
    signed_by: str | None = Field(default=None, description=(
        "The name a byline, signature or sign-off gives for the whole text, copied exactly from the text; "
        "null when the text is unsigned"))
    authorship: Label = Field(description="The label that fits most of the text")
    other_paragraphs: list[int] = Field(default_factory=list,
                                        description="Numbers N of the [PN] paragraphs that have the other label")
    evidence_quotes: list[str] = Field(default_factory=list,
                                       description="Up to three passages copied exactly from the text that settle the decision")
    source_facts_used: list[FactName] = Field(default_factory=list,
                                              description="Source facts that settle the decision")
    uncertain: bool = Field(description="True when the text and source facts do not settle it")


@lru_cache(maxsize=None)
def _schema_for(given: tuple[str, ...]) -> type[ProvenanceReading]:
    if given:
        facts_field = (list[Literal[given]], Field(default_factory=list, description="Source facts that settle the decision"))
    else:
        facts_field = (list[str], Field(default_factory=list, max_length=0, description="No source facts were given"))
    return create_model("ProvenanceReading", __base__=ProvenanceReading, source_facts_used=facts_field)


def reading_schema(facts: SourceFacts) -> type[ProvenanceReading]:
    """The answer schema for one source: source_facts_used offers only the facts
    that have a value, so an absent fact cannot be cited (the v1 and v2 baselines:
    the model cited provider_author when none was reported)."""
    return _schema_for(facts.given())


@dataclass
class Provenance:
    authorship: str                  # the source's label: user_authored | external
    confident: bool                  # apply without asking the user
    spans: list[dict]                # passages whose label differs: [{start, end, authorship}]
    reasons: list[str]               # why it is not confident; empty when it is
    readings: list[ProvenanceReading] = field(default_factory=list)   # every sample, part by part
    # What each failed sample's attempts returned (StructuredOutputError.replies), with the part
    # number. For diagnosis; detail() keeps only how many there were.
    failures: list[dict] = field(default_factory=list)

    def detail(self) -> dict[str, Any]:
        """The value for sources.authorship_detail."""
        return {
            "spans": self.spans,
            "classifier": {
                "name": CLASSIFIER[0], "version": CLASSIFIER[1],
                "confident": self.confident, "reasons": self.reasons, "samples": SAMPLES,
                "failed_samples": len(self.failures),
                "readings": [r.model_dump() for r in self.readings],
            },
        }


_QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_QUOTE_CHARS)).strip()


def _quote_in_text(quote: str, text: str) -> bool:
    quote = _normalised(quote).strip("\"' ")
    return bool(quote) and quote in text


def _opening(paras: list[Paragraph]) -> list[Paragraph]:
    opening = [paras[0]]
    for para in paras[1:]:
        if para.end - paras[0].start > OPENING_CHARS:
            break
        opening.append(para)
    return opening


_NAME_TOKEN = re.compile(r"\w+")


def _name_tokens(text: str) -> list[str]:
    return [t.casefold() for t in _NAME_TOKEN.findall(text)]


def _contains_name(signed_by: str, name: str) -> bool:
    """Every word of `name`, in order, as consecutive words of the signature."""
    want, have = _name_tokens(name), _name_tokens(signed_by)
    return bool(want) and any(have[i:i + len(want)] == want for i in range(len(have) - len(want) + 1))


def _signed_by_user(signed_by: str, author: AuthorContext) -> bool:
    """The signature contains the user's full name or their business's full
    name. A first name or initials alone do not match: the reading is then
    asked about, never applied as the user's (the safe side)."""
    return _contains_name(signed_by, author.name) or _contains_name(signed_by, author.business_name)


def _check(reading: ProvenanceReading, part: list[Paragraph], text_normalised: str,
           facts: SourceFacts, author: AuthorContext, where: str) -> list[str]:
    """Reasons this part's reading is not confident (structural checks only)."""
    reasons = []
    if reading.signed_by:
        if not _quote_in_text(reading.signed_by, text_normalised):
            reasons.append(f"{where}: the signature is not in the text")
        elif (not _signed_by_user(reading.signed_by, author)
              and "user_authored" in _paragraph_labels(reading, part).values()):
            reasons.append(f"{where}: signed by someone other than the user, yet labelled the user's")
    if reading.uncertain:
        reasons.append(f"{where}: the model was uncertain")
    ids = {p.id for p in part}
    if any(i not in ids for i in reading.other_paragraphs):
        reasons.append(f"{where}: paragraph numbers outside this part")
    if any(not _quote_in_text(q, text_normalised) for q in reading.evidence_quotes):
        reasons.append(f"{where}: an evidence quote is not in the text")
    if any(not getattr(facts, name) for name in reading.source_facts_used):
        reasons.append(f"{where}: cited a source fact that was not given")
    if not reading.evidence_quotes and not reading.source_facts_used:
        reasons.append(f"{where}: no evidence given")
    return reasons


def _source_label(paras: list[Paragraph], labels: dict[int, str]) -> str:
    """The label covering most characters; a tie is external (the safe side)."""
    size = {"user_authored": 0, "external": 0}
    for para in paras:
        size[labels[para.id]] += para.end - para.start
    return "user_authored" if size["user_authored"] > size["external"] else "external"


TOOL_NAME = "record_provenance"
TOOL_DESCRIPTION = "Record whose material the text is, with the evidence."
MAX_TOKENS = 800


@dataclass(frozen=True)
class PartRequest:
    """One classifier call: the paragraphs it labels and the message it sends."""
    number: int
    count: int
    paragraphs: list[Paragraph]
    message: str


def plan_requests(text: str, *, facts: SourceFacts, author: AuthorContext) -> list[PartRequest]:
    """The calls classify_provenance makes for this text, in order (also what
    the eval's cost estimate counts). Empty when the text has no paragraphs."""
    paras = paragraphs(text)
    if not paras:
        return []
    groups = parts(paras)
    opening = _opening(paras)
    return [PartRequest(number, len(groups), part,
                        user_message(text, part, part_number=number, part_count=len(groups),
                                     opening=opening, facts=facts, author=author))
            for number, part in enumerate(groups, start=1)]


# Offline cost estimate (the eval's --estimate and the backfill's): characters
# per token for English prose (expected), and a denser ratio for the upper
# bound; the forced tool call's own system prompt; a typical answer.
CHARS_PER_TOKEN, CHARS_PER_TOKEN_UPPER = 3.5, 3.0
TOOL_USE_OVERHEAD_TOKENS = 350
TYPICAL_OUTPUT_TOKENS = 300


def request_chars(text: str, *, facts: SourceFacts, author: AuthorContext) -> list[int]:
    """Characters each call of classify_provenance sends: system prompt, tool definition, message."""
    schema = reading_schema(facts).model_json_schema()
    fixed = len(SYSTEM_PROMPT) + len(TOOL_NAME) + len(TOOL_DESCRIPTION) + len(json.dumps(schema))
    return [fixed + len(r.message) for r in plan_requests(text, facts=facts, author=author)]


def estimated_tokens(chars: int) -> tuple[int, int]:
    """(expected, upper-bound) input tokens of one call that sends `chars` characters."""
    return (math.ceil(chars / CHARS_PER_TOKEN) + TOOL_USE_OVERHEAD_TOKENS,
            math.ceil(chars / CHARS_PER_TOKEN_UPPER) + TOOL_USE_OVERHEAD_TOKENS)


def call_costs(input_pairs: list[tuple[int, int]]) -> tuple[int, int, float, float]:
    """(calls, expected input tokens, expected USD, upper-bound USD) for parts
    with these (expected, upper) input tokens: SAMPLES calls per part, and a
    structured call is retried at most once, so the upper bound doubles every
    call at max_tokens."""
    calls = tokens = 0
    expected = upper = 0.0
    for exp_in, up_in in input_pairs:
        calls += SAMPLES
        tokens += SAMPLES * exp_in
        expected += SAMPLES * call_cost(HAIKU, exp_in, TYPICAL_OUTPUT_TOKENS)
        upper += SAMPLES * 2 * call_cost(HAIKU, up_in, MAX_TOKENS)
    return calls, tokens, expected, upper


def _read(request: PartRequest, schema: type[ProvenanceReading],
          user_id: str) -> ProvenanceReading | StructuredOutputError:
    """One sample of one part, or the error when it gave no valid answer after its retry."""
    try:
        return complete_structured(
            schema=schema,
            tool_name=TOOL_NAME,
            tool_description=TOOL_DESCRIPTION,
            model=HAIKU,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": request.message}],
            user_id=user_id,
            event_type="provenance_classify",
            usage_metadata={"part": request.number, "parts": request.count},
        )
    except StructuredOutputError as e:
        logger.warning("provenance sample failed (part %d of %d): %s", request.number, request.count, e)
        return e


def _samples(request: PartRequest, schema: type[ProvenanceReading],
             user_id: str) -> list[ProvenanceReading | StructuredOutputError]:
    """SAMPLES readings of one part, in parallel. Each thread runs in a copy of
    this context, so the calls stay in the caller's trace (trace_calls)."""
    with ThreadPoolExecutor(max_workers=SAMPLES) as pool:
        futures = [pool.submit(contextvars.copy_context().run, _read, request, schema, user_id)
                   for _ in range(SAMPLES)]
        return [f.result() for f in futures]


def _paragraph_labels(reading: ProvenanceReading, part: list[Paragraph]) -> dict[int, str]:
    other = "external" if reading.authorship == "user_authored" else "user_authored"
    flipped = set(reading.other_paragraphs)
    return {p.id: other if p.id in flipped else reading.authorship for p in part}


def classify_provenance(text: str, *, facts: SourceFacts, author: AuthorContext,
                        user_id: str) -> Provenance | None:
    """Label a source's text. None when the text is empty or no sample of some
    part gave a valid answer (the source stays unknown and the user is asked).
    API errors propagate."""
    requests = plan_requests(text, facts=facts, author=author)
    if not requests:
        return None
    text_normalised = _normalised(text)
    labels: dict[int, str] = {}
    readings: list[ProvenanceReading] = []
    reasons: list[str] = []
    failures: list[dict] = []
    schema = reading_schema(facts)
    for request in requests:
        answers = _samples(request, schema, user_id)
        samples = [a for a in answers if isinstance(a, ProvenanceReading)]
        failures += [{"part": request.number, "replies": a.replies} for a in answers
                     if isinstance(a, StructuredOutputError)]
        if not samples:
            return None
        where = f"part {request.number}" if request.count > 1 else "source"
        if len(samples) < SAMPLES:
            reasons.append(f"{where}: a sample gave no valid answer")
        for reading in samples:
            readings.append(reading)
            reasons += [r for r in _check(reading, request.paragraphs, text_normalised, facts, author, where)
                        if r not in reasons]
        sampled = [_paragraph_labels(r, request.paragraphs) for r in samples]
        if any(s != sampled[0] for s in sampled[1:]):
            reasons.append(f"{where}: the samples disagree")
        for para in request.paragraphs:
            labels[para.id] = "external" if any(s[para.id] == "external" for s in sampled) else "user_authored"
    paras = [p for request in requests for p in request.paragraphs]
    authorship = _source_label(paras, labels)
    differing = {i: label for i, label in labels.items() if label != authorship}
    return Provenance(authorship=authorship, confident=not reasons,
                      spans=merge_runs(paras, differing), reasons=reasons, readings=readings,
                      failures=failures)


def author_context_from(profile: dict | None, account: dict | None, nodes: list[dict]) -> AuthorContext:
    """Who the user is: profile name and role, a business account's profile,
    and experience nodes."""
    profile, account = profile or {}, account or {}
    business = ""
    if account.get("segment") == SEGMENT_BUSINESS and account.get("business_profile"):
        business = profile_note(account["business_profile"], get_niche(account.get("business_niche")),
                                account.get("business_niche_other"))
    business_name = ""
    if account.get("segment") == SEGMENT_BUSINESS:
        business_name = str((account.get("business_profile") or {}).get("business_name") or "")
    return AuthorContext(
        name=str(profile.get("name") or ""),
        business_name=business_name,
        role=str(profile.get("role") or ""),
        business=business,
        experience=experience_nodes_to_context_string(nodes),
    )


def author_context(user_id: str) -> AuthorContext:
    return author_context_from(load_profile(user_id), get_account(user_id), get_experience_nodes(user_id))
