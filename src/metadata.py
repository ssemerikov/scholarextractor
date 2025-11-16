"""
Metadata extraction module for parsing Google Scholar results.
"""

import re
import logging
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .config import Config
from .storage import PaperMetadata


logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extracts metadata from Google Scholar search results."""

    def __init__(self):
        """Initialize metadata extractor."""
        self.base_url = Config.SCHOLAR_BASE_URL

    def extract_from_search_page(self, html: str) -> List[PaperMetadata]:
        """
        Extract paper metadata from a Google Scholar search results page.

        Args:
            html: HTML content of search results page

        Returns:
            List of PaperMetadata objects
        """
        soup = BeautifulSoup(html, 'lxml')
        papers = []

        # Find all result items (Google Scholar uses div.gs_r or div.gs_ri)
        result_divs = soup.select('div.gs_ri, div.gs_r')

        logger.info(f"Found {len(result_divs)} potential results on page")

        for div in result_divs:
            try:
                paper = self._extract_paper_from_result(div)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning(f"Error extracting paper: {e}")
                continue

        return papers

    def _extract_paper_from_result(self, result_div) -> Optional[PaperMetadata]:
        """
        Extract metadata from a single search result.

        Args:
            result_div: BeautifulSoup div element containing result

        Returns:
            PaperMetadata object or None if extraction failed
        """
        try:
            # Extract title and URL
            title_elem = result_div.select_one('h3.gs_rt a, h3.gs_rt')
            if not title_elem:
                logger.debug("No title found, skipping")
                return None

            # Get title text (remove citation markers like [PDF], [HTML])
            title = self._clean_title(title_elem.get_text())

            # Get URL if available
            url = ''
            if title_elem.name == 'a':
                url = title_elem.get('href', '')
            else:
                # Title might be in nested <a> tag
                link = title_elem.find('a')
                if link:
                    url = link.get('href', '')

            # Generate unique ID from title
            paper_id = self._generate_id(title)

            # Extract authors, venue, and year from metadata line
            meta_elem = result_div.select_one('div.gs_a')
            authors, venue, year = self._parse_metadata_line(meta_elem.get_text() if meta_elem else '')

            # Extract abstract/snippet
            abstract_elem = result_div.select_one('div.gs_rs')
            abstract = abstract_elem.get_text().strip() if abstract_elem else ''

            # Extract citation count
            citations = self._extract_citation_count(result_div)

            # Extract PDF link
            pdf_url = self._extract_pdf_link(result_div)

            # Extract BibTeX link for later retrieval
            bibtex_url = self._extract_bibtex_link(result_div)

            # Try to extract DOI from URL or content
            doi = self._extract_doi(url, abstract)

            # Create paper metadata
            paper = PaperMetadata(
                id=paper_id,
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                abstract=abstract,
                citations=citations,
                url=url,
                doi=doi,
                pdf_url=pdf_url,
                bibtex='',  # Will be fetched separately if needed
            )

            logger.debug(f"Extracted: {paper.title[:50]}...")
            return paper

        except Exception as e:
            logger.error(f"Error extracting paper from result: {e}")
            return None

    def _clean_title(self, title: str) -> str:
        """
        Clean title by removing markers like [PDF], [HTML], etc.

        Args:
            title: Raw title text

        Returns:
            Cleaned title
        """
        # Remove citation format markers
        title = re.sub(r'\[(?:PDF|HTML|CITATION)\]', '', title)
        # Remove extra whitespace
        title = ' '.join(title.split())
        return title.strip()

    def _generate_id(self, title: str) -> str:
        """
        Generate unique ID from title.

        Args:
            title: Paper title

        Returns:
            Unique identifier
        """
        return hashlib.md5(title.encode('utf-8')).hexdigest()[:12]

    def _parse_metadata_line(self, meta_text: str) -> tuple:
        """
        Parse the metadata line containing authors, venue, and year.
        Format is typically: "Authors - Venue, Year - Publisher"

        Args:
            meta_text: Metadata line text

        Returns:
            Tuple of (authors_list, venue, year)
        """
        authors = []
        venue = ''
        year = None

        try:
            # Split by dashes
            parts = meta_text.split(' - ')

            # First part is usually authors
            if len(parts) > 0:
                authors_text = parts[0].strip()
                # Split by commas or 'and'
                authors = [a.strip() for a in re.split(r',|\sand\s', authors_text) if a.strip()]
                # Remove ellipsis entries
                authors = [a for a in authors if a != '…' and a != '...']

            # Second part usually contains venue and year
            if len(parts) > 1:
                venue_year_text = parts[1].strip()

                # Extract year (4 digits)
                year_match = re.search(r'\b(19|20)\d{2}\b', venue_year_text)
                if year_match:
                    year = int(year_match.group(0))
                    # Remove year from venue text
                    venue = venue_year_text.replace(year_match.group(0), '').strip(' ,')
                else:
                    venue = venue_year_text

        except Exception as e:
            logger.debug(f"Error parsing metadata line: {e}")

        return authors, venue, year

    def _extract_citation_count(self, result_div) -> int:
        """
        Extract citation count from result.

        Args:
            result_div: BeautifulSoup div element

        Returns:
            Citation count (0 if not found)
        """
        try:
            # Look for "Cited by XXX" link
            cited_by = result_div.select_one('a:-soup-contains("Cited by")')
            if cited_by:
                text = cited_by.get_text()
                match = re.search(r'Cited by (\d+)', text)
                if match:
                    return int(match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting citation count: {e}")

        return 0

    def _extract_pdf_link(self, result_div) -> str:
        """
        Extract PDF link from result.

        Args:
            result_div: BeautifulSoup div element

        Returns:
            PDF URL or empty string
        """
        try:
            # Look for PDF links (usually in right column with class gs_or_ggsm)
            pdf_link = result_div.select_one('div.gs_or_ggsm a, div.gs_ggsd a')
            if pdf_link:
                href = pdf_link.get('href', '')
                # Check if it's actually a PDF link
                if href and ('.pdf' in href.lower() or pdf_link.get_text().strip() == '[PDF]'):
                    return href

            # Alternative: look for direct PDF links in the title/main link
            main_link = result_div.select_one('h3.gs_rt a')
            if main_link:
                href = main_link.get('href', '')
                if '.pdf' in href.lower():
                    return href

        except Exception as e:
            logger.debug(f"Error extracting PDF link: {e}")

        return ''

    def _extract_bibtex_link(self, result_div) -> str:
        """
        Extract BibTeX citation link.

        Args:
            result_div: BeautifulSoup div element

        Returns:
            BibTeX URL or empty string
        """
        try:
            # Look for "Cite" link
            cite_link = result_div.select_one('a.gs_or_cit, a:-soup-contains("Cite")')
            if cite_link:
                return urljoin(self.base_url, cite_link.get('href', ''))
        except Exception as e:
            logger.debug(f"Error extracting BibTeX link: {e}")

        return ''

    def _extract_doi(self, url: str, text: str) -> str:
        """
        Extract DOI from URL or text.

        Args:
            url: Paper URL
            text: Abstract or other text

        Returns:
            DOI or empty string
        """
        # DOI pattern: 10.XXXX/...
        doi_pattern = r'10\.\d{4,}/[^\s]+'

        # Try URL first
        if url:
            match = re.search(doi_pattern, url)
            if match:
                return match.group(0)

        # Try text
        if text:
            match = re.search(doi_pattern, text)
            if match:
                return match.group(0)

        return ''

    def fetch_bibtex(self, session, paper: PaperMetadata) -> str:
        """
        Fetch BibTeX citation for a paper.

        Args:
            session: HTTP session
            paper: PaperMetadata object

        Returns:
            BibTeX string or empty string
        """
        # This would require fetching the citation page
        # Not implemented in MVP to reduce complexity
        # Can be added later if needed
        return ''

    def check_next_page(self, html: str) -> Optional[str]:
        """
        Check if there's a next page and return its URL.

        Args:
            html: HTML content of current page

        Returns:
            Next page URL or None
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Look for "Next" button
            next_button = soup.select_one('button#gs_n, a:-soup-contains("Next"), button:-soup-contains("Next")')

            if next_button:
                if next_button.name == 'a':
                    return urljoin(self.base_url, next_button.get('href', ''))
                else:
                    # For buttons, we need to extract the onclick handler or find associated link
                    # Google Scholar uses JavaScript for pagination
                    # Look for the actual link in the navigation area
                    nav_area = soup.select_one('div#gs_n')
                    if nav_area:
                        links = nav_area.find_all('a')
                        if links:
                            # Usually the last link is "Next"
                            last_link = links[-1]
                            return urljoin(self.base_url, last_link.get('href', ''))

        except Exception as e:
            logger.debug(f"Error checking for next page: {e}")

        return None
