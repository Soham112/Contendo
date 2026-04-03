import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

SKIP_FOLDERS = {
    ".obsidian",
    ".trash",
    "templates",
    "Templates",
    ".git",
}

MIN_CONTENT_LENGTH = 100


def clean_obsidian_markdown(text: str) -> str:
    """Remove Obsidian-specific syntax before ingestion."""
    # Remove YAML frontmatter (between --- lines)
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)

    # Convert [[wikilinks]] to just the link text
    text = re.sub(r"\[\[([^\]|]+)\|?[^\]]*\]\]", r"\1", text)

    # Remove ^block-references
    text = re.sub(r"\^\w+", "", text)

    # Remove ==highlights== markers but keep text
    text = re.sub(r"==([^=]+)==", r"\1", text)

    # Remove embedded file references ![[file]]
    text = re.sub(r"!\[\[[^\]]+\]\]", "", text)

    # Remove Dataview queries (```dataview blocks)
    text = re.sub(r"```dataview.*?```", "", text, flags=re.DOTALL)

    return text.strip()


def read_vault(vault_path: str) -> Iterator[dict]:
    """Recursively read all .md files from an Obsidian vault.

    Yields dicts with: filename, relative_path, content, word_count.
    Skips config folders, hidden folders, and notes shorter than MIN_CONTENT_LENGTH.
    """
    vault = Path(vault_path)

    if not vault.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")

    if not vault.is_dir():
        raise ValueError(f"Vault path is not a folder: {vault_path}")

    for md_file in vault.rglob("*.md"):
        parts = md_file.parts
        if any(part in SKIP_FOLDERS for part in parts):
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        content = clean_obsidian_markdown(content)

        if len(content.strip()) < MIN_CONTENT_LENGTH:
            continue

        yield {
            "filename": md_file.stem,
            "relative_path": str(md_file.relative_to(vault)),
            "content": content,
            "word_count": len(content.split()),
        }


def get_vault_stats(vault_path: str) -> dict:
    """Return stats about the vault without ingesting anything."""
    vault = Path(vault_path)

    if not vault.exists() or not vault.is_dir():
        raise ValueError("Invalid vault path")

    total_files = 0
    total_words = 0
    skipped = 0

    for md_file in vault.rglob("*.md"):
        parts = md_file.parts
        if any(part in SKIP_FOLDERS for part in parts):
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            content = clean_obsidian_markdown(content)

            if len(content.strip()) < MIN_CONTENT_LENGTH:
                skipped += 1
                continue

            total_files += 1
            total_words += len(content.split())

        except Exception:
            skipped += 1

    estimated_chunks = max(1, round(total_words / 400))

    return {
        "total_files": total_files,
        "total_words": total_words,
        "estimated_chunks": estimated_chunks,
        "skipped_files": skipped,
        "vault_name": vault.name,
    }


def get_vault_stats_from_dir(vault_dir: str) -> dict:
    """Return stats about a vault directory without ingesting anything.
    
    Accepts a vault directory path (can be extracted from zip or a local path).
    Called by both the local path preview and zip preview endpoints.
    """
    return get_vault_stats(vault_dir)


def extract_vault_from_zip(zip_bytes: bytes) -> str:
    """Extract a Obsidian vault from a zip file to a temp directory.
    
    Returns the temp directory path. Caller is responsible for cleanup via shutil.rmtree().
    
    Raises ValueError if:
    - The zip is empty or not a valid zip file
    - The zip contains no .md files after extraction
    - Any entry has a path starting with / or containing .. (path traversal guard)
    """
    if not zip_bytes:
        raise ValueError("Zip file is empty")
    
    # Verify it's a valid zip and check for path traversal
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            # Check for path traversal attacks in all entries
            for name in zf.namelist():
                if name.startswith('/') or '..' in name:
                    raise ValueError(f"Invalid zip entry (path traversal): {name}")
    except zipfile.BadZipFile:
        raise ValueError("Invalid zip file")
    
    # Extract to temp directory
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            zf.extractall(temp_dir)
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f"Failed to extract zip file: {str(e)}")
    
    # Verify there are .md files
    temp_path = Path(temp_dir)
    md_files = list(temp_path.rglob("*.md"))
    if not md_files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("No markdown files found in zip")
    
    return temp_dir


