# Semantic Scholar API Extraction - Ultrathink Analysis

**Date**: 2025-11-16
**Purpose**: Comprehensive analysis for extracting ~64 papers using Semantic Scholar API
**Branch**: claude/plan-development-strategy-01WeBFDUixTJVAaQCv8nUdS9

---

## 🎯 Objective

Extract comprehensive metadata and PDFs for papers matching the original search criteria:
- **Topic**: Student learning with web design/programming/development/HTML
- **Year range**: 2007-present
- **Target count**: ~64 papers
- **Method**: Semantic Scholar Academic Graph API

---

## 📋 Original Search Criteria Analysis

### Google Scholar Query (Original)
```
allintitle: student "web design" OR "web programming" OR "web development" OR HTML
Year: 2007-present
Language: English
Exclude: citations, patents
```

### Translation to Semantic Scholar API

**Challenge**: Semantic Scholar doesn't support Google's `allintitle:` operator

**Solutions**:
1. **Approach A**: Search for keywords, filter by title relevance manually
2. **Approach B**: Use multiple specific queries and merge results
3. **Approach C**: Search broadly, then filter programmatically

**Recommended**: Approach B (Multiple Specific Queries)

---

## 🔍 Query Strategy

### Query Set Design

To match the original intent, we'll run **4 separate searches** and merge unique results:

**Query 1**: Student + Web Design
```python
query='student "web design"'
```

**Query 2**: Student + Web Programming
```python
query='student "web programming"'
```

**Query 3**: Student + Web Development
```python
query='student "web development"'
```

**Query 4**: Student + HTML (Education context)
```python
query='student HTML learning OR education'
```

### Expected Coverage

| Query | Expected Results | Relevance |
|-------|-----------------|-----------|
| student "web design" | ~1000+ | High |
| student "web programming" | ~500+ | High |
| student "web development" | ~800+ | High |
| student HTML learning | ~2000+ | Medium |

**Total unique papers**: Expected ~3000+, will filter to top 64 by citations

---

## 🏗️ Implementation Architecture

### Data Flow

```
┌─────────────────────────┐
│ Query Definitions       │
│ - 4 specific queries    │
│ - Year filter: 2007+    │
│ - Sort: citationCount   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Semantic Scholar API    │
│ - Rate limited requests │
│ - Batch retrieval       │
│ - JSON responses        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Result Merging          │
│ - Deduplicate by DOI    │
│ - Deduplicate by title  │
│ - Rank by citations     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Post-Processing Filter  │
│ - Title relevance check │
│ - Year verification     │
│ - Quality threshold     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Top 64 Selection        │
│ - Sort by citations     │
│ - Take top 64           │
│ - Ensure diversity      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Storage                 │
│ - data/semantic_scholar/│
│   - metadata.json       │
│   - metadata.csv        │
│   - papers/ (PDFs)      │
│   - query_log.txt       │
└─────────────────────────┘
```

### Module Structure

```python
# New extraction script
src/extract_semantic_scholar.py
    ├── load_queries()           # Define 4 queries
    ├── fetch_papers_batch()     # API calls for each query
    ├── deduplicate_papers()     # Remove duplicates
    ├── filter_by_title()        # Ensure title relevance
    ├── rank_and_select()        # Get top 64
    ├── download_pdfs()          # Get open access PDFs
    └── save_results()           # Store in dedicated folder
```

---

## 🔬 Deduplication Strategy

### Primary Key Hierarchy

1. **DOI** (Digital Object Identifier) - Most reliable
   - If two papers have same DOI → duplicate

2. **Semantic Scholar Paper ID** - Platform-specific
   - If same paperId → duplicate

3. **Title similarity** - Fuzzy matching
   - Normalize: lowercase, remove punctuation
   - Compare: Levenshtein distance < 5 → likely duplicate

4. **Author + Year combination** - Weak signal
   - Same first author + year + similar title → investigate

### Implementation

