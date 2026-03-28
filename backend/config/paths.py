"""Centralised storage-path configuration for Contendo.

All data paths are derived from a single DATA_DIR environment variable.

Local default: <repo-root>/backend/data  (identical to previous hardcoded paths)
Railway production: set DATA_DIR=/data (or wherever the persistent volume is mounted)

Usage:
    from config.paths import CHROMA_DIR, POSTS_DB_PATH, HIERARCHY_DB_PATH, PROFILE_PATH, PROFILES_DIR
"""

import os
from pathlib import Path

# Resolve DATA_DIR: env var → absolute path; otherwise fall back to the
# canonical local default (same directory that was previously hardcoded).
_DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"

DATA_DIR = Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA_DIR))).resolve()

CHROMA_DIR = DATA_DIR / "chroma_db"
POSTS_DB_PATH = DATA_DIR / "posts.db"
HIERARCHY_DB_PATH = DATA_DIR / "hierarchy.db"
PROFILE_PATH = DATA_DIR / "profile.json"       # legacy single-user location
PROFILES_DIR = DATA_DIR / "profiles"           # per-user profiles: profile_{user_id}.json
