"""
Storage module for saving and loading metadata, state, and papers.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd

from .config import Config


logger = logging.getLogger(__name__)


class PaperMetadata:
    """Represents metadata for a single paper."""

    def __init__(self, **kwargs):
        """Initialize paper metadata from keyword arguments."""
        self.id = kwargs.get('id', '')
        self.title = kwargs.get('title', '')
        self.authors = kwargs.get('authors', [])
        self.year = kwargs.get('year', None)
        self.venue = kwargs.get('venue', '')
        self.abstract = kwargs.get('abstract', '')
        self.citations = kwargs.get('citations', 0)
        self.url = kwargs.get('url', '')
        self.doi = kwargs.get('doi', '')
        self.bibtex = kwargs.get('bibtex', '')
        self.pdf_url = kwargs.get('pdf_url', '')
        self.pdf_downloaded = kwargs.get('pdf_downloaded', False)
        self.pdf_path = kwargs.get('pdf_path', '')
        self.extracted_at = kwargs.get('extracted_at', datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'authors': self.authors,
            'year': self.year,
            'venue': self.venue,
            'abstract': self.abstract,
            'citations': self.citations,
            'url': self.url,
            'doi': self.doi,
            'bibtex': self.bibtex,
            'pdf_url': self.pdf_url,
            'pdf_downloaded': self.pdf_downloaded,
            'pdf_path': self.pdf_path,
            'extracted_at': self.extracted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperMetadata':
        """Create from dictionary."""
        return cls(**data)

    def __repr__(self):
        """String representation."""
        return f"PaperMetadata(title='{self.title[:50]}...', year={self.year})"


class Storage:
    """Handles all storage operations for Scholar Extractor."""

    def __init__(self):
        """Initialize storage manager."""
        Config.ensure_directories()
        self.papers: List[PaperMetadata] = []
        self.state: Dict[str, Any] = {}
        self.query_info: Dict[str, Any] = {}

    def add_paper(self, paper: PaperMetadata):
        """
        Add a paper to the collection.

        Args:
            paper: PaperMetadata instance
        """
        self.papers.append(paper)
        logger.debug(f"Added paper: {paper.title}")

    def save_metadata_json(self, filepath: Optional[Path] = None) -> bool:
        """
        Save all metadata to JSON file.

        Args:
            filepath: Optional custom filepath (default: Config.METADATA_JSON)

        Returns:
            True if successful, False otherwise
        """
        filepath = filepath or Config.METADATA_JSON

        try:
            data = {
                'papers': [paper.to_dict() for paper in self.papers],
                'query': self.query_info,
                'total_papers': len(self.papers),
                'saved_at': datetime.utcnow().isoformat(),
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.papers)} papers to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save metadata JSON: {e}")
            return False

    def save_metadata_csv(self, filepath: Optional[Path] = None) -> bool:
        """
        Save metadata to CSV file.

        Args:
            filepath: Optional custom filepath (default: Config.METADATA_CSV)

        Returns:
            True if successful, False otherwise
        """
        filepath = filepath or Config.METADATA_CSV

        try:
            if not self.papers:
                logger.warning("No papers to save")
                return False

            # Convert to DataFrame
            df = pd.DataFrame([paper.to_dict() for paper in self.papers])

            # Convert list columns to strings for CSV
            if 'authors' in df.columns:
                df['authors'] = df['authors'].apply(lambda x: '; '.join(x) if isinstance(x, list) else x)

            df.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"Saved {len(self.papers)} papers to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save metadata CSV: {e}")
            return False

    def load_metadata_json(self, filepath: Optional[Path] = None) -> bool:
        """
        Load metadata from JSON file.

        Args:
            filepath: Optional custom filepath (default: Config.METADATA_JSON)

        Returns:
            True if successful, False otherwise
        """
        filepath = filepath or Config.METADATA_JSON

        try:
            if not filepath.exists():
                logger.info(f"Metadata file not found: {filepath}")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.papers = [PaperMetadata.from_dict(p) for p in data.get('papers', [])]
            self.query_info = data.get('query', {})

            logger.info(f"Loaded {len(self.papers)} papers from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to load metadata JSON: {e}")
            return False

    def save_state(self, filepath: Optional[Path] = None) -> bool:
        """
        Save current state for resumability.

        Args:
            filepath: Optional custom filepath (default: Config.STATE_FILE)

        Returns:
            True if successful, False otherwise
        """
        filepath = filepath or Config.STATE_FILE

        try:
            state = {
                'papers_processed': len(self.papers),
                'last_paper_id': self.papers[-1].id if self.papers else None,
                'query': self.query_info,
                'timestamp': datetime.utcnow().isoformat(),
                'custom_state': self.state,
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)

            logger.debug(f"Saved state to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    def load_state(self, filepath: Optional[Path] = None) -> bool:
        """
        Load state for resuming.

        Args:
            filepath: Optional custom filepath (default: Config.STATE_FILE)

        Returns:
            True if successful, False otherwise
        """
        filepath = filepath or Config.STATE_FILE

        try:
            if not filepath.exists():
                logger.info("No previous state found")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                self.state = json.load(f)

            logger.info(f"Loaded state from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False

    def set_query_info(self, url: str, description: str = ""):
        """
        Set query information.

        Args:
            url: Query URL
            description: Optional query description
        """
        self.query_info = {
            'url': url,
            'description': description,
            'executed_at': datetime.utcnow().isoformat(),
        }

    def get_paper_by_id(self, paper_id: str) -> Optional[PaperMetadata]:
        """
        Get paper by ID.

        Args:
            paper_id: Paper identifier

        Returns:
            PaperMetadata if found, None otherwise
        """
        for paper in self.papers:
            if paper.id == paper_id:
                return paper
        return None

    def get_papers_without_pdf(self) -> List[PaperMetadata]:
        """Get all papers that don't have PDFs downloaded."""
        return [p for p in self.papers if not p.pdf_downloaded and p.pdf_url]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        total = len(self.papers)
        with_pdf = sum(1 for p in self.papers if p.pdf_downloaded)
        with_abstract = sum(1 for p in self.papers if p.abstract)
        with_doi = sum(1 for p in self.papers if p.doi)

        return {
            'total_papers': total,
            'papers_with_pdf': with_pdf,
            'papers_with_abstract': with_abstract,
            'papers_with_doi': with_doi,
            'pdf_success_rate': (with_pdf / total * 100) if total > 0 else 0,
        }

    def __len__(self):
        """Return number of papers."""
        return len(self.papers)
