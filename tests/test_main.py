"""
Tests for src/main.py

Strategy: patch builtins.input to feed a predetermined sequence of commands
into run_shell(), then let it exit via EOFError (same as Ctrl+D). This tests
every dispatch branch without starting a real interactive session.

We also patch crawl, build_index, save_index, load_index, print_word, and
find_pages so the shell logic is tested in isolation from the other modules
(those are already tested in their own test files).
"""

from unittest.mock import MagicMock, call, patch

import pytest

from src.main import run_shell


# ---------------------------------------------------------------------------
# Helper: run the shell with a scripted sequence of input lines
# ---------------------------------------------------------------------------

def _run_with_inputs(*lines: str):
    """
    Feed `lines` into run_shell() one at a time, then raise EOFError so
    the shell exits cleanly. Returns (stdout_output, ) via capsys.
    """
    responses = list(lines) + [EOFError]

    def fake_input(_prompt=""):
        val = responses.pop(0)
        if val is EOFError:
            raise EOFError
        return val

    with patch("builtins.input", side_effect=fake_input):
        run_shell()


# ---------------------------------------------------------------------------
# Startup and exit
# ---------------------------------------------------------------------------

class TestStartupAndExit:
    def test_prints_welcome_message(self, capsys):
        _run_with_inputs()
        assert "Search Engine Tool" in capsys.readouterr().out

    def test_quit_exits_cleanly(self, capsys):
        _run_with_inputs("quit")
        assert "Goodbye" in capsys.readouterr().out

    def test_exit_exits_cleanly(self, capsys):
        _run_with_inputs("exit")
        assert "Goodbye" in capsys.readouterr().out

    def test_ctrl_d_exits_cleanly(self, capsys):
        # EOFError is raised when no more inputs remain
        _run_with_inputs()
        assert "Goodbye" in capsys.readouterr().out

    def test_empty_input_does_not_crash(self, capsys):
        _run_with_inputs("", "   ", "quit")
        # Should exit normally
        assert "Goodbye" in capsys.readouterr().out

    def test_unknown_command_prints_message(self, capsys):
        _run_with_inputs("foobar", "quit")
        assert "Unknown command" in capsys.readouterr().out

    def test_invalid_quotes_handled_gracefully(self, capsys):
        _run_with_inputs("find 'unclosed quote", "quit")
        out = capsys.readouterr().out
        assert "Invalid input" in out or "Goodbye" in out


# ---------------------------------------------------------------------------
# help command
# ---------------------------------------------------------------------------

class TestHelpCommand:
    def test_help_lists_all_commands(self, capsys):
        _run_with_inputs("help", "quit")
        out = capsys.readouterr().out
        for cmd in ["build", "load", "print", "find", "quit"]:
            assert cmd in out


# ---------------------------------------------------------------------------
# build command
# ---------------------------------------------------------------------------

class TestBuildCommand:
    @patch("src.main.save_index")
    @patch("src.main.build_index", return_value={"hello": {}})
    @patch("src.main.crawl", return_value=[("https://example.com/", "<p>hello</p>")])
    def test_build_calls_crawl_build_save(self, mock_crawl, mock_build, mock_save, capsys):
        _run_with_inputs("build", "quit")
        mock_crawl.assert_called_once()
        mock_build.assert_called_once()
        mock_save.assert_called_once()

    @patch("src.main.save_index")
    @patch("src.main.build_index", return_value={"hello": {}, "world": {}})
    @patch("src.main.crawl", return_value=[])
    def test_build_reports_word_count(self, mock_crawl, mock_build, mock_save, capsys):
        _run_with_inputs("build", "quit")
        out = capsys.readouterr().out
        assert "2" in out

    @patch("src.main.save_index")
    @patch("src.main.build_index", return_value={"word": {}})
    @patch("src.main.crawl", return_value=[])
    def test_build_loads_index_into_memory(self, mock_crawl, mock_build, mock_save, capsys):
        """After build, print and find should work without a separate load."""
        _run_with_inputs("build", "print word", "quit")
        out = capsys.readouterr().out
        # Should not see the "no index loaded" error
        assert "No index loaded" not in out


