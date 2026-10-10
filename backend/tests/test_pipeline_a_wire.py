"""Pipeline A's requests as they leave the Anthropic SDK, frozen across the SDK upgrade.

Every other test replaces Messages.create, so it sees the arguments the code
passes to the SDK and nothing of what the SDK sends. Here the real SDK client
runs against a mock HTTP transport (the `wire` fixture in conftest.py), and the
JSON body of every request is recorded: the model, the parameters, the prompt, the tool schema and the tool
choice, exactly as the API would receive them.

tests/snapshots/pipeline_a_wire.json holds those bodies for two fixed runs of
the whole pipeline (standard and polished, the background fact check included),
captured with anthropic 0.40.0 on main (commit a5b9d11) before the upgrade to
1.x. This test renders the same runs with the installed SDK and requires the
bodies, the endpoint and the API version header to be identical. Headers the SDK
generates about itself (user agent, package version, runtime) are not compared.

If this fails, what pipeline A sends to Claude changed. Do not update the
snapshot to make it pass.
"""

import json
import pathlib

import pytest

from tests.conftest import ARCHETYPE_GENERAL, score_json
from tests.test_generation_trace import USER, _run, seeded_kb  # noqa: F401  (shared fixture)

SNAPSHOT_FILE = pathlib.Path(__file__).parent / "snapshots" / "pipeline_a_wire.json"

_CRITIC_HOOK_NEEDS_WORK = json.dumps({
    **{area: {"verdict": "strong", "fix": None} for area in ("topic", "substance", "structure", "voice")},
    "hook": {"verdict": "needs_work", "fix": "Open with the claim itself."},
    "overall": "needs_work",
})
_DRAFT = "Retrieval used to be the slow part. Then pgvector made it fast. That changed what we could build."
_HUMANIZED = "Retrieval was the slow part. Then pgvector made it fast. That changed what we could build."
_AUDITED = "Retrieval was the slow part. pgvector made it fast. That changed what we could build."
_NO_FLAGS = '{"flagged": []}'

# The model's replies, in call order, for each frozen run.
RUNS = {
    "standard": {
        "request": {"context": "for a talk"},
        "replies": [
            ARCHETYPE_GENERAL,                   # archetype (structured)
            _DRAFT,                              # draft
            _CRITIC_HOOK_NEEDS_WORK,                   # critic (structured)
            _HUMANIZED,                          # humanizer
            "Then pgvector made it fast.",       # audit step 1: the flagged sentence
            "pgvector made it fast.",            # audit step 2: its replacement
            _AUDITED,                            # audit step 3
            "Final text.",                       # word count enforcer
            _NO_FLAGS,                           # background fact check (structured)
        ],
    },
    "polished": {
        "request": {"quality": "polished", "length": "concise", "tone": "technical"},
        "replies": [
            ARCHETYPE_GENERAL, _DRAFT, _CRITIC_HOOK_NEEDS_WORK, _HUMANIZED,
            "CLEAN",                             # audit step 1: nothing flagged, step 2 is skipped
            _AUDITED,                            # audit step 3
            score_json(16),                      # scorer (structured): 80, no rewrite
            "Final text.",                       # word count enforcer
            _NO_FLAGS,
        ],
    },
}


def render(name: str, claude, sent: list[dict]) -> list[dict]:
    """Run one frozen run through run_pipeline and its background fact check."""
    run = RUNS[name]
    claude.queue(*run["replies"])
    result = _run(**run["request"])
    assert result["status"] == "ok"
    result["fact_check_job"]()
    assert len(sent) == len(run["replies"]), "the run made a different number of calls than it has replies"
    return sent


def test_the_snapshot_covers_every_kind_of_pipeline_a_call():
    snapshot = json.loads(SNAPSHOT_FILE.read_text())

    assert set(snapshot) == set(RUNS)
    tools = {(body.get("tool_choice") or {}).get("name") for run in snapshot.values() for body in (r["body"] for r in run)}
    assert tools == {None, "choose_post_type", "record_critique", "record_score", "record_fact_check"}
    assert [len(run) for run in snapshot.values()] == [len(run["replies"]) for run in RUNS.values()]
    assert {r["body"]["model"] for run in snapshot.values() for r in run} == {"claude-sonnet-4-6", "claude-haiku-4-5-20251001"}


@pytest.mark.parametrize("name", list(RUNS))
def test_pipeline_a_sends_the_same_requests_as_before_the_sdk_upgrade(claude, fake_db, seeded_kb, wire, name):
    expected = json.loads(SNAPSHOT_FILE.read_text())[name]

    rendered = render(name, claude, wire)

    assert len(rendered) == len(expected)
    for number, (new, old) in enumerate(zip(rendered, expected), 1):
        assert new["body"].get("model") == old["body"].get("model"), f"call {number}: model changed"
        assert new["body"].get("max_tokens") == old["body"].get("max_tokens"), f"call {number}: max_tokens changed"
        assert set(new["body"]) == set(old["body"]), f"call {number}: request parameters changed"
        assert new == old, f"call {number}: request changed"
