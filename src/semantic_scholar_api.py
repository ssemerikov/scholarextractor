"""
Semantic Scholar API client for paper metadata extraction.

This module provides an alternative to Google Scholar scraping using the
official Semantic Scholar Academic Graph API.

API Documentation: https://api.semanticscholar.org/api-docs/
"""

import logging
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .storage import PaperMetadata
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class SemanticScholarConfig:
    """Configuration for Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    # Default fields to retrieve
    DEFAULT_FIELDS = [
        "paperId",
        "title",
        "abstract",
        "authors",
        "year",
        "publicationDate",
        "venue",
        "citationCount",
        "url",
        "openAccessPdf",
        "externalIds",
        "publicationTypes",
        "fieldsOfStudy"
    ]

    # Rate limits (requests per second)
    RATE_LIMIT_NO_AUTH = 1  # 1 request per second without API key
    RATE_LIMIT_WITH_AUTH = 1  # 1 request per second with API key

    # Pagination
    MAX_RESULTS_PER_REQUEST = 100  # API returns up to 100 results per request


class SemanticScholarAPIClient:
    """
    Client for Semantic Scholar Academic Graph API.

    This provides an alternative to Google Scholar scraping using an official API
    with no CAPTCHA, no rate limiting issues (with API key), and structured data.

    Advantages over Google Scholar scraping:
    - Official API (no Terms of Service violations)
    - No CAPTCHA challenges
    - Structured JSON responses
    - Higher rate limits with API key
    - More reliable and maintainable
    - Includes open access PDF links

    Limitations:
    - Different coverage than Google Scholar
    - Requires API key for higher limits
    - Limited to 100 results per request (need pagination for more)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar API client.

        Args:
            api_key: Optional API key for higher rate limits
                    Get one at: https://www.semanticscholar.org/product/api
        """
        self.api_key = api_key
        self.base_url = SemanticScholarConfig.BASE_URL
        self.session = requests.Session()

        # Set up headers
        if api_key:
            self.session.headers['x-api-key'] = api_key
            self.rate_limit = SemanticScholarConfig.RATE_LIMIT_WITH_AUTH
        else:
            self.rate_limit = SemanticScholarConfig.RATE_LIMIT_NO_AUTH
            logger.warning(
                "No API key provided. Rate limited to 1 request/second. "
                "Get a free API key at https://www.semanticscholar.org/product/api"
            )

        self.last_request_time = 0

    def _rate_limit_delay(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        required_delay = 1.0 / self.rate_limit

        if elapsed < required_delay:
            sleep_time = required_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dictionary
        """
        self._rate_limit_delay()

        url = f"{self.base_url}{endpoint}"

        logger.debug(f"API request: {url}")
        logger.debug(f"Parameters: {params}")

        response = self.session.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def search_papers(
        self,
        query: str,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        min_citations: Optional[int] = None,
        max_results: int = 100,
        fields: Optional[List[str]] = None,
        sort: str = "citationCount"
    ) -> List[PaperMetadata]:
        """
        Search for papers using Semantic Scholar API.

        Args:
            query: Search query (use quotes for phrases)
            year_min: Minimum publication year
            year_max: Maximum publication year
            min_citations: Minimum citation count
            max_results: Maximum number of results (default 100)
            fields: List of fields to retrieve (uses defaults if None)
            sort: Sort order - 'citationCount', 'publicationDate', or 'paperId'

        Returns:
            List of PaperMetadata objects

        Example:
            >>> client = SemanticScholarAPIClient(api_key="your_key")
            >>> papers = client.search_papers(
            ...     query='student "web design"',
            ...     year_min=2007,
            ...     max_results=50
            ... )
        """
        # Build query parameters
        params = {
            "query": query,
            "fields": ",".join(fields or SemanticScholarConfig.DEFAULT_FIELDS),
            "limit": min(max_results, SemanticScholarConfig.MAX_RESULTS_PER_REQUEST),
            "sort": sort
        }

        # Add year filter
        if year_min or year_max:
            year_filter = f"{year_min or ''}-{year_max or ''}"
            params["year"] = year_filter

        # Add citation filter
        if min_citations:
            params["minCitationCount"] = min_citations

        logger.info(f"Searching Semantic Scholar: {query}")
        logger.info(f"Filters - Years: {params.get('year', 'all')}, "
                   f"Min citations: {min_citations or 0}, "
                   f"Max results: {max_results}")

        papers = []
        offset = 0

        try:
            while len(papers) < max_results:
                # Update offset for pagination
                if offset > 0:
                    params["offset"] = offset

                # Make API request
                response = self._make_request("/paper/search/bulk", params)

                # Extract papers from response
                batch = response.get("data", [])

                if not batch:
                    logger.info(f"No more results. Total: {len(papers)}")
                    break

                # Convert to PaperMetadata
                for paper_data in batch:
                    paper = self._convert_to_paper_metadata(paper_data)
                    if paper:
                        papers.append(paper)

                logger.info(f"Retrieved {len(papers)}/{max_results} papers")

                # Check if we got fewer results than requested (end of results)
                if len(batch) < params["limit"]:
                    logger.info(f"Reached end of results. Total: {len(papers)}")
                    break

                # Update offset for next page
                offset += len(batch)

                # Check if we've reached max_results
                if len(papers) >= max_results:
                    papers = papers[:max_results]
                    break

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

        logger.info(f"Search complete. Retrieved {len(papers)} papers")
        return papers

    def _convert_to_paper_metadata(self, data: Dict[str, Any]) -> Optional[PaperMetadata]:
        """
        Convert Semantic Scholar API response to PaperMetadata.

        Args:
            data: Paper data from API response

        Returns:
            PaperMetadata object or None if conversion fails
        """
        try:
            # Extract authors
            authors = []
            for author in data.get("authors", []):
                name = author.get("name", "")
                if name:
                    authors.append(name)

            # Extract year
            year = data.get("year")
            if not year and data.get("publicationDate"):
                # Try to extract year from publicationDate (YYYY-MM-DD)
                try:
                    year = int(data["publicationDate"][:4])
                except (ValueError, TypeError):
                    year = None

            # Extract PDF URL
            pdf_url = ""
            open_access = data.get("openAccessPdf")
            if open_access and open_access.get("url"):
                pdf_url = open_access["url"]

            # Extract DOI
            doi = ""
            external_ids = data.get("externalIds", {})
            if external_ids and "DOI" in external_ids:
                doi = external_ids["DOI"]

            # Create PaperMetadata
            paper = PaperMetadata(
                id=data.get("paperId", ""),
                title=data.get("title", ""),
                authors=authors,
                year=year,
                venue=data.get("venue", ""),
                abstract=data.get("abstract", ""),
                citations=data.get("citationCount", 0),
                url=data.get("url", ""),
                pdf_url=pdf_url,
                doi=doi
            )

            return paper

        except Exception as e:
            logger.warning(f"Failed to convert paper data: {e}")
            logger.debug(f"Problem data: {data}")
            return None

    def get_paper_by_id(self, paper_id: str, fields: Optional[List[str]] = None) -> Optional[PaperMetadata]:
        """
        Get paper details by Semantic Scholar paper ID.

        Args:
            paper_id: Semantic Scholar paper ID
            fields: List of fields to retrieve

        Returns:
            PaperMetadata object or None
        """
        params = {
            "fields": ",".join(fields or SemanticScholarConfig.DEFAULT_FIELDS)
        }

        try:
            response = self._make_request(f"/paper/{paper_id}", params)
            return self._convert_to_paper_metadata(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get paper {paper_id}: {e}")
            return None

    def close(self):
        """Close the session."""
        self.session.close()


def demo_semantic_scholar_search():
    """
    Demonstration of Semantic Scholar API search.

    This shows how to use the API to search for papers matching the
    original Google Scholar query from prompt.md.
    """
    print("=== Semantic Scholar API Demo ===\n")

    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)

    # Create client (no API key for demo - will be rate limited)
    client = SemanticScholarAPIClient()

    # Search with similar criteria to original Google Scholar query
    print("Searching for: student web design/programming papers (2007-present)")
    print("Query: student web design")
    print()

    try:
        # Try simpler query first
        papers = client.search_papers(
            query='student web design',
            year_min=2007,
            max_results=10,  # Limit for demo
            sort="citationCount"  # Get most cited papers
        )

        print(f"\nFound {len(papers)} papers:\n")

        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper.title}")
            print(f"   Authors: {', '.join(paper.authors[:3]) if paper.authors else 'N/A'}")
            print(f"   Year: {paper.year} | Citations: {paper.citations}")
            print(f"   Venue: {paper.venue}")
            if paper.pdf_url:
                print(f"   PDF: {paper.pdf_url}")
            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    # Run demo
    demo_semantic_scholar_search()
