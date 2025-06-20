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

Edit main.py and change the prompt and path to your desired specifications. Call only the modules that are desired.

Streamlined API support to come.

## Known Limitations

Many sites respond to automated requests with HTTP 403 errors, "Forbidden Access". The frequency of these errors varies greatly from one prompt to the next, but severely limits the number of papers that are gathered. This remains an active issue.

## Considerations

This tool systematically pings Google Scholar and any returned URLs, potentially many times. As such, built in delays are added for compliance and bot-throttling reasons. Change or remove these at your own risk.
