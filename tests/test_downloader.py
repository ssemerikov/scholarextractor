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
