"""Shared builders for the finalise, trim and single-writer length tests
(test_finalise.py, test_trim.py, test_single_writer_length.py)."""

from anthropic.types import Message, TextBlock, Usage

from tests.test_generation_trace import USER as KB_USER

FIRST_POST_USER = "user-first-post"   # no posts and no notes: every run is a first post (70-100 words)
TRIM = "claude-haiku-4-5-20251001"
# Runs with one draft, no review and no redraft: variant C, and variant B at
# quality="draft". Standard variant B is tested in test_pipeline_b.py.
DRAFT_ONLY = [("C", "standard"), ("B", "draft")]


def _lines(count: int, words_each: int = 10, marker: str = "[[V]]") -> list[str]:
    """count one-span lines of words_each words, each with a marker."""
    filler = " ".join(["word"] * (words_each - 2))
    return [f"Line {i} {filler} {marker}" for i in range(1, count + 1)]


def _post(count: int, words_each: int = 10) -> str:
    return "\n\n".join(_lines(count, words_each))


def _clean(marked: str) -> str:
    from utils.citations import strip_citations

    return strip_citations(marked).text


def _cut_off(text: str = "") -> Message:
    return Message(id="msg_cut", type="message", role="assistant", model="fake",
                   content=[TextBlock(type="text", text=text)], stop_reason="max_tokens",
                   stop_sequence=None, usage=Usage(input_tokens=10, output_tokens=2000))


def _run(variant, user_id=KB_USER, **overrides):
    from pipeline.graph import run_pipeline

    kwargs = dict(topic="pgvector retrieval", format="linkedin post", tone="casual", user_id=user_id, variant=variant)
    kwargs.update(overrides)
    return run_pipeline(**kwargs)


def _outputs(fake_db) -> dict:
    [trace] = fake_db.tables["generation_traces"]
    return trace["node_outputs"]
