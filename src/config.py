"""
Configuration module for Scholar Extractor.
Centralizes all configurable parameters and settings.
"""

import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration class for Scholar Extractor."""

    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    METADATA_DIR = DATA_DIR / "metadata"
    PAPERS_DIR = DATA_DIR / "papers"

    # HTTP client settings
    REQUEST_DELAY = 8.0  # Seconds between requests (ethical scraping)
    REQUEST_TIMEOUT = 30  # Seconds
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0  # Exponential backoff multiplier

    # User agents (rotate to avoid detection)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]

    # Scholar Extractor specific user agent
    CUSTOM_USER_AGENT = "ScholarExtractor/0.1.0 (Educational Research Tool; +https://github.com/yourorg/scholarextractor)"

    # Google Scholar settings
    SCHOLAR_BASE_URL = "https://scholar.google.com"
    RESULTS_PER_PAGE = 10  # Google Scholar typically shows 10-20 results per page
    MAX_PAGES = 10  # Maximum pages to scrape

    # PDF download settings
    PDF_DOWNLOAD_TIMEOUT = 60  # Seconds for PDF downloads
    PDF_MAX_SIZE_MB = 50  # Maximum PDF size to download
    VERIFY_PDF = True  # Verify PDF integrity after download

    # Storage settings
    STATE_FILE = DATA_DIR / "state.json"
    METADATA_JSON = METADATA_DIR / "metadata.json"
    METADATA_CSV = METADATA_DIR / "metadata.csv"
    DOWNLOAD_LOG = PAPERS_DIR / "download_log.json"

    # Logging
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FILE = DATA_DIR / "scholarextractor.log"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Feature flags
    ENABLE_PDF_DOWNLOAD = True
    ENABLE_BIBTEX_EXTRACTION = True
    ENABLE_ABSTRACT_EXTRACTION = True
    USE_SCHOLARLY_LIBRARY = False  # Try custom scraper first for more control

    # Rate limiting
    CAPTCHA_KEYWORDS = [
        "unusual traffic",
        "captcha",
        "robot",
        "automated",
        "verify you're not a robot"
    ]

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.METADATA_DIR.mkdir(exist_ok=True)
        cls.PAPERS_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Return configuration as a dictionary."""
        return {
            "request_delay": cls.REQUEST_DELAY,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "max_retries": cls.MAX_RETRIES,
            "results_per_page": cls.RESULTS_PER_PAGE,
            "max_pages": cls.MAX_PAGES,
            "pdf_download_timeout": cls.PDF_DOWNLOAD_TIMEOUT,
            "pdf_max_size_mb": cls.PDF_MAX_SIZE_MB,
            "log_level": cls.LOG_LEVEL,
        }

    @classmethod
    def update_from_dict(cls, config_dict: Dict[str, Any]):
        """Update configuration from dictionary."""
        for key, value in config_dict.items():
            attr_name = key.upper()
            if hasattr(cls, attr_name):
                setattr(cls, attr_name, value)
