"""
Search module for orchestrating Google Scholar searches.
"""

import logging
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from tqdm import tqdm

from .config import Config
from .client import RateLimitedSession, CaptchaDetectedException
from .metadata import MetadataExtractor
from .storage import Storage, PaperMetadata


logger = logging.getLogger(__name__)


class ScholarSearcher:
    """Manages Google Scholar search operations."""

    def __init__(self, storage: Storage, max_papers: int = None):
        """
        Initialize searcher.

        Args:
            storage: Storage instance for saving results
            max_papers: Maximum number of papers to extract (None for unlimited)
        """
        self.storage = storage
        self.max_papers = max_papers or float('inf')
        self.session = RateLimitedSession()
        self.extractor = MetadataExtractor()

    def search(self, query_url: str, resume: bool = False) -> List[PaperMetadata]:
        """
        Execute search and extract metadata from all results.

        Args:
            query_url: Google Scholar search URL
            resume: Whether to resume from previous state

        Returns:
            List of extracted papers
        """
        logger.info(f"Starting search with URL: {query_url}")
        self.storage.set_query_info(query_url, "Google Scholar search")

        # Handle resume
        start_paper_count = 0
        if resume:
            logger.info("Resume mode enabled")
            if self.storage.load_state():
                start_paper_count = len(self.storage.papers)
                logger.info(f"Resuming from {start_paper_count} papers")

        papers_extracted = []
        current_url = query_url
        page_num = 1
        total_papers = start_paper_count

        try:
            with tqdm(total=self.max_papers if self.max_papers != float('inf') else None,
                     desc="Extracting papers",
                     initial=start_paper_count,
                     unit="paper") as pbar:

                while current_url and total_papers < self.max_papers:
                    logger.info(f"Fetching page {page_num}: {current_url}")

                    try:
                        # Fetch page
                        response = self.session.get(current_url)
                        html = response.text

                        # Extract papers from page
                        page_papers = self.extractor.extract_from_search_page(html)
                        logger.info(f"Extracted {len(page_papers)} papers from page {page_num}")

                        # Add papers to storage
                        for paper in page_papers:
                            if total_papers >= self.max_papers:
                                break

                            # Check if already extracted (for resume)
                            if not self.storage.get_paper_by_id(paper.id):
                                self.storage.add_paper(paper)
                                papers_extracted.append(paper)
                                total_papers += 1
                                pbar.update(1)

                        # Save state periodically
                        if page_num % 2 == 0:
                            self.storage.save_state()
                            self.storage.save_metadata_json()

                        # Check for next page
                        if total_papers < self.max_papers:
                            next_url = self.extractor.check_next_page(html)
                            if next_url:
                                current_url = next_url
                                page_num += 1
                                logger.info(f"Found next page: {next_url}")
                            else:
                                logger.info("No more pages found")
                                break
                        else:
                            break

                        # Safety check: don't exceed max pages
                        if page_num > Config.MAX_PAGES:
                            logger.warning(f"Reached maximum pages ({Config.MAX_PAGES})")
                            break

                    except CaptchaDetectedException as e:
                        logger.error(f"CAPTCHA detected: {e}")
                        logger.error("Search stopped. Please wait and try again later.")
                        break

                    except Exception as e:
                        logger.error(f"Error on page {page_num}: {e}")
                        # Continue to next page on error
                        continue

        except KeyboardInterrupt:
            logger.warning("Search interrupted by user")

        finally:
            # Always save final state
            self.storage.save_state()
            self.storage.save_metadata_json()
            self.storage.save_metadata_csv()
            self.session.close()

        logger.info(f"Search completed. Total papers extracted: {total_papers}")
        return papers_extracted

    def search_by_params(self, keywords: List[str], year_start: int = None,
                        year_end: int = None, **kwargs) -> List[PaperMetadata]:
        """
        Build search URL from parameters and execute search.

        Args:
            keywords: List of search keywords
            year_start: Start year filter
            year_end: End year filter
            **kwargs: Additional search parameters

        Returns:
            List of extracted papers
        """
        url = self._build_search_url(keywords, year_start, year_end, **kwargs)
        return self.search(url)

    def _build_search_url(self, keywords: List[str], year_start: int = None,
                         year_end: int = None, **kwargs) -> str:
        """
        Build Google Scholar search URL from parameters.

        Args:
            keywords: List of search keywords
            year_start: Start year filter
            year_end: End year filter
            **kwargs: Additional parameters (hl, as_sdt, as_vis, etc.)

        Returns:
            Complete search URL
        """
        base_url = f"{Config.SCHOLAR_BASE_URL}/scholar"
        query = ' '.join(keywords)

        params = {
            'q': query,
            'hl': kwargs.get('hl', 'en'),
            'as_sdt': kwargs.get('as_sdt', '0,5'),
        }

        if year_start:
            params['as_ylo'] = year_start
        if year_end:
            params['as_yhi'] = year_end

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in ['hl', 'as_sdt'] and value is not None:
                params[key] = value

        # Build URL
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{base_url}?{param_str}"

        logger.debug(f"Built search URL: {url}")
        return url

    def get_statistics(self) -> dict:
        """Get search statistics."""
        return {
            'papers_extracted': len(self.storage.papers),
            'request_count': self.session.request_count,
            **self.storage.get_statistics()
        }

    def close(self):
        """Clean up resources."""
        self.session.close()
