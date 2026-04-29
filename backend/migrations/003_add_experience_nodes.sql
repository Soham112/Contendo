-- Phase 2: Experience graph seed — add experience_nodes table.
--
-- node_type values:
--   "work"             — paid employment / contract role
--   "personal_project" — side project built outside of employment
--   "education"        — degree, bootcamp, certification, course of study
--
-- domain_areas: comma-separated generic skill/domain labels extracted from
--   the resume (e.g. "React, fundraising, OKRs, Python"). Used by Phase 3
--   entity extraction to cross-reference ingested content.
--
-- context_label: human-readable display label shown in the UI
--   (e.g. "Software Engineer at Stripe · 2021–2023").
--
-- All rows are scoped by user_id for full multi-user isolation.

CREATE TABLE IF NOT EXISTS experience_nodes (
  experience_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        TEXT NOT NULL,
  node_type      TEXT NOT NULL CHECK (node_type IN ('work', 'personal_project', 'education')),
  entity_name    TEXT NOT NULL,   -- company name, project name, or institution
  role           TEXT,            -- job title, project role, or degree/major
  start_date     TEXT,            -- year or "YYYY-MM" string; free-form for flexibility
  end_date       TEXT,            -- year, "YYYY-MM", "present", or NULL
  domain_areas   TEXT,            -- comma-separated generic labels
  description    TEXT,            -- what they built / did / achieved
  context_label  TEXT,            -- display label for UI and prompt injection
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast per-user lookups (used at retrieval time).
CREATE INDEX IF NOT EXISTS idx_experience_nodes_user_id
  ON experience_nodes (user_id);

-- Index for node_type filtering (Phase 3 cross-reference queries).
CREATE INDEX IF NOT EXISTS idx_experience_nodes_type
  ON experience_nodes (user_id, node_type);
