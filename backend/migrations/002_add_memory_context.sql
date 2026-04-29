-- Phase 1: Context tagging — add memory_context column to embeddings table.
--
-- memory_context values:
--   "work"             — content from a professional work context
--   "personal_project" — content from a personal side project
--   "learning"         — externally sourced content the user read/watched
--   "observation"      — patterns the user noticed in the world
--   NULL               — untagged (legacy chunks); falls back to source_type heuristics
--
-- The column is nullable so all existing rows are unaffected.

ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS memory_context TEXT;

-- Update the match_embeddings RPC to return memory_context in its result set.
-- Run this in the Supabase SQL editor to replace the existing function.

CREATE OR REPLACE FUNCTION match_embeddings(
  query_embedding vector(384),
  match_user_id   text,
  match_count     int
)
RETURNS TABLE (
  id            text,
  content       text,
  source_id     text,
  source_title  text,
  source_type   text,
  tags          text,
  chunk_index   int,
  total_chunks  int,
  content_hash  text,
  node_type     text,
  memory_context text,
  ingested_at   timestamptz,
  similarity    float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    content,
    source_id,
    source_title,
    source_type,
    tags,
    chunk_index,
    total_chunks,
    content_hash,
    node_type,
    memory_context,
    ingested_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM embeddings
  WHERE user_id = match_user_id
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
