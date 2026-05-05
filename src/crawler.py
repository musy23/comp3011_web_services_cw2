"""
Web crawler for quotes.toscrape.com.

Performs a breadth-first crawl starting from BASE_URL, staying within the
same domain, and observing a mandatory politeness window between requests.
Returns a list of (url, html) pairs for the indexer to process.
"""

import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://quotes.toscrape.com/"
POLITENESS_WINDOW = 6  # seconds — required by the assignment brief


def _same_domain(url: str) -> bool:
    """Return True if url belongs to the same host as BASE_URL."""
    return urlparse(url).netloc == urlparse(BASE_URL).netloc


def _extract_links(html: str, current_url: str) -> list[str]:
    """
    Parse all <a href> links from an HTML page and return absolute URLs
    that belong to the same domain.

    urljoin handles relative paths (e.g. '/page/2/' → full URL) so the
    visited-set comparison always works on normalised absolute URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        absolute = urljoin(current_url, tag["href"])
        # Strip fragment (#...) so '#top' and the bare URL aren't treated as different pages
        absolute = absolute.split("#")[0]
        if _same_domain(absolute):
            links.append(absolute)
    return links


def crawl(start_url: str = BASE_URL) -> list[tuple[str, str]]:
    """
    BFS crawl of the target website.

    Uses a deque as the frontier (queue) and a set for O(1) visited-URL
    lookup. Every URL is visited at most once. A 6-second politeness
    window is observed between successive HTTP requests.

    Returns a list of (url, html_string) tuples — one per successfully
    fetched page — for the indexer to consume.
    """
    visited: set[str] = set()
    # deque gives O(1) append to the right and popleft from the left,
    # making it the correct data structure for a BFS queue.
    queue: deque[str] = deque([start_url])
    pages: list[tuple[str, str]] = []
    first_request = True

    print(f"Starting crawl from {start_url}")

    while queue:
        url = queue.popleft()

        # Normalise trailing slash so '/page/1' and '/page/1/' aren't duplicated
        normalised = url.rstrip("/") + "/"
        if normalised in visited:
            continue
        visited.add(normalised)

        # Politeness window — sleep before every request except the very first
        if not first_request:
            print(f"  Waiting {POLITENESS_WINDOW}s (politeness window)...")
            time.sleep(POLITENESS_WINDOW)
        first_request = False

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # raises HTTPError for 4xx/5xx responses
        except requests.RequestException as exc:
            # Network errors (timeouts, DNS failures, HTTP errors) are logged
            # and skipped — the crawl continues with remaining queued URLs.
            print(f"  ERROR fetching {url}: {exc}")
            continue

        html = response.text
        pages.append((url, html))
        print(f"  Crawled [{len(pages)}]: {url}")

        # Discover new links and enqueue any not yet visited
        for link in _extract_links(html, url):
            normalised_link = link.rstrip("/") + "/"
            if normalised_link not in visited:
                queue.append(link)

    print(f"Crawl complete. {len(pages)} pages fetched.")
    return pages