```python
def deduplicate_papers(papers: List[PaperMetadata]) -> List[PaperMetadata]:
    """Remove duplicate papers using multi-level strategy."""
    seen_dois = set()
    seen_ids = set()
    seen_titles = set()
    unique_papers = []

    for paper in papers:
        # Check DOI
        if paper.doi and paper.doi in seen_dois:
            continue

        # Check paper ID
        if paper.id and paper.id in seen_ids:
            continue

        # Check normalized title
        norm_title = normalize_title(paper.title)
        if norm_title in seen_titles:
            continue

        # New unique paper
        if paper.doi:
            seen_dois.add(paper.doi)
        if paper.id:
            seen_ids.add(paper.id)
        seen_titles.add(norm_title)
        unique_papers.append(paper)

    return unique_papers
```

---

## 🎯 Title Relevance Filtering

### Problem

Semantic Scholar search returns papers where keywords appear in abstract/body, not just title.
We need to filter for title-only matches to replicate `allintitle:` behavior.

### Solution: Title Matching Score

```python
def calculate_title_relevance(title: str) -> float:
    """
    Calculate relevance score 0-1 based on keyword presence in title.

    Required keywords:
    - "student" OR "learning" OR "education" (at least 1)

    Topic keywords (at least 1):
    - "web design"
    - "web programming"
    - "web development"
    - "HTML"
    - "CSS"
    - "JavaScript"
    """
    title_lower = title.lower()
    score = 0.0

    # Education context (0.5 points)
    education_terms = ["student", "learning", "education", "teaching", "course"]
    if any(term in title_lower for term in education_terms):
        score += 0.5

    # Web technology topic (0.5 points)
    tech_terms = [
        "web design", "web programming", "web development",
        "html", "css", "javascript", "website", "web page"
    ]
    if any(term in title_lower for term in tech_terms):
        score += 0.5

    return score

# Filter threshold
TITLE_RELEVANCE_THRESHOLD = 0.8  # Must have both education + tech terms
```

### Expected Filtering Impact

- **Before filtering**: ~200 papers (from 4 queries)
- **After filtering**: ~80-100 papers with high title relevance
- **After top-64 selection**: Exactly 64 papers

---

## 📊 Ranking Strategy

### Multi-Factor Ranking

Instead of citations alone, use **weighted score**:

```python
def calculate_paper_score(paper: PaperMetadata) -> float:
    """
    Calculate composite score for ranking.

    Factors:
    - Citation count: 50% weight
    - Recency: 30% weight
    - PDF availability: 10% weight
    - Venue quality: 10% weight
    """
    score = 0.0

    # Citations (normalized log scale, max 50 points)
    if paper.citations > 0:
        citation_score = min(math.log10(paper.citations + 1) * 10, 50)
        score += citation_score

    # Recency (newer papers get bonus, max 30 points)
    if paper.year:
        years_old = 2025 - paper.year
        recency_score = max(0, 30 - years_old)
        score += recency_score

    # PDF availability (10 points if available)
    if paper.pdf_url:
        score += 10

    # Venue quality (10 points for known venues)
    known_venues = [
        "Computers & Education", "IEEE", "ACM", "SIGCSE",
        "Journal of Educational Technology", "Educational Technology & Society"
    ]
    if any(venue.lower() in paper.venue.lower() for venue in known_venues):
        score += 10

    return score
```

### Diversity Consideration

After ranking, ensure diversity:
- No more than 5 papers from same venue
- No more than 10 papers from same year
- At least 2 papers from each query group

---

## 💾 Storage Structure

### Directory Layout

```
data/semantic_scholar/
├── metadata/
│   ├── all_papers.json           # All fetched papers before filtering
│   ├── filtered_papers.json      # After title relevance filter
│   ├── final_64_papers.json      # Final selection
│   ├── final_64_papers.csv       # CSV export
│   └── extraction_log.txt        # Detailed log
├── papers/
│   ├── Author1_2023_Title.pdf
│   ├── Author2_2021_Title.pdf
│   └── ...
├── queries/
│   ├── query1_results.json       # Results from "student web design"
│   ├── query2_results.json       # Results from "student web programming"
│   ├── query3_results.json       # Results from "student web development"
│   └── query4_results.json       # Results from "student HTML"
└── statistics/
    ├── summary.txt               # Overall statistics
    ├── citation_distribution.txt # Citation analysis
    └── year_distribution.txt     # Temporal analysis
```

### Metadata Format

