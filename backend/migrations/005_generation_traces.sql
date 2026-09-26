-- Generation traces: one row per /generate pipeline run, for offline eval.
--
-- Written by run_pipeline() in backend/pipeline/graph.py (row built in
-- pipeline/trace.py). A failed write is logged and never fails the request.
--
-- post_id: set by /log-post when it carries trace_id; NULL until then, and set
--   back to NULL if the post is deleted.
-- retrieved: snapshot of the chunks actually used, text included, because chunk
--   ids dangle once a library source is deleted:
--   [{chunk_id, source_id, source_title, source_type, similarity, bm25_score,
--     rrf_score, rrf_rank, entity_linked, text}]
--   similarity is a fixed 0.35 for BM25-only and entity-linked chunks.
-- node_outputs: {draft_history: [{node, iteration, text}], critic_brief,
--   score_history: [{iteration, score, score_feedback}], final_post}
-- llm_calls: from llm.client.trace_calls():
--   [{event_type, model, input_tokens, output_tokens, latency_ms}]
--
-- post_id is INTEGER to match posts.id (confirmed integer in Supabase).
--
-- RLS is enabled with no policies: only the backend's service-role key can read
-- or write. Every backend query must filter by user_id.
--
-- Run this in the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS generation_traces (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               TEXT NOT NULL,
  post_id               INTEGER NULL REFERENCES posts (id) ON DELETE SET NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  topic                 TEXT,
  context               TEXT,
  format                TEXT,
  tone                  TEXT,
  length                TEXT,
  quality               TEXT,
  retrieval_query       TEXT,
  retrieval_path        TEXT,   -- "hybrid" | "flat_fallback"
  retrieval_confidence  TEXT,   -- "low" | "medium" | "high"
  retrieved             JSONB,
  retrieved_context     TEXT,
  profile_snapshot      JSONB,
  node_outputs          JSONB,
  llm_calls             JSONB,
  score                 INT,
  iterations            INT,
  archetype             TEXT,
  eval_status           TEXT DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_generation_traces_user_created
  ON generation_traces (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_generation_traces_eval_status
  ON generation_traces (eval_status);

ALTER TABLE generation_traces ENABLE ROW LEVEL SECURITY;
