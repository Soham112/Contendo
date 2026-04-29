-- Phase 3: Entity extraction — add entities and chunk_entities tables.
--
-- entities: one row per unique (user_id, entity_name, entity_type) triple.
--   Deduplicated at upsert time — same entity mentioned across many chunks
--   maps to a single row.
--
-- entity_type values:
--   "technology"   — programming languages, frameworks, tools, platforms
--   "company"      — organisations, employers, clients, competitors
--   "project"      — named products, codebases, or initiatives
--   "concept"      — abstract ideas, methodologies, paradigms
--   "methodology"  — processes, frameworks, workflows (e.g. "Agile", "OKRs")
--   "market"       — industries, verticals, customer segments
--   "metric"       — quantitative measures (e.g. "ARR", "MAU", "p99 latency")
--   "person"       — named individuals (authors, public figures)
--
-- chunk_entities: junction table linking embeddings chunks to entities.
--
-- relationship_type values:
--   "mentions"      — chunk references the entity in passing
--   "explains"      — chunk teaches or describes the entity in depth
--   "used_in"       — chunk describes using/applying the entity
--   "contrasts_with"— chunk compares or argues against the entity
--
-- All rows are scoped by user_id for full multi-user isolation.

-- ── entities ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entities (
  entity_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      TEXT NOT NULL,
  entity_name  TEXT NOT NULL,
  entity_type  TEXT NOT NULL CHECK (entity_type IN (
    'technology', 'company', 'project', 'concept',
    'methodology', 'market', 'metric', 'person'
  )),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, entity_name, entity_type)
);

-- Fast lookup by user (list all entities for a user).
CREATE INDEX IF NOT EXISTS idx_entities_user_id
  ON entities (user_id);

-- Fast lookup by name for deduplication at upsert time.
CREATE INDEX IF NOT EXISTS idx_entities_user_name
  ON entities (user_id, entity_name);

-- ── chunk_entities ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS chunk_entities (
  chunk_id          TEXT NOT NULL,   -- references embeddings.id
  entity_id         UUID NOT NULL REFERENCES entities (entity_id) ON DELETE CASCADE,
  user_id           TEXT NOT NULL,
  relationship_type TEXT NOT NULL CHECK (relationship_type IN (
    'mentions', 'explains', 'used_in', 'contrasts_with'
  )),
  PRIMARY KEY (chunk_id, entity_id)
);

-- Fast reverse lookup: given an entity, find all chunks that reference it.
CREATE INDEX IF NOT EXISTS idx_chunk_entities_entity_id
  ON chunk_entities (entity_id);

-- Fast forward lookup: given a chunk, find all its entities.
CREATE INDEX IF NOT EXISTS idx_chunk_entities_chunk_id
  ON chunk_entities (chunk_id);

-- Fast per-user lookup (used in Phase 4 retrieval enrichment).
CREATE INDEX IF NOT EXISTS idx_chunk_entities_user_id
  ON chunk_entities (user_id);