**JSON Structure**:
```json
{
  "extraction_metadata": {
    "date": "2025-11-16",
    "method": "Semantic Scholar API",
    "queries": [
      "student \"web design\"",
      "student \"web programming\"",
      "student \"web development\"",
      "student HTML learning OR education"
    ],
    "filters": {
      "year_min": 2007,
      "year_max": 2025,
      "title_relevance_threshold": 0.8
    },
    "total_fetched": 234,
    "after_dedup": 156,
    "after_filter": 89,
    "final_count": 64
  },
  "papers": [
    {
      "id": "abc123",
      "title": "Student perceptions of web design...",
      "authors": ["Smith, J.", "Johnson, M."],
      "year": 2010,
      "venue": "Computers & Education",
      "citations": 152,
      "abstract": "...",
      "pdf_url": "https://...",
      "doi": "10.1016/...",
      "relevance_score": 1.0,
      "rank_score": 78.5,
      "source_query": "student \"web design\""
    }
  ]
}
```

---

## ⚡ Performance Optimization

### Rate Limiting Strategy

**Without API Key**:
- Rate: 1 request/second
- 4 queries × ~3 requests each = 12 requests
- Time: ~12 seconds

**With Free API Key**:
- Rate: 100 requests/second
- 4 queries × ~3 requests each = 12 requests
- Time: ~1 second

**Recommendation**: Use API key for faster execution

### Caching Strategy

```python
# Cache API responses to avoid re-fetching
CACHE_DIR = "data/semantic_scholar/cache/"

def get_cached_or_fetch(query: str, **params):
    """Check cache before making API call."""
    cache_key = hashlib.md5(
        f"{query}{params}".encode()
    ).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        # Cache hit
        with open(cache_file) as f:
            return json.load(f)

    # Cache miss - fetch from API
    result = api_client.search_papers(query, **params)

    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(result, f)

    return result
```

---

## 🔍 Quality Assurance Checks

### Pre-Flight Checks

Before running extraction:
1. ✅ Test API connectivity
2. ✅ Verify rate limits
3. ✅ Check disk space (need ~500 MB for PDFs)
4. ✅ Validate query syntax
5. ✅ Ensure output directories exist

### Post-Extraction Validation

After extraction:
1. ✅ Verify count = 64 papers
2. ✅ Check year range (all >= 2007)
3. ✅ Validate no duplicates (by DOI, title)
4. ✅ Ensure title relevance (all scores >= threshold)
5. ✅ Check citation distribution (not all 0)
6. ✅ Verify venue diversity
7. ✅ Count PDF success rate

### Expected Validation Results

```
✅ Total papers: 64
✅ Year range: 2007-2025
✅ Duplicate DOIs: 0
✅ Duplicate titles: 0
✅ Avg relevance score: >0.85
✅ Papers with citations: >90%
✅ Unique venues: >20
✅ PDFs available: ~20-30 (30-50%)
```

---

## 🚨 Risk Assessment & Mitigation

### High Risks

**Risk 1: Query returns too few papers**
- **Probability**: Medium (30%)
- **Impact**: Cannot reach 64 papers
- **Mitigation**:
  - Relax title relevance threshold to 0.6
  - Add more query variations
  - Include papers with keywords in abstract

**Risk 2: High duplicate rate across queries**
- **Probability**: High (60%)
- **Impact**: Need more queries to reach 64 unique
- **Mitigation**:
  - Already planned with deduplication
  - Have 4 diverse queries
  - Can add more specific queries if needed

**Risk 3: API rate limiting even with key**
- **Probability**: Low (10%)
- **Impact**: Slower extraction
- **Mitigation**:
  - Built-in retry logic
  - Respect rate limits
  - Cache all responses

### Medium Risks

**Risk 4: Low PDF availability**
- **Probability**: High (70%)
- **Impact**: Fewer PDFs than expected
- **Expected**: ~20-30 PDFs out of 64
- **Mitigation**:
  - Accept that not all papers have open access
  - Document which papers lack PDFs
  - Provide DOI links for paid access

**Risk 5: Title relevance filter too strict**
- **Probability**: Medium (40%)
- **Impact**: Filters out too many papers
- **Mitigation**:
  - Adjustable threshold (parameterized)
  - Manual review of filtered papers
  - Keep all data for re-filtering

### Low Risks

