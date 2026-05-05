"""
Tests for src/crawler.py

Strategy: mock requests.get so tests run instantly without network calls.
This lets us simulate success, HTTP errors, timeouts, and edge cases
deterministically. unittest.mock.patch replaces requests.get for the
duration of each test then restores it automatically.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.crawler import BASE_URL, POLITENESS_WINDOW, _extract_links, _same_domain, crawl


# ---------------------------------------------------------------------------
# _same_domain
# ---------------------------------------------------------------------------

class TestSameDomain:
    def test_base_url_is_same_domain(self):
        assert _same_domain("https://quotes.toscrape.com/page/2/") is True

    def test_root_is_same_domain(self):
        assert _same_domain("https://quotes.toscrape.com/") is True

    def test_external_url_is_different_domain(self):
        assert _same_domain("https://www.goodreads.com/author/1") is False

    def test_similar_but_different_domain(self):
        # Ensure subdomain variations are treated as different
        assert _same_domain("https://evil-quotes.toscrape.com/") is False

    def test_empty_string_is_different_domain(self):
        assert _same_domain("") is False


# ---------------------------------------------------------------------------
# _extract_links
# ---------------------------------------------------------------------------

class TestExtractLinks:
    def test_extracts_relative_links_as_absolute(self):
        html = '<a href="/page/2/">Next</a>'
        links = _extract_links(html, BASE_URL)
        assert "https://quotes.toscrape.com/page/2/" in links

    def test_extracts_absolute_same_domain_links(self):
        html = '<a href="https://quotes.toscrape.com/tag/love/">Love</a>'
        links = _extract_links(html, BASE_URL)
        assert "https://quotes.toscrape.com/tag/love/" in links

    def test_excludes_external_links(self):
        html = '<a href="https://www.goodreads.com/author/1">Author</a>'
        links = _extract_links(html, BASE_URL)
        assert links == []

    def test_strips_fragment_from_link(self):
        html = '<a href="/page/1/#top">Top</a>'
        links = _extract_links(html, BASE_URL)
        # Fragment stripped — URL ends at the path
        assert all("#" not in link for link in links)

    def test_ignores_tags_without_href(self):
        html = '<a>No href here</a><a href="/page/2/">Has href</a>'
        links = _extract_links(html, BASE_URL)
        assert len(links) == 1

    def test_returns_empty_list_for_no_links(self):
        html = "<p>No links here at all.</p>"
        links = _extract_links(html, BASE_URL)
        assert links == []

    def test_mixed_internal_and_external(self):
        html = """
        <a href="/page/2/">Internal</a>
        <a href="https://goodreads.com">External</a>
        <a href="/tag/humor/">Also internal</a>
        """
        links = _extract_links(html, BASE_URL)
        assert len(links) == 2
        assert all(_same_domain(l) for l in links)


# ---------------------------------------------------------------------------
# crawl — using mocked requests.get
# ---------------------------------------------------------------------------

def _make_response(html: str, status_code: int = 200) -> MagicMock:
    """Helper: build a mock requests.Response object."""
    import requests as req
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = html
    # raise_for_status must raise requests.HTTPError (a subclass of
    # RequestException) so the crawler's except clause catches it correctly.
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError(f"HTTP {status_code}")
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestCrawl:
    @patch("src.crawler.time.sleep")  # prevent real sleeping in tests
    @patch("src.crawler.requests.get")
    def test_crawls_single_page_with_no_links(self, mock_get, mock_sleep):
        """Crawl a page that has no internal links — should return just that one page."""
        mock_get.return_value = _make_response("<html><body><p>Hello</p></body></html>")
        pages = crawl(BASE_URL)
        assert len(pages) == 1
        assert pages[0][0] == BASE_URL

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_crawls_linked_pages(self, mock_get, mock_sleep):
        """Crawl should follow internal links and return all reachable pages."""
        page1_html = '<a href="/page/2/">Next</a>'
        page2_html = "<p>Last page, no links.</p>"

        def get_side_effect(url, **kwargs):
            if "page/2" in url:
                return _make_response(page2_html)
            return _make_response(page1_html)

        mock_get.side_effect = get_side_effect
        pages = crawl(BASE_URL)
        urls = [p[0] for p in pages]
        assert len(pages) == 2
        assert BASE_URL in urls
        assert any("page/2" in u for u in urls)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_does_not_revisit_pages(self, mock_get, mock_sleep):
        """A page linked from multiple places should only be crawled once."""
        # Both page/2 and page/3 link back to the root — root must only appear once
        root_html = '<a href="/page/2/">P2</a><a href="/page/3/">P3</a>'
        page2_html = '<a href="/">Home</a>'  # links back to root
        page3_html = '<a href="/">Home</a>'  # links back to root

        def get_side_effect(url, **kwargs):
            if "page/2" in url:
                return _make_response(page2_html)
            if "page/3" in url:
                return _make_response(page3_html)
            return _make_response(root_html)

        mock_get.side_effect = get_side_effect
        pages = crawl(BASE_URL)
        urls = [p[0] for p in pages]
        # Root should appear exactly once despite being linked from two pages
        assert urls.count(BASE_URL) == 1

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_skips_external_links(self, mock_get, mock_sleep):
        """External links in the page must not be followed."""
        html = '<a href="https://goodreads.com/author/1">External</a>'
        mock_get.return_value = _make_response(html)
        pages = crawl(BASE_URL)
        # Only the start page — external link not followed
        assert len(pages) == 1

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_continues_after_http_error(self, mock_get, mock_sleep):
        """A 404 on one page should not halt the crawl of other pages."""
        root_html = '<a href="/page/2/">P2</a><a href="/page/3/">P3</a>'
        page3_html = "<p>Good page</p>"

        def get_side_effect(url, **kwargs):
            if "page/2" in url:
                return _make_response("", status_code=404)
            if "page/3" in url:
                return _make_response(page3_html)
            return _make_response(root_html)

        mock_get.side_effect = get_side_effect
        pages = crawl(BASE_URL)
        urls = [p[0] for p in pages]
        # Root and page/3 should be crawled; page/2 skipped due to 404
        assert any("page/3" in u for u in urls)
        assert not any("page/2" in u for u in urls)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_continues_after_network_timeout(self, mock_get, mock_sleep):
        """A timeout exception on one page should not halt the crawl."""
        import requests as req

        root_html = '<a href="/page/2/">P2</a><a href="/page/3/">P3</a>'
        page3_html = "<p>Good page</p>"

        def get_side_effect(url, **kwargs):
            if "page/2" in url:
                raise req.exceptions.Timeout("timed out")
            if "page/3" in url:
                return _make_response(page3_html)
            return _make_response(root_html)

        mock_get.side_effect = get_side_effect
        pages = crawl(BASE_URL)
        urls = [p[0] for p in pages]
        assert any("page/3" in u for u in urls)

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_politeness_window_observed(self, mock_get, mock_sleep):
        """sleep must be called between requests with the correct duration."""
        page1_html = '<a href="/page/2/">Next</a>'
        page2_html = "<p>Done</p>"

        def get_side_effect(url, **kwargs):
            if "page/2" in url:
                return _make_response(page2_html)
            return _make_response(page1_html)

        mock_get.side_effect = get_side_effect
        crawl(BASE_URL)
        # sleep should be called at least once (between page 1 and page 2)
        mock_sleep.assert_called()
        # Every call must use the correct politeness window duration
        for call in mock_sleep.call_args_list:
            assert call.args[0] == POLITENESS_WINDOW

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_no_sleep_before_first_request(self, mock_get, mock_sleep):
        """The very first request must not be preceded by a sleep."""
        mock_get.return_value = _make_response("<p>Only page</p>")
        crawl(BASE_URL)
        # Only one page crawled, so sleep should never be called
        mock_sleep.assert_not_called()

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_returns_html_content(self, mock_get, mock_sleep):
        """Each returned tuple must contain the correct HTML string."""
        html = "<html><body><p>Quote content</p></body></html>"
        mock_get.return_value = _make_response(html)
        pages = crawl(BASE_URL)
        assert pages[0][1] == html

    @patch("src.crawler.time.sleep")
    @patch("src.crawler.requests.get")
    def test_empty_crawl_on_immediate_error(self, mock_get, mock_sleep):
        """If the start URL itself fails, return an empty list gracefully."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("no connection")
        pages = crawl(BASE_URL)
        assert pages == []
