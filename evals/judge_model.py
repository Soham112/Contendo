"""DeepEval judge that calls Claude through the backend's llm.client.complete().

DeepEval asks for structured output by passing a pydantic schema to generate().
The judge gets it with a forced tool call whose input_schema is the schema's JSON
schema, so the answer arrives as validated JSON. If that response fails
validation, it retries once asking for plain JSON text. `stats` counts which
path each call took so a run can show whether structured output is reliable.
"""

import asyncio
import json
import re
from typing import Any, Callable, Optional

from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel, ValidationError

import eval_config as config

_TOOL_NAME = "submit_answer"


def _prompt_text(prompt: Any) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        return "\n".join(str(p) for p in prompt)
    return str(prompt)


def _text_of(message: Any) -> str:
    return "".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", "") == "text")


def _parse_json_text(text: str) -> Any:
    """JSON from a text reply, tolerating code fences and prose around the object."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


class ContendoJudge(DeepEvalBaseLLM):
    """One judge per golden: user_id is the persona's uuid, so any usage logging lands on the eval user."""

    def __init__(
        self,
        user_id: str,
        model_constant: str = config.JUDGE_MODEL,
        complete_fn: Optional[Callable[..., Any]] = None,
        model_id: Optional[str] = None,
    ):
        if complete_fn is None or model_id is None:
            from llm import client as llm_client  # backend import: env.py must already be loaded

            complete_fn = complete_fn or llm_client.complete
            model_id = model_id or getattr(llm_client, model_constant)
        self.user_id = user_id
        self.model_constant = model_constant
        self.model_id = model_id
        self._complete = complete_fn
        self.stats = {"tool": 0, "text_fallback": 0, "plain": 0}
        super().__init__(model=model_id)

    def load_model(self, *args, **kwargs) -> "ContendoJudge":
        return self

    def get_model_name(self, *args, **kwargs) -> str:
        return f"{self.model_constant} via llm.client.complete"

    def _call(self, prompt: str, **kwargs: Any) -> Any:
        return self._complete(
            model=self.model_id,
            max_tokens=config.JUDGE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            user_id=self.user_id,
            event_type=config.JUDGE_EVENT_TYPE,
            temperature=0,
            **kwargs,
        )

    def generate(self, prompt: Any, schema: Optional[type[BaseModel]] = None, **kwargs: Any) -> Any:
        text = _prompt_text(prompt)
        if schema is None:
            self.stats["plain"] += 1
            return _text_of(self._call(text))

        message = self._call(
            text,
            tools=[{
                "name": _TOOL_NAME,
                "description": "Submit the answer in exactly this structure.",
                "input_schema": schema.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
        )
        tool_input = next((b.input for b in message.content if getattr(b, "type", "") == "tool_use"), None)
        if tool_input is not None:
            try:
                result = schema.model_validate(tool_input)
                self.stats["tool"] += 1
                return result
            except ValidationError:
                pass

        self.stats["text_fallback"] += 1
        fallback_prompt = (
            f"{text}\n\nReturn only a JSON object that matches this JSON schema, with no other text:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        return schema.model_validate(_parse_json_text(_text_of(self._call(fallback_prompt))))

    async def a_generate(self, prompt: Any, schema: Optional[type[BaseModel]] = None, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.generate, prompt, schema)


def is_fatal_api_error(exc: Exception) -> bool:
    """Errors that will repeat for every remaining call: out of credits, bad or forbidden key."""
    import anthropic

    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return True
    return isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc).lower()
