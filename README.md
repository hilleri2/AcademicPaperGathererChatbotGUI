# AcademicPaperGatherer

**AcademicPaperGatherer** is a modular Python tool that automates the collection, filtering, and preparation of academic papers from Google Scholar. Designed to streamline literature reviews and support large language model (LLM) workflows, it converts papers into plain text and extracts useful metadata for further analysis. Created as part of a larger project (Scholarly AI Analyzer), but is designed to run independently of the other portion.

## Key Features

- **Prompt-to-Search Conversion**: Builds a Google Scholar search query from a user-provided prompt.
- **Result and File Collection**: Gathers links and attempts to download full-text PDFs and any directly referenced articles.
- **Relevance Filtering**: Filters out unrelated papers and removes duplicates based on the original prompt.
- **Metadata Extraction & Text Conversion**: Extracts author, title, abstract, and other metadata; converts papers to plaintext for use in downstream Natural Language Processing (NLP) tasks.

## Modules

The tool consists of three independent modules, each of which can be executed separately or as part of a complete pipeline:

| Module | Description |
|--------|-------------|
| **ResultGatherer** | Gathers the specified number of results from Google Scholar using the supplied prompt. Returns a list of dictionaries. |
| **FileGatherer** | Visits each result and attempts to gather the directly referenced article and/or any referenced articles on the page. Filters based on relevance to the prompt. Extracts metadata (title, keywords, authors, modification date) and saves relevant articles. |
| **TextConverterAndExtractor** | Iterates over all PDFs at a specified path. Converts each to plain text and attempts to extract its abstract. |

## Installation

```bash
git clone https://github.com/clarautu/AcademicPaperGatherer.git
cd AcademicPaperGatherer
pip install -r requirements.txt
```

## Usage

This tool can run its full pipeline or individual modules using subcommands.

**Note:** `main.py` can be edited and run, if desired. It has the same functionality as `cli.py`, but requires manual parameter setting. Not recommended for general use.

### General Structure

```bash
python cli.py <command> [options]
```

### Subcommands

#### `all` — Run the full pipeline

```bash
python cli.py all --query "search query" --directory "output directory" [options]
```

**Required:**
- `--query` – search query used to gather results
- `--directory` – directory to save files to

**Optional:**
- `--total_results` – number of results to gather (default: 100)
- `--year_start` – start of year range (e.g., 2010)
- `--year_end` – end of year range (e.g., 2024)
- `--meta_can_be_missing` – allow files with missing metadata

---

#### `results` — Only gather search results

```bash
python cli.py results --query "search query" --directory "output directory" [options]
```

**Same options as `all`, except no file processing or conversion.**

---

#### `files` — Only gather files from an existing `results.txt` file

```bash
python cli.py files --query "search query" --directory "output directory" [options]
```

**Note:** Requires a `results.txt` file already present in the given directory.

---

#### `convert` — Only run text conversion and extraction

```bash
python cli.py convert --directory "output directory"
```

**Note:** Assumes files have already been gathered into the output directory.

---

### Examples

Run everything:

```bash
python cli.py all --query "climate change" --directory "data"
```

Only gather results:

```bash
python cli.py results --query "machine learning" --directory "ml_data" --total_results 50
```

Convert already-downloaded files:

```bash
python cli.py convert --directory "ml_data"
```


## Known Limitations

Many sites respond to automated requests with HTTP 403 errors, "Forbidden Access". The frequency of these errors varies greatly from one prompt to the next, but severely limits the number of papers that are gathered. In an attempt to combat this, several methods were explored and tested (such as free proxies, headless browsers, and user behavior mimicking) with little success.

This remains an active issue.

## Considerations

This tool systematically pings Google Scholar and any returned URLs, potentially many times. As such, built in delays are added for compliance and bot-throttling reasons. Change or remove these at your own risk.
