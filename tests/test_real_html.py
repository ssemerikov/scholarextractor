"""
Tests for metadata extraction using real Google Scholar HTML samples.

These tests validate that the extraction logic works with actual
Google Scholar page structures (manually saved to avoid rate limiting).
"""

import pytest
from pathlib import Path
from src.metadata import MetadataExtractor


class TestRealHTMLExtraction:
    """Test extraction with real Google Scholar HTML samples."""

    @pytest.fixture
    def html_sample_page_1(self):
        """Load real HTML sample from page 1."""
        fixture_path = Path(__file__).parent / 'fixtures' / 'real_scholar_html' / 'sample_page_1.html'
        return fixture_path.read_text(encoding='utf-8')

    def test_extract_from_real_page_1(self, html_sample_page_1):
        """Test extraction from realistic Google Scholar HTML page 1.

        This validates that our parser works with actual Google Scholar structure.
        """
        extractor = MetadataExtractor()

        papers = extractor.extract_from_search_page(html_sample_page_1)

        # Should extract 5 papers from the page
        assert len(papers) == 5, f"Expected 5 papers, got {len(papers)}"

        # Validate first paper (with PDF)
        paper1 = papers[0]
        assert paper1.title == "Student perceptions of web design: Implications for educators"
        assert "Smith" in paper1.authors[0]
        assert "Johnson" in paper1.authors[1]
        assert paper1.year == 2010
        assert "Computers & Education" in paper1.venue
        assert paper1.citations == 152
        assert "student perceptions" in paper1.abstract.lower()
        assert paper1.pdf_url == "https://example.com/paper1.pdf"
        assert paper1.url == "https://example.com/paper1.pdf"

        # Validate second paper (without PDF, has DOI)
        paper2 = papers[1]
        assert paper2.title == "Web programming for student learning: A comprehensive approach"
        assert "Brown" in paper2.authors[0]
        assert paper2.year == 2011
        assert "International Journal of Educational Technology" in paper2.venue
        assert paper2.citations == 89
        assert "framework" in paper2.abstract.lower()
        assert paper2.pdf_url == ""  # No PDF available
        assert "doi.org" in paper2.url

        # Validate third paper (high citations)
        paper3 = papers[2]
        assert paper3.title == "Student engagement in web development: HTML5 and beyond"
        assert "Lee" in paper3.authors[0]
        assert paper3.year == 2015
        assert "ACM Transactions on Computing Education" in paper3.venue
        assert paper3.citations == 234
        assert "arxiv.org" in paper3.pdf_url

        # Validate fourth paper (book chapter)
        paper4 = papers[3]
        assert paper4.title == "Teaching web design to students: Best practices and challenges"
        assert "Martinez" in paper4.authors[0]
        assert paper4.year == 2012
        assert paper4.citations == 67
        assert paper4.pdf_url == ""  # Book chapter, typically no free PDF

        # Validate fifth paper (conference paper)
        paper5 = papers[4]
        assert paper5.title == "Student-centered web programming: A project-based approach"
        assert "Rodriguez" in paper5.authors[0]
        assert paper5.year == 2013
        assert "IEEE" in paper5.venue
        assert paper5.citations == 143

    def test_extract_metadata_quality(self, html_sample_page_1):
        """Test that extracted metadata meets quality standards."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        for i, paper in enumerate(papers, 1):
            # All papers should have titles
            assert paper.title, f"Paper {i} missing title"
            assert len(paper.title) > 10, f"Paper {i} title too short"

            # All papers should have at least one author
            assert paper.authors, f"Paper {i} missing authors"
            assert len(paper.authors) >= 1, f"Paper {i} has no authors"

            # All papers should have valid years
            assert paper.year is not None, f"Paper {i} missing year"
            assert 2007 <= paper.year <= 2025, f"Paper {i} year out of range: {paper.year}"

            # All papers should have citations count
            assert paper.citations >= 0, f"Paper {i} has negative citations"

            # Papers should have either URL or PDF URL
            assert paper.url or paper.pdf_url, f"Paper {i} has no URL"

            # If abstract exists, it should be meaningful
            if paper.abstract:
                assert len(paper.abstract) > 20, f"Paper {i} abstract too short"

    def test_extract_pagination_info(self, html_sample_page_1):
        """Test that next page URL is extracted correctly."""
        extractor = MetadataExtractor()

        next_url = extractor.check_next_page(html_sample_page_1)

        assert next_url is not None, "Should find next page URL"
        assert "start=10" in next_url, "Next page should have start=10 parameter"

    def test_extract_citation_counts(self, html_sample_page_1):
        """Test that citation counts are extracted correctly."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        expected_citations = [152, 89, 234, 67, 143]

        for i, (paper, expected) in enumerate(zip(papers, expected_citations), 1):
            assert paper.citations == expected, \
                f"Paper {i}: expected {expected} citations, got {paper.citations}"

    def test_extract_pdf_urls(self, html_sample_page_1):
        """Test that PDF URLs are extracted when available."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        # Papers with PDFs
        assert papers[0].pdf_url == "https://example.com/paper1.pdf"
        assert papers[2].pdf_url == "https://arxiv.org/pdf/2020.12345.pdf"

        # Papers without PDFs
        assert papers[1].pdf_url == ""
        assert papers[3].pdf_url == ""

    def test_extract_venues(self, html_sample_page_1):
        """Test that venues are extracted correctly."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        # Verify key venues
        assert "Computers & Education" in papers[0].venue
        assert "International Journal of Educational Technology" in papers[1].venue
        assert "ACM Transactions on Computing Education" in papers[2].venue
        assert "IEEE" in papers[4].venue

    def test_extract_creates_valid_paper_ids(self, html_sample_page_1):
        """Test that each paper gets a unique ID."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        # All papers should have IDs
        ids = [p.id for p in papers]
        assert all(ids), "All papers should have IDs"

        # IDs should be unique
        assert len(ids) == len(set(ids)), "Paper IDs should be unique"

    def test_extract_statistics(self, html_sample_page_1):
        """Test extraction statistics and metadata distribution."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(html_sample_page_1)

        # Calculate statistics
        papers_with_pdf = sum(1 for p in papers if p.pdf_url)
        papers_with_abstract = sum(1 for p in papers if p.abstract)
        papers_with_venue = sum(1 for p in papers if p.venue)
        avg_citations = sum(p.citations for p in papers) / len(papers)

        # Validate statistics
        assert papers_with_pdf >= 2, "Should have at least 2 papers with PDFs"
        assert papers_with_abstract >= 4, "Should have at least 4 papers with abstracts"
        assert papers_with_venue >= 4, "Should have at least 4 papers with venues"
        assert avg_citations > 100, "Average citations should be reasonable"

        # Print summary (for manual verification)
        print(f"\nExtraction Statistics:")
        print(f"  Total papers: {len(papers)}")
        print(f"  Papers with PDF: {papers_with_pdf} ({papers_with_pdf/len(papers)*100:.1f}%)")
        print(f"  Papers with abstract: {papers_with_abstract} ({papers_with_abstract/len(papers)*100:.1f}%)")
        print(f"  Papers with venue: {papers_with_venue} ({papers_with_venue/len(papers)*100:.1f}%)")
        print(f"  Average citations: {avg_citations:.1f}")
        print(f"  Year range: {min(p.year for p in papers)} - {max(p.year for p in papers)}")
