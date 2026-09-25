"""In-memory stand-in for the Supabase client.

Supports the subset of the supabase-py query builder the backend uses:
table().select/insert/upsert/update/delete, filters eq/neq/in_/gt/gte/lt/lte,
order, limit, execute, and rpc("match_embeddings").

Tables start empty for every test (see conftest.py). Inspect them directly
in assertions via `fake_db.tables["posts"]`.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class FakeResponse:
    data: list[dict]
    count: int | None = None


_SIMPLE_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class FakeQuery:
    def __init__(self, db: "FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._op = "select"
        self._columns = "*"
        self._payload: Any = None
        self._on_conflict: list[str] | None = None
        self._filters: list[Callable[[dict], bool]] = []
        self._order: list[tuple[str, bool]] = []
        self._limit: int | None = None
        self._count = None

    # --- operations -------------------------------------------------------
    def select(self, columns: str = "*", count=None, **_):
        self._op, self._columns, self._count = "select", columns, count
        return self

    def insert(self, rows, **_):
        self._op, self._payload = "insert", rows
        return self

    def upsert(self, rows, on_conflict: str | None = None, **_):
        self._op, self._payload = "upsert", rows
        self._on_conflict = [c.strip() for c in on_conflict.split(",")] if on_conflict else None
        return self

    def update(self, values: dict, **_):
        self._op, self._payload = "update", values
        return self

    def delete(self, **_):
        self._op = "delete"
        return self

    # --- filters ----------------------------------------------------------
    def eq(self, col, val):
        self._filters.append(lambda r: r.get(col) == val)
        return self

    def neq(self, col, val):
        self._filters.append(lambda r: r.get(col) != val)
        return self

    def in_(self, col, vals):
        vals = list(vals)
        self._filters.append(lambda r: r.get(col) in vals)
        return self

    def gt(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) > val)
        return self

    def gte(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) >= val)
        return self

    def lt(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) < val)
        return self

    def lte(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) <= val)
        return self

    def order(self, col, desc: bool = False, **_):
        self._order.append((col, desc))
        return self

    def limit(self, n: int, **_):
        self._limit = n
        return self

    # --- execution --------------------------------------------------------
    def _matches(self, row: dict) -> bool:
        return all(f(row) for f in self._filters)

    def _project(self, row: dict) -> dict:
        cols = [c.strip() for c in self._columns.split(",")]
        if self._columns.strip() == "*" or not all(_SIMPLE_COLUMN.match(c) for c in cols):
            return copy.deepcopy(row)
        return {c: copy.deepcopy(row.get(c)) for c in cols}

    def execute(self) -> FakeResponse:
        rows = self._db.tables.setdefault(self._table, [])
        self._db.log.append((self._table, self._op))

        if self._op == "select":
            out = [r for r in rows if self._matches(r)]
            for col, desc in reversed(self._order):
                out.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
            total = len(out)
            if self._limit is not None:
                out = out[: self._limit]
            return FakeResponse([self._project(r) for r in out], total if self._count else None)

        if self._op in ("insert", "upsert"):
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            written = []
            for new in payload:
                new = copy.deepcopy(new)
                existing = None
                if self._op == "upsert":
                    keys = self._on_conflict or ["id"]
                    if all(k in new for k in keys):
                        existing = next((r for r in rows if all(r.get(k) == new[k] for k in keys)), None)
                if existing is not None:
                    existing.update(new)
                    written.append(copy.deepcopy(existing))
                else:
                    if "id" not in new:
                        new["id"] = self._db.next_id(self._table)
                    rows.append(new)
                    written.append(copy.deepcopy(new))
            return FakeResponse(written)

        if self._op == "update":
            written = []
            for r in rows:
                if self._matches(r):
                    r.update(copy.deepcopy(self._payload))
                    written.append(copy.deepcopy(r))
            return FakeResponse(written)

        if self._op == "delete":
            kept, removed = [], []
            for r in rows:
                (removed if self._matches(r) else kept).append(r)
            self._db.tables[self._table] = kept
            return FakeResponse(copy.deepcopy(removed))

        raise NotImplementedError(self._op)


class FakeRpc:
    def __init__(self, fn: Callable[[], list[dict]]):
        self._fn = fn

    def execute(self) -> FakeResponse:
        return FakeResponse(self._fn())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.log: list[tuple[str, str]] = []
        self._ids: dict[str, int] = {}

    def reset(self) -> None:
        self.tables.clear()
        self.log.clear()
        self._ids.clear()

    def next_id(self, table: str) -> int:
        self._ids[table] = self._ids.get(table, 0) + 1
        return self._ids[table]

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, name: str, params: dict) -> FakeRpc:
        if name == "match_embeddings":
            def run():
                rows = [
                    r for r in self.tables.get("embeddings", [])
                    if r.get("user_id") == params["match_user_id"] and r.get("embedding")
                ]
                scored = []
                for r in rows:
                    out = {k: copy.deepcopy(v) for k, v in r.items() if k != "embedding"}
                    out["similarity"] = _cosine(params["query_embedding"], r["embedding"])
                    scored.append(out)
                scored.sort(key=lambda r: r["similarity"], reverse=True)
                return scored[: params.get("match_count", 8)]
            return FakeRpc(run)
        raise NotImplementedError(f"FakeSupabase has no rpc {name!r}")
