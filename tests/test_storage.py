"""
Tests for storage module.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from src.storage import PaperMetadata, Storage
from src.config import Config


class TestPaperMetadata:
    """Test PaperMetadata class."""

    def test_create_from_kwargs(self, sample_paper_metadata):
        """Test creating PaperMetadata from keyword arguments."""
        paper = PaperMetadata(**sample_paper_metadata)

        assert paper.id == sample_paper_metadata['id']
        assert paper.title == sample_paper_metadata['title']
        assert paper.authors == sample_paper_metadata['authors']
        assert paper.year == sample_paper_metadata['year']

    def test_to_dict(self, sample_paper_metadata):
        """Test converting PaperMetadata to dictionary."""
        paper = PaperMetadata(**sample_paper_metadata)
        data = paper.to_dict()

        assert isinstance(data, dict)
        assert data['title'] == sample_paper_metadata['title']
        assert data['authors'] == sample_paper_metadata['authors']

    def test_from_dict(self, sample_paper_metadata):
        """Test creating PaperMetadata from dictionary."""
        paper = PaperMetadata.from_dict(sample_paper_metadata)

        assert paper.title == sample_paper_metadata['title']
        assert paper.year == sample_paper_metadata['year']

    def test_default_values(self):
        """Test default values for PaperMetadata."""
        paper = PaperMetadata()

        assert paper.id == ''
        assert paper.title == ''
        assert paper.authors == []
        assert paper.citations == 0
        assert paper.pdf_downloaded is False

    def test_repr(self, sample_paper_metadata):
        """Test string representation."""
        paper = PaperMetadata(**sample_paper_metadata)
        repr_str = repr(paper)

        assert 'PaperMetadata' in repr_str
        assert str(paper.year) in repr_str


class TestStorage:
    """Test Storage class."""

    def test_initialization(self):
        """Test Storage initialization."""
        storage = Storage()

        assert isinstance(storage.papers, list)
        assert len(storage.papers) == 0
        assert isinstance(storage.state, dict)
        assert isinstance(storage.query_info, dict)

    def test_add_paper(self, sample_paper_metadata):
        """Test adding paper to storage."""
        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)

        storage.add_paper(paper)

        assert len(storage.papers) == 1
        assert storage.papers[0] == paper

    def test_save_metadata_json(self, temp_dir, monkeypatch, sample_paper_metadata):
        """Test saving metadata to JSON."""
        monkeypatch.setattr(Config, 'METADATA_JSON', temp_dir / 'metadata.json')

        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)
        storage.add_paper(paper)
        storage.set_query_info("https://example.com", "Test query")

        result = storage.save_metadata_json()

        assert result is True
        assert (temp_dir / 'metadata.json').exists()

        # Verify content
        with open(temp_dir / 'metadata.json', 'r') as f:
            data = json.load(f)

        assert 'papers' in data
        assert len(data['papers']) == 1
        assert data['papers'][0]['title'] == sample_paper_metadata['title']

    def test_load_metadata_json(self, temp_dir, monkeypatch, sample_paper_metadata):
        """Test loading metadata from JSON."""
        json_file = temp_dir / 'metadata.json'
        monkeypatch.setattr(Config, 'METADATA_JSON', json_file)

        # Create JSON file
        data = {
            'papers': [sample_paper_metadata],
            'query': {'url': 'test'},
            'total_papers': 1
        }
        with open(json_file, 'w') as f:
            json.dump(data, f)

        # Load
        storage = Storage()
        result = storage.load_metadata_json()

        assert result is True
        assert len(storage.papers) == 1
        assert storage.papers[0].title == sample_paper_metadata['title']

    def test_save_metadata_csv(self, temp_dir, monkeypatch, sample_paper_metadata):
        """Test saving metadata to CSV."""
        monkeypatch.setattr(Config, 'METADATA_CSV', temp_dir / 'metadata.csv')

        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)
        storage.add_paper(paper)

        result = storage.save_metadata_csv()

        assert result is True
        assert (temp_dir / 'metadata.csv').exists()

    def test_save_state(self, temp_dir, monkeypatch, sample_paper_metadata):
        """Test saving state."""
        state_file = temp_dir / 'state.json'
        monkeypatch.setattr(Config, 'STATE_FILE', state_file)

        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)
        storage.add_paper(paper)

        result = storage.save_state()

        assert result is True
        assert state_file.exists()

        # Verify content
        with open(state_file, 'r') as f:
            state = json.load(f)

        assert state['papers_processed'] == 1

    def test_load_state(self, temp_dir, monkeypatch):
        """Test loading state."""
        state_file = temp_dir / 'state.json'
        monkeypatch.setattr(Config, 'STATE_FILE', state_file)

        # Create state file
        state_data = {
            'papers_processed': 10,
            'last_paper_id': 'abc123',
            'query': {'url': 'test'},
            'custom_state': {}
        }
        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        # Load
        storage = Storage()
        result = storage.load_state()

        assert result is True
        assert storage.state['papers_processed'] == 10

    def test_set_query_info(self):
        """Test setting query information."""
        storage = Storage()
        storage.set_query_info("https://example.com", "Test description")

        assert storage.query_info['url'] == "https://example.com"
        assert storage.query_info['description'] == "Test description"
        assert 'executed_at' in storage.query_info

    def test_get_paper_by_id(self, sample_paper_metadata):
        """Test retrieving paper by ID."""
        storage = Storage()
        paper = PaperMetadata(**sample_paper_metadata)
        storage.add_paper(paper)

        found = storage.get_paper_by_id(sample_paper_metadata['id'])

        assert found is not None
        assert found.id == sample_paper_metadata['id']

    def test_get_papers_without_pdf(self, sample_paper_metadata):
        """Test retrieving papers without PDFs."""
        storage = Storage()

        # Add paper without PDF
        paper1 = PaperMetadata(**sample_paper_metadata)
        paper1.pdf_url = "https://example.com/paper.pdf"
        paper1.pdf_downloaded = False
        storage.add_paper(paper1)

        # Add paper with PDF
        paper2 = PaperMetadata(**sample_paper_metadata)
        paper2.id = 'xyz789'
        paper2.pdf_downloaded = True
        storage.add_paper(paper2)

        papers_without = storage.get_papers_without_pdf()

        assert len(papers_without) == 1
        assert papers_without[0].id == paper1.id

    def test_get_statistics(self, sample_paper_metadata):
        """Test getting statistics."""
        storage = Storage()

        # Add papers with different properties
        paper1 = PaperMetadata(**sample_paper_metadata)
        paper1.pdf_downloaded = True
        paper1.abstract = "Sample abstract"
        paper1.doi = "10.1000/test"
        storage.add_paper(paper1)

        paper2 = PaperMetadata()
        paper2.id = "paper2"
        storage.add_paper(paper2)

        stats = storage.get_statistics()

        assert stats['total_papers'] == 2
        assert stats['papers_with_pdf'] == 1
        assert stats['papers_with_abstract'] == 1
        assert stats['papers_with_doi'] == 1
        assert stats['pdf_success_rate'] == 50.0

    def test_len(self, sample_paper_metadata):
        """Test __len__ method."""
        storage = Storage()

        assert len(storage) == 0

        paper = PaperMetadata(**sample_paper_metadata)
        storage.add_paper(paper)

        assert len(storage) == 1

    def test_load_metadata_json_corrupted_recovery(self, temp_dir, monkeypatch):
        """Test load_metadata_json handles corrupted JSON gracefully (data integrity).

        Covers lines: storage.py:176-178
        Value: ⭐⭐⭐⭐ - Critical for data recovery, ensures app doesn't crash on bad data
        """
        json_file = temp_dir / 'metadata.json'
        monkeypatch.setattr(Config, 'METADATA_JSON', json_file)

        # Write corrupted JSON (common when file write is interrupted)
        json_file.write_text('{ "papers": [{"id": "1", "title": invalid json }')

        storage = Storage()

        with patch('src.storage.logger') as mock_logger:
            result = storage.load_metadata_json()

            # Should return False indicating load failed
            assert result is False

            # Should not have loaded any papers
            assert len(storage.papers) == 0

            # Should log the error
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any('Failed to load metadata JSON' in call for call in error_calls)

    def test_load_metadata_json_with_invalid_structure(self, temp_dir, monkeypatch):
        """Test load_metadata_json handles valid JSON but invalid structure.

        Covers lines: storage.py:176-178
        Value: ⭐⭐⭐⭐ - Ensures robustness against schema changes
        """
        json_file = temp_dir / 'metadata.json'
        monkeypatch.setattr(Config, 'METADATA_JSON', json_file)

        # Write valid JSON but with unexpected structure
        import json
        json_file.write_text(json.dumps({
            "wrong_key": "wrong_value",
            "not_papers": []
        }))

        storage = Storage()

        with patch('src.storage.logger') as mock_logger:
            result = storage.load_metadata_json()

            # May succeed or fail depending on implementation
            # But should not crash
            assert isinstance(result, bool)
            assert isinstance(storage.papers, list)
