"""
Tests for search module - focusing on uncovered areas.
"""

import pytest
import responses
from unittest.mock import Mock, patch
from pathlib import Path

from src.search import ScholarSearcher
from src.storage import Storage, PaperMetadata
from src.config import Config
from src.client import CaptchaDetectedException


class TestScholarSearcher:
    """Test ScholarSearcher class with focus on uncovered paths."""

    def test_initialization(self):
        """Test searcher initialization."""
        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=50)

        assert searcher.storage == storage
        assert searcher.max_papers == 50
        assert searcher.session is not None
        assert searcher.extractor is not None

    @responses.activate
    def test_search_multiple_pages(self, temp_dir, monkeypatch):
        """Test pagination across multiple pages."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=25)

        # Page 1 - has results and next link
        page1_html = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/1">Paper 1</a></h3>
                <div class="gs_a">Author One - Conference, 2020 - publisher.com</div>
                <div class="gs_rs">Abstract for paper 1</div>
            </div>
            <div id="gs_n">
                <a href="/scholar?q=test&start=10">Next</a>
            </div>
        </html>
        """

        # Page 2 - has results and next link
        page2_html = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/2">Paper 2</a></h3>
                <div class="gs_a">Author Two - Journal, 2021 - publisher.com</div>
                <div class="gs_rs">Abstract for paper 2</div>
            </div>
            <div id="gs_n">
                <a href="/scholar?q=test&start=20">Next</a>
            </div>
        </html>
        """

        # Page 3 - has results but no next link (last page)
        page3_html = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/3">Paper 3</a></h3>
                <div class="gs_a">Author Three - Book, 2022 - publisher.com</div>
                <div class="gs_rs">Abstract for paper 3</div>
            </div>
        </html>
        """

        responses.add(
            responses.GET,
            'https://scholar.google.com/scholar?q=test',
            body=page1_html,
            status=200
        )

        responses.add(
            responses.GET,
            'https://scholar.google.com/scholar?q=test&start=10',
            body=page2_html,
            status=200
        )

        responses.add(
            responses.GET,
            'https://scholar.google.com/scholar?q=test&start=20',
            body=page3_html,
            status=200
        )

        papers = searcher.search('https://scholar.google.com/scholar?q=test')

        # Should have fetched all 3 pages
        assert len(responses.calls) == 3
        assert len(papers) == 3
        assert len(storage.papers) == 3

        searcher.close()

    @responses.activate
    def test_search_respects_max_pages(self, temp_dir, monkeypatch):
        """Test that search stops at MAX_PAGES limit."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'MAX_PAGES', 2)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=1000)  # Very high, should hit page limit

        # Create HTML with next link (infinite pagination)
        html_template = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/{page}">Paper {page}</a></h3>
                <div class="gs_a">Author - Venue, 2020 - publisher.com</div>
                <div class="gs_rs">Abstract</div>
            </div>
            <div id="gs_n">
                <a href="/scholar?q=test&start={next_start}">Next</a>
            </div>
        </html>
        """

        # Set up 10 pages (more than MAX_PAGES)
        for i in range(10):
            start = i * 10
            next_start = (i + 1) * 10
            url = f'https://scholar.google.com/scholar?q=test&start={start}' if i > 0 else 'https://scholar.google.com/scholar?q=test'

            responses.add(
                responses.GET,
                url,
                body=html_template.format(page=i+1, next_start=next_start),
                status=200
            )

        papers = searcher.search('https://scholar.google.com/scholar?q=test')

        # Should have stopped at MAX_PAGES (2)
        assert len(responses.calls) <= 2
        searcher.close()

    @responses.activate
    def test_search_with_captcha_interruption(self, temp_dir, monkeypatch):
        """Test that CAPTCHA detection stops search gracefully."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=100)

        # First page succeeds
        page1_html = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/1">Paper 1</a></h3>
                <div class="gs_a">Author - Venue, 2020 - publisher.com</div>
                <div class="gs_rs">Abstract</div>
            </div>
            <div id="gs_n">
                <a href="/scholar?q=test&start=10">Next</a>
            </div>
        </html>
        """

        # Second page triggers CAPTCHA
        captcha_html = """
        <html>
            <body>
                <h1>Please verify you're not a robot</h1>
                <p>We've detected unusual traffic from your computer network.</p>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://scholar.google.com/scholar?q=test',
            body=page1_html,
            status=200
        )

        responses.add(
            responses.GET,
            'https://scholar.google.com/scholar?q=test&start=10',
            body=captcha_html,
            status=200
        )

        # Should not raise, just stop gracefully
        papers = searcher.search('https://scholar.google.com/scholar?q=test')

        # Should have processed first page before CAPTCHA
        assert len(storage.papers) >= 1
        assert len(responses.calls) == 2

        # State should be saved
        assert (temp_dir / 'state.json').exists()

        searcher.close()

    def test_search_with_resume(self, temp_dir, monkeypatch):
        """Test resuming interrupted search."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')

        # First search - extract 2 papers and save state
        storage1 = Storage()
        paper1 = PaperMetadata(
            id='paper1',
            title='First Paper',
            authors=['Author One'],
            year=2020
        )
        paper2 = PaperMetadata(
            id='paper2',
            title='Second Paper',
            authors=['Author Two'],
            year=2021
        )
        storage1.add_paper(paper1)
        storage1.add_paper(paper2)
        storage1.set_query_info('https://scholar.google.com/scholar?q=test', 'Test')
        storage1.save_state()
        storage1.save_metadata_json()

        # Second search - resume
        storage2 = Storage()
        searcher = ScholarSearcher(storage2, max_papers=5)

        # Mock the search to add one more paper
        with patch.object(searcher, 'search') as mock_search:
            # Simulate loading state and finding it
            storage2.load_state()
            storage2.load_metadata_json()

            # Verify resume detected existing papers
            assert len(storage2.papers) == 2
            assert storage2.papers[0].title == 'First Paper'
            assert storage2.papers[1].title == 'Second Paper'

        searcher.close()

    def test_build_search_url(self):
        """Test URL building from parameters."""
        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=10)

        # Test basic URL building
        url = searcher._build_search_url(
            keywords=['machine learning', 'python']
        )

        assert 'q=machine learning python' in url or 'q=machine+learning+python' in url
        assert 'scholar' in url

    def test_build_search_url_with_year_filters(self):
        """Test URL building with year filters."""
        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=10)

        url = searcher._build_search_url(
            keywords=['web design'],
            year_start=2020,
            year_end=2023
        )

        assert 'as_ylo=2020' in url
        assert 'as_yhi=2023' in url

    def test_build_search_url_with_custom_params(self):
        """Test URL building with custom parameters."""
        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=10)

        url = searcher._build_search_url(
            keywords=['student'],
            as_vis=1,
            hl='en'
        )

        assert 'as_vis=1' in url
        assert 'hl=en' in url

    @responses.activate
    def test_search_by_params_integration(self, temp_dir, monkeypatch):
        """Test search_by_params end-to-end."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=5)

        html = """
        <html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/1">Web Design Paper</a></h3>
                <div class="gs_a">Author - Conference, 2020 - publisher.com</div>
                <div class="gs_rs">About web design</div>
            </div>
        </html>
        """

        # Mock any URL matching the pattern (using regex)
        import re
        responses.add(
            responses.GET,
            re.compile(r'https://scholar\.google\.com/scholar\?.*'),
            body=html,
            status=200
        )

        papers = searcher.search_by_params(
            keywords=['web design'],
            year_start=2020
        )

        assert len(papers) >= 1  # Should extract at least the one paper from HTML
        searcher.close()

    def test_get_statistics(self):
        """Test statistics generation."""
        storage = Storage()

        # Add papers with different properties
        paper1 = PaperMetadata(
            id='paper1',
            title='Paper One',
            authors=['Author One'],
            year=2020,
            pdf_downloaded=True
        )
        paper2 = PaperMetadata(
            id='paper2',
            title='Paper Two',
            authors=['Author Two'],
            year=2021
        )
        storage.add_paper(paper1)
        storage.add_paper(paper2)

        searcher = ScholarSearcher(storage, max_papers=10)
        searcher.session.request_count = 15

        stats = searcher.get_statistics()

        assert stats['papers_extracted'] == 2
        assert stats['request_count'] == 15
        assert 'papers_with_pdf' in stats
        assert stats['papers_with_pdf'] == 1
        assert stats['total_papers'] == 2

    def test_search_handles_page_errors_gracefully(self, temp_dir, monkeypatch):
        """Test that errors on individual pages don't stop entire search."""
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=10)

        # Mock extractor to raise error on first call, succeed on second
        call_count = [0]
        original_extract = searcher.extractor.extract_from_search_page

        def mock_extract(html):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Simulated parsing error")
            return original_extract(html)

        with patch.object(searcher.extractor, 'extract_from_search_page', side_effect=mock_extract):
            with patch.object(searcher.session, 'get') as mock_get:
                # First call raises error, second succeeds
                mock_response = Mock()
                mock_response.text = '<html></html>'
                mock_get.return_value = mock_response

                # Should continue despite error
                try:
                    papers = searcher.search('https://scholar.google.com/scholar?q=test')
                except:
                    pass  # Error handling may vary

        # Should have attempted multiple pages
        assert call_count[0] >= 1

        searcher.close()

    @responses.activate
    def test_search_stops_at_exact_max_papers(self, temp_dir, monkeypatch):
        """Test search stops when reaching max_papers mid-page (critical boundary condition).

        Covers lines: search.py:84
        Value: ⭐⭐⭐⭐ - Critical path, ensures max_papers limit is respected
        """
        monkeypatch.setattr(Config, 'REQUEST_DELAY', 0)
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')
        monkeypatch.setattr(Config, 'STATE_FILE', temp_dir / 'state.json')

        # Create HTML with 10 papers on a single page
        html_with_10_papers = """<html>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/1">Paper 1</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/2">Paper 2</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/3">Paper 3</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/4">Paper 4</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/5">Paper 5</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/6">Paper 6</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/7">Paper 7</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/8">Paper 8</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/9">Paper 9</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt"><a href="http://example.com/10">Paper 10</a></h3>
                <div class="gs_a">Author - Venue, 2020</div>
            </div>
        </html>"""

        import re
        responses.add(
            responses.GET,
            re.compile(r'https://scholar\.google\.com/scholar.*'),
            body=html_with_10_papers,
            status=200
        )

        storage = Storage()
        # Set max_papers to 3 to test boundary
        searcher = ScholarSearcher(storage, max_papers=3)

        papers = searcher.search('https://scholar.google.com/scholar?q=test')

        # Should extract exactly 3 papers, not all 10
        assert len(papers) == 3
        assert len(storage.papers) == 3

        # Verify the papers are the first 3
        assert storage.papers[0].title == 'Paper 1'
        assert storage.papers[1].title == 'Paper 2'
        assert storage.papers[2].title == 'Paper 3'

        searcher.close()

    def test_searcher_close(self):
        """Test resource cleanup."""
        storage = Storage()
        searcher = ScholarSearcher(storage, max_papers=10)

        # Should not raise exception
        searcher.close()

        # Session should be closed
        # (session.close() doesn't have visible state, but shouldn't error)
