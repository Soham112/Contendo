"""The review's verdicts, decided in code.

The review model (agents/review_agent.py) does not judge a post, and it never
sees the post's citations. For every sentence it reports observations: what
kind of thing the sentence says, how it is stated and presented, which sources
state it, which of its words nothing states, which detail differs from a source,
whether it links facts, whether it leaves the topic. derive_issues() turns
those observations into issues by fixed rules, using the sentence's citation
(from the draft, which only code has) and the run's source index. The pieces of
text a record quotes have already been checked against the sentence and the
sources; no rule reads free text.

The seven issue types, each standing for one thing a redraft can do:
  not_in_sources     a fact, feeling, motive or event, or a generalisation stated
                     as fact, that nothing states; or words of a sentence
                     stated as fact that nothing states (unsupported_part)
  wrong_citation     something states it, but the sentence's citation does not
                     point there
  changed_detail     a source states it, with a detail that differs
  wrong_attribution  an external source's content presented as the author's own,
                     the author's own content credited to a source, or content
                     credited to a source when no source states it
  cross_source_link  facts from different sources linked, with no source stating the link
  off_topic          the sentence leaves the topic
  ai_rhythm          from the review's post-level list (see review_agent)
"""

from typing import Any

from utils.citations import Span

REQUEST = "request"

ISSUE_TYPES = ("not_in_sources", "changed_detail", "wrong_citation", "wrong_attribution",
               "cross_source_link", "off_topic", "ai_rhythm")

# Content that needs something to state it: when nothing does, it is not_in_sources.
# A generalisation is in this group only when it is stated as fact.
_NEEDS_SUPPORT = frozenset({"fact_or_event", "feeling_or_reaction", "motive"})
# Content that is the author's own by its nature. It needs no support, its
# citation is not checked, and it is not an attribution of anything.
_AUTHORS_OWN = frozenset({"disclaimer", "opinion", "advice_or_question"})
# An analogy is the author's own too, unless the sentence presents it as one of these.
_NOT_AUTHORS_FRAMING = frozenset({"a_source_says", "author_did_or_experienced"})


def _is_authors_own(record: dict) -> bool:
    if record["content"] in _AUTHORS_OWN:
        return True
    return record["content"] == "analogy_or_comparison" and record["presented_as"] not in _NOT_AUTHORS_FRAMING


def _needs_support(record: dict) -> bool:
    if record["content"] in _NEEDS_SUPPORT:
        return True
    if record["content"] == "generalisation":
        return record["stated_as"] == "fact"
    # An analogy told as something that happened to the author is a claim that it happened.
    return record["content"] == "analogy_or_comparison" and record["presented_as"] == "author_did_or_experienced"


def _citation_points_at(sentence: Span, supported_by: list[str]) -> bool:
    """Whether the sentence's own citation names only places that state it."""
    if sentence.basis == "sources":
        return all(sid in supported_by for sid in sentence.sources)
    if sentence.basis == "request":
        return REQUEST in supported_by
    return False                                    # cited as a view, or not cited at all


def derive_issues(records: list[dict], sentences: list[tuple[int, Span]],
                  source_index: dict[str, dict]) -> list[dict[str, Any]]:
    """Issues for the sentence records, in sentence order.

    records: one validated record per sentence, in order (review_agent): its
    detail_change and unsupported_part are present only if they passed their checks.
    sentences: (span position, sentence) for the same sentences.
    Each issue is {type, sentence, span, text, sources, evidence, detail}:
    sentence is 0-based; sources are the ids a redraft needs (the supporting
    sources for wrong_citation and changed_detail, the linked ones for
    cross_source_link); evidence is the source's own words where there are
    any; detail is a small dict of the observations the rule used.
    """
    issues: list[dict[str, Any]] = []
    for position, (record, (span_position, sentence)) in enumerate(zip(records, sentences)):
        supported_by = record.get("supported_by") or []
        supporting_sources = [sid for sid in supported_by if sid != REQUEST]
        authorships = {source_index[sid]["authorship"] for sid in supporting_sources}
        authors_own = _is_authors_own(record)

        def issue(kind: str, sources=(), evidence=None, **detail: Any) -> None:
            issues.append({"type": kind, "sentence": position, "span": span_position, "text": sentence.text,
                           "sources": list(sources), "evidence": evidence, "detail": detail})

        unsupported_part = record.get("unsupported_part")
        if _needs_support(record) and not supported_by:
            issue("not_in_sources", content=record["content"], stated_as=record["stated_as"])
        elif unsupported_part and record["stated_as"] == "fact" and not authors_own:
            issue("not_in_sources", content=record["content"], stated_as=record["stated_as"],
                  unsupported_part=unsupported_part)

        if supported_by and not authors_own and not _citation_points_at(sentence, supported_by):
            issue("wrong_citation", supporting_sources, record.get("evidence"),
                  cited=list(sentence.sources) if sentence.basis == "sources" else sentence.basis,
                  supported_by=list(supported_by))

        change = record.get("detail_change")
        if change:
            issue("changed_detail", supporting_sources, change["source_words"],
                  source_words=change["source_words"], post_words=change["post_words"])

        if not authors_own:
            presented = record["presented_as"]
            if presented == "author_did_or_experienced" and authorships == {"external"}:
                issue("wrong_attribution", supporting_sources, record.get("evidence"),
                      presented_as=presented, authorship="external")
            elif presented == "a_source_says" and authorships == {"self"}:
                issue("wrong_attribution", supporting_sources, record.get("evidence"),
                      presented_as=presented, authorship="self")
            elif presented == "a_source_says" and not supporting_sources:
                issue("wrong_attribution", presented_as=presented, authorship="none")

        link = record.get("link")
        if link and len(set(link["sources"])) > 1 and not link.get("stated_by"):
            issue("cross_source_link", sorted(set(link["sources"])))

        if record.get("off_topic"):
            issue("off_topic")
    return issues
