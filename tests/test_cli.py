"""
Tests for CLI interface using Click testing utilities.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from src.cli import cli, extract, download, status, export
from src.storage import Storage, PaperMetadata
from src.config import Config


class TestCLIBasics:
    """Test basic CLI functionality with Click testing."""

    def test_cli_help(self):
        """Test main CLI help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert 'Scholar Extractor' in result.output or 'extract' in result.output
        assert 'download' in result.output
        assert 'status' in result.output
        assert 'export' in result.output

    def test_cli_version(self):
        """Test version display."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])

        assert result.exit_code == 0
        assert '0.1.0' in result.output

    def test_extract_help(self):
        """Test extract command help."""
        runner = CliRunner()
        result = runner.invoke(extract, ['--help'])

        assert result.exit_code == 0
        assert '--url' in result.output
        assert '--max-papers' in result.output
        assert '--delay' in result.output
        assert '--download-pdfs' in result.output
        assert '--resume' in result.output
        assert '--verbose' in result.output

    def test_download_help(self):
        """Test download command help."""
        runner = CliRunner()
        result = runner.invoke(download, ['--help'])

        assert result.exit_code == 0
        assert '--verbose' in result.output or 'verbose' in result.output

    def test_status_help(self):
        """Test status command help."""
        runner = CliRunner()
        result = runner.invoke(status, ['--help'])

        assert result.exit_code == 0

    def test_export_help(self):
        """Test export command help."""
        runner = CliRunner()
        result = runner.invoke(export, ['--help'])

        assert result.exit_code == 0
        assert '--format' in result.output
        assert 'json' in result.output.lower()
        assert 'csv' in result.output.lower()


class TestExtractCommand:
    """Test extract command with mocked components."""

    def test_extract_requires_url(self):
        """Test that extract command requires --url argument."""
        runner = CliRunner()
        result = runner.invoke(extract, [])

        assert result.exit_code != 0
        assert 'url' in result.output.lower() or 'required' in result.output.lower()

    @patch('src.cli.PDFDownloader')
    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_extract_with_minimal_args(self, mock_storage, mock_searcher, mock_downloader):
        """Test extract with just URL (minimal arguments)."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage_instance.papers = []
        mock_storage.return_value = mock_storage_instance

        mock_searcher_instance = Mock()
        mock_searcher_instance.search.return_value = []
        mock_searcher_instance.get_statistics.return_value = {
            'papers_extracted': 0,
            'request_count': 1,
            'total_papers': 0,
            'papers_with_pdf': 0,
            'papers_with_abstract': 0,
            'papers_with_doi': 0,
            'pdf_success_rate': 0
        }
        mock_searcher.return_value = mock_searcher_instance

        with runner.isolated_filesystem():
            result = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test'
            ])

            # Should complete successfully
            assert result.exit_code == 0
            # Should call search
            mock_searcher_instance.search.assert_called_once()
            # Should close searcher
            mock_searcher_instance.close.assert_called_once()

    @patch('src.cli.PDFDownloader')
    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_extract_with_all_options(self, mock_storage, mock_searcher, mock_downloader):
        """Test extract with all command-line options."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        mock_searcher_instance = Mock()
        mock_searcher_instance.search.return_value = [Mock()]
        mock_searcher_instance.get_statistics.return_value = {
            'papers_extracted': 1,
            'request_count': 5,
            'total_papers': 1,
            'papers_with_pdf': 0,
            'papers_with_abstract': 1,
            'papers_with_doi': 0,
            'pdf_success_rate': 0
        }
        mock_searcher.return_value = mock_searcher_instance

        mock_downloader_instance = Mock()
        mock_downloader_instance.download_all.return_value = {
            'downloaded': 1,
            'failed': 0,
            'skipped': 0,
            'total': 1
        }
        mock_downloader.return_value = mock_downloader_instance

        with runner.isolated_filesystem():
            result = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test',
                '--max-papers', '50',
                '--delay', '5.0',
                '--download-pdfs',
                '--resume',
                '--verbose'
            ])

            # Should complete successfully
            assert result.exit_code == 0

            # Verify searcher was called with correct parameters
            mock_searcher_instance.search.assert_called_once()

            # Verify downloader was called (because of --download-pdfs)
            mock_downloader_instance.download_all.assert_called_once()

    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_extract_workflow_no_pdfs(self, mock_storage, mock_searcher):
        """Test extract workflow without PDF download."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        mock_searcher_instance = Mock()
        mock_papers = [Mock(title='Test Paper', year=2020)]
        mock_searcher_instance.search.return_value = mock_papers
        mock_searcher_instance.get_statistics.return_value = {
            'papers_extracted': 1,
            'request_count': 3,
            'total_papers': 1,
            'papers_with_pdf': 0,
            'papers_with_abstract': 0,
            'papers_with_doi': 0,
            'pdf_success_rate': 0
        }
        mock_searcher.return_value = mock_searcher_instance

        with runner.isolated_filesystem():
            result = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test',
                '--max-papers', '10'
            ])

            assert result.exit_code == 0
            assert 'Extraction completed' in result.output or 'Done' in result.output

            # Verify workflow
            mock_searcher_instance.search.assert_called_once()
            mock_searcher_instance.close.assert_called_once()

    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_extract_handles_keyboard_interrupt(self, mock_storage, mock_searcher):
        """Test graceful handling of keyboard interrupt."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        mock_searcher_instance = Mock()
        mock_searcher_instance.search.side_effect = KeyboardInterrupt()
        mock_searcher.return_value = mock_searcher_instance

        with runner.isolated_filesystem():
            result = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test'
            ])

            assert result.exit_code != 0
            assert 'Interrupted' in result.output or 'interrupted' in result.output.lower()

    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_extract_handles_errors(self, mock_storage, mock_searcher):
        """Test error handling in extract command."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        mock_searcher_instance = Mock()
        mock_searcher_instance.search.side_effect = Exception("Test error")
        mock_searcher.return_value = mock_searcher_instance

        with runner.isolated_filesystem():
            result = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test'
            ])

            assert result.exit_code != 0
            assert 'Error' in result.output or 'error' in result.output.lower()


