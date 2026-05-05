"""
Tests for src/indexer.py

Covers: tokenisation, index structure, frequency counting, position
tracking, script/style tag exclusion, save/load round-trip, and edge
cases (empty input, repeated words, missing index file).
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.indexer import _tokenise, build_index, load_index, save_index


# ---------------------------------------------------------------------------
# _tokenise
# ---------------------------------------------------------------------------

class TestTokenise:
    def test_lowercase_conversion(self):
        assert _tokenise("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokenise("don't stop!") == ["don", "t", "stop"]

    def test_strips_numbers(self):
        assert _tokenise("page 42 results") == ["page", "results"]

    def test_empty_string_returns_empty_list(self):
        assert _tokenise("") == []

    def test_only_punctuation_returns_empty_list(self):
        assert _tokenise("!!! --- ...") == []

    def test_mixed_case_normalised(self):
        tokens = _tokenise("Good GOOD good")
        assert tokens == ["good", "good", "good"]

    def test_preserves_word_order(self):
        assert _tokenise("the quick brown fox") == ["the", "quick", "brown", "fox"]


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    def test_returns_dict(self):
        pages = [("https://example.com/", "<p>hello</p>")]
        index = build_index(pages)
        assert isinstance(index, dict)

    def test_word_present_in_index(self):
        pages = [("https://example.com/", "<p>hello world</p>")]
        index = build_index(pages)
        assert "hello" in index
        assert "world" in index

    def test_correct_frequency(self):
        pages = [("https://example.com/", "<p>good good bad</p>")]
        index = build_index(pages)
        assert index["good"]["https://example.com/"]["frequency"] == 2
        assert index["bad"]["https://example.com/"]["frequency"] == 1

    def test_positions_recorded(self):
        pages = [("https://example.com/", "<p>apple banana apple</p>")]
        index = build_index(pages)
        positions = index["apple"]["https://example.com/"]["positions"]
        # apple appears at position 0 and 2
        assert len(positions) == 2
        assert positions[0] < positions[1]

    def test_case_insensitive_indexing(self):
        pages = [("https://example.com/", "<p>Good good GOOD</p>")]
        index = build_index(pages)
        assert "good" in index
        assert "Good" not in index
        assert index["good"]["https://example.com/"]["frequency"] == 3

    def test_multiple_pages_indexed(self):
        pages = [
            ("https://example.com/page/1/", "<p>hello</p>"),
            ("https://example.com/page/2/", "<p>hello world</p>"),
        ]
        index = build_index(pages)
        # 'hello' should appear in both pages
        assert "https://example.com/page/1/" in index["hello"]
        assert "https://example.com/page/2/" in index["hello"]
        # 'world' should only appear on page 2
        assert "https://example.com/page/2/" in index["world"]
        assert "https://example.com/page/1/" not in index["world"]

    def test_script_tags_excluded(self):
        html = "<script>var hello = 1;</script><p>goodbye</p>"
        pages = [("https://example.com/", html)]
        index = build_index(pages)
        # 'var' is a JS token — must not appear in the index
        assert "var" not in index
        assert "goodbye" in index

    def test_style_tags_excluded(self):
        html = "<style>.hello { color: red; }</style><p>world</p>"
        pages = [("https://example.com/", html)]
        index = build_index(pages)
        assert "color" not in index
        assert "world" in index

    def test_empty_pages_list_returns_empty_index(self):
        index = build_index([])
        assert index == {}

    def test_empty_html_returns_empty_index(self):
        pages = [("https://example.com/", "")]
        index = build_index(pages)
        assert index == {}

    def test_index_values_are_plain_dicts_not_defaultdict(self):
        """Ensure no defaultdict leaks through — plain dict required for JSON."""
        pages = [("https://example.com/", "<p>hello</p>")]
        index = build_index(pages)
        assert type(index) is dict
        for url_dict in index.values():
            assert type(url_dict) is dict

    def test_positions_are_zero_based(self):
        pages = [("https://example.com/", "<p>first second third</p>")]
        index = build_index(pages)
        assert index["first"]["https://example.com/"]["positions"][0] == 0

    def test_html_tags_not_indexed_as_words(self):
        pages = [("https://example.com/", "<div><p>actual content</p></div>")]
        index = build_index(pages)
        assert "div" not in index
        assert "actual" in index
        assert "content" in index


# ---------------------------------------------------------------------------
# save_index / load_index
# ---------------------------------------------------------------------------

class TestSaveLoadIndex:
    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            index = {"hello": {"https://example.com/": {"frequency": 1, "positions": [0]}}}
            save_index(index, path)
            assert path.exists()

    def test_saved_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            index = {"hello": {"https://example.com/": {"frequency": 1, "positions": [0]}}}
            save_index(index, path)
            with open(path) as fh:
                loaded = json.load(fh)
            assert loaded == index

    def test_round_trip_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            original = {
                "good": {
                    "https://example.com/page/1/": {"frequency": 2, "positions": [0, 5]},
                    "https://example.com/page/2/": {"frequency": 1, "positions": [3]},
                },
                "bad": {
                    "https://example.com/page/1/": {"frequency": 1, "positions": [1]},
                },
            }
            save_index(original, path)
            loaded = load_index(path)
            assert loaded == original

    def test_load_raises_if_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.json"
            with pytest.raises(FileNotFoundError):
                load_index(path)

    def test_load_error_message_mentions_build(self):
        """The error message should guide the user to run 'build' first."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.json"
            with pytest.raises(FileNotFoundError, match="build"):
                load_index(path)

    def test_save_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir" / "index.json"
            save_index({}, path)
            assert path.exists()