**Risk 6: Network failures**
- **Probability**: Low (5%)
- **Impact**: Partial extraction
- **Mitigation**:
  - Retry logic (already implemented)
  - Save results incrementally
  - Resume capability

---

## 📈 Success Metrics

### Primary Metrics

| Metric | Target | Minimum Acceptable |
|--------|--------|-------------------|
| Total papers | 64 | 50 |
| Year coverage | 2007-2025 | 2007-2025 |
| Title relevance | >85% | >70% |
| Papers with citations | >90% | >80% |
| Unique venues | >20 | >15 |
| PDFs available | >30% | >20% |

### Secondary Metrics

| Metric | Target | Nice to Have |
|--------|--------|--------------|
| Avg citations | >50 | >100 |
| Papers from top venues | >20% | >30% |
| Geographic diversity | >5 countries | >10 countries |
| Year diversity | All years represented | Balanced distribution |

### Quality Metrics

| Metric | Target | Validation Method |
|--------|--------|------------------|
| Zero duplicates | 100% | DOI + title check |
| Valid years | 100% | Range check 2007-2025 |
| Valid DOIs | >80% | Format validation |
| Complete metadata | >95% | All required fields |

---

## 🔄 Execution Plan

### Phase 1: Setup (2 minutes)

1. Create directory structure
2. Initialize logging
3. Test API connectivity
4. Load query definitions

### Phase 2: Data Collection (5-10 minutes)

1. Execute Query 1: "student web design"
   - Fetch up to 100 papers, sorted by citations
   - Save raw results to query1_results.json

2. Execute Query 2: "student web programming"
   - Fetch up to 100 papers, sorted by citations
   - Save raw results to query2_results.json

3. Execute Query 3: "student web development"
   - Fetch up to 100 papers, sorted by citations
   - Save raw results to query3_results.json

4. Execute Query 4: "student HTML learning"
   - Fetch up to 100 papers, sorted by citations
   - Save raw results to query4_results.json

**Expected**: ~400 total papers (with duplicates)

### Phase 3: Processing (2 minutes)

1. Load all query results
2. Merge into single list
3. Deduplicate by DOI/ID/title
4. Filter by title relevance (threshold: 0.8)
5. Calculate ranking scores
6. Sort by score
7. Select top 64

**Expected**: 64 unique, relevant, highly-cited papers

### Phase 4: PDF Download (10-15 minutes)

1. For each of 64 papers:
   - Check if pdf_url exists
   - Download PDF (with rate limiting)
   - Verify PDF integrity
   - Save with clean filename

**Expected**: ~20-30 successful downloads

### Phase 5: Export & Validation (1 minute)

1. Save final_64_papers.json
2. Save final_64_papers.csv
3. Generate statistics report
4. Run validation checks
5. Create summary.txt

### Total Time: ~20-30 minutes

---

## 📝 Implementation Code Structure

### Main Script: `src/extract_semantic_scholar.py`

```python
#!/usr/bin/env python3
"""
Extract papers using Semantic Scholar API.

This script executes the comprehensive extraction strategy to get
64 papers matching the original Google Scholar search criteria.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .semantic_scholar_api import SemanticScholarAPIClient
from .storage import PaperMetadata, Storage

# Configuration
QUERIES = [
    'student "web design"',
    'student "web programming"',
    'student "web development"',
    'student HTML learning OR education'
]

YEAR_MIN = 2007
YEAR_MAX = 2025
PAPERS_PER_QUERY = 100
TARGET_PAPERS = 64
TITLE_RELEVANCE_THRESHOLD = 0.8

OUTPUT_DIR = Path("data/semantic_scholar")

def main():
    """Main execution function."""
    setup_directories()
    setup_logging()

    logger.info("Starting Semantic Scholar extraction")

    # Phase 1: Collection
    all_papers = collect_papers()

    # Phase 2: Processing
    unique_papers = deduplicate_papers(all_papers)
    relevant_papers = filter_by_title(unique_papers)
    ranked_papers = rank_papers(relevant_papers)
    final_papers = select_top_papers(ranked_papers, TARGET_PAPERS)

    # Phase 3: Download PDFs
    download_pdfs(final_papers)

    # Phase 4: Export
    save_results(final_papers)

    # Phase 5: Validation
    validate_results(final_papers)

    logger.info(f"Extraction complete! {len(final_papers)} papers extracted.")

if __name__ == "__main__":
    main()
```