class TestDownloadCommand:
    """Test download command with mocked components."""

    @patch('src.cli.Storage')
    def test_download_no_metadata(self, mock_storage):
        """Test download command when no metadata exists."""
        runner = CliRunner()

        # Configure mock to fail loading metadata
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = False
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(download)

            assert result.exit_code != 0
            assert 'No metadata found' in result.output or 'extract' in result.output.lower()

    @patch('src.cli.PDFDownloader')
    @patch('src.cli.Storage')
    def test_download_with_metadata(self, mock_storage, mock_downloader):
        """Test download command with existing metadata."""
        runner = CliRunner()

        # Configure mocks
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.get_papers_without_pdf.return_value = [Mock()]
        mock_storage.return_value = mock_storage_instance

        mock_downloader_instance = Mock()
        mock_downloader_instance.download_all.return_value = {
            'downloaded': 1,
            'failed': 0,
            'skipped': 0,
            'total': 1
        }
        mock_downloader.return_value = mock_downloader_instance

        with runner.isolated_filesystem():
            result = runner.invoke(download)

            assert result.exit_code == 0
            mock_downloader_instance.download_all.assert_called_once()

    @patch('src.cli.Storage')
    def test_download_no_papers_to_download(self, mock_storage):
        """Test download when all papers already have PDFs."""
        runner = CliRunner()

        # Configure mock - has papers but all have PDFs
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.get_papers_without_pdf.return_value = []
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(download)

            # Should complete successfully but indicate nothing to download
            assert result.exit_code == 0 or 'No papers to download' in result.output


class TestStatusCommand:
    """Test status command with mocked storage."""

    @patch('src.cli.Storage')
    def test_status_no_data(self, mock_storage):
        """Test status command with no extracted data."""
        runner = CliRunner()

        # Configure mock to fail loading
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = False
        mock_storage.return_value = mock_storage_instance

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert 'No data found' in result.output or 'extract' in result.output.lower()

    @patch('src.cli.Storage')
    def test_status_with_data(self, mock_storage):
        """Test status command with extracted data."""
        runner = CliRunner()

        # Configure mock with data
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock(), Mock()]
        mock_storage_instance.get_statistics.return_value = {
            'total_papers': 2,
            'papers_with_pdf': 1,
            'papers_with_abstract': 2,
            'papers_with_doi': 1,
            'pdf_success_rate': 50.0
        }
        mock_storage_instance.query_info = {
            'url': 'https://example.com',
            'executed_at': '2025-11-16T20:00:00Z'
        }
        mock_storage.return_value = mock_storage_instance

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert 'Status' in result.output or 'statistics' in result.output.lower()
        # Should show statistics
        assert '2' in result.output  # total papers


