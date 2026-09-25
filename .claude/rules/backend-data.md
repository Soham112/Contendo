---
paths:
  - "backend/memory/**"
  - "backend/routers/**"
  - "backend/migrations/**"
  - "backend/auth/**"
---

# Data, routing, and auth rules

- Use the helpers in `backend/memory/` for database access; don't query Supabase directly from routers.
- Every Supabase query filters by `user_id`, or checks ownership first (see `_post_owned_by` in `feedback_store.py` for the pattern). The service-role key bypasses RLS, so a missing filter leaks data across users.
- Embeddings live in the `embeddings` table and are always scoped by `user_id`. After writing chunks, call `invalidate_bm25_cache(user_id)`.
- Do not reintroduce ChromaDB or SQLite storage.
- New endpoints: add `Depends(get_user_id_dep)` unless the endpoint is explicitly public or admin (admin uses the `x-admin-secret` header). Update section 3 of CODEBASE.md.
- Error responses: log the exception, return a generic message. Don't return `str(e)` to the client.
