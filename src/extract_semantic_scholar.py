#!/usr/bin/env python3
"""
Extract papers using Semantic Scholar API.

This script executes the comprehensive extraction strategy to get
64 papers matching the original Google Scholar search criteria.
"""

import os
import json
import math
import logging
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime
from collections import Counter

from .semantic_scholar_api import SemanticScholarAPIClient
from .storage import PaperMetadata, Storage
from .downloader import PDFDownloader

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

# Setup logging
logger = logging.getLogger(__name__)


def setup_directories():
    """Create output directory structure."""
    dirs = [
        OUTPUT_DIR / "metadata",
        OUTPUT_DIR / "papers",
        OUTPUT_DIR / "queries",
        OUTPUT_DIR / "statistics",
        OUTPUT_DIR / "cache"
    ]

    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directories created at: {OUTPUT_DIR}")


def setup_logging():
    """Configure logging."""
    log_file = OUTPUT_DIR / "extraction_log.txt"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def collect_papers(api_key: Optional[str] = None) -> List[PaperMetadata]:
    """
    Collect papers from all queries.

    Args:
        api_key: Optional Semantic Scholar API key

    Returns:
        List of all papers from all queries
    """
    print("\n=== Phase 1: Data Collection ===\n")
    logger.info("Starting data collection")

    client = SemanticScholarAPIClient(api_key=api_key)
    all_papers = []

    try:
        for i, query in enumerate(QUERIES, 1):
            logger.info(f"Executing Query {i}/{len(QUERIES)}: {query}")
            print(f"Query {i}: \"{query}\"")

            try:
                papers = client.search_papers(
                    query=query,
                    year_min=YEAR_MIN,
                    year_max=YEAR_MAX,
                    max_results=PAPERS_PER_QUERY,
                    sort="citationCount"
                )

                print(f"  → Retrieved {len(papers)} papers")
                logger.info(f"Query {i} returned {len(papers)} papers")

                # Save query results
                query_file = OUTPUT_DIR / "queries" / f"query{i}_results.json"
                with open(query_file, 'w', encoding='utf-8') as f:
                    json.dump([p.__dict__ for p in papers], f, indent=2, ensure_ascii=False)

                # Tag papers with source query
                for paper in papers:
                    paper.source_query = query

                all_papers.extend(papers)

            except Exception as e:
                logger.error(f"Error in query {i}: {e}")
                print(f"  ✗ Error: {e}")
                continue

    finally:
        client.close()

    # Save all collected papers
    all_papers_file = OUTPUT_DIR / "metadata" / "all_papers.json"
    with open(all_papers_file, 'w', encoding='utf-8') as f:
        json.dump([p.__dict__ for p in all_papers], f, indent=2, ensure_ascii=False)

    print(f"\nTotal collected: {len(all_papers)} papers")
    logger.info(f"Data collection complete. Total papers: {len(all_papers)}")

    return all_papers


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    # Lowercase, remove punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', '', title.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def deduplicate_papers(papers: List[PaperMetadata]) -> List[PaperMetadata]:
    """
    Remove duplicate papers using multi-level strategy.

    Args:
        papers: List of papers to deduplicate

    Returns:
        List of unique papers
    """
    print("\n=== Phase 2: Processing - Deduplication ===\n")
    logger.info("Starting deduplication")

    seen_dois: Set[str] = set()
    seen_ids: Set[str] = set()
    seen_titles: Set[str] = set()
    unique_papers = []

    duplicates_by_doi = 0
    duplicates_by_id = 0
    duplicates_by_title = 0

    for paper in papers:
        # Check DOI
        if paper.doi and paper.doi in seen_dois:
            duplicates_by_doi += 1
            continue

        # Check paper ID
        if paper.id and paper.id in seen_ids:
            duplicates_by_id += 1
            continue

        # Check normalized title
        norm_title = normalize_title(paper.title)
        if norm_title in seen_titles:
            duplicates_by_title += 1
            continue

        # New unique paper
        if paper.doi:
            seen_dois.add(paper.doi)
        if paper.id:
            seen_ids.add(paper.id)
        seen_titles.add(norm_title)
        unique_papers.append(paper)

    print(f"Before deduplication: {len(papers)} papers")
    print(f"After deduplication: {len(unique_papers)} papers")
    print(f"  - Duplicates by DOI: {duplicates_by_doi}")
    print(f"  - Duplicates by ID: {duplicates_by_id}")
    print(f"  - Duplicates by title: {duplicates_by_title}")

    logger.info(f"Deduplication complete: {len(papers)} → {len(unique_papers)}")

    return unique_papers


