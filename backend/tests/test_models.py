"""Models per role, the price table, and what the 5.5 models need from a call:
text read from the text blocks, room for thinking, a tool call that is not
forced, and a refusal that becomes an explicit status. All through the fake."""

import asyncio

import pytest
from anthropic.types import Message, OutputTokensDetails, RefusalStopDetails, TextBlock, ThinkingBlock, ToolUseBlock, Usage
from pydantic import BaseModel

from llm.models import HAIKU_4_5, HAIKU_5_5, OPUS_5_5, SONNET_4_6, SONNET_5_5
from tests.length_fixtures import KB_USER, _outputs, _post, _run
from tests.review_fixtures import answer_pipeline, enveloped
from tests.test_generation_trace import STANDARD_RUN, seeded_kb  # noqa: F401  (shared fixture)

CLEAN = "pgvector makes retrieval fast. [[S1]]\n\nThat is most of the argument. [[V]]"


def _thinking_block() -> ThinkingBlock:
    # As the API returns it by default: the thinking text is omitted, the signature is not.
    return ThinkingBlock(type="thinking", thinking="", signature="sig")


def _reply(*blocks, stop_reason="end_turn", output_tokens=900, thinking_tokens=None, refused_for=None) -> Message:
    """A reply built from the SDK's own types, validated as a real response is."""
    details = None if thinking_tokens is None else OutputTokensDetails(thinking_tokens=thinking_tokens)
    stop_details = None if refused_for is None else RefusalStopDetails(type="refusal", category=refused_for, explanation=None)
    return Message(id="msg", type="message", role="assistant", model="claude-opus-5-5", content=list(blocks),
                   stop_reason=stop_reason, stop_sequence=None, stop_details=stop_details,
                   usage=Usage(input_tokens=10, output_tokens=output_tokens, output_tokens_details=details))


def _models_called(claude) -> dict[str, set[str]]:
    """event -> models, read from the request each call sent (tool name, or the drafter's prompt)."""
    seen: dict[str, set[str]] = {}
    for call in claude.calls:
        tool = (call.get("tool_choice") or {}).get("name") or "drafter"
        seen.setdefault(tool, set()).add(call["model"])
    return seen


# --- Role configuration ---------------------------------------------------------------

def test_each_variant_resolves_its_role_models():
    from llm.models import role_models

    assert role_models("B") == role_models("C") == {"draft": SONNET_4_6, "review": SONNET_4_6, "small": HAIKU_4_5}
    assert role_models("B-Opus") == role_models("C-Opus") == {"draft": OPUS_5_5, "review": SONNET_4_6, "small": HAIKU_4_5}
    assert role_models("B", {"small": HAIKU_5_5})["small"] == HAIKU_5_5


@pytest.mark.parametrize("overrides", [{"writer": SONNET_4_6}, {"draft": "claude-some-other-model"}])
def test_an_unknown_role_or_model_is_refused(overrides):
    from llm.models import ModelConfigError, role_models

    with pytest.raises(ModelConfigError):
        role_models("B", overrides)


def test_variant_tables_agree_and_every_model_has_a_price():
    from config import features
    from llm.models import MODELS, VARIANT_ROLE_MODELS
    from llm.pricing import PRICES

    assert set(VARIANT_ROLE_MODELS) <= set(features.PIPELINE_VARIANTS)
    assert set(features.VARIANT_GRAPH) == set(features.PIPELINE_VARIANTS)
    assert set(features.VARIANT_GRAPH.values()) <= {"A", "B", "C"}
    assert set(MODELS) == set(PRICES)


@pytest.mark.parametrize("variant,drafter", [("B", SONNET_4_6), ("C", SONNET_4_6), ("B-Opus", OPUS_5_5),
                                             ("C-Opus", OPUS_5_5)])
def test_each_call_of_a_run_uses_its_role_model(claude, fake_db, seeded_kb, variant, drafter):
    over = _post(36)                       # 360 words: over the standard maximum, so the trim runs too
    answer_pipeline(claude, [over, over], trim='{"ranking": [36, 35, 34, 33, 32, 31, 30]}')

    result = _run(variant)

    assert result["status"] == "ok"
    called = _models_called(claude)
    assert called["drafter"] == {drafter}
    assert called["choose_post_type"] == called["rank_sentences_to_delete"] == {HAIKU_4_5}
    if variant in ("B", "B-Opus"):
        assert called["record_review"] == {SONNET_4_6}
    else:
        assert "record_review" not in called            # C and C-Opus draft and trim, nothing else
    outputs = _outputs(fake_db)
    assert outputs["variant"] == variant
    assert outputs["models"] == {"draft": drafter, "review": SONNET_4_6, "small": HAIKU_4_5}


