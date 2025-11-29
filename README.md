# Academic Reference Extractor

A Python tool that extracts author affiliations and contact information from academic PDF bibliographies. It parses reference entries, identifies authors, and uses multiple data sources (Semantic Scholar, DBLP, and Claude LLM) to find institutional affiliations and email addresses.

## Features

- **PDF Parsing**: Extracts references from academic PDF bibliographies with chapter organization
- **Smart Citation Parsing**: Handles various citation formats including:
  - Standard format: `Author, A., & Author, B. (YYYY). Title. Venue.`
  - Semicolon-separated: `Author, A.; Author, B. (YYYY).`
  - Translation format: `Original Author. Title. Translated by Translator (YYYY).`
  - Et al patterns: `Author, A., ... & Author, Z. (YYYY).`
  - Full name format: `LastName, FirstName (YYYY)`
- **Multi-Source Author Lookup**: 
  - Semantic Scholar API for academic author data
  - DBLP for computer science publications
  - Claude LLM for intelligent affiliation extraction from web data
- **Excel Output**: Generates professionally formatted Excel reports with:
  - Chapter organization
  - First and last author information
  - Affiliations, departments, and emails
  - Confidence scores and data sources
- **Web Interface**: Optional Flask-based UI for easy PDF upload and processing

## Project Structure

```
academic-reference-extractor/
├── main.py                 # CLI application entry point
├── web_interface.py        # Flask web UI (optional)
├── requirements.txt        # Python dependencies
├── .env                    # API keys configuration
├── src/
│   ├── pdf_parser.py       # PDF text extraction and reference parsing
│   ├── author_lookup.py    # Multi-source author information lookup
│   └── excel_output.py     # Excel report generation
└── data/
    ├── input/              # Place input PDFs here
    └── output/             # Generated Excel files
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/academic-reference-extractor.git
   cd academic-reference-extractor
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API keys**
   
   Copy the example environment file and add your API keys:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

## Usage

### Command Line Interface

**Basic usage:**
```bash
python main.py data/input/References.pdf
```

**Specify output file:**
```bash
python main.py data/input/References.pdf data/output/results.xlsx
```

**Process limited references (for testing):**
```bash
python main.py data/input/References.pdf --max-refs 10
```

**Disable LLM lookup (faster, less accurate):**
```bash
python main.py data/input/References.pdf --no-llm
```

**Full options:**
```bash
python main.py --help
```

### Web Interface

Start the Flask web server:
```bash
python web_interface.py
```

Then open http://localhost:5000 in your browser to:
1. Upload a PDF file
2. Monitor processing progress
3. Download the generated Excel report

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key for Claude LLM (author info extraction) |
| `SEMANTIC_SCHOLAR_API_KEY` | No | Optional API key for higher rate limits |
| `GOOGLE_API_KEY` | No | Google Custom Search API key (optional) |
| `GOOGLE_CSE_ID` | No | Google Custom Search Engine ID (optional) |

### PDF Input Format

The parser expects PDFs with references in a bibliography format. It works best with:
- References in `[Author 'YY]` citation key format
- Chapter markers in `———— Chapter N ————` format
- Standard academic citation styles (APA, IEEE, etc.)

## Output Format

The generated Excel file contains the following columns:

| Column | Description |
|--------|-------------|
| Chapter | Source chapter in the PDF |
| Citation Key | Reference identifier (e.g., "Smith '23") |
| Title | Paper/book title |
| Year | Publication year |
| First Author | Name of first author |
| First Author Affiliation | Institution of first author |
| First Author Department | Department (if available) |
| First Author Email | Email address (if found) |
| Last Author | Name of last author (if different) |
| Last Author Affiliation | Institution of last author |
| Last Author Department | Department (if available) |
| Last Author Email | Email address (if found) |
| Confidence | Confidence score (0-1) of author info |
| Source | Data source (Semantic Scholar, DBLP, LLM) |

## Performance

Tested on a bibliography with 625 references:
- **Title extraction**: 100% accuracy
- **Year extraction**: 99.8% accuracy
- **Author extraction**: 100% accuracy
- **Processing time**: ~2-5 minutes (depending on LLM usage)

## Troubleshooting

### Common Issues

**"ANTHROPIC_API_KEY not set"**
- Ensure your `.env` file exists and contains a valid API key
- Check that `python-dotenv` is installed

**PDF parsing returns empty results**
- Verify the PDF contains selectable text (not scanned images)
- Try a different PDF to rule out format issues

**Rate limiting errors**
- The tool includes automatic rate limiting
- For large PDFs, consider using `--max-refs` to process in batches

**Missing author information**
- Some authors may not have public profiles
- LLM extraction requires the Anthropic API key

## Dependencies

- `pdfplumber` - PDF text extraction
- `pypdf` - Fallback PDF reader
- `pandas` - Data manipulation
- `openpyxl` - Excel file generation
- `requests` - HTTP requests for APIs
- `beautifulsoup4` - HTML parsing
- `anthropic` - Claude LLM API client
- `python-dotenv` - Environment variable management
- `flask` - Web interface (optional)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Semantic Scholar API](https://www.semanticscholar.org/product/api) for academic author data
- [DBLP](https://dblp.org/) for computer science publication data
- [Anthropic Claude](https://www.anthropic.com/) for intelligent text extraction