def calculate_title_relevance(title: str) -> float:
    """
    Calculate relevance score 0-1 based on keyword presence in title.

    Args:
        title: Paper title

    Returns:
        Relevance score between 0 and 1
    """
    title_lower = title.lower()
    score = 0.0

    # Education context (0.5 points)
    education_terms = ["student", "learning", "education", "teaching", "course", "training", "learner"]
    if any(term in title_lower for term in education_terms):
        score += 0.5

    # Web technology topic (0.5 points)
    tech_terms = [
        "web design", "web programming", "web development",
        "html", "css", "javascript", "website", "web page",
        "web-based", "online learning", "e-learning"
    ]
    if any(term in title_lower for term in tech_terms):
        score += 0.5

    return score


def filter_by_title(papers: List[PaperMetadata], threshold: float = TITLE_RELEVANCE_THRESHOLD) -> List[PaperMetadata]:
    """
    Filter papers by title relevance.

    Args:
        papers: List of papers to filter
        threshold: Minimum relevance score

    Returns:
        List of relevant papers
    """
    print("\n=== Phase 2: Processing - Title Filtering ===\n")
    logger.info(f"Filtering by title relevance (threshold: {threshold})")

    relevant_papers = []

    for paper in papers:
        relevance = calculate_title_relevance(paper.title)
        paper.relevance_score = relevance

        if relevance >= threshold:
            relevant_papers.append(paper)

    print(f"Before title filtering: {len(papers)} papers")
    print(f"After title filtering: {len(relevant_papers)} papers")
    print(f"  - Filtered out: {len(papers) - len(relevant_papers)} papers")

    # Save filtered papers
    filtered_file = OUTPUT_DIR / "metadata" / "filtered_papers.json"
    with open(filtered_file, 'w', encoding='utf-8') as f:
        json.dump([p.__dict__ for p in relevant_papers], f, indent=2, ensure_ascii=False)

    logger.info(f"Title filtering complete: {len(papers)} → {len(relevant_papers)}")

    return relevant_papers


def calculate_paper_score(paper: PaperMetadata) -> float:
    """
    Calculate composite score for ranking.

    Factors:
    - Citation count: 50% weight
    - Recency: 30% weight
    - PDF availability: 10% weight
    - Venue quality: 10% weight

    Args:
        paper: Paper to score

    Returns:
        Composite score
    """
    score = 0.0

    # Citations (normalized log scale, max 50 points)
    if paper.citations and paper.citations > 0:
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
        "Computers & Education", "Computers and Education",
        "IEEE", "ACM", "SIGCSE",
        "Journal of Educational Technology",
        "Educational Technology & Society",
        "British Journal of Educational Technology",
        "Interactive Learning Environments"
    ]
    if paper.venue and any(venue.lower() in paper.venue.lower() for venue in known_venues):
        score += 10

    return score


def rank_papers(papers: List[PaperMetadata]) -> List[PaperMetadata]:
    """
    Rank papers by composite score.

    Args:
        papers: List of papers to rank

    Returns:
        Sorted list of papers (highest score first)
    """
    print("\n=== Phase 2: Processing - Ranking ===\n")
    logger.info("Ranking papers by composite score")

    # Calculate scores
    for paper in papers:
        paper.rank_score = calculate_paper_score(paper)

    # Sort by score (descending)
    ranked_papers = sorted(papers, key=lambda p: p.rank_score, reverse=True)

    print(f"Papers ranked: {len(ranked_papers)}")
    if ranked_papers:
        print(f"  - Top score: {ranked_papers[0].rank_score:.1f}")
        print(f"  - Median score: {ranked_papers[len(ranked_papers)//2].rank_score:.1f}")
        print(f"  - Lowest score: {ranked_papers[-1].rank_score:.1f}")

    logger.info(f"Ranking complete. Top score: {ranked_papers[0].rank_score:.1f}")

    return ranked_papers