def test_an_eval_override_changes_only_that_role(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [CLEAN])

    _run("B", models={"small": HAIKU_5_5})

    called = _models_called(claude)
    assert (called["choose_post_type"], called["drafter"], called["record_review"]) == (
        {HAIKU_5_5}, {SONNET_4_6}, {SONNET_4_6})


def test_pipeline_a_has_no_role_models(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    _run("A")

    assert "models" not in _outputs(fake_db)
    assert {call["model"] for call in claude.calls} <= {SONNET_4_6, HAIKU_4_5}
    with pytest.raises(ValueError, match="fixed models"):
        _run("A", models={"draft": OPUS_5_5})


# --- A model that thinks ----------------------------------------------------------------

def test_the_post_is_read_from_the_text_block_after_the_thinking_blocks(claude, fake_db, seeded_kb):
    draft = _reply(_thinking_block(), _thinking_block(), TextBlock(type="text", text=enveloped(CLEAN)),
                   thinking_tokens=400)
    answer_pipeline(claude, [draft])

    result = _run("B-Opus")

    assert result["status"] == "ok"
    assert result["post"] == "pgvector makes retrieval fast.\n\nThat is most of the argument."
    [trace] = fake_db.tables["generation_traces"]
    [generate] = [c for c in trace["llm_calls"] if c["event_type"] == "generate"]
    assert (generate["model"], generate["output_tokens"], generate["thinking_tokens"]) == (OPUS_5_5, 900, 400)


def test_message_text_ignores_blocks_that_are_not_text():
    from llm.client import message_text

    tool = ToolUseBlock(type="tool_use", id="t", name="x", input={})
    assert message_text(_reply(_thinking_block(), TextBlock(type="text", text="a"), tool,
                               TextBlock(type="text", text="b"))) == "ab"
    assert message_text(_reply(_thinking_block())) == ""
    assert message_text(_reply()) == ""


def test_the_draft_budget_leaves_room_for_thinking_and_for_the_newer_tokenizer(claude, fake_db, seeded_kb):
    from llm.client import THINKING_ALLOWANCE_TOKENS
    from utils.formatters import draft_max_tokens, resolve_length_target

    long_form = max((resolve_length_target(fmt, "long-form") for fmt in ("linkedin post", "medium article")),
                    key=lambda target: target["max_words"])
    assert draft_max_tokens(long_form, OPUS_5_5) > draft_max_tokens(long_form, SONNET_4_6)

    budgets = {}
    for variant in ("B", "B-Opus"):
        claude.reset()
        answer_pipeline(claude, [CLEAN])
        _run(variant)
        [budgets[variant]] = [c["max_tokens"] for c in claude.calls if "tool_choice" not in c]
    assert budgets["B"] == 2000                                    # unchanged for a model that does not think
    assert budgets["B-Opus"] == 2000 + THINKING_ALLOWANCE_TOKENS


def test_thinking_that_uses_the_whole_budget_is_a_truncated_draft_not_a_post(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_reply(_thinking_block(), stop_reason="max_tokens", output_tokens=10_000)])

    result = _run("B-Opus")

    assert (result["status"], result["post"]) == ("draft_truncated", "")


def test_a_refusal_without_a_category_records_none(claude, fake_db, seeded_kb):
    answer_pipeline(claude, [_reply(stop_reason="refusal", output_tokens=0)])

    assert _run("B-Opus")["status"] == "draft_refused"
    assert _outputs(fake_db)["draft_refused"] == {"category": None}


# --- Through the real SDK: what is sent, and what its types give back ----------------------

