"""
PDF downloader module for fetching full-text papers.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any

from tqdm import tqdm

from .config import Config
from .client import RateLimitedSession
from .storage import Storage, PaperMetadata


logger = logging.getLogger(__name__)


class PDFDownloader:
    """Manages PDF download operations."""

    def __init__(self, storage: Storage):
        """
        Initialize PDF downloader.

        Args:
            storage: Storage instance containing paper metadata
        """
        self.storage = storage
        self.session = RateLimitedSession()
        self.download_log: Dict[str, Any] = {}

        # Ensure download directory exists
        Config.ensure_directories()

    def download_all(self, papers: List[PaperMetadata] = None) -> Dict[str, Any]:
        """
        Download PDFs for all papers with available PDF links.

        Args:
            papers: Optional list of papers to download (default: all papers without PDFs)

        Returns:
            Dictionary with download statistics
        """
        if papers is None:
            papers = self.storage.get_papers_without_pdf()

        if not papers:
            logger.info("No papers to download")
            return {'downloaded': 0, 'failed': 0, 'skipped': 0}

        logger.info(f"Starting PDF download for {len(papers)} papers")

        downloaded = 0
        failed = 0
        skipped = 0

        with tqdm(total=len(papers), desc="Downloading PDFs", unit="file") as pbar:
            for paper in papers:
                if not paper.pdf_url:
                    logger.debug(f"No PDF URL for: {paper.title[:50]}")
                    skipped += 1
                    pbar.update(1)
                    continue

                try:
                    success = self.download_paper(paper)
                    if success:
                        downloaded += 1
                    else:
                        failed += 1

                except Exception as e:
                    logger.error(f"Error downloading {paper.title[:50]}: {e}")
                    failed += 1

                pbar.update(1)

                # Save progress periodically
                if (downloaded + failed) % 10 == 0:
                    self._save_download_log()
                    self.storage.save_metadata_json()

        # Final save
        self._save_download_log()
        self.storage.save_metadata_json()
        self.storage.save_metadata_csv()

        stats = {
            'downloaded': downloaded,
            'failed': failed,
            'skipped': skipped,
            'total': len(papers)
        }

        logger.info(f"Download completed: {downloaded} succeeded, {failed} failed, {skipped} skipped")
        return stats

    def download_paper(self, paper: PaperMetadata) -> bool:
        """
        Download PDF for a single paper.

        Args:
            paper: PaperMetadata object

        Returns:
            True if successful, False otherwise
        """
        if not paper.pdf_url:
            logger.debug(f"No PDF URL for: {paper.title}")
            return False

        # Generate filename
        filename = self._generate_filename(paper)
        filepath = Config.PAPERS_DIR / filename

        # Check if already downloaded
        if filepath.exists() and filepath.stat().st_size > 0:
            logger.info(f"PDF already exists: {filename}")
            paper.pdf_downloaded = True
            paper.pdf_path = str(filepath)
            return True

        # Download
        logger.info(f"Downloading: {paper.title[:50]}...")
        success = self.session.download_file(paper.pdf_url, str(filepath))

        if success:
            # Verify it's actually a PDF
            if self._verify_pdf(filepath):
                paper.pdf_downloaded = True
                paper.pdf_path = str(filepath)
                self.download_log[paper.id] = {
                    'status': 'success',
                    'filename': filename,
                    'url': paper.pdf_url
                }
                logger.info(f"Successfully downloaded: {filename}")
                return True
            else:
                logger.warning(f"Downloaded file is not a valid PDF: {filename}")
                # Remove invalid file
                if filepath.exists():
                    filepath.unlink()
                self.download_log[paper.id] = {
                    'status': 'invalid',
                    'error': 'Not a valid PDF',
                    'url': paper.pdf_url
                }
                return False
        else:
            self.download_log[paper.id] = {
                'status': 'failed',
                'error': 'Download failed',
                'url': paper.pdf_url
            }
            return False

    def _generate_filename(self, paper: PaperMetadata, max_length: int = 100) -> str:
        """
        Generate a clean filename for the paper.

        Format: FirstAuthor_Year_ShortTitle.pdf

        Args:
            paper: PaperMetadata object
            max_length: Maximum filename length

        Returns:
            Sanitized filename
        """
        # Get first author's last name
        author = "Unknown"
        if paper.authors:
            first_author = paper.authors[0]
            # Try to extract last name (usually last word)
            parts = first_author.split()
            if parts:
                author = parts[-1]

        # Get year
        year = paper.year or "Unknown"

        # Get shortened title
        title = paper.title[:50] if paper.title else "Untitled"

        # Combine
        filename = f"{author}_{year}_{title}"

        # Sanitize filename (remove invalid characters)
        filename = self._sanitize_filename(filename)

        # Truncate if too long
        if len(filename) > max_length - 4:  # -4 for .pdf extension
            filename = filename[:max_length - 4]

        # Add .pdf extension if not present
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'

        return filename

    def _sanitize_filename(self, filename: str) -> str:
        """
        Remove invalid characters from filename.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove invalid characters for filesystems
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        filename = re.sub(invalid_chars, '', filename)

        # Replace spaces and multiple underscores
        filename = re.sub(r'\s+', '_', filename)
        filename = re.sub(r'_+', '_', filename)

        # Remove leading/trailing underscores and dots
        filename = filename.strip('._')

        return filename

    def _verify_pdf(self, filepath: Path) -> bool:
        """
        Verify that file is a valid PDF.

        Args:
            filepath: Path to PDF file

        Returns:
            True if valid PDF, False otherwise
        """
        if not Config.VERIFY_PDF:
            return True

        try:
            # Check file size
            if filepath.stat().st_size == 0:
                logger.warning("PDF file is empty")
                return False

            # Check PDF magic bytes (PDF files start with %PDF)
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if not header.startswith(b'%PDF'):
                    logger.warning("File does not have PDF magic bytes")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error verifying PDF: {e}")
            return False

    def _save_download_log(self):
        """Save download log to file."""
        try:
            import json
            log_file = Config.PAPERS_DIR / "download_log.json"
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.download_log, f, indent=2)
            logger.debug("Download log saved")
        except Exception as e:
            logger.error(f"Failed to save download log: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get download statistics."""
        return {
            'total_downloaded': sum(1 for log in self.download_log.values()
                                   if log.get('status') == 'success'),
            'total_failed': sum(1 for log in self.download_log.values()
                               if log.get('status') == 'failed'),
            'total_invalid': sum(1 for log in self.download_log.values()
                                if log.get('status') == 'invalid'),
        }

    def close(self):
        """Clean up resources."""
        self.session.close()
