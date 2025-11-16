"""
Pytest configuration and fixtures.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_scholar_html():
    """Sample Google Scholar search results HTML."""
    return """
    <html>
        <body>
            <div class="gs_ri">
                <h3 class="gs_rt">
                    <a href="https://example.com/paper1">
                        Sample Paper Title: Web Design for Students
                    </a>
                </h3>
                <div class="gs_a">
                    John Doe, Jane Smith - Journal of Web Education, 2020 - publisher.com
                </div>
                <div class="gs_rs">
                    This is a sample abstract about web design education for students.
                    It covers HTML, CSS, and JavaScript fundamentals.
                </div>
                <div class="gs_fl">
                    <a href="#">Cited by 42</a>
                </div>
            </div>
            <div class="gs_ri">
                <h3 class="gs_rt">
                    <a href="https://example.com/paper2.pdf">
                        Another Paper on Web Programming
                    </a>
                </h3>
                <div class="gs_a">
                    Bob Johnson - Conference on Programming, 2019 - ieee.org
                </div>
                <div class="gs_rs">
                    This paper discusses web programming techniques for beginners.
                </div>
                <div class="gs_fl">
                    <a href="#">Cited by 15</a>
                </div>
                <div class="gs_or_ggsm">
                    <a href="https://example.com/paper2.pdf">[PDF]</a>
                </div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_paper_metadata():
    """Sample paper metadata dictionary."""
    return {
        'id': 'abc123',
        'title': 'Sample Paper Title',
        'authors': ['John Doe', 'Jane Smith'],
        'year': 2020,
        'venue': 'Journal of Computer Science',
        'abstract': 'This is a sample abstract.',
        'citations': 42,
        'url': 'https://example.com/paper',
        'doi': '10.1000/example',
        'bibtex': '@article{doe2020sample}',
        'pdf_url': 'https://example.com/paper.pdf',
        'pdf_downloaded': False,
        'pdf_path': '',
    }


@pytest.fixture
def mock_pdf_content():
    """Mock PDF file content with proper magic bytes."""
    # PDF files start with %PDF-
    return b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\nSample PDF content here...'