def test_the_sdk_parses_a_thinking_reply_into_the_types_the_code_reads(claude, fake_db, seeded_kb, wire):
    from anthropic.types import ThinkingBlock as SdkThinkingBlock

    import llm.client as llm_client

    parsed = []
    real_create = llm_client.client.messages.create
    llm_client.client.messages.create = lambda **kwargs: parsed.append(real_create(**kwargs)) or parsed[-1]
    draft = _reply(_thinking_block(), TextBlock(type="text", text=enveloped(CLEAN)), thinking_tokens=400)
    answer_pipeline(claude, [draft])

    result = _run("B-Opus")

    [message] = [m for m in parsed if m.model == OPUS_5_5]
    assert [type(block) for block in message.content] == [SdkThinkingBlock, TextBlock]
    assert message.usage.output_tokens_details.thinking_tokens == 400
    assert result["post"] == "pgvector makes retrieval fast.\n\nThat is most of the argument."
    [trace] = fake_db.tables["generation_traces"]
    assert [c["thinking_tokens"] for c in trace["llm_calls"] if c["event_type"] == "generate"] == [400]


def test_an_opus_draft_sends_its_effort_and_no_other_call_does(claude, fake_db, seeded_kb, wire):
    from llm.models import MODELS, OPUS_5_5_DRAFT_EFFORT, draft_effort

    assert OPUS_5_5_DRAFT_EFFORT == MODELS[OPUS_5_5].default_effort == "medium"      # the API default, written out
    assert draft_effort(SONNET_4_6) is None

    answer_pipeline(claude, [CLEAN])
    _run("B-Opus")
    by_model = {}
    for request in wire:
        by_model.setdefault(request["body"]["model"], []).append(request["body"].get("output_config"))
    assert by_model[OPUS_5_5] == [{"effort": "medium"}]
    assert set(by_model[SONNET_4_6]) == set(by_model[HAIKU_4_5]) == {None}

    wire.clear()
    claude.reset()
    answer_pipeline(claude, [CLEAN])
    _run("B")
    assert all("output_config" not in request["body"] for request in wire)


def test_c_opus_is_c_with_an_opus_draft_at_the_same_effort(claude, fake_db, seeded_kb, wire):
    from config import features
    from llm.models import OPUS_5_5_DRAFT_EFFORT

    assert features.VARIANT_GRAPH["C-Opus"] == "C"
    answer_pipeline(claude, [CLEAN])

    result = _run("C-Opus")

    assert result["status"] == "ok" and result["review"] is None
    assert [(r["body"]["model"], r["body"].get("output_config")) for r in wire] == [
        (HAIKU_4_5, None), (OPUS_5_5, {"effort": OPUS_5_5_DRAFT_EFFORT})]       # the structure choice, then the draft
    outputs = _outputs(fake_db)
    assert (outputs["variant"], outputs["models"]["draft"]) == ("C-Opus", OPUS_5_5)
    assert "review" not in outputs


