#!/usr/bin/env python3
"""
PDF Hunter - Multi-source PDF acquisition system.

This module implements strategies for finding PDFs from multiple legal sources:
1. Unpaywall API - Finds legal open access versions
2. CORE API - Aggregates from repositories worldwide
3. CrossRef API - Metadata and links
"""

import time
import logging
import requests
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote

from .storage import PaperMetadata
from .client import RateLimitedSession

logger = logging.getLogger(__name__)


@dataclass
class PDFSource:
    """Information about a PDF source."""
    url: str
    source_name: str
    is_open_access: bool
    license: Optional[str] = None


class UnpaywallAPI:
    """
    Client for Unpaywall API.

    API: https://unpaywall.org/products/api
    Rate limit: 100,000 requests/day (no key needed with email)
    """

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str = "researcher@example.com"):
        """
        Initialize Unpaywall client.

        Args:
            email: Email for polite API usage (required by Unpaywall)
        """
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'ScholarExtractor/1.0 (mailto:{email})'
        })

    def find_pdf(self, paper: PaperMetadata) -> Optional[PDFSource]:
        """
        Find PDF using Unpaywall API.

        Args:
            paper: Paper metadata

        Returns:
            PDFSource if found, None otherwise
        """
        # Unpaywall requires DOI
        if not paper.doi:
            logger.debug(f"No DOI for paper: {paper.title[:50]}")
            return None

        try:
            url = f"{self.BASE_URL}/{paper.doi}"
            params = {'email': self.email}

            logger.debug(f"Querying Unpaywall for DOI: {paper.doi}")

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Check if paper is open access
                is_oa = data.get('is_oa', False)

                if is_oa:
                    # Get best OA location
                    best_oa = data.get('best_oa_location')
                    if best_oa and best_oa.get('url_for_pdf'):
                        pdf_url = best_oa['url_for_pdf']
                        license = best_oa.get('license')
                        version = best_oa.get('version', 'unknown')

                        logger.info(f"✓ Unpaywall found PDF: {paper.title[:50]}")
                        logger.info(f"  URL: {pdf_url}")
                        logger.info(f"  License: {license}")
                        logger.info(f"  Version: {version}")

                        return PDFSource(
                            url=pdf_url,
                            source_name=f"Unpaywall ({version})",
                            is_open_access=True,
                            license=license
                        )

                logger.debug(f"Paper not open access: {paper.title[:50]}")
                return None

            elif response.status_code == 404:
                logger.debug(f"DOI not found in Unpaywall: {paper.doi}")
                return None

            else:
                logger.warning(f"Unpaywall API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logger.debug(f"Unpaywall request failed: {e}")
            return None

        except Exception as e:
            logger.error(f"Unpaywall unexpected error: {e}")
            return None


class COREAPI:
    """
    Client for CORE API.

    API: https://core.ac.uk/services/api
    Rate limit: Variable (respectful use recommended)
    """

    BASE_URL = "https://core.ac.uk:443/api-v2/articles/search"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CORE API client.

        Args:
            api_key: Optional CORE API key for higher limits
        """
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })

    def find_pdf(self, paper: PaperMetadata) -> Optional[PDFSource]:
        """
        Find PDF using CORE API.

        Args:
            paper: Paper metadata

        Returns:
            PDFSource if found, None otherwise
        """
        try:
            # Search by title
            query = paper.title

            params = {
                'page': 1,
                'pageSize': 5,  # Get top 5 matches
                'metadata': 'true'
            }

            # Add API key to params if available
            if self.api_key:
                params['apiKey'] = self.api_key

            url = f"{self.BASE_URL}/{quote(query)}"

            logger.debug(f"Querying CORE for: {query[:50]}")

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                results = data.get('data', [])

                if results:
                    # Check first result (best match)
                    for result in results:
                        # Verify it's a good match (similar title)
                        result_title = result.get('title', '').lower()
                        query_title = paper.title.lower()

                        # Simple similarity check
                        if len(result_title) > 10 and result_title[:30] in query_title:
                            # Check if download URL exists
                            download_url = result.get('downloadUrl')

                            if download_url:
                                logger.info(f"✓ CORE found PDF: {paper.title[:50]}")
                                logger.info(f"  URL: {download_url}")

                                return PDFSource(
                                    url=download_url,
                                    source_name="CORE (repository)",
                                    is_open_access=True
                                )

                logger.debug(f"CORE found no matching PDFs: {query[:50]}")
                return None

            elif response.status_code == 429:
                logger.warning("CORE API rate limit exceeded")
                return None

            else:
                logger.warning(f"CORE API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logger.debug(f"CORE request failed: {e}")
            return None

        except Exception as e:
            logger.error(f"CORE unexpected error: {e}")
            return None


class CrossRefAPI:
    """
    Client for CrossRef API.

    API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
    Rate limit: Polite pool with email
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: str = "researcher@example.com"):
        """
        Initialize CrossRef client.

        Args:
            email: Email for polite pool
        """
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'ScholarExtractor/1.0 (mailto:{email})'
        })

    def find_pdf(self, paper: PaperMetadata) -> Optional[PDFSource]:
        """
        Find PDF metadata using CrossRef API.

        Args:
            paper: Paper metadata

        Returns:
            PDFSource if found, None otherwise
        """
        # CrossRef works best with DOI
        if not paper.doi:
            return None

        try:
            url = f"{self.BASE_URL}/{paper.doi}"

            logger.debug(f"Querying CrossRef for DOI: {paper.doi}")

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})

                # Check for link to full text
                links = message.get('link', [])

                for link in links:
                    if link.get('content-type') == 'application/pdf':
                        pdf_url = link.get('URL')

                        if pdf_url:
                            logger.info(f"✓ CrossRef found PDF link: {paper.title[:50]}")
                            logger.info(f"  URL: {pdf_url}")

                            return PDFSource(
                                url=pdf_url,
                                source_name="CrossRef",
                                is_open_access=False  # Unknown
                            )

                logger.debug(f"CrossRef found no PDF links: {paper.doi}")
                return None

            else:
                logger.debug(f"CrossRef API error {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logger.debug(f"CrossRef request failed: {e}")
            return None

        except Exception as e:
            logger.error(f"CrossRef unexpected error: {e}")
            return None


class PDFHunter:
    """
    Multi-source PDF acquisition system.

    Tries multiple legal sources to find PDFs for papers.
    """

    def __init__(
        self,
        email: str = "researcher@example.com",
        core_api_key: Optional[str] = None
    ):
        """
        Initialize PDF hunter.

        Args:
            email: Email for API usage
            core_api_key: Optional CORE API key
        """
        self.sources = [
            UnpaywallAPI(email=email),
            COREAPI(api_key=core_api_key),
            CrossRefAPI(email=email),
        ]

        self.stats = {
            'attempted': 0,
            'found': 0,
            'not_found': 0,
            'by_source': {}
        }

    def hunt_pdf(self, paper: PaperMetadata) -> Optional[PDFSource]:
        """
        Hunt for PDF across all sources.

        Args:
            paper: Paper to find PDF for

        Returns:
            PDFSource if found, None otherwise
        """
        self.stats['attempted'] += 1

        # Try each source in order
        for source in self.sources:
            try:
                result = source.find_pdf(paper)

                if result:
                    self.stats['found'] += 1

                    # Track by source
                    source_name = source.__class__.__name__
                    if source_name not in self.stats['by_source']:
                        self.stats['by_source'][source_name] = 0
                    self.stats['by_source'][source_name] += 1

                    return result

                # Small delay between API calls
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} error: {e}")
                continue

        # No PDF found
        self.stats['not_found'] += 1
        return None

    def hunt_batch(self, papers: List[PaperMetadata]) -> Dict[str, PDFSource]:
        """
        Hunt for PDFs for multiple papers.

        Args:
            papers: List of papers to hunt PDFs for

        Returns:
            Dictionary mapping paper IDs to PDFSources
        """
        results = {}

        logger.info(f"Starting PDF hunt for {len(papers)} papers")

        for i, paper in enumerate(papers, 1):
            logger.info(f"\n[{i}/{len(papers)}] Hunting PDF for: {paper.title[:60]}...")

            # Skip papers that already have PDFs
            if paper.pdf_url:
                logger.info("  ⊙ Already has PDF URL from Semantic Scholar")
                continue

            # Hunt for PDF
            pdf_source = self.hunt_pdf(paper)

            if pdf_source:
                results[paper.id] = pdf_source
                logger.info(f"  ✓ Found PDF from {pdf_source.source_name}")
            else:
                logger.info(f"  ✗ No PDF found")

            # Rate limiting between papers
            if i < len(papers):
                time.sleep(1)

        return results

    def get_statistics(self) -> Dict:
        """Get hunt statistics."""
        return self.stats.copy()
