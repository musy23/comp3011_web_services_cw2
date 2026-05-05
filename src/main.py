"""
Command-line interface shell for the search engine tool.

Supported commands:
    build               -- crawl the website, build index, save to disk
    load                -- load a previously saved index from disk
    print <word>        -- display the inverted index entry for a word
    find <word(s)>      -- find pages containing all given words (AND)
    help                -- list available commands
    quit / exit         -- exit the shell

State: the index lives in memory as a plain dict after build or load.
All commands that need the index check for it first and print a helpful
message if it has not been loaded yet.
"""

import shlex

from src.crawler import crawl
from src.indexer import build_index, load_index, save_index
from src.search import find_pages, print_word

HELP_TEXT = """
Available commands:
  build               Crawl the website and build the inverted index
  load                Load a previously built index from disk
  print <word>        Print the index entry for a word
  find <word(s)>      Find pages containing all given words
  help                Show this help message
  quit / exit         Exit the shell
"""


def run_shell() -> None:
    """
    Main REPL loop.

    Reads a line of input, tokenises it with shlex.split (handles quoted
    arguments correctly), dispatches to the appropriate handler, and loops.
    The index starts as None and is populated by build or load.
    """
    index = None
    print("Search Engine Tool — type 'help' for available commands.")

    while True:
        try:
            raw = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C or Ctrl+D: exit cleanly without a traceback
            print("\nExiting. Goodbye.")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            # shlex.split raises ValueError on unmatched quotes
            print(f"Invalid input: {exc}")
            continue

        command = parts[0].lower()
        args = parts[1:]

        if command == "build":
            pages = crawl()
            index = build_index(pages)
            save_index(index)
            print(f"Index built and saved ({len(index)} unique words).")

        elif command == "load":
            try:
                index = load_index()
            except FileNotFoundError as exc:
                print(exc)

        elif command == "print":
            if index is None:
                print("No index loaded. Run 'build' or 'load' first.")
                continue
            if not args:
                print("Usage: print <word>")
                continue
            print_word(index, args[0])

        elif command == "find":
            if index is None:
                print("No index loaded. Run 'build' or 'load' first.")
                continue
            if not args:
                print("Usage: find <word(s)>")
                continue
            results = find_pages(index, args)
            if results:
                print(f"\nFound {len(results)} page(s):")
                print("-" * 60)
                for rank, (url, score) in enumerate(results, start=1):
                    print(f"  {rank}. {url}  (score: {score:.4f})")
                print()

        elif command in ("quit", "exit"):
            print("Exiting. Goodbye.")
            break

        elif command == "help":
            print(HELP_TEXT)

        else:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")


if __name__ == "__main__":
    run_shell()
