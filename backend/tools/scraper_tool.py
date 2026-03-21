import httpx
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def clean_scraped_text(text: str) -> str:
    """Light cleaning of Jina Reader output.

    Jina already returns clean markdown so this is minimal post-processing —
    removes navigation artifacts, bare URLs, and image syntax.
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip very short lines that are likely UI elements, not content
        if len(stripped) < 15 and not stripped.startswith("#"):
            continue
        # Skip lines that are just bare URLs
        if stripped.startswith("http") and " " not in stripped:
            continue
        # Skip markdown image syntax
        if stripped.startswith("!["):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def scrape_url(url: str) -> dict:
    """Scrape a URL using Jina Reader (r.jina.ai).

    Returns a dict with: content, title, word_count, source_url.
    Raises ValueError with a user-friendly message on any failure.

    Upgrade path to Tavily for higher quality:
        pip install tavily-python
        Add TAVILY_API_KEY to .env
        Replace body with:
            from tavily import TavilyClient
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.extract(urls=[url])
            content = result['results'][0]['raw_content']
    """
    if not is_valid_url(url):
        raise ValueError("Invalid URL. Please include https:// at the start.")

    jina_url = f"https://r.jina.ai/{url}"

    try:
        response = httpx.get(
            jina_url,
            headers={
                "Accept": "text/plain",
                "X-Return-Format": "markdown",
            },
            timeout=30.0,
            follow_redirects=True,
        )
    except httpx.TimeoutException:
        raise ValueError(
            "The request timed out. The site may be slow or blocking scrapers. "
            "Try copying the text manually."
        )
    except httpx.RequestError:
        raise ValueError("Could not reach the URL. Check the link and try again.")

    if response.status_code != 200:
        raise ValueError(
            f"Could not scrape this URL (status {response.status_code}). "
            "The site may block automated access. Try copying the text manually."
        )

    raw_text = response.text.strip()

    if len(raw_text) < 200:
        raise ValueError(
            "Could not extract enough content from this URL. The page may require "
            "login, be paywalled, or be mostly JavaScript. Try copying the text manually."
        )

    cleaned = clean_scraped_text(raw_text)

    # Extract title from the first markdown heading if present
    title = url
    for line in cleaned.split("\n")[:10]:
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break

    word_count = len(cleaned.split())

    return {
        "content": cleaned,
        "title": title,
        "word_count": word_count,
        "source_url": url,
    }
