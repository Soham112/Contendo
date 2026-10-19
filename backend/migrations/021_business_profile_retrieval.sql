-- Apply after 020 and BEFORE deploying the business-block backend.
-- Stored rows and original RPC remain intact for immediate flag rollback.
CREATE OR REPLACE FUNCTION public.match_embeddings_without_business_profile(query_embedding public.vector, match_user_id text, match_count integer) RETURNS TABLE(id text, content text, source_id text, source_title text, source_type text, tags text, chunk_index integer, total_chunks integer, content_hash text, node_type text, memory_context text, ingested_at timestamp with time zone, similarity double precision)
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
    AND source_type IS DISTINCT FROM 'business_profile'
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
