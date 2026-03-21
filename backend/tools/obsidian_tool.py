import re
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
