# Scholar Extractor

A robust Python tool for extracting comprehensive metadata and downloading papers from Google Scholar.

## Features

- **Metadata Extraction**: Extract detailed paper metadata including:
  - Title, authors, publication year
  - Journal/conference venue
  - Abstract, citation count
  - DOI, URLs, BibTeX citations

- **PDF Downloads**: Automatically download available full-text PDFs

- **Ethical Scraping**:
  - Configurable rate limiting (default: 8 seconds between requests)
  - User-agent rotation
  - CAPTCHA detection
  - Respects robots.txt

- **Resumability**: Save progress and resume interrupted sessions

- **Multiple Export Formats**: Export metadata to JSON and CSV

- **Progress Tracking**: Real-time progress bars and statistics

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourorg/scholarextractor.git
cd scholarextractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Extract metadata from a Google Scholar search:

```bash
python scholarextractor.py extract --url "YOUR_GOOGLE_SCHOLAR_URL"
```

### Example with Your Query

Based on the goal in `prompt.md`, here's how to extract papers about student web design/programming:

```bash
python scholarextractor.py extract \
  --url "https://scholar.google.com/scholar?q=allintitle%3A+student+%22web+design%22+OR+%22web+programming%22+OR+%22web+development%22+OR+HTML&hl=en&as_sdt=0%2C5&as_vis=1&as_ylo=2007&as_yhi=" \
  --max-papers 64 \
  --download-pdfs
```

### Command Reference

#### `extract` - Extract metadata from Google Scholar

```bash
python scholarextractor.py extract [OPTIONS]
```

**Options:**
- `--url, -u`: Google Scholar search URL (required)
- `--max-papers, -n`: Maximum number of papers to extract (default: 100)
- `--delay, -d`: Delay between requests in seconds (default: 8.0)
- `--download-pdfs`: Download PDFs automatically
- `--resume`: Resume from previous session
- `--verbose, -v`: Enable verbose logging
- `--output, -o`: Custom output directory

**Example:**
```bash
python scholarextractor.py extract \
  --url "https://scholar.google.com/scholar?q=machine+learning" \
  --max-papers 50 \
  --delay 10 \
  --download-pdfs \
  --verbose
```

#### `download` - Download PDFs for extracted papers

Download PDFs for papers that don't have them yet:

```bash
python scholarextractor.py download
```

**Options:**
- `--verbose, -v`: Enable verbose logging

#### `status` - Show extraction status

Display statistics about extracted papers:

```bash
python scholarextractor.py status
```

#### `export` - Export metadata

Export metadata to different formats:

```bash
python scholarextractor.py export [OPTIONS]
```

**Options:**
- `--format, -f`: Export format: json, csv, or both (default: both)
- `--output, -o`: Output file path

**Example:**
```bash
python scholarextractor.py export --format csv --output results.csv
```

## Output Files

The tool creates the following directory structure:

```
scholarextractor/
├── data/
│   ├── metadata/
│   │   ├── metadata.json      # Complete metadata in JSON format
│   │   └── metadata.csv       # Metadata in CSV format
│   ├── papers/
│   │   ├── *.pdf              # Downloaded PDF files
│   │   └── download_log.json  # Download status log
│   ├── state.json             # State file for resuming
│   └── scholarextractor.log   # Detailed log file
```

### Metadata Format

**JSON Structure:**
```json
{
  "papers": [
    {
      "id": "unique_id",
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "year": 2020,
      "venue": "Journal Name",
      "abstract": "Abstract text...",
      "citations": 42,
      "url": "https://...",
      "doi": "10.1000/...",
      "bibtex": "@article{...}",
      "pdf_url": "https://.../paper.pdf",
      "pdf_downloaded": true,
      "pdf_path": "data/papers/Author_2020_Title.pdf",
      "extracted_at": "2025-11-16T20:00:00Z"
    }
  ],
  "query": {
    "url": "...",
    "executed_at": "2025-11-16T20:00:00Z"
  },
  "total_papers": 64
}
```

**CSV Format:**
The CSV includes all fields with list columns (like authors) joined by semicolons.

## Configuration

You can modify settings in `src/config.py`:

```python
# Rate limiting
REQUEST_DELAY = 8.0  # Seconds between requests
REQUEST_TIMEOUT = 30  # Request timeout

# PDF downloads
PDF_DOWNLOAD_TIMEOUT = 60  # PDF download timeout
PDF_MAX_SIZE_MB = 50  # Maximum PDF size

# Search settings
MAX_PAGES = 10  # Maximum pages to scrape
RESULTS_PER_PAGE = 10  # Results per page
```

## Ethical Considerations

This tool is designed for **academic research and educational purposes only**. Please use responsibly:

### Best Practices

✅ **DO:**
- Use reasonable delays (8-10 seconds recommended)
- Respect CAPTCHA warnings and wait before retrying
- Only download publicly accessible papers
- Use for personal research and education
- Cite papers properly in your work

❌ **DON'T:**
- Run multiple instances simultaneously
- Use aggressive delays (< 5 seconds)
- Download paywalled content without access
- Redistribute downloaded papers
- Use for commercial purposes without permission

### Legal Notice

- Google Scholar's Terms of Service prohibit automated access
- This tool is for educational and research purposes only
- Users are responsible for complying with applicable laws and terms of service
- Respect copyright and intellectual property rights
- Only download papers you have legal access to

## Troubleshooting

### CAPTCHA Detected

If you see "CAPTCHA detected" errors:
1. Wait 30-60 minutes before retrying
2. Increase the delay with `--delay 15`
3. Use `--resume` to continue from where you stopped

### No PDFs Downloaded

- Many papers are behind paywalls and cannot be downloaded freely
- The tool only downloads publicly accessible PDFs
- Expected success rate: 30-50%

### Network Errors

- Check your internet connection
- The tool automatically retries failed requests
- Use `--resume` to continue after network issues

### Empty Results

- Verify your search URL returns results in a browser
- Check that the URL is properly quoted in the command
- Some queries may have no accessible papers

## Development

### Project Structure

```
scholarextractor/
├── src/
│   ├── __init__.py        # Package initialization
│   ├── cli.py             # Command-line interface
│   ├── client.py          # HTTP client with rate limiting
│   ├── config.py          # Configuration settings
│   ├── downloader.py      # PDF download functionality
│   ├── metadata.py        # Metadata extraction
│   ├── search.py          # Search orchestration
│   └── storage.py         # Data storage and retrieval
├── tests/                 # Unit tests
├── data/                  # Output directory
├── requirements.txt       # Python dependencies
├── scholarextractor.py    # Main entry point
└── README.md             # This file
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided for educational and research purposes. Users are responsible for ensuring their use complies with applicable laws and terms of service.

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review logs in `data/scholarextractor.log`

## Acknowledgments

Built with:
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Requests](https://requests.readthedocs.io/) - HTTP library
- [Click](https://click.palletsprojects.com/) - CLI framework
- [tqdm](https://github.com/tqdm/tqdm) - Progress bars
- [Pandas](https://pandas.pydata.org/) - Data manipulation

## Version History

### v0.1.0 (2025-11-16)
- Initial release
- Basic metadata extraction
- PDF download functionality
- CLI interface
- Export to JSON/CSV
- Resumability support