# --- Refusals ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["B-Opus", "C"])
def test_a_refused_draft_is_an_explicit_status_and_no_post(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import DRAFT_REFUSED_MESSAGE

    refused = _reply(stop_reason="refusal", output_tokens=0, refused_for="bio")
    answer_pipeline(claude, [refused])

    result = _run(variant)

    assert (result["status"], result["post"], result["message"]) == ("draft_refused", "", DRAFT_REFUSED_MESSAGE)
    assert len(claude.calls) == 2                     # the structure choice and the draft: nothing after it
    outputs = _outputs(fake_db)
    assert outputs["draft_refused"] == {"category": "bio"}
    assert outputs["final_post"] == "" and "draft_truncated" not in outputs and "review" not in outputs


def test_the_generate_route_returns_the_refused_status(claude, fake_db, seeded_kb, client, auth_headers, monkeypatch):
    monkeypatch.setenv("PIPELINE_VARIANT", "B-Opus")
    answer_pipeline(claude, [_reply(stop_reason="refusal", output_tokens=0)])

    body = client.post("/generate", headers=auth_headers(KB_USER),
                       json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"}).json()

    assert (body["status"], body["post"]) == ("draft_refused", "")
    assert body["message"]


class _Answer(BaseModel):
    value: int


def _structured(model, **overrides):
    from llm.client import complete_structured

    kwargs = dict(schema=_Answer, tool_name="record_answer", tool_description="Record it.", model=model,
                  messages=[{"role": "user", "content": "How many?"}], max_tokens=300, user_id="u", event_type="test")
    return complete_structured(**{**kwargs, **overrides})


def test_a_refused_structured_call_raises_at_once_and_is_not_retried(claude):
    from llm.client import RefusedStructuredOutputError, StructuredOutputError

    claude.queue(_reply(stop_reason="refusal", output_tokens=0))

    with pytest.raises(RefusedStructuredOutputError) as raised:
        _structured(SONNET_5_5)

    assert isinstance(raised.value, StructuredOutputError) and len(claude.calls) == 1


# --- Structured calls where a tool cannot be forced ---------------------------------------

def test_a_model_that_rejects_a_forced_tool_gets_auto_and_an_instruction(claude):
    from llm.client import THINKING_ALLOWANCE_TOKENS, TOOL_INSTRUCTION

    sent = [{"role": "user", "content": "How many?"}]
    claude.queue(_reply(_thinking_block(), ToolUseBlock(type="tool_use", id="t", name="record_answer", input={"value": 3}),
                        stop_reason="tool_use"))

    answer = _structured(SONNET_5_5, messages=sent)

    [call] = claude.calls
    assert answer.value == 3
    assert call["tool_choice"] == {"type": "auto"}
    assert call["messages"][-1]["content"] == "How many?\n\n" + TOOL_INSTRUCTION.format(tool_name="record_answer")
    assert call["max_tokens"] == 300 + THINKING_ALLOWANCE_TOKENS
    assert sent == [{"role": "user", "content": "How many?"}]          # the caller's messages are not changed


def test_an_unforced_call_that_answers_in_text_is_retried_then_fails(claude):
    from llm.client import StructuredOutputError

    claude.queue(_reply(TextBlock(type="text", text="Three.")), _reply(TextBlock(type="text", text="Three.")))

    with pytest.raises(StructuredOutputError, match="no record_answer tool call"):
        _structured(OPUS_5_5)
    assert len(claude.calls) == 2


@pytest.mark.parametrize("model", [SONNET_4_6, HAIKU_4_5, HAIKU_5_5])
def test_a_model_that_accepts_a_forced_tool_keeps_the_forced_call_and_its_prompt(claude, model):
    claude.queue('{"value": 3}')

    _structured(model)

    [call] = claude.calls
    assert call["tool_choice"] == {"type": "tool", "name": "record_answer"}
    assert call["messages"] == [{"role": "user", "content": "How many?"}]


# --- Prices -----------------------------------------------------------------------------

@pytest.mark.parametrize("model,per_million", [
    (OPUS_5_5, 4 + 20), (SONNET_5_5, 2 + 10), (HAIKU_5_5, 0.10 + 0.50), (SONNET_4_6, 3 + 15), (HAIKU_4_5, 1 + 5),
])
def test_list_prices_by_exact_model_id(model, per_million):
    from llm.pricing import call_cost

    assert call_cost(model, 1_000_000, 1_000_000) == pytest.approx(per_million if model != HAIKU_5_5 else 0.50 + 2.50)
    assert call_cost(model, 1_000, 1_000) == pytest.approx(per_million / 1_000)


def test_haiku_5_5_pays_the_long_prompt_price_only_above_its_threshold():
    from llm.pricing import call_cost

    assert call_cost(HAIKU_5_5, 100_000, 0) == pytest.approx(0.01)
    assert call_cost(HAIKU_5_5, 100_001, 0) == pytest.approx(100_001 * 0.50 / 1_000_000)


def test_a_model_without_a_price_is_never_priced_as_another():
    from llm.pricing import call_cost

    with pytest.raises(KeyError):
        call_cost("claude-some-other-model", 1, 1)


def _logged(monkeypatch, **event) -> list[dict]:
    import memory.usage_store as usage_store

    rows: list[dict] = []

    async def fake_insert(payload):
        rows.append(payload)

    monkeypatch.setattr(usage_store, "_insert_event", fake_insert)
    asyncio.run(usage_store.log_usage_event(user_id="u", event_type="critic", **event))
    return rows


def test_usage_store_prices_a_call_from_the_shared_table(monkeypatch):
    from llm import pricing

    [row] = _logged(monkeypatch, input_tokens=1_000_000, output_tokens=1_000_000, model=HAIKU_4_5)
    assert row["estimated_cost_usd"] == pytest.approx(6.0)             # $1 / $5, not the old $0.25 / $1.25

    monkeypatch.setitem(pricing.PRICES, HAIKU_4_5, pricing.Price(2.00, 10.00))
    [row] = _logged(monkeypatch, input_tokens=1_000_000, output_tokens=1_000_000, model=HAIKU_4_5)
    assert row["estimated_cost_usd"] == pytest.approx(12.0)


def test_usage_for_a_model_without_a_price_writes_no_row(monkeypatch):
    assert _logged(monkeypatch, input_tokens=1, output_tokens=1, model="claude-some-other-model") == []
