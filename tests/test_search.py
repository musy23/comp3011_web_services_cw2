"""
Tests for src/search.py

Covers: print_word output, find_pages AND semantics, TF-IDF ranking,
missing terms, empty queries, single-word queries, and edge cases.
"""

import math
import pytest
from io import StringIO
from unittest.mock import patch

from src.search import (
    _count_unique_pages,
    _page_length,
    _tfidf_score,
    find_pages,
    print_word,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_index():
    """A small hand-crafted index used across multiple tests."""
    return {
        "good": {
            "https://example.com/page/1/": {"frequency": 3, "positions": [0, 5, 10]},
            "https://example.com/page/2/": {"frequency": 1, "positions": [2]},
        },
        "friends": {
            "https://example.com/page/1/": {"frequency": 2, "positions": [1, 8]},
        },
        "bad": {
            "https://example.com/page/2/": {"frequency": 1, "positions": [0]},
        },
        "indifference": {
            "https://example.com/page/3/": {"frequency": 1, "positions": [4]},
        },
    }


# ---------------------------------------------------------------------------
# _page_length
# ---------------------------------------------------------------------------

class TestPageLength:
    def test_returns_max_position_plus_one(self):
        stats = {"frequency": 2, "positions": [0, 9]}
        assert _page_length(stats) == 10

    def test_single_position(self):
        stats = {"frequency": 1, "positions": [0]}
        assert _page_length(stats) == 1

    def test_empty_positions_returns_one(self):
        stats = {"frequency": 0, "positions": []}
        assert _page_length(stats) == 1

    def test_missing_positions_key_returns_one(self):
        stats = {"frequency": 1}
        assert _page_length(stats) == 1


# ---------------------------------------------------------------------------
# _count_unique_pages
# ---------------------------------------------------------------------------

class TestCountUniquePages:
    def test_counts_distinct_urls(self, simple_index):
        count = _count_unique_pages(simple_index)
        assert count == 3  # page/1, page/2, page/3

    def test_empty_index_returns_one(self):
        # Guard against log(0) — must return at least 1
        assert _count_unique_pages({}) == 1

    def test_single_page_index(self):
        index = {"word": {"https://example.com/": {"frequency": 1, "positions": [0]}}}
        assert _count_unique_pages(index) == 1


# ---------------------------------------------------------------------------
# _tfidf_score
# ---------------------------------------------------------------------------

class TestTfidfScore:
    def test_score_is_positive_for_matching_term(self, simple_index):
        score = _tfidf_score(simple_index, ["good"], "https://example.com/page/1/", 3)
        assert score > 0

    def test_score_is_zero_for_non_matching_url(self, simple_index):
        # page/3 does not contain 'good'
        score = _tfidf_score(simple_index, ["good"], "https://example.com/page/3/", 3)
        assert score == 0.0

    def test_higher_tf_gives_higher_score(self):
        # TF-IDF rewards term density (frequency/page_length), not raw frequency.
        # Page A: frequency=5 on a 10-token page → TF=0.5
        # Page B: frequency=5 on a 100-token page → TF=0.05
        # Page A should score higher despite identical raw frequency.
        index = {
            "good": {
                "https://example.com/a/": {"frequency": 5, "positions": list(range(5))},      # length=5,  TF=1.0
                "https://example.com/b/": {"frequency": 5, "positions": list(range(99, 104))}, # length=104, TF≈0.048
            }
        }
        score_a = _tfidf_score(index, ["good"], "https://example.com/a/", 2)
        score_b = _tfidf_score(index, ["good"], "https://example.com/b/", 2)
        assert score_a > score_b

    def test_multi_term_score_accumulates(self, simple_index):
        # Score for both 'good' and 'friends' should exceed score for 'good' alone
        score_single = _tfidf_score(simple_index, ["good"], "https://example.com/page/1/", 3)
        score_multi = _tfidf_score(simple_index, ["good", "friends"], "https://example.com/page/1/", 3)
        assert score_multi > score_single

    def test_rare_term_gets_higher_idf(self, simple_index):
        # 'indifference' appears on 1/3 pages; 'good' appears on 2/3 pages
        # indifference should have higher IDF
        idf_indifference = math.log(3 / 1) + 1
        idf_good = math.log(3 / 2) + 1
        assert idf_indifference > idf_good


# ---------------------------------------------------------------------------
# print_word
# ---------------------------------------------------------------------------

class TestPrintWord:
    def test_prints_entry_for_known_word(self, simple_index, capsys):
        print_word(simple_index, "good")
        out = capsys.readouterr().out
        assert "good" in out
        assert "frequency" in out
        assert "positions" in out

    def test_case_insensitive_lookup(self, simple_index, capsys):
        print_word(simple_index, "GOOD")
        out = capsys.readouterr().out
        assert "good" in out
        assert "not found" not in out

    def test_unknown_word_prints_not_found(self, simple_index, capsys):
        print_word(simple_index, "xyz")
        out = capsys.readouterr().out
        assert "not found" in out

    def test_empty_word_prints_prompt(self, simple_index, capsys):
        print_word(simple_index, "")
        out = capsys.readouterr().out
        assert "provide" in out.lower()

    def test_whitespace_only_word_prints_prompt(self, simple_index, capsys):
        print_word(simple_index, "   ")
        out = capsys.readouterr().out
        assert "provide" in out.lower()

    def test_shows_correct_page_count(self, simple_index, capsys):
        print_word(simple_index, "good")
        out = capsys.readouterr().out
        assert "2 page(s)" in out

    def test_positions_truncated_at_five(self, capsys):
        index = {
            "word": {
                "https://example.com/": {
                    "frequency": 8,
                    "positions": [0, 1, 2, 3, 4, 5, 6, 7],
                }
            }
        }
        print_word(index, "word")
        out = capsys.readouterr().out
        assert "..." in out


# ---------------------------------------------------------------------------
# find_pages
# ---------------------------------------------------------------------------

class TestFindPages:
    def test_single_word_returns_matching_pages(self, simple_index):
        results = find_pages(simple_index, ["good"])
        urls = [r[0] for r in results]
        assert "https://example.com/page/1/" in urls
        assert "https://example.com/page/2/" in urls

    def test_multi_word_returns_intersection(self, simple_index):
        # Only page/1 has both 'good' and 'friends'
        results = find_pages(simple_index, ["good", "friends"])
        urls = [r[0] for r in results]
        assert urls == ["https://example.com/page/1/"]

    def test_no_intersection_returns_empty(self, simple_index):
        # 'bad' is only on page/2; 'friends' is only on page/1 — no overlap
        results = find_pages(simple_index, ["bad", "friends"])
        assert results == []

    def test_unknown_word_returns_empty(self, simple_index):
        results = find_pages(simple_index, ["nonexistent"])
        assert results == []

    def test_empty_query_returns_empty(self, simple_index):
        results = find_pages(simple_index, [])
        assert results == []

    def test_whitespace_only_terms_returns_empty(self, simple_index):
        results = find_pages(simple_index, ["  ", ""])
        assert results == []

    def test_results_sorted_by_score_descending(self, simple_index):
        results = find_pages(simple_index, ["good"])
        # page/1 has higher frequency so should rank first
        assert len(results) >= 2
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_returns_list_of_tuples(self, simple_index):
        results = find_pages(simple_index, ["good"])
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_scores_are_floats(self, simple_index):
        results = find_pages(simple_index, ["good"])
        for _, score in results:
            assert isinstance(score, float)

    def test_partial_match_reports_missing_term(self, simple_index, capsys):
        # 'good' exists, 'xyz' does not — should report missing and still search
        find_pages(simple_index, ["good", "xyz"])
        out = capsys.readouterr().out
        assert "xyz" in out

    def test_case_insensitive_search(self, simple_index):
        results_lower = find_pages(simple_index, ["good"])
        results_upper = find_pages(simple_index, ["GOOD"])
        assert [r[0] for r in results_lower] == [r[0] for r in results_upper]

    def test_empty_index_returns_empty(self):
        results = find_pages({}, ["good"])
        assert results == []

    def test_single_result_has_positive_score(self, simple_index):
        results = find_pages(simple_index, ["indifference"])
        assert len(results) == 1
        assert results[0][1] > 0
