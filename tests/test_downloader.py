"""
Tests for PDF downloader module.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from src.downloader import PDFDownloader
from src.storage import Storage, PaperMetadata
from src.config import Config


class TestPDFDownloader:
    """Test PDFDownloader class."""

    def test_initialization(self):
        """Test downloader initialization."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        assert downloader.storage == storage
        assert isinstance(downloader.download_log, dict)

    def test_generate_filename(self, sample_paper_metadata):
        """Test filename generation."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        paper = PaperMetadata(**sample_paper_metadata)
        filename = downloader._generate_filename(paper)

        assert isinstance(filename, str)
        assert filename.endswith('.pdf')
        assert len(filename) <= 104  # 100 + .pdf

        # Check components
        assert 'Doe' in filename  # Last name of first author
        assert '2020' in filename

    def test_generate_filename_no_author(self):
        """Test filename generation without author."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        paper = PaperMetadata(title="Test Paper", year=2020)
        filename = downloader._generate_filename(paper)

        assert 'Unknown' in filename
        assert '2020' in filename

    def test_generate_filename_long_title(self):
        """Test filename generation with very long title."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        long_title = "A" * 200
        paper = PaperMetadata(title=long_title, authors=["John Doe"], year=2020)
        filename = downloader._generate_filename(paper)

        # Should be truncated
        assert len(filename) <= 104

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        # Test invalid characters
        dirty = 'file<name>with:invalid|chars?.pdf'
        clean = downloader._sanitize_filename(dirty)

        assert '<' not in clean
        assert '>' not in clean
        assert ':' not in clean
        assert '|' not in clean
        assert '?' not in clean

        # Test spaces
        dirty = '  file   with   spaces  '
        clean = downloader._sanitize_filename(dirty)
        assert '   ' not in clean
        assert clean.startswith('file')

    def test_verify_pdf_valid(self, temp_dir, mock_pdf_content, monkeypatch):
        """Test PDF verification with valid PDF."""
        monkeypatch.setattr(Config, 'VERIFY_PDF', True)

        storage = Storage()
        downloader = PDFDownloader(storage)

        # Create valid PDF file
        pdf_file = temp_dir / 'valid.pdf'
        pdf_file.write_bytes(mock_pdf_content)

        assert downloader._verify_pdf(pdf_file) is True

    def test_verify_pdf_invalid(self, temp_dir, monkeypatch):
        """Test PDF verification with invalid PDF."""
        monkeypatch.setattr(Config, 'VERIFY_PDF', True)

        storage = Storage()
        downloader = PDFDownloader(storage)

        # Create invalid file (not a PDF)
        invalid_file = temp_dir / 'invalid.pdf'
        invalid_file.write_bytes(b'Not a PDF file')

        assert downloader._verify_pdf(invalid_file) is False

    def test_verify_pdf_empty(self, temp_dir, monkeypatch):
        """Test PDF verification with empty file."""
        monkeypatch.setattr(Config, 'VERIFY_PDF', True)

        storage = Storage()
        downloader = PDFDownloader(storage)

        # Create empty file
        empty_file = temp_dir / 'empty.pdf'
        empty_file.touch()

        assert downloader._verify_pdf(empty_file) is False

    def test_verify_pdf_disabled(self, temp_dir, monkeypatch):
        """Test PDF verification when disabled."""
        monkeypatch.setattr(Config, 'VERIFY_PDF', False)

        storage = Storage()
        downloader = PDFDownloader(storage)

        # Any file should pass when verification is disabled
        file = temp_dir / 'any.pdf'
        file.write_bytes(b'anything')

        assert downloader._verify_pdf(file) is True

    @patch('src.downloader.RateLimitedSession')
    def test_download_paper_success(self, mock_session_class, temp_dir,
                                    mock_pdf_content, sample_paper_metadata, monkeypatch):
        """Test successful paper download."""
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        # Mock session
        mock_session = Mock()
        mock_session.download_file.return_value = True
        mock_session_class.return_value = mock_session

        storage = Storage()
        downloader = PDFDownloader(storage)

        # Create paper
        paper = PaperMetadata(**sample_paper_metadata)
        paper.pdf_url = "https://example.com/paper.pdf"

        # Mock file creation
        def mock_download(url, filepath):
            Path(filepath).write_bytes(mock_pdf_content)
            return True

        downloader.session.download_file = mock_download

        result = downloader.download_paper(paper)

        assert result is True
        assert paper.pdf_downloaded is True
        assert paper.pdf_path != ''

    @patch('src.downloader.RateLimitedSession')
    def test_download_paper_no_url(self, mock_session_class, sample_paper_metadata):
        """Test download attempt without PDF URL."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        paper = PaperMetadata(**sample_paper_metadata)
        paper.pdf_url = ""

        result = downloader.download_paper(paper)

        assert result is False

    @patch('src.downloader.RateLimitedSession')
    def test_download_paper_already_exists(self, mock_session_class, temp_dir,
                                          mock_pdf_content, sample_paper_metadata, monkeypatch):
        """Test download when PDF already exists."""
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        storage = Storage()
        downloader = PDFDownloader(storage)

        paper = PaperMetadata(**sample_paper_metadata)
        paper.pdf_url = "https://example.com/paper.pdf"

        # Pre-create the PDF file
        filename = downloader._generate_filename(paper)
        filepath = temp_dir / filename
        filepath.write_bytes(mock_pdf_content)

        result = downloader.download_paper(paper)

        assert result is True
        assert paper.pdf_downloaded is True

    def test_download_all_no_papers(self):
        """Test download_all with no papers."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        stats = downloader.download_all()

        assert stats['downloaded'] == 0
        assert stats['failed'] == 0
        assert stats['skipped'] == 0

    @patch('src.downloader.RateLimitedSession')
    def test_download_all_with_papers(self, mock_session_class, sample_paper_metadata):
        """Test download_all with multiple papers."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        # Add papers
        paper1 = PaperMetadata(**sample_paper_metadata)
        paper1.id = "paper1"
        paper1.pdf_url = "https://example.com/paper1.pdf"
        storage.add_paper(paper1)

        paper2 = PaperMetadata(**sample_paper_metadata)
        paper2.id = "paper2"
        paper2.pdf_url = ""  # No URL - should be skipped
        storage.add_paper(paper2)

        # Mock download_paper
        with patch.object(downloader, 'download_paper') as mock_download:
            mock_download.return_value = True

            stats = downloader.download_all()

            # Only paper1 should be attempted (paper2 has no URL)
            assert stats['total'] == 1

    def test_get_statistics(self):
        """Test getting download statistics."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        downloader.download_log = {
            'paper1': {'status': 'success'},
            'paper2': {'status': 'failed'},
            'paper3': {'status': 'invalid'},
        }

        stats = downloader.get_statistics()

        assert stats['total_downloaded'] == 1
        assert stats['total_failed'] == 1
        assert stats['total_invalid'] == 1

    def test_close(self):
        """Test closing downloader."""
        storage = Storage()
        downloader = PDFDownloader(storage)

        # Should not raise exception
        downloader.close()

    @patch('src.downloader.RateLimitedSession')
    def test_download_paper_invalid_pdf_detection(self, mock_session_class, temp_dir,
                                                   sample_paper_metadata, monkeypatch):
        """Test download_paper detects and removes invalid PDFs (CRITICAL - data quality).

        Covers lines: downloader.py:144-160
        Value: ⭐⭐⭐⭐⭐ - Critical for ensuring data integrity
        """
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)
        paper.id = "p1"
        paper.title = "Test Paper"
        paper.pdf_url = "https://example.com/fake.pdf"
        storage.add_paper(paper)

        # Mock download that returns HTML instead of PDF (common issue)
        mock_session = Mock()
        def mock_download(url, filepath):
            # Download succeeds but returns HTML, not PDF
            Path(filepath).write_bytes(b"<html>Not a PDF - 404 page</html>")
            return True
        mock_session.download_file = mock_download
        mock_session_class.return_value = mock_session

        downloader = PDFDownloader(storage)
        downloader.session = mock_session

        with patch('src.downloader.logger') as mock_logger:
            result = downloader.download_paper(paper)

            # Should detect invalid PDF and return False
            assert result is False

            # Should log warning about invalid PDF
            assert any('invalid' in str(call).lower() or 'not a valid pdf' in str(call).lower()
                      for call in mock_logger.warning.call_args_list)

            # Invalid file should be removed
            expected_path = temp_dir / downloader._generate_filename(paper)
            assert not expected_path.exists(), "Invalid PDF file should be deleted"

            # Download log should record invalid status
            assert downloader.download_log['p1']['status'] == 'invalid'
            assert 'Not a valid PDF' in downloader.download_log['p1']['error']

    @patch('src.downloader.RateLimitedSession')
    def test_download_all_skips_papers_without_pdf_url(self, mock_session_class, temp_dir,
                                                       monkeypatch):
        """Test download_all skips papers without PDF URL (common scenario).

        Covers lines: downloader.py:64-67
        Value: ⭐⭐⭐⭐ - Common case, important for efficiency
        """
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        storage = Storage()
        # Create papers without PDF URLs
        paper1 = PaperMetadata(id="p1", title="No PDF Available")
        paper2 = PaperMetadata(id="p2", title="Also No PDF", pdf_url="")
        paper3 = PaperMetadata(id="p3", title="Third Paper")

        # Note: get_papers_without_pdf() filters out papers without URLs
        # So we need to pass them explicitly to test the skipping logic
        downloader = PDFDownloader(storage)

        with patch('src.downloader.logger') as mock_logger:
            # Pass papers explicitly to bypass the filtering
            stats = downloader.download_all(papers=[paper1, paper2, paper3])

            # All should be skipped (no PDF URLs)
            assert stats['skipped'] == 3
            assert stats['downloaded'] == 0
            assert stats['failed'] == 0

            # Should log debug messages about missing URLs
            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
            assert any('No PDF URL' in call for call in debug_calls)

    @patch('src.downloader.RateLimitedSession')
    def test_download_all_handles_exceptions(self, mock_session_class, temp_dir,
                                             sample_paper_metadata, monkeypatch):
        """Test download_all handles exceptions during download gracefully.

        Covers lines: downloader.py:74-78
        Value: ⭐⭐⭐⭐ - Important for robustness
        """
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        storage = Storage()
        storage.add_paper(PaperMetadata(
            id="p1",
            title="Paper That Fails",
            pdf_url="https://example.com/will-fail.pdf"
        ))

        # Mock session that raises exception
        mock_session = Mock()
        mock_session.download_file.side_effect = RuntimeError("Network timeout")
        mock_session_class.return_value = mock_session

        downloader = PDFDownloader(storage)
        downloader.session = mock_session

        with patch('src.downloader.logger') as mock_logger:
            stats = downloader.download_all()

            # Should handle exception gracefully
            assert stats['failed'] == 1
            assert stats['downloaded'] == 0

            # Should log the error
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any('Error downloading' in call and 'Network timeout' in call
                      for call in error_calls)

    @patch('src.downloader.RateLimitedSession')
    def test_download_all_periodic_save(self, mock_session_class, temp_dir,
                                       mock_pdf_content, monkeypatch):
        """Test download_all saves progress every 10 downloads.

        Covers lines: downloader.py:84-85
        Value: ⭐⭐⭐ - Important for resumability
        """
        monkeypatch.setattr(Config, 'PAPERS_DIR', temp_dir)

        storage = Storage()
        # Add 15 papers to trigger periodic save at 10
        for i in range(15):
            storage.add_paper(PaperMetadata(
                id=f"p{i}",
                title=f"Paper {i}",
                pdf_url=f"https://example.com/paper{i}.pdf"
            ))

        # Mock successful downloads
        mock_session = Mock()
        def mock_download(url, filepath):
            Path(filepath).write_bytes(mock_pdf_content)
            return True
        mock_session.download_file = mock_download
        mock_session_class.return_value = mock_session

        downloader = PDFDownloader(storage)
        downloader.session = mock_session

        with patch.object(downloader, '_save_download_log') as mock_save:
            with patch.object(storage, 'save_metadata_json') as mock_save_metadata:
                downloader.download_all()

                # Should save at download #10 and at the end (15)
                # So at least 2 saves (could be more depending on implementation)
                assert mock_save.call_count >= 2
                assert mock_save_metadata.call_count >= 2