class TestExportCommand:
    """Test export command with mocked storage."""

    @patch('src.cli.Storage')
    def test_export_no_metadata(self, mock_storage):
        """Test export with no metadata."""
        runner = CliRunner()

        # Configure mock to fail loading
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = False
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(export, ['--format', 'json'])

            assert result.exit_code != 0
            assert 'No metadata found' in result.output or 'extract' in result.output.lower()

    @patch('src.cli.Storage')
    def test_export_json(self, mock_storage):
        """Test exporting to JSON format."""
        runner = CliRunner()

        # Configure mock with data
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.save_metadata_json.return_value = True
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(export, ['--format', 'json'])

            assert result.exit_code == 0
            assert 'JSON' in result.output or 'json' in result.output
            mock_storage_instance.save_metadata_json.assert_called_once()

    @patch('src.cli.Storage')
    def test_export_csv(self, mock_storage):
        """Test exporting to CSV format."""
        runner = CliRunner()

        # Configure mock with data
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.save_metadata_csv.return_value = True
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(export, ['--format', 'csv'])

            assert result.exit_code == 0
            assert 'CSV' in result.output or 'csv' in result.output
            mock_storage_instance.save_metadata_csv.assert_called_once()

    @patch('src.cli.Storage')
    def test_export_both(self, mock_storage):
        """Test exporting to both JSON and CSV."""
        runner = CliRunner()

        # Configure mock with data
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.save_metadata_json.return_value = True
        mock_storage_instance.save_metadata_csv.return_value = True
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(export, ['--format', 'both'])

            assert result.exit_code == 0
            mock_storage_instance.save_metadata_json.assert_called_once()
            mock_storage_instance.save_metadata_csv.assert_called_once()

    @patch('src.cli.Storage')
    def test_export_with_custom_output(self, mock_storage):
        """Test export with custom output path."""
        runner = CliRunner()

        # Configure mock
        mock_storage_instance = Mock()
        mock_storage_instance.load_metadata_json.return_value = True
        mock_storage_instance.papers = [Mock()]
        mock_storage_instance.save_metadata_json.return_value = True
        mock_storage.return_value = mock_storage_instance

        with runner.isolated_filesystem():
            result = runner.invoke(export, [
                '--format', 'json',
                '--output', 'custom_output.json'
            ])

            assert result.exit_code == 0
            # Custom path should be passed to save function
            # (exact verification depends on implementation)


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    @patch('src.cli.PDFDownloader')
    @patch('src.cli.ScholarSearcher')
    @patch('src.cli.Storage')
    def test_full_workflow_extract_then_status(self, mock_storage, mock_searcher, mock_downloader):
        """Test complete workflow: extract, then status."""
        runner = CliRunner()

        # Configure mocks for extract
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        mock_paper = Mock()
        mock_paper.title = 'Test Paper'
        mock_paper.year = 2020

        mock_searcher_instance = Mock()
        mock_searcher_instance.search.return_value = [mock_paper]
        mock_searcher_instance.get_statistics.return_value = {
            'papers_extracted': 1,
            'request_count': 3,
            'total_papers': 1,
            'papers_with_pdf': 0,
            'papers_with_abstract': 0,
            'papers_with_doi': 0,
            'pdf_success_rate': 0
        }
        mock_searcher.return_value = mock_searcher_instance

        with runner.isolated_filesystem():
            # First: extract
            result1 = runner.invoke(extract, [
                '--url', 'https://scholar.google.com/scholar?q=test',
                '--max-papers', '5'
            ])

            assert result1.exit_code == 0

            # Configure mock for status (showing data exists)
            mock_storage_instance.load_metadata_json.return_value = True
            mock_storage_instance.papers = [mock_paper]
            mock_storage_instance.get_statistics.return_value = {
                'total_papers': 1,
                'papers_with_pdf': 0,
                'papers_with_abstract': 0,
                'papers_with_doi': 0,
                'pdf_success_rate': 0
            }
            mock_storage_instance.query_info = {'url': 'https://example.com'}

            # Second: status
            result2 = runner.invoke(status)

            assert result2.exit_code == 0