def select_top_papers(papers: List[PaperMetadata], target: int = TARGET_PAPERS) -> List[PaperMetadata]:
    """
    Select top N papers with diversity considerations.

    Args:
        papers: Ranked list of papers
        target: Number of papers to select

    Returns:
        List of selected papers
    """
    print("\n=== Phase 2: Processing - Selection ===\n")
    logger.info(f"Selecting top {target} papers")

    if len(papers) <= target:
        print(f"Only {len(papers)} papers available (target: {target})")
        print(f"Returning all {len(papers)} papers")
        return papers

    # Simple top-N selection
    # (Diversity constraints can be added here if needed)
    selected = papers[:target]

    print(f"Selected: {len(selected)} papers")

    # Show selection statistics
    years = [p.year for p in selected if p.year]
    venues = [p.venue for p in selected if p.venue]

    print(f"  - Year range: {min(years)} - {max(years)}")
    print(f"  - Unique venues: {len(set(venues))}")
    print(f"  - With PDFs: {sum(1 for p in selected if p.pdf_url)}")

    logger.info(f"Selection complete: {len(selected)} papers")

    return selected


def download_pdfs(papers: List[PaperMetadata]):
    """
    Download PDFs for papers.

    Args:
        papers: List of papers to download PDFs for
    """
    print("\n=== Phase 3: PDF Download ===\n")
    logger.info("Starting PDF downloads")

    # Count available PDFs
    available = sum(1 for p in papers if p.pdf_url)
    print(f"PDFs available: {available}/{len(papers)}")

    if available == 0:
        print("No PDFs to download")
        logger.info("No PDFs available for download")
        return

    # Create storage and add papers
    storage = Storage()
    for paper in papers:
        storage.add_paper(paper)

    # Create downloader
    downloader = PDFDownloader(storage=storage)

    # Download PDFs
    print("Downloading...")

    # Use the downloader but copy files to our directory
    stats = {
        'total': available,
        'successful': 0,
        'failed': 0,
        'skipped': 0
    }

    pdf_dir = OUTPUT_DIR / "papers"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    from src.config import Config

    # Download using existing downloader
    download_stats = downloader.download_all()

    # Copy PDFs to our directory
    for paper in papers:
        if paper.pdf_url:
            # Get the filename that would have been used
            filename = downloader._generate_filename(paper)
            source = Path(Config.PAPERS_DIR) / filename

            if source.exists():
                dest = pdf_dir / filename
                shutil.copy2(source, dest)
                stats['successful'] += 1
            else:
                stats['failed'] += 1

    print(f"\nDownload complete:")
    print(f"  - Successful: {stats['successful']}")
    print(f"  - Failed: {stats['failed']}")
    print(f"  - Success rate: {stats['successful']/max(stats['total'], 1)*100:.1f}%")

    logger.info(f"PDF download complete. Success: {stats['successful']}/{stats['total']}")


