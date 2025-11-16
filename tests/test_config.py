"""
Tests for configuration module.
"""

import pytest
from pathlib import Path
from src.config import Config


class TestConfig:
    """Test Config class."""

    def test_config_paths_exist(self):
        """Test that config defines required paths."""
        assert hasattr(Config, 'PROJECT_ROOT')
        assert hasattr(Config, 'DATA_DIR')
        assert hasattr(Config, 'METADATA_DIR')
        assert hasattr(Config, 'PAPERS_DIR')

        assert isinstance(Config.PROJECT_ROOT, Path)
        assert isinstance(Config.DATA_DIR, Path)

    def test_config_request_settings(self):
        """Test HTTP request settings."""
        assert Config.REQUEST_DELAY > 0
        assert Config.REQUEST_TIMEOUT > 0
        assert Config.MAX_RETRIES >= 0
        assert Config.RETRY_BACKOFF > 0

    def test_config_user_agents(self):
        """Test user agent configuration."""
        assert isinstance(Config.USER_AGENTS, list)
        assert len(Config.USER_AGENTS) > 0
        assert all(isinstance(ua, str) for ua in Config.USER_AGENTS)

    def test_config_scholar_settings(self):
        """Test Google Scholar settings."""
        assert Config.SCHOLAR_BASE_URL.startswith('https://')
        assert Config.RESULTS_PER_PAGE > 0
        assert Config.MAX_PAGES > 0

    def test_config_pdf_settings(self):
        """Test PDF download settings."""
        assert Config.PDF_DOWNLOAD_TIMEOUT > 0
        assert Config.PDF_MAX_SIZE_MB > 0
        assert isinstance(Config.VERIFY_PDF, bool)

    def test_ensure_directories(self, temp_dir, monkeypatch):
        """Test directory creation."""
        # Temporarily override paths
        monkeypatch.setattr(Config, 'DATA_DIR', temp_dir / 'data')
        monkeypatch.setattr(Config, 'METADATA_DIR', temp_dir / 'data' / 'metadata')
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir / 'data' / 'papers')

        Config.ensure_directories()

        assert Config.DATA_DIR.exists()
        assert Config.METADATA_DIR.exists()
        assert Config.PAPERS_DIR.exists()

    def test_get_config_dict(self):
        """Test configuration dictionary export."""
        config_dict = Config.get_config_dict()

        assert isinstance(config_dict, dict)
        assert 'request_delay' in config_dict
        assert 'max_retries' in config_dict
        assert 'log_level' in config_dict

    def test_update_from_dict(self):
        """Test updating configuration from dictionary."""
        original_delay = Config.REQUEST_DELAY

        Config.update_from_dict({'request_delay': 15.0})
        assert Config.REQUEST_DELAY == 15.0

        # Restore original
        Config.REQUEST_DELAY = original_delay

    def test_captcha_keywords(self):
        """Test CAPTCHA detection keywords."""
        assert isinstance(Config.CAPTCHA_KEYWORDS, list)
        assert len(Config.CAPTCHA_KEYWORDS) > 0
        assert all(isinstance(kw, str) for kw in Config.CAPTCHA_KEYWORDS)
