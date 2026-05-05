# COMP3011 Web Services CW2 — Search Engine Tool

A command-line search engine that crawls [quotes.toscrape.com](https://quotes.toscrape.com/), builds an inverted index of all word occurrences, and lets you search for pages by keyword.

Built for COMP3011 Web Services and Web Data, University of Leeds.

---

## Project Overview

The tool is split into four modules:

| Module | Responsibility |
|---|---|
| `src/crawler.py` | BFS crawl of the target site, 6s politeness window, error handling |
| `src/indexer.py` | Build inverted index from crawled HTML, JSON save/load |
| `src/search.py` | `print` and `find` commands with TF-IDF ranking |
| `src/main.py` | Interactive CLI shell, command dispatch |

### Inverted Index Structure

```
{
  "word": {
    "https://quotes.toscrape.com/page/1/": {
      "frequency": 3,
      "positions": [4, 17, 42]
    }
  }
}
```

Each word maps to the pages it appears on, with frequency and token positions stored per page. This gives O(1) word lookup and makes multi-word query intersection a simple set operation.

---

## Dependencies

- Python 3.10+
- [requests](https://docs.python-requests.org/en/master/) — HTTP requests
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — HTML parsing
- [pytest](https://docs.pytest.org/) — test runner
- [pytest-cov](https://pytest-cov.readthedocs.io/) — coverage reporting

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/musy23/comp3011_web_services_cw2.git
cd comp3011_web_services_cw2
```

2. (Recommended) Create and activate a virtual environment:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Start the interactive shell from the project root:

```bash
python -m src.main
```

You will see the `>` prompt. The following commands are available:

---

### `build`

Crawls the entire target website, builds the inverted index, and saves it to `data/index.json`.

> **Note:** The politeness window of 6 seconds between requests means this takes several minutes to complete.

```
> build
Starting crawl from https://quotes.toscrape.com/
  Crawled [1]: https://quotes.toscrape.com/
  Waiting 6s (politeness window)...
  Crawled [2]: https://quotes.toscrape.com/page/2/
  ...
Index saved to data/index.json (45 KB)
Index built and saved (1042 unique words).
```

---

### `load`

Loads a previously built index from `data/index.json`. Must be run before `print` or `find` if you have not just run `build`.

```
> load
Index loaded from data/index.json (1042 unique words)
```

---

### `print <word>`

Prints the inverted index entry for a single word — all pages it appears on, with frequency and token positions.

```
> print nonsense
Inverted index entry for 'nonsense' (2 page(s)):
------------------------------------------------------------
  https://quotes.toscrape.com/page/1/
    frequency : 1
    positions : [42]
  https://quotes.toscrape.com/page/3/
    frequency : 2
    positions : [7, 19]
```

Search is case-insensitive: `print Nonsense` and `print NONSENSE` produce the same result.

---

### `find <word(s)>`

Finds all pages containing every search term (AND semantics), ranked by TF-IDF relevance score.

Single word:

```
> find indifference
Found 1 page(s):
------------------------------------------------------------
  1. https://quotes.toscrape.com/page/4/  (score: 0.2341)
```

Multi-word query (pages must contain ALL terms):

```
> find good friends
Found 1 page(s):
------------------------------------------------------------
  1. https://quotes.toscrape.com/page/1/  (score: 0.5123)
```

---

### `help`

Lists all available commands.

```
> help
```

---

### `quit` / `exit`

Exits the shell. You can also press `Ctrl+C` or `Ctrl+D`.

```
> quit
Exiting. Goodbye.
```

---

## Testing

Run the full test suite from the project root:

```bash
python -m pytest tests/ -v
```

Run with coverage report:

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Test suite summary

| Test file | Module tested | Tests |
|---|---|---|
| `tests/test_crawler.py` | `src/crawler.py` | 22 |
| `tests/test_indexer.py` | `src/indexer.py` | 26 |
| `tests/test_search.py` | `src/search.py` | 32 |
| `tests/test_main.py` | `src/main.py` | 24 |
| **Total** | | **104** |

Coverage: **99%** across all `src` modules.

Tests use `unittest.mock` to patch `requests.get`, `time.sleep`, and `builtins.input` so the suite runs instantly without network calls or interactive input.

---

## Repository Structure

```
comp3011_web_services_cw2/
├── src/
│   ├── crawler.py       # BFS web crawler
│   ├── indexer.py       # Inverted index builder and JSON persistence
│   ├── search.py        # print and find with TF-IDF ranking
│   └── main.py          # Interactive CLI shell
├── tests/
│   ├── test_crawler.py
│   ├── test_indexer.py
│   ├── test_search.py
│   └── test_main.py
├── data/
│   └── index.json       # Generated by the build command
├── requirements.txt
└── README.md
```
