"""The spend cap of an ablation: one ledger for every script that takes part.

Pure: no env, no backend, no network. The scripts pass in the backend's price
table (llm.pricing.call_cost) and the calls their own trace collected
(llm.client.trace_calls), so the sum is measured usage at list prices, the
same figures the report shows, with the background fact checks included.

The ledger is results/ablations/<name>/spend.json. Each script that is given
--ablation <name> adds to it after every post (a pipeline run, a judged post,
a regression case) and looks at it before the next one: once the total has
reached the cap, the script stops there, records where, and exits with
STOPPED_EXIT. The post in progress when the cap is crossed is finished, so the
total can pass the cap by at most that one post.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import eval_config as config

LEDGER_FILE = "spend.json"
STOPPED_EXIT = 4      # exit code of a script that stopped at the cap


class SpendCap:
    def __init__(self, ledger: Path, cap_usd: float, call_cost: Callable[[str, int, int], float]):
        self.ledger, self.cap_usd, self._call_cost = ledger, float(cap_usd), call_cost
        state = json.loads(ledger.read_text()) if ledger.exists() else {}
        self.spent_usd: float = state.get("spent_usd", 0.0)
        self.entries: list[dict[str, Any]] = state.get("entries", [])
        self.stopped_at: str | None = None        # set by this script only; an earlier stop is history
        self._earlier_stops: list[str] = state.get("stops", [])

    @property
    def reached(self) -> bool:
        return self.spent_usd >= self.cap_usd

    def record(self, calls: Iterable[dict[str, Any]], item: str) -> float:
        """Add the measured cost of these calls (trace entries: model,
        input_tokens, output_tokens) under `item`, write the ledger, return the cost."""
        calls = list(calls)
        cost = sum(self._call_cost(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls)
        self.spent_usd += cost
        self.entries.append({"item": item, "calls": len(calls), "cost_usd": round(cost, 6),
                             "at": datetime.now(timezone.utc).isoformat()})
        self._write()
        return cost

    def stop(self, where: str) -> str:
        """Record that the cap stopped the work at `where`; returns the message to print."""
        self.stopped_at = where
        self._earlier_stops.append(where)
        self._write()
        return (f"SPEND CAP REACHED: ${self.spent_usd:.2f} measured against a cap of ${self.cap_usd:.2f}. "
                f"Stopped {where}. Everything finished so far is written. Ledger: {self.ledger}")

    def guard(self, items: Iterable[Any], where: Callable[[Any, int], str]) -> Iterator[Any]:
        """Yield items until the cap is reached; then stop before the next one
        and record where (where(item, how many were done))."""
        for done, item in enumerate(items):
            if self.reached:
                print(self.stop(where(item, done)))
                return
            yield item

    def _write(self) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({
            "cap_usd": self.cap_usd, "spent_usd": round(self.spent_usd, 6), "reached": self.reached,
            "stops": self._earlier_stops, "entries": self.entries}, indent=1) + "\n")


class NoCap:
    """What a script uses when it is run outside an ablation: nothing is capped or recorded."""
    reached, stopped_at = False, None

    def record(self, calls: Iterable[dict[str, Any]], item: str) -> float:
        return 0.0

    def guard(self, items: Iterable[Any], where: Callable[[Any, int], str]) -> Iterator[Any]:
        yield from items


def add_arguments(parser) -> None:
    parser.add_argument("--ablation", metavar="NAME",
                        help="take part in this ablation (results/ablations/NAME/): its spend ledger and cap apply")
    parser.add_argument("--spend-cap", type=float, default=config.EVAL_SPEND_CAP_USD, metavar="USD",
                        help=f"with --ablation: the cap on the ablation's total measured spend (default {config.EVAL_SPEND_CAP_USD})")


def open_cap(ablation: str | None, cap_usd: float, call_cost: Callable[[str, int, int], float]) -> "SpendCap | NoCap":
    if not ablation:
        return NoCap()
    return SpendCap(config.ABLATIONS_DIR / ablation / LEDGER_FILE, cap_usd, call_cost)
