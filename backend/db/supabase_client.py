"""Single module-level Supabase client shared across the backend."""

import os

from supabase import Client, create_client

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)
