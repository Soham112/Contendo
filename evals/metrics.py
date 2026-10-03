"""Metrics for one generation, built from its generation_traces row (no pipeline re-run).

Test cases:
    input              topic, plus the golden's context when it has one
    actual_output      node_outputs.final_post
    retrieval_context  retrieved chunk texts; for faithfulness and
                       unsupported_specifics the author profile is added as one
                       extra item, so facts from the profile count as supported
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from deepeval.metrics import (
    AnswerRelevancyMetric,
    BaseMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams

import eval_config as config

UNSUPPORTED_SPECIFICS_STEPS = [
    "List every specific claim in the actual output: names of people, companies, products or "
    "projects; numbers, percentages, money amounts, dates and durations; and first-person "
    "incidents (things the author says happened to them or their team).",
    "For each specific, check whether the retrieval context (knowledge-base excerpts and the "
    "author profile) states it or directly supports it.",
    "Ignore opinions, advice, rhetorical questions and generic statements; they are not specifics.",
    "Give a high score when every specific is supported. Lower the score for each unsupported "
    "specific, most of all for invented numbers and invented first-person incidents.",
]


def profile_text(profile: dict[str, Any]) -> str:
    """The profile exactly as the pipeline formats it for its prompts."""
    from memory.profile_store import profile_to_context_string  # backend import: env.py loaded first

    return "Author profile:\n" + profile_to_context_string(profile)


def build_input(golden: dict[str, Any]) -> str:
    context = (golden.get("context") or "").strip()
    return golden["topic"] if not context else f"{golden['topic']}\n\nContext: {context}"


def chunk_texts(trace: dict[str, Any]) -> list[str]:
    return [c["text"] for c in (trace.get("retrieved") or []) if (c.get("text") or "").strip()]


def retrieved_titles(trace: dict[str, Any]) -> list[str]:
    return [c.get("source_title", "") for c in (trace.get("retrieved") or [])]


def final_post(trace: dict[str, Any]) -> str:
    return ((trace.get("node_outputs") or {}).get("final_post")) or ""


def build_cases(
    trace: dict[str, Any],
    golden: dict[str, Any],
    profile_formatter: Callable[[dict[str, Any]], str] = profile_text,
) -> dict[str, LLMTestCase]:
    """Two test cases per golden: chunks only, and chunks plus the profile."""
    chunks = chunk_texts(trace)
    common = {"input": build_input(golden), "actual_output": final_post(trace), "name": golden["id"]}
    return {
        "chunks": LLMTestCase(retrieval_context=chunks, **common),
        "grounded": LLMTestCase(
            retrieval_context=chunks + [profile_formatter(trace.get("profile_snapshot") or {})], **common
        ),
    }


class SourceRecallMetric(BaseMetric):
    """Share of the golden's expected source titles that retrieval returned. Deterministic.

    Skipped (score None) when the golden expects no sources, e.g. off_topic.
    """

    def __init__(self, expected_titles: list[str], threshold: float = config.THRESHOLDS["source_recall"]):
        self.expected_titles = list(expected_titles)
        self.threshold = threshold
        self.include_reason = True
        self.async_mode = False
        self.strict_mode = False
        self.evaluation_model = None
        self.skipped = False

    def measure(self, test_case: LLMTestCase, *args: Any, retrieved: Optional[list[str]] = None, **kwargs: Any) -> Optional[float]:
        retrieved_set = set(retrieved or [])
        if not self.expected_titles:
            self.skipped = True
            self.score = None
            self.success = None
            self.reason = "skipped: golden expects no sources"
            return None
        found = [t for t in self.expected_titles if t in retrieved_set]
        missing = [t for t in self.expected_titles if t not in retrieved_set]
        self.score = len(found) / len(self.expected_titles)
        self.success = self.score >= self.threshold
        self.reason = f"retrieved {len(found)}/{len(self.expected_titles)} expected sources" + (
            f"; missing: {missing}" if missing else ""
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> Optional[float]:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "source_recall"


@dataclass(frozen=True)
class MetricSpec:
    name: str
    case: str  # "chunks" or "grounded"
    build: Callable[[Any], BaseMetric]
    needs_chunks: bool = False  # skip (not 0) when retrieval returned nothing


def judge_metric_specs() -> list[MetricSpec]:
    """The LLM-judged metrics. Each build(judge) returns a fresh metric."""
    t = config.THRESHOLDS
    common = {"async_mode": False, "include_reason": True}
    return [
        MetricSpec("answer_relevancy", "chunks",
                   lambda judge: AnswerRelevancyMetric(threshold=t["answer_relevancy"], model=judge, **common)),
        MetricSpec("contextual_relevancy", "chunks",
                   lambda judge: ContextualRelevancyMetric(threshold=t["contextual_relevancy"], model=judge, **common),
                   needs_chunks=True),
        MetricSpec("faithfulness", "grounded",
                   lambda judge: FaithfulnessMetric(threshold=t["faithfulness"], model=judge, **common)),
        MetricSpec("unsupported_specifics", "grounded",
                   lambda judge: GEval(
                       name="unsupported_specifics",
                       evaluation_steps=UNSUPPORTED_SPECIFICS_STEPS,
                       evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT],
                       threshold=t["unsupported_specifics"],
                       model=judge,
                       async_mode=False,
                       _include_g_eval_suffix=False,
                   )),
    ]
