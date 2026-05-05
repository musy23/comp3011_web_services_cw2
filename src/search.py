"""
Search logic: print index entries and find pages matching query terms.

Two public functions:
    print_word(index, word)         -- display posting list for one word
    find_pages(index, query_terms)  -- return ranked list of matching URLs

Ranking uses TF-IDF so results reflect relevance rather than raw count:
    TF  = frequency / page_length       (length-normalised term density)
    IDF = log(total_pages / pages_with_term) + 1   (rarity bonus)
    Score = sum of TF-IDF across all query terms
"""

import math


def print_word(index: dict, word: str) -> None:
    """
    Print the inverted index entry for a single word.

    Looks up the lowercased word in O(1) and prints each page URL with
    its term frequency and the first few token positions.
    """
    word = word.lower().strip()

    if not word:
        print("Please provide a word to print.")
        return

    if word not in index:
        print(f"'{word}' not found in the index.")
        return

    postings = index[word]
    print(f"\nInverted index entry for '{word}' ({len(postings)} page(s)):")
    print("-" * 60)
    for url, stats in postings.items():
        freq = stats["frequency"]
        positions = stats["positions"]
        # Show only the first 5 positions to keep terminal output readable
        pos_preview = positions[:5]
        ellipsis = "..." if len(positions) > 5 else ""
        print(f"  {url}")
        print(f"    frequency : {freq}")
        print(f"    positions : {pos_preview}{ellipsis}")
    print()


def _page_length(stats: dict) -> int:
    """
    Estimate page length as max token position + 1.

    We store positions rather than a separate word count, so the highest
    recorded position is a reliable proxy for total tokens on that page.
    The +1 converts from zero-based index to a count.
    """
    positions = stats.get("positions", [])
    return max(positions) + 1 if positions else 1


def _count_unique_pages(index: dict) -> int:
    """
    Count distinct URLs across all posting lists.

    Used as N (total documents) in the IDF formula. Derived from the
    index itself so no separate metadata file is needed.
    """
    all_urls: set[str] = set()
    for postings in index.values():
        all_urls.update(postings.keys())
    return max(len(all_urls), 1)  # guard against empty index


def _tfidf_score(index: dict, query_terms: list[str], url: str, total_pages: int) -> float:
    """
    Compute the combined TF-IDF score for a URL across all query terms.

    TF  = frequency / page_length
        Normalises for page length so a dense occurrence on a short page
        ranks higher than the same raw count buried in a long page.

    IDF = log(total_pages / pages_containing_term) + 1
        Penalises terms that appear on almost every page (e.g. 'the').
        The +1 floor ensures the score never collapses to zero even when
        a term appears on every crawled page.

    Final score is the sum across all query terms so multi-word queries
    accumulate relevance from each term.
    """
    score = 0.0
    for term in query_terms:
        if term not in index or url not in index[term]:
            continue
        stats = index[term][url]
        tf = stats["frequency"] / _page_length(stats)
        pages_with_term = len(index[term])
        idf = math.log(total_pages / pages_with_term) + 1
        score += tf * idf
    return score


def find_pages(index: dict, query_terms: list[str]) -> list[tuple[str, float]]:
    """
    Find all pages containing every query term (AND semantics) and rank
    them by TF-IDF score.

    Steps:
      1. Lowercase and strip all terms.
      2. Report any terms absent from the index (helpful user feedback).
      3. Build a URL set for each present term, sort by size ascending
         (smallest first minimises intersection work), then intersect —
         result contains only pages that have ALL terms.
      4. Score each matching page with TF-IDF and sort descending.

    Returns a list of (url, score) tuples, best-first.
    An empty list means no pages matched all terms.
    """
    if not query_terms:
        print("Please provide at least one search term.")
        return []

    terms = [t.lower().strip() for t in query_terms if t.strip()]

    if not terms:
        print("Please provide at least one search term.")
        return []

    # Report missing terms so the user knows why results may be limited
    missing = [t for t in terms if t not in index]
    if missing:
        print(f"Term(s) not found in index: {', '.join(missing)}")

    present_terms = [t for t in terms if t in index]
    if not present_terms:
        return []

    # Build posting sets and sort smallest-first to minimise intersection cost
    posting_sets = sorted(
        [set(index[t].keys()) for t in present_terms], key=len
    )
    matching_urls = posting_sets[0].intersection(*posting_sets[1:])

    if not matching_urls:
        print("No pages found containing all search terms.")
        return []

    total_pages = _count_unique_pages(index)
    results = [
        (url, _tfidf_score(index, present_terms, url, total_pages))
        for url in matching_urls
    ]
    # Sort descending by score — most relevant page first
    results.sort(key=lambda x: x[1], reverse=True)
    return results