def save_results(papers: List[PaperMetadata]):
    """
    Save final results in multiple formats.

    Args:
        papers: List of papers to save
    """
    print("\n=== Phase 4: Export ===\n")
    logger.info("Saving results")

    # Save JSON manually
    json_file = OUTPUT_DIR / "metadata" / "final_64_papers.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        # Convert papers to dictionaries
        papers_data = []
        for paper in papers:
            paper_dict = paper.__dict__.copy()
            # Add our custom fields if they exist
            if hasattr(paper, 'source_query'):
                paper_dict['source_query'] = paper.source_query
            if hasattr(paper, 'relevance_score'):
                paper_dict['relevance_score'] = paper.relevance_score
            if hasattr(paper, 'rank_score'):
                paper_dict['rank_score'] = paper.rank_score
            papers_data.append(paper_dict)

        json.dump({
            'extraction_metadata': {
                'date': datetime.now().isoformat(),
                'method': 'Semantic Scholar API',
                'queries': QUERIES,
                'filters': {
                    'year_min': YEAR_MIN,
                    'year_max': YEAR_MAX,
                    'title_relevance_threshold': TITLE_RELEVANCE_THRESHOLD
                },
                'target_count': TARGET_PAPERS,
                'final_count': len(papers)
            },
            'papers': papers_data
        }, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved: {json_file}")

    # Save CSV
    csv_file = OUTPUT_DIR / "metadata" / "final_64_papers.csv"
    import csv
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        if papers:
            # Define CSV fields
            fieldnames = ['id', 'title', 'authors', 'year', 'venue', 'citations',
                         'abstract', 'pdf_url', 'doi', 'url', 'relevance_score', 'rank_score']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for paper in papers:
                row = {
                    'id': paper.id,
                    'title': paper.title,
                    'authors': '; '.join(paper.authors) if paper.authors else '',
                    'year': paper.year,
                    'venue': paper.venue,
                    'citations': paper.citations,
                    'abstract': paper.abstract[:200] + '...' if paper.abstract and len(paper.abstract) > 200 else paper.abstract,
                    'pdf_url': paper.pdf_url,
                    'doi': paper.doi,
                    'url': paper.url,
                    'relevance_score': getattr(paper, 'relevance_score', ''),
                    'rank_score': getattr(paper, 'rank_score', '')
                }
                writer.writerow(row)

    print(f"✓ Saved: {csv_file}")

    # Generate statistics
    stats_file = OUTPUT_DIR / "statistics" / "summary.txt"
    generate_statistics(papers, stats_file)
    print(f"✓ Saved: {stats_file}")

    logger.info("Results saved successfully")


def generate_statistics(papers: List[PaperMetadata], output_file: Path):
    """
    Generate comprehensive statistics report.

    Args:
        papers: List of papers
        output_file: Path to save statistics
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("SEMANTIC SCHOLAR EXTRACTION - STATISTICS REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Papers: {len(papers)}\n\n")

        # Citation statistics
        citations = [p.citations for p in papers if p.citations]
        if citations:
            f.write("CITATION STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total citations: {sum(citations):,}\n")
            f.write(f"Average: {sum(citations)/len(citations):.1f}\n")
            f.write(f"Median: {sorted(citations)[len(citations)//2]}\n")
            f.write(f"Min: {min(citations)}\n")
            f.write(f"Max: {max(citations)}\n\n")

        # Year distribution
        years = [p.year for p in papers if p.year]
        if years:
            f.write("YEAR DISTRIBUTION\n")
            f.write("-" * 40 + "\n")
            year_counts = Counter(years)
            for year in sorted(year_counts.keys()):
                f.write(f"{year}: {year_counts[year]} papers\n")
            f.write("\n")

        # Venue distribution
        venues = [p.venue for p in papers if p.venue]
        if venues:
            f.write("TOP 10 VENUES\n")
            f.write("-" * 40 + "\n")
            venue_counts = Counter(venues)
            for venue, count in venue_counts.most_common(10):
                f.write(f"{count:2d}x {venue}\n")
            f.write(f"\nTotal unique venues: {len(venue_counts)}\n\n")

        # PDF availability
        pdfs = sum(1 for p in papers if p.pdf_url)
        f.write("PDF AVAILABILITY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Papers with PDF: {pdfs}/{len(papers)} ({pdfs/len(papers)*100:.1f}%)\n\n")

        # Top 10 most cited
        f.write("TOP 10 MOST CITED PAPERS\n")
        f.write("-" * 40 + "\n")
        sorted_papers = sorted(papers, key=lambda p: p.citations or 0, reverse=True)
        for i, paper in enumerate(sorted_papers[:10], 1):
            f.write(f"{i}. {paper.title}\n")
            f.write(f"   Citations: {paper.citations} | Year: {paper.year}\n\n")


def validate_results(papers: List[PaperMetadata]):
    """
    Validate extraction results.

    Args:
        papers: List of papers to validate
    """
    print("\n=== Phase 5: Validation ===\n")
    logger.info("Running validation checks")

    checks_passed = 0
    checks_total = 0

    # Check 1: Paper count
    checks_total += 1
    if len(papers) == TARGET_PAPERS:
        print(f"✓ Total papers: {len(papers)}")
        checks_passed += 1
    else:
        print(f"⚠ Total papers: {len(papers)} (target: {TARGET_PAPERS})")

    # Check 2: Year range
    checks_total += 1
    years = [p.year for p in papers if p.year]
    if years and min(years) >= YEAR_MIN and max(years) <= YEAR_MAX:
        print(f"✓ Year range: {min(years)}-{max(years)}")
        checks_passed += 1
    else:
        print(f"⚠ Year range: {min(years) if years else 'N/A'}-{max(years) if years else 'N/A'}")

    # Check 3: No duplicates (by title)
    checks_total += 1
    titles = [normalize_title(p.title) for p in papers]
    if len(titles) == len(set(titles)):
        print(f"✓ Duplicates: 0")
        checks_passed += 1
    else:
        print(f"⚠ Duplicates: {len(titles) - len(set(titles))}")

    # Check 4: Title relevance
    checks_total += 1
    relevance_scores = [getattr(p, 'relevance_score', 0) for p in papers]
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
    if avg_relevance >= TITLE_RELEVANCE_THRESHOLD:
        print(f"✓ Title relevance: avg {avg_relevance:.2f}")
        checks_passed += 1
    else:
        print(f"⚠ Title relevance: avg {avg_relevance:.2f} (threshold: {TITLE_RELEVANCE_THRESHOLD})")

    # Check 5: Citations
    checks_total += 1
    citations = [p.citations for p in papers if p.citations and p.citations > 0]
    if len(citations) / len(papers) > 0.8:
        print(f"✓ Papers with citations: {len(citations)}/{len(papers)} ({len(citations)/len(papers)*100:.1f}%)")
        checks_passed += 1
    else:
        print(f"⚠ Papers with citations: {len(citations)}/{len(papers)} ({len(citations)/len(papers)*100:.1f}%)")

    # Check 6: Unique venues
    checks_total += 1
    venues = set(p.venue for p in papers if p.venue)
    if len(venues) >= 15:
        print(f"✓ Unique venues: {len(venues)}")
        checks_passed += 1
    else:
        print(f"⚠ Unique venues: {len(venues)} (target: ≥15)")

    # Check 7: PDFs
    checks_total += 1
    pdfs = sum(1 for p in papers if p.pdf_url)
    if pdfs / len(papers) >= 0.2:
        print(f"✓ PDFs available: {pdfs}/{len(papers)} ({pdfs/len(papers)*100:.1f}%)")
        checks_passed += 1
    else:
        print(f"⚠ PDFs available: {pdfs}/{len(papers)} ({pdfs/len(papers)*100:.1f}%)")

    print(f"\nValidation: {checks_passed}/{checks_total} checks passed")

    if checks_passed == checks_total:
        print("✓ All validation checks passed!")
        logger.info("Validation complete: All checks passed")
    else:
        print("⚠ Some validation checks failed")
        logger.warning(f"Validation complete: {checks_passed}/{checks_total} checks passed")


def main(api_key: Optional[str] = None):
    """
    Main execution function.

    Args:
        api_key: Optional Semantic Scholar API key
    """
    print("\n" + "=" * 60)
    print("SEMANTIC SCHOLAR PAPER EXTRACTION")
    print("=" * 60)
    print()
    print(f"Configuration:")
    print(f"  - Queries: {len(QUERIES)}")
    print(f"  - Year range: {YEAR_MIN}-{YEAR_MAX}")
    print(f"  - Target papers: {TARGET_PAPERS}")
    print(f"  - Title relevance threshold: {TITLE_RELEVANCE_THRESHOLD}")
    print(f"  - Output: {OUTPUT_DIR}")
    print()

    setup_directories()
    setup_logging()

    logger.info("=" * 60)
    logger.info("Starting Semantic Scholar extraction")
    logger.info(f"Target: {TARGET_PAPERS} papers from {YEAR_MIN}-{YEAR_MAX}")

    try:
        # Phase 1: Collection
        all_papers = collect_papers(api_key=api_key)

        if not all_papers:
            print("\n✗ No papers collected. Exiting.")
            logger.error("No papers collected")
            return

        # Phase 2: Processing
        unique_papers = deduplicate_papers(all_papers)
        relevant_papers = filter_by_title(unique_papers)

        if len(relevant_papers) < TARGET_PAPERS:
            print(f"\n⚠ Warning: Only {len(relevant_papers)} relevant papers found (target: {TARGET_PAPERS})")
            print(f"  Lowering threshold and retrying...")
            relevant_papers = filter_by_title(unique_papers, threshold=0.5)

        ranked_papers = rank_papers(relevant_papers)
        final_papers = select_top_papers(ranked_papers, TARGET_PAPERS)

        # Phase 3: Download PDFs
        download_pdfs(final_papers)

        # Phase 4: Export
        save_results(final_papers)

        # Phase 5: Validation
        validate_results(final_papers)

        print("\n" + "=" * 60)
        print("EXTRACTION COMPLETE!")
        print("=" * 60)
        print(f"\nResults saved to: {OUTPUT_DIR}")
        print(f"Total papers: {len(final_papers)}")
        print()

        logger.info(f"Extraction complete! {len(final_papers)} papers extracted.")

    except Exception as e:
        print(f"\n✗ Error during extraction: {e}")
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys

    # Check for API key argument
    api_key = sys.argv[1] if len(sys.argv) > 1 else None

    if api_key:
        print(f"Using API key: {api_key[:10]}...")
    else:
        print("No API key provided - using rate-limited access (1 req/sec)")
        print("Get a free API key at: https://www.semanticscholar.org/product/api")
        print()

    main(api_key=api_key)
