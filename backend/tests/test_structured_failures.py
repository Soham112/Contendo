"""Structured calls fail explicitly: an error marker or None, never a made-up verdict or score."""

import json

import pytest

from tests.conftest import CRITIC_ALL_STRONG, score_json
from tests.generation_fixtures import ARTICLE, USER, agent_sources, last_prompt, make_state


# --- Critic and scorer: explicit failures ------------------------------------------------------

@pytest.mark.parametrize("reply", ["not json", "{}", '{"overall": "postable"}',
                                   json.dumps({"topic": {"verdict": "fine"}})])
def test_critic_failure_is_an_error_marker_not_a_clean_brief(claude, reply):
    from agents.critic_agent import critic_node
    from agents.humanizer_agent import _format_critic_brief

    claude.queue(reply, reply)  # the structured call retries once before giving up
    brief = critic_node(make_state([ARTICLE]))["critic_brief"]

    assert len(claude.calls) == 2
    assert set(brief) == {"error"} and "after 2 attempts" in brief["error"]
    section, instruction = _format_critic_brief(brief)
    assert section == "" and "Preserve the structure" in instruction  # no critic-driven rewrite


def test_critic_judges_structure_only_where_the_sources_have_material(claude):
    from agents.critic_agent import critic_node

    claude.queue(CRITIC_ALL_STRONG)
    state = critic_node(make_state([ARTICLE], archetype="general"))
    assert state["critic_brief"]["overall"] == "postable"
    assert "A section the sources cannot fill is correctly left out" in last_prompt(claude)
    assert "General Post" in last_prompt(claude)


def test_score_is_the_sum_of_the_dimensions(claude):
    from agents.scorer_agent import score_text

    claude.queue(json.dumps({
        "dimension_scores": {"natural_voice": 18, "sentence_variety": 15, "precision": 12,
                             "no_llm_fingerprints": 17, "value_delivery": 14},
        "flagged_sentences": ["A weak sentence."], "feedback": ["Tighten the opening."],
        "total_score": 3,  # a total the model volunteers is ignored
    }))
    assert score_text("post", user_id=USER) == (76, ["Tighten the opening.", "A weak sentence."])


@pytest.mark.parametrize("reply", ["not json", '{"total_score": 50}',
                                   json.dumps({"dimension_scores": {"natural_voice": 99}})])
def test_scorer_failure_is_none_never_a_placeholder_score(claude, reply):
    from agents import scorer_agent

    claude.queue(reply, reply)  # the structured call retries once before giving up
    assert scorer_agent.score_text("post", user_id=USER) == (None, [])
    assert len(claude.calls) == 2
    assert "== 50" not in agent_sources()["scorer_agent.py"]
    assert not hasattr(scorer_agent, "parse_scorer_response")


def test_scorer_rubric_does_not_reward_or_request_personal_specifics(claude):
    from agents.scorer_agent import SYSTEM_PROMPT

    assert "real numbers, named examples, specific situations" not in SYSTEM_PROMPT
    assert "founder/builder" not in SYSTEM_PROMPT
    assert "Never reward a post for containing personal anecdotes, numbers or named examples" in SYSTEM_PROMPT
    assert "Never ask the author to add an anecdote" in SYSTEM_PROMPT


def test_score_route_returns_null_and_a_message_when_scoring_fails(client, claude, auth_headers):
    claude.queue("not json", "still not json")  # the first attempt and its one retry
    resp = client.post("/score", json={"post_content": "p"}, headers=auth_headers(USER))

    assert resp.status_code == 200
    assert resp.json() == {"score": None, "score_feedback": [], "message": "Couldn't score this post. Try again."}


def test_score_route_returns_the_score_when_it_works(client, claude, auth_headers):
    claude.queue(score_json(17))
    resp = client.post("/score", json={"post_content": "p"}, headers=auth_headers(USER))
    assert resp.json() == {"score": 85, "score_feedback": [], "message": ""}


def test_failed_score_ends_the_polished_retry_loop():
    from agents.scorer_agent import scorer_node
    from pipeline.graph import should_retry

    assert should_retry({"score": 0, "score_error": True, "iterations": 1}) == "word_count_enforcer"
    assert should_retry({"score": 0, "score_error": False, "iterations": 1}) == "humanizer"
    assert scorer_node({"quality": "draft"}).get("score_error") is None


# --- The structured-call helper ------------------------------------------------------------------

def test_complete_structured_returns_a_validated_model_or_raises(claude):
    from pydantic import BaseModel

    from llm.client import HAIKU, StructuredOutputError, complete_structured

    class Answer(BaseModel):
        value: int

    def call():
        return complete_structured(schema=Answer, tool_name="answer", tool_description="d", model=HAIKU,
                                   messages=[{"role": "user", "content": "q"}], max_tokens=50,
                                   user_id=USER, event_type="test")

    claude.queue('{"value": 3}')
    assert call().value == 3
    assert claude.calls[0]["tool_choice"] == {"type": "tool", "name": "answer"}
    assert claude.calls[0]["tools"][0]["input_schema"]["required"] == ["value"]

    for bad in ("plain text", '{"value": "many"}', "{}"):
        claude.reset()
        claude.queue(bad, bad)
        with pytest.raises(StructuredOutputError, match="after 2 attempts"):
            call()
        assert len(claude.calls) == 2


def test_complete_structured_retries_once_and_logs_both_attempts(claude, caplog):
    from pydantic import BaseModel

    from llm.client import HAIKU, StructuredOutputError, complete_structured, trace_calls

    class Answer(BaseModel):
        value: int

    def call():
        return complete_structured(schema=Answer, tool_name="answer", tool_description="d", model=HAIKU,
                                   messages=[{"role": "user", "content": "q"}], max_tokens=50,
                                   user_id=USER, event_type="test")

    # A malformed first reply (the nested value arrives as a string, as Haiku did in the
    # smoke run) followed by a valid one: the caller gets the valid answer.
    claude.queue('{"value": "{\\"oops\\": 1}"}', '{"value": 7}')
    with caplog.at_level("WARNING", logger="llm.client"), trace_calls() as calls:
        assert call().value == 7
    assert len(claude.calls) == 2
    assert claude.calls[0]["messages"] == claude.calls[1]["messages"]  # same request, sent again
    assert [c["event_type"] for c in calls] == ["test", "test"]         # both attempts are traced and billed
    assert "test attempt 1 of 2 failed" in caplog.text and "attempt 2 of 2" not in caplog.text

    # Two bad replies: one more attempt, never a third, and the error names both failures.
    claude.reset(); caplog.clear()
    claude.queue("plain text", '{"value": "many"}', '{"value": 1}')
    with caplog.at_level("WARNING", logger="llm.client"), pytest.raises(StructuredOutputError) as exc:
        call()
    assert len(claude.calls) == 2
    assert "attempt 1 of 2 failed" in caplog.text and "attempt 2 of 2 failed" in caplog.text
    assert "First: no answer tool call" in str(exc.value) and "Second: reply does not match the schema" in str(exc.value)


def test_a_first_valid_answer_makes_one_call(claude):
    from agents.scorer_agent import score_text

    claude.queue(score_json())
    assert score_text("post", user_id=USER)[0] == 80
    assert len(claude.calls) == 1


def test_api_errors_are_not_retried_by_the_structured_helper(claude):
    from agents.scorer_agent import score_text

    def boom(kwargs):
        raise RuntimeError("anthropic down")

    claude.respond_with(boom)
    with pytest.raises(RuntimeError, match="anthropic down"):
        score_text("post", user_id=USER)
    assert len(claude.calls) == 1
