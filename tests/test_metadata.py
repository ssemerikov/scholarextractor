"""
Tests for metadata extraction module.
"""

import pytest
from src.metadata import MetadataExtractor
from src.storage import PaperMetadata


class TestMetadataExtractor:
    """Test MetadataExtractor class."""

    def test_initialization(self):
        """Test MetadataExtractor initialization."""
        extractor = MetadataExtractor()

        assert extractor.base_url == "https://scholar.google.com"

    def test_extract_from_search_page(self, sample_scholar_html):
        """Test extracting papers from search results."""
        extractor = MetadataExtractor()
        papers = extractor.extract_from_search_page(sample_scholar_html)

        assert isinstance(papers, list)
        assert len(papers) == 2

        # Check first paper
        paper1 = papers[0]
        assert isinstance(paper1, PaperMetadata)
        assert "Web Design for Students" in paper1.title
        assert len(paper1.authors) > 0
        assert paper1.year == 2020
        assert paper1.citations == 42
        assert paper1.abstract != ""

        # Check second paper
        paper2 = papers[1]
        assert "Web Programming" in paper2.title
        assert paper2.year == 2019
        assert paper2.citations == 15
        assert paper2.pdf_url != ""

    def test_clean_title(self):
        """Test title cleaning."""
        extractor = MetadataExtractor()

        # Test removing citation markers
        dirty_title = "[PDF] Sample Paper Title [HTML]"
        clean = extractor._clean_title(dirty_title)
        assert clean == "Sample Paper Title"

        # Test whitespace normalization
        dirty_title = "  Title   with   spaces  "
        clean = extractor._clean_title(dirty_title)
        assert clean == "Title with spaces"

    def test_generate_id(self):
        """Test ID generation from title."""
        extractor = MetadataExtractor()

        id1 = extractor._generate_id("Sample Title")
        id2 = extractor._generate_id("Sample Title")
        id3 = extractor._generate_id("Different Title")

        # Same title should generate same ID
        assert id1 == id2
        # Different title should generate different ID
        assert id1 != id3
        # ID should be 12 characters
        assert len(id1) == 12

    def test_parse_metadata_line(self):
        """Test parsing metadata line."""
        extractor = MetadataExtractor()

        # Test standard format
        meta_text = "John Doe, Jane Smith - Journal of Science, 2020 - publisher.com"
        authors, venue, year = extractor._parse_metadata_line(meta_text)

        assert len(authors) >= 2
        assert "John Doe" in authors
        assert "Jane Smith" in authors
        assert year == 2020
        assert "Journal of Science" in venue

    def test_parse_metadata_line_variations(self):
        """Test parsing different metadata line formats."""
        extractor = MetadataExtractor()

        # Format with 'and'
        meta_text = "A Smith and B Jones - Conference, 2019 - IEEE"
        authors, venue, year = extractor._parse_metadata_line(meta_text)

        assert len(authors) >= 2
        assert year == 2019

        # Format without year
        meta_text = "Author Name - Some Venue - Publisher"
        authors, venue, year = extractor._parse_metadata_line(meta_text)

        assert len(authors) >= 1
        assert year is None

    def test_extract_citation_count(self):
        """Test extracting citation count."""
        from bs4 import BeautifulSoup

        extractor = MetadataExtractor()

        # HTML with citation link
        html = '<div class="gs_fl"><a>Cited by 123</a></div>'
        soup = BeautifulSoup(html, 'lxml')
        div = soup.find('div')

        count = extractor._extract_citation_count(div)
        assert count == 123

        # HTML without citation
        html = '<div class="gs_fl"></div>'
        soup = BeautifulSoup(html, 'lxml')
        div = soup.find('div')

        count = extractor._extract_citation_count(div)
        assert count == 0

    def test_extract_pdf_link(self):
        """Test extracting PDF link."""
        from bs4 import BeautifulSoup

        extractor = MetadataExtractor()

        # HTML with PDF link
        html = '''
        <div class="gs_ri">
            <div class="gs_or_ggsm">
                <a href="https://example.com/paper.pdf">[PDF]</a>
            </div>
        </div>
        '''
        soup = BeautifulSoup(html, 'lxml')
        div = soup.find('div', class_='gs_ri')

        pdf_url = extractor._extract_pdf_link(div)
        assert pdf_url == "https://example.com/paper.pdf"

        # HTML without PDF link
        html = '<div class="gs_ri"></div>'
        soup = BeautifulSoup(html, 'lxml')
        div = soup.find('div')

        pdf_url = extractor._extract_pdf_link(div)
        assert pdf_url == ''

    def test_extract_doi(self):
        """Test DOI extraction."""
        extractor = MetadataExtractor()

        # DOI in URL
        url = "https://doi.org/10.1000/example.123"
        doi = extractor._extract_doi(url, "")
        assert doi == "10.1000/example.123"

        # DOI in text
        text = "Available at DOI: 10.1234/journal.2020.456"
        doi = extractor._extract_doi("", text)
        assert "10.1234/journal.2020.456" in doi

        # No DOI
        doi = extractor._extract_doi("https://example.com", "No DOI here")
        assert doi == ""

    def test_check_next_page(self):
        """Test checking for next page."""
        extractor = MetadataExtractor()

        # HTML with next button
        html = '''
        <div id="gs_n">
            <a href="/scholar?start=10">Next</a>
        </div>
        '''
        next_url = extractor.check_next_page(html)
        assert next_url is not None
        assert "scholar" in next_url

        # HTML without next button
        html = '<div id="gs_n"></div>'
        next_url = extractor.check_next_page(html)
        assert next_url is None

    def test_empty_html(self):
        """Test handling empty HTML."""
        extractor = MetadataExtractor()

        papers = extractor.extract_from_search_page("")
        assert isinstance(papers, list)
        assert len(papers) == 0

    def test_malformed_html(self):
        """Test handling malformed HTML."""
        extractor = MetadataExtractor()

        html = "<div><h3>Title without proper structure"
        papers = extractor.extract_from_search_page(html)

        # Should not crash, may return empty list
        assert isinstance(papers, list)
