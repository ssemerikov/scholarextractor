"""
Tests for HTTP client module.
"""

import pytest
import responses
import time
from unittest.mock import Mock, patch
from src.client import RateLimitedSession, CaptchaDetectedException
from src.config import Config


class TestRateLimitedSession:
    """Test RateLimitedSession class."""

    def test_initialization(self):
        """Test session initialization."""
        session = RateLimitedSession()

        assert session.delay == Config.REQUEST_DELAY
        assert session.timeout == Config.REQUEST_TIMEOUT
        assert session.last_request_time == 0
        assert session.request_count == 0

    def test_custom_delay_and_timeout(self):
        """Test custom delay and timeout."""
        session = RateLimitedSession(delay=5.0, timeout=20)

        assert session.delay == 5.0
        assert session.timeout == 20

    def test_get_user_agent(self):
        """Test user agent retrieval."""
        session = RateLimitedSession()

        ua1 = session._get_user_agent()
        assert isinstance(ua1, str)
        assert len(ua1) > 0

        # After 5 requests, should use custom UA
        session.request_count = 5
        ua2 = session._get_user_agent()
        assert ua2 == Config.CUSTOM_USER_AGENT

    def test_enforce_rate_limit(self):
        """Test rate limiting enforcement."""
        session = RateLimitedSession(delay=0.1)  # Short delay for testing

        # First request should not wait
        start = time.time()
        session._enforce_rate_limit()
        elapsed = time.time() - start
        assert elapsed < 0.05

        # Second request should wait
        session.last_request_time = time.time()
        start = time.time()
        session._enforce_rate_limit()
        elapsed = time.time() - start
        assert elapsed >= 0.1

    @responses.activate
    def test_get_success(self):
        """Test successful GET request."""
        session = RateLimitedSession(delay=0)  # No delay for testing

        # Mock response
        responses.add(
            responses.GET,
            'https://example.com/test',
            body='<html>Success</html>',
            status=200
        )

        response = session.get('https://example.com/test')

        assert response.status_code == 200
        assert 'Success' in response.text
        assert session.request_count == 1

    @responses.activate
    def test_get_with_custom_headers(self):
        """Test GET request with custom headers."""
        session = RateLimitedSession(delay=0)

        responses.add(
            responses.GET,
            'https://example.com/test',
            body='Success',
            status=200
        )

        custom_headers = {'X-Custom': 'value'}
        response = session.get('https://example.com/test', headers=custom_headers)

        assert response.status_code == 200

    def test_check_captcha_detection(self):
        """Test CAPTCHA detection."""
        session = RateLimitedSession()

        # Mock response with CAPTCHA keyword
        mock_response = Mock()
        mock_response.text = "unusual traffic detected, please verify you're not a robot"
        mock_response.status_code = 200

        assert session._check_captcha(mock_response) is True

        # Mock response without CAPTCHA
        mock_response.text = "Normal content here"
        assert session._check_captcha(mock_response) is False

        # Mock response with 429 status
        mock_response.text = "Normal content"
        mock_response.status_code = 429
        assert session._check_captcha(mock_response) is True

    @responses.activate
    def test_get_raises_captcha_exception(self):
        """Test that CAPTCHA detection raises exception."""
        session = RateLimitedSession(delay=0)

        # Mock response with CAPTCHA
        responses.add(
            responses.GET,
            'https://example.com/test',
            body='unusual traffic from your computer',
            status=200
        )

        with pytest.raises(CaptchaDetectedException):
            session.get('https://example.com/test')

    @responses.activate
    def test_download_file_success(self, temp_dir, mock_pdf_content):
        """Test successful file download."""
        session = RateLimitedSession(delay=0)

        # Mock file download
        responses.add(
            responses.GET,
            'https://example.com/file.pdf',
            body=mock_pdf_content,
            status=200,
            headers={'content-length': str(len(mock_pdf_content))}
        )

        filepath = temp_dir / 'test.pdf'
        result = session.download_file('https://example.com/file.pdf', str(filepath))

        assert result is True
        assert filepath.exists()
        assert filepath.read_bytes() == mock_pdf_content

    @responses.activate
    def test_download_file_too_large(self, temp_dir):
        """Test download rejection for large files."""
        session = RateLimitedSession(delay=0)

        # Mock large file
        large_size = (Config.PDF_MAX_SIZE_MB + 1) * 1024 * 1024
        responses.add(
            responses.GET,
            'https://example.com/huge.pdf',
            body=b'content',
            status=200,
            headers={'content-length': str(large_size)}
        )

        filepath = temp_dir / 'huge.pdf'
        result = session.download_file('https://example.com/huge.pdf', str(filepath))

        assert result is False
        assert not filepath.exists()

    @responses.activate
    def test_download_file_failure(self, temp_dir):
        """Test download failure handling."""
        session = RateLimitedSession(delay=0)

        # Mock failed download
        responses.add(
            responses.GET,
            'https://example.com/missing.pdf',
            status=404
        )

        filepath = temp_dir / 'missing.pdf'
        result = session.download_file('https://example.com/missing.pdf', str(filepath))

        assert result is False

    def test_context_manager(self):
        """Test session as context manager."""
        with RateLimitedSession() as session:
            assert session is not None
            assert session.session is not None

        # Session should be closed after exiting context

    def test_close(self):
        """Test closing session."""
        session = RateLimitedSession()
        session.close()

        # Should not raise exception