---

## 🎯 Expected Output

### Console Output

```
=== Semantic Scholar Paper Extraction ===

Configuration:
- Queries: 4
- Year range: 2007-2025
- Target papers: 64
- Title relevance threshold: 0.8

Phase 1: Data Collection
✓ Query 1: "student web design" → 87 papers
✓ Query 2: "student web programming" → 54 papers
✓ Query 3: "student web development" → 76 papers
✓ Query 4: "student HTML learning" → 123 papers
Total collected: 340 papers

Phase 2: Processing
✓ Deduplication: 340 → 198 unique papers
✓ Title filtering: 198 → 91 relevant papers
✓ Ranking and selection: 91 → 64 top papers

Phase 3: PDF Download
✓ Downloading PDFs: 28/64 available
✓ Downloaded: 28 PDFs (43.8%)
✓ Failed: 0
✓ Not available: 36

Phase 4: Export
✓ Saved: data/semantic_scholar/metadata/final_64_papers.json
✓ Saved: data/semantic_scholar/metadata/final_64_papers.csv
✓ Saved: data/semantic_scholar/statistics/summary.txt

Phase 5: Validation
✓ Total papers: 64
✓ Year range: 2007-2024 ✓
✓ Duplicates: 0 ✓
✓ Title relevance: avg 0.92 ✓
✓ Citations: avg 76, median 48 ✓
✓ Unique venues: 34 ✓
✓ PDFs: 28 (43.8%) ✓

=== Extraction Successful! ===
Results saved to: data/semantic_scholar/
```

---

## 📊 Expected Statistics

### Citation Distribution

```
Min: 0
Q1: 24
Median: 48
Q3: 89
Max: 456
Mean: 76
Total: 4,864

Top 10 most cited:
1. "Teaching Web Development..." (456 citations)
2. "Student Engagement in Web Design..." (342 citations)
3. "HTML5 in Education..." (298 citations)
...
```

### Year Distribution

```
2007-2010: 8 papers (12.5%)
2011-2015: 16 papers (25.0%)
2016-2020: 24 papers (37.5%)
2021-2025: 16 papers (25.0%)
```

### Venue Distribution

```
Top venues:
- Computers & Education: 8 papers
- IEEE Transactions: 6 papers
- ACM Conference Proceedings: 5 papers
- Educational Technology & Society: 4 papers
- Others: 41 papers
```

---

## ✅ Definition of Done

Extraction is considered complete when:

1. ✅ Exactly 64 papers extracted
2. ✅ All papers from year range 2007-2025
3. ✅ Zero duplicate papers (verified by DOI + title)
4. ✅ All papers have title relevance score >= 0.8
5. ✅ All metadata fields populated (title, authors, year)
6. ✅ Results saved in 3 formats:
   - JSON (machine-readable)
   - CSV (spreadsheet-compatible)
   - TXT (human-readable summary)
7. ✅ PDFs downloaded where available (>20%)
8. ✅ Validation checks all pass
9. ✅ Statistics generated
10. ✅ Committed to git and pushed

---

## 🚀 Next Steps After Extraction

### Immediate

1. Review extracted papers manually
2. Verify relevance of top 10 papers
3. Check for any obvious missing important papers
4. Update README with new approach

### Future Enhancements

1. Add CLI integration for Semantic Scholar
2. Implement hybrid approach (Semantic Scholar + manual Google Scholar)
3. Add more data sources (CrossRef, CORE)
4. Create visualization of citation network
5. Generate bibliography in multiple formats (BibTeX, APA, etc.)

---

## 📚 References

- [Semantic Scholar API Documentation](https://api.semanticscholar.org/api-docs/)
- [Semantic Scholar Tutorial](https://www.semanticscholar.org/product/api/tutorial)
- [Original Project Requirements](CLAUDE.md)
- [Production Run Report](PRODUCTION_RUN_REPORT.md)
- [API Comparison Analysis](SEMANTIC_SCHOLAR_COMPARISON.md)

---

**Analysis Complete**: 2025-11-16
**Status**: Ready for implementation
**Estimated Time**: 20-30 minutes
**Expected Success Rate**: 95%+
**Risk Level**: Low
