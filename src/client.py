"""
HTTP client module with rate limiting, retry logic, and anti-bot detection.
"""

import time
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .config import Config


logger = logging.getLogger(__name__)


class RateLimitedSession:
    """HTTP session with rate limiting and anti-bot measures."""

    def __init__(self, delay: float = None, timeout: int = None):
        """
        Initialize rate-limited session.

        Args:
            delay: Seconds to wait between requests (default from config)
            timeout: Request timeout in seconds (default from config)
        """
        self.delay = delay or Config.REQUEST_DELAY
        self.timeout = timeout or Config.REQUEST_TIMEOUT
        self.last_request_time = 0
        self.session = self._create_session()
        self.request_count = 0
        self.user_agent_index = 0

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=Config.MAX_RETRIES,
            backoff_factor=Config.RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_user_agent(self) -> str:
        """Get user agent, rotating through available options."""
        # Use custom user agent occasionally
        if self.request_count % 5 == 0:
            return Config.CUSTOM_USER_AGENT

        # Rotate through standard user agents
        ua = Config.USER_AGENTS[self.user_agent_index]
        self.user_agent_index = (self.user_agent_index + 1) % len(Config.USER_AGENTS)
        return ua

    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed
            # Add small random jitter to appear more human-like
            jitter = random.uniform(0, 0.5)
            total_sleep = sleep_time + jitter
            logger.debug(f"Rate limiting: sleeping for {total_sleep:.2f}s")
            time.sleep(total_sleep)

        self.last_request_time = time.time()

    def _check_captcha(self, response: requests.Response) -> bool:
        """
        Check if response indicates CAPTCHA or bot detection.

        Args:
            response: HTTP response object

        Returns:
            True if CAPTCHA detected, False otherwise
        """
        content = response.text.lower()
        for keyword in Config.CAPTCHA_KEYWORDS:
            if keyword in content:
                logger.warning(f"CAPTCHA/bot detection keyword found: '{keyword}'")
                return True

        # Check for CAPTCHA-related status codes
        if response.status_code == 429:
            logger.warning("Rate limit exceeded (HTTP 429)")
            return True

        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True
    )
    def get(self, url: str, headers: Optional[Dict[str, str]] = None,
            **kwargs) -> requests.Response:
        """
        Perform GET request with rate limiting.

        Args:
            url: URL to fetch
            headers: Optional custom headers
            **kwargs: Additional arguments for requests.get()

        Returns:
            Response object

        Raises:
            CaptchaDetectedException: If CAPTCHA is detected
            requests.RequestException: On request failure
        """
        self._enforce_rate_limit()

        # Prepare headers
        request_headers = {
            'User-Agent': self._get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        if headers:
            request_headers.update(headers)

        # Perform request
        logger.debug(f"GET {url}")
        response = self.session.get(
            url,
            headers=request_headers,
            timeout=self.timeout,
            **kwargs
        )

        self.request_count += 1

        # Check for CAPTCHA
        if self._check_captcha(response):
            raise CaptchaDetectedException(
                f"CAPTCHA detected when accessing {url}. "
                "Please wait and try again later, or solve CAPTCHA manually."
            )

        response.raise_for_status()
        logger.debug(f"Response: {response.status_code}, Size: {len(response.content)} bytes")

        return response

    def download_file(self, url: str, filepath: str,
                     chunk_size: int = 8192) -> bool:
        """
        Download file with progress tracking.

        Args:
            url: URL of file to download
            filepath: Local path to save file
            chunk_size: Size of chunks to download

        Returns:
            True if successful, False otherwise
        """
        try:
            self._enforce_rate_limit()

            headers = {'User-Agent': self._get_user_agent()}

            logger.info(f"Downloading {url}")
            response = self.session.get(
                url,
                headers=headers,
                timeout=Config.PDF_DOWNLOAD_TIMEOUT,
                stream=True
            )

            response.raise_for_status()

            # Check file size
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > Config.PDF_MAX_SIZE_MB:
                    logger.warning(f"File too large: {size_mb:.2f}MB (max: {Config.PDF_MAX_SIZE_MB}MB)")
                    return False

            # Download file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

            logger.info(f"Downloaded to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return False

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class CaptchaDetectedException(Exception):
    """Exception raised when CAPTCHA is detected."""
    pass


class NetworkException(Exception):
    """Exception raised for network-related errors."""
    pass
