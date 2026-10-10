"""Pipeline A's prompts are frozen while feat/single-writer adds variants B and C.

tests/snapshots/pipeline_a_prompts.json holds, for two fixed inputs, every
request draft_node, critic_node and humanizer_node sent to Claude, captured from
the code as it was on main (commit 653c6c0) before the draft prompt was split
and the style rules moved into one constant. The inputs are the pm-01 golden
(a story post from the author's own note) and the pm-09 golden (external
source only). This test renders the same requests with the current code and
requires them to be identical, character for character: prompt text, model,
max_tokens, tool schema and tool choice.

If this fails, pipeline A changed. Do not update the snapshot to make it pass.
"""

import copy
import json
import pathlib

import pytest

SNAPSHOT = json.loads((pathlib.Path(__file__).parent / "snapshots" / "pipeline_a_prompts.json").read_text())
NODES = ("archetype", "draft", "critic", "humanizer")


def _render(claude, case: dict) -> list[dict]:
    from agents.critic_agent import critic_node
    from agents.draft_agent import draft_node
    from agents.humanizer_agent import humanizer_node

    claude.queue(*case["replies"])
    humanizer_node(critic_node(draft_node(copy.deepcopy(case["state"]))))
    return json.loads(json.dumps(claude.calls))


def test_the_snapshot_covers_a_story_post_and_an_external_only_post():
    perspectives = {name: case["state"]["perspective"] for name, case in SNAPSHOT.items()}

    assert perspectives == {"story (pm-01)": "experience", "external only (pm-09)": "learned"}
    assert json.loads(SNAPSHOT["story (pm-01)"]["replies"][0])["event_quote"]


@pytest.mark.parametrize("name", list(SNAPSHOT))
def test_pipeline_a_requests_are_identical_to_main(claude, name):
    case = SNAPSHOT[name]

    rendered = _render(claude, case)

    assert len(rendered) == len(case["requests"]) == len(NODES)
    for node, new, old in zip(NODES, rendered, case["requests"]):
        assert new["messages"][-1]["content"] == old["messages"][-1]["content"], f"{node} prompt changed"
        assert new == old, f"{node} request changed"


@pytest.mark.parametrize("name", list(SNAPSHOT))
def test_pipeline_a_prompts_are_byte_identical(claude, name):
    case = SNAPSHOT[name]

    rendered = _render(claude, case)

    for node, new, old in zip(NODES, rendered, case["requests"]):
        new_bytes = new["messages"][-1]["content"].encode("utf-8")
        assert new_bytes == old["messages"][-1]["content"].encode("utf-8"), f"{node} prompt bytes changed"