# ---------------------------------------------------------------------------
# load command
# ---------------------------------------------------------------------------

class TestLoadCommand:
    @patch("src.main.load_index", return_value={"word": {}})
    def test_load_calls_load_index(self, mock_load, capsys):
        _run_with_inputs("load", "quit")
        mock_load.assert_called_once()

    @patch("src.main.load_index", side_effect=FileNotFoundError("Index not found. Run 'build' first."))
    def test_load_prints_error_if_file_missing(self, mock_load, capsys):
        _run_with_inputs("load", "quit")
        out = capsys.readouterr().out
        assert "build" in out.lower()

    @patch("src.main.load_index", return_value={"hello": {}})
    def test_load_makes_index_available(self, mock_load, capsys):
        """After load, print and find should work without 'no index' error."""
        _run_with_inputs("load", "print hello", "quit")
        out = capsys.readouterr().out
        assert "No index loaded" not in out


# ---------------------------------------------------------------------------
# print command
# ---------------------------------------------------------------------------

class TestPrintCommand:
    def test_print_without_index_shows_error(self, capsys):
        _run_with_inputs("print hello", "quit")
        assert "No index loaded" in capsys.readouterr().out

    def test_print_without_argument_shows_usage(self, capsys):
        with patch("src.main.load_index", return_value={"hello": {}}):
            _run_with_inputs("load", "print", "quit")
        assert "Usage" in capsys.readouterr().out

    @patch("src.main.print_word")
    @patch("src.main.load_index", return_value={"hello": {}})
    def test_print_calls_print_word_with_correct_arg(self, mock_load, mock_print_word, capsys):
        _run_with_inputs("load", "print hello", "quit")
        mock_print_word.assert_called_once()
        args = mock_print_word.call_args[0]
        assert args[1] == "hello"

    @patch("src.main.print_word")
    @patch("src.main.load_index", return_value={"hello": {}})
    def test_print_passes_index_to_print_word(self, mock_load, mock_print_word, capsys):
        _run_with_inputs("load", "print hello", "quit")
        args = mock_print_word.call_args[0]
        assert args[0] == {"hello": {}}


# ---------------------------------------------------------------------------
# find command
# ---------------------------------------------------------------------------

class TestFindCommand:
    def test_find_without_index_shows_error(self, capsys):
        _run_with_inputs("find hello", "quit")
        assert "No index loaded" in capsys.readouterr().out

    def test_find_without_argument_shows_usage(self, capsys):
        with patch("src.main.load_index", return_value={}):
            _run_with_inputs("load", "find", "quit")
        assert "Usage" in capsys.readouterr().out

    @patch("src.main.find_pages", return_value=[("https://example.com/", 0.75)])
    @patch("src.main.load_index", return_value={})
    def test_find_displays_results(self, mock_load, mock_find, capsys):
        _run_with_inputs("load", "find hello", "quit")
        out = capsys.readouterr().out
        assert "https://example.com/" in out
        assert "0.7500" in out

    @patch("src.main.find_pages", return_value=[])
    @patch("src.main.load_index", return_value={})
    def test_find_no_results_does_not_crash(self, mock_load, mock_find, capsys):
        _run_with_inputs("load", "find xyzzy", "quit")
        # Should exit cleanly — no exception
        assert "Goodbye" in capsys.readouterr().out

    @patch("src.main.find_pages", return_value=[("https://example.com/", 0.5)])
    @patch("src.main.load_index", return_value={})
    def test_find_multi_word_passes_all_terms(self, mock_load, mock_find, capsys):
        _run_with_inputs("load", "find good friends", "quit")
        args = mock_find.call_args[0]
        assert "good" in args[1]
        assert "friends" in args[1]

    @patch("src.main.find_pages", return_value=[
        ("https://example.com/page/1/", 0.9),
        ("https://example.com/page/2/", 0.4),
    ])
    @patch("src.main.load_index", return_value={})
    def test_find_shows_rank_numbers(self, mock_load, mock_find, capsys):
        _run_with_inputs("load", "find hello", "quit")
        out = capsys.readouterr().out
        assert "1." in out
        assert "2." in out
