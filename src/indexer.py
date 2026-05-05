"""
Inverted index builder and persistence layer.

The index maps every word to the set of pages it appears in, storing
frequency and token positions for each occurrence.

Structure:
    {
        "word": {
            "https://...page/1/": {
                "frequency": 3,
                "positions": [4, 17, 42]
            }
        }
    }

This nested-dict layout gives O(1) lookup for any word, and makes
multi-word query intersection a simple set operation on the inner keys.
JSON is used for storage: human-readable, inspectable, and avoids the
security and portability issues of pickle.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

INDEX_PATH = Path("data/index.json")


def _tokenise(text: str) -> list[str]:
    """
    Lowercase the text and extract alphabetic tokens only.

    re.findall(r'[a-z]+') discards punctuation, numbers, and whitespace
    in one pass — cleaner than split() which leaves punctuation attached.
    Case-insensitive search is achieved by lowercasing before tokenising,
    so 'Good' and 'good' map to the same token 'good'.
    """
    return re.findall(r"[a-z]+", text.lower())


def build_index(pages: list[tuple[str, str]]) -> dict:
    """
    Build an inverted index from a list of (url, html) pairs.

    For each page, all visible text is extracted (BeautifulSoup strips
    tags), tokenised, and each token is recorded with its page URL,
    frequency, and zero-based token position within that page.

    defaultdict is used during construction to avoid 'if key not in dict'
    checks on every token. The result is converted to a plain dict before
    returning so callers don't need to import defaultdict.
    """
    from bs4 import BeautifulSoup

    # Two-level defaultdict:
    # level 1: word  -> dict of pages
    # level 2: url   -> {"frequency": int, "positions": [int]}
    index: dict = defaultdict(
        lambda: defaultdict(lambda: {"frequency": 0, "positions": []})
    )

    for url, html in pages:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style tags so JS/CSS tokens don't pollute the index
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        tokens = _tokenise(text)

        for position, word in enumerate(tokens):
            index[word][url]["frequency"] += 1
            index[word][url]["positions"].append(position)

    # Convert nested defaultdicts to plain dicts for JSON compatibility
    return {word: dict(pages) for word, pages in index.items()}


def save_index(index: dict, path: Path = INDEX_PATH) -> None:
    """Serialise the index to a JSON file. Creates parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        # indent=2 keeps the file human-readable for inspection and the video demo
        json.dump(index, fh, indent=2, ensure_ascii=False)
    print(f"Index saved to {path} ({path.stat().st_size // 1024} KB)")


def load_index(path: Path = INDEX_PATH) -> dict:
    """
    Load the index from a JSON file.

    Raises FileNotFoundError with a helpful message if the index has
    not been built yet, rather than letting Python emit a raw traceback.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Index file not found at '{path}'. Run 'build' first."
        )
    with open(path, "r", encoding="utf-8") as fh:
        index = json.load(fh)
    print(f"Index loaded from {path} ({len(index)} unique words)")
    return index
