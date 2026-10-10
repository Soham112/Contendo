"""Anthropic list prices, keyed by exact model id. The one price table:
memory/usage_store.py (production cost tracking) and the evals both read it.

Source: https://platform.claude.com/docs/en/about-claude/pricing, checked
2026-10-10. Base input and output prices only: no call in this codebase uses
prompt caching, the Batch API, fast mode or US-only inference, each of which
has its own multiplier there.
"""

from dataclasses import dataclass

from llm.models import HAIKU_4_5, HAIKU_5_5, OPUS_5_5, SONNET_4_6, SONNET_5_5

PRICES_CHECKED_ON = "2026-10-10"
_PER_MTOK = 1_000_000


@dataclass(frozen=True)
class Price:
    """USD per million tokens. long_prompt, when set, is (prompt tokens above
    which the request pays it, input, output): the whole request is then priced
    at those rates."""
    input: float
    output: float
    long_prompt: tuple[int, float, float] | None = None


PRICES: dict[str, Price] = {
    OPUS_5_5: Price(4.00, 20.00),
    SONNET_5_5: Price(2.00, 10.00),
    HAIKU_5_5: Price(0.10, 0.50, long_prompt=(100_000, 0.50, 2.50)),
    SONNET_4_6: Price(3.00, 15.00),
    HAIKU_4_5: Price(1.00, 5.00),
}


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call. Thinking tokens are part of output_tokens, as billed.
    An unknown model raises: a call is never priced at another model's rate."""
    if model not in PRICES:
        raise KeyError(f"No price for model {model!r}: add it to llm.pricing.PRICES.")
    price = PRICES[model]
    price_in, price_out = price.input, price.output
    if price.long_prompt is not None and input_tokens > price.long_prompt[0]:
        _, price_in, price_out = price.long_prompt
    return (input_tokens * price_in + output_tokens * price_out) / _PER_MTOK
