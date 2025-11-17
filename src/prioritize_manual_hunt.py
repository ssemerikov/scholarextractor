#!/usr/bin/env python3
"""
Prioritize papers for manual PDF acquisition.

This script identifies the top papers by value and generates a manual
acquisition checklist for Tier 2 methods (ResearchGate, Google Scholar, etc.)
"""

import json
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

# Paths
DATA_DIR = Path("data/semantic_scholar")
METADATA_FILE = DATA_DIR / "metadata" / "final_64_papers.json"
OUTPUT_FILE = DATA_DIR / "metadata" / "manual_hunt_priorities.txt"


@dataclass
class PaperPriority:
    """Paper with priority score."""
    id: str
    title: str
    authors: List[str]
    year: int
    venue: str
    citations: int
    doi: str
    url: str
    has_pdf: bool
    priority_score: float
    priority_reason: str


def calculate_priority_score(paper: Dict) -> tuple[float, str]:
    """
    Calculate priority score for manual PDF hunting.

    Higher scores = higher priority to find.

    Factors:
    - Citation count: 40%
    - Recency: 30%
    - Venue quality: 20%
    - Has DOI: 10%

    Returns:
        Tuple of (score, reason)
    """
    score = 0.0
    reasons = []

    # Citations (max 40 points)
    citations = paper.get('citations', 0) or 0
    if citations > 100:
        citation_score = 40
        reasons.append(f"highly cited ({citations})")
    elif citations > 50:
        citation_score = 30
        reasons.append(f"well cited ({citations})")
    elif citations > 10:
        citation_score = 20
    else:
        citation_score = 10

    score += citation_score

    # Recency (max 30 points)
    year = paper.get('year', 0) or 0
    if year >= 2023:
        recency_score = 30
        reasons.append("recent paper")
    elif year >= 2020:
        recency_score = 25
    elif year >= 2015:
        recency_score = 15
    elif year >= 2010:
        recency_score = 10
    else:
        recency_score = 5

    score += recency_score

    # Venue quality (max 20 points)
    venue = paper.get('venue', '').lower()
    quality_venues = [
        'computers & education', 'computers and education',
        'ieee', 'acm', 'sigcse',
        'journal of educational technology',
        'educational technology & society',
        'british journal of educational technology'
    ]

    if any(q in venue for q in quality_venues):
        score += 20
        reasons.append("quality venue")
    elif venue:
        score += 10

    # Has DOI (max 10 points)
    if paper.get('doi'):
        score += 10
        reasons.append("has DOI")

    reason = ", ".join(reasons) if reasons else "low priority"
    return score, reason


def load_and_prioritize() -> List[PaperPriority]:
    """Load papers and calculate priorities."""
    with open(METADATA_FILE) as f:
        data = json.load(f)

    papers_with_priority = []

    for paper_dict in data['papers']:
        # Skip papers that already have PDFs
        has_pdf = bool(paper_dict.get('pdf_url'))

        priority_score, priority_reason = calculate_priority_score(paper_dict)

        paper_priority = PaperPriority(
            id=paper_dict.get('id', ''),
            title=paper_dict.get('title', ''),
            authors=paper_dict.get('authors', []),
            year=paper_dict.get('year', 0),
            venue=paper_dict.get('venue', ''),
            citations=paper_dict.get('citations', 0) or 0,
            doi=paper_dict.get('doi', ''),
            url=paper_dict.get('url', ''),
            has_pdf=has_pdf,
            priority_score=priority_score,
            priority_reason=priority_reason
        )

        papers_with_priority.append(paper_priority)

    # Sort by priority score (descending)
    papers_with_priority.sort(key=lambda p: p.priority_score, reverse=True)

    return papers_with_priority


def generate_manual_hunt_guide(papers: List[PaperPriority]):
    """Generate comprehensive manual hunt guide."""

    # Filter to papers without PDFs
    missing_pdfs = [p for p in papers if not p.has_pdf]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("MANUAL PDF HUNT - PRIORITY CHECKLIST\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Generated: {Path(OUTPUT_FILE).name}\n")
        f.write(f"Total papers without PDFs: {len(missing_pdfs)}\n")
        f.write(f"Papers with PDFs: {len(papers) - len(missing_pdfs)}\n\n")

        f.write("Instructions:\n")
        f.write("-" * 80 + "\n")
        f.write("1. Start with highest priority papers (top 20 recommended)\n")
        f.write("2. For each paper, try sources in this order:\n")
        f.write("   a) Google Scholar - search title, look for [PDF] links\n")
        f.write("   b) ResearchGate - search title, request from author\n")
        f.write("   c) Author website - Google 'FirstAuthor university'\n")
        f.write("   d) Publisher website - use DOI link\n")
        f.write("3. Mark papers as you find them\n")
        f.write("4. Save PDFs with format: Author_Year_Title.pdf\n\n")

        # TOP 20 HIGH PRIORITY
        f.write("=" * 80 + "\n")
        f.write("TOP 20 HIGH-PRIORITY PAPERS\n")
        f.write("=" * 80 + "\n\n")

        for i, paper in enumerate(missing_pdfs[:20], 1):
            f.write(f"[{i:2d}] Priority Score: {paper.priority_score:.0f}/100 ({paper.priority_reason})\n")
            f.write(f"     Title: {paper.title}\n")

            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" et al. ({len(paper.authors)} total)"
            f.write(f"     Authors: {authors_str}\n")

            f.write(f"     Year: {paper.year} | Citations: {paper.citations}\n")
            f.write(f"     Venue: {paper.venue}\n")

            if paper.doi:
                f.write(f"     DOI: https://doi.org/{paper.doi}\n")

            f.write(f"     Semantic Scholar: {paper.url}\n")

            # Search links
            title_encoded = paper.title.replace(' ', '+')
            f.write(f"\n     Quick Links:\n")
            f.write(f"     - Google Scholar: https://scholar.google.com/scholar?q={title_encoded}\n")
            f.write(f"     - ResearchGate: https://www.researchgate.net/search/publication?q={title_encoded}\n")

            if paper.authors:
                first_author = paper.authors[0].replace(' ', '+')
                f.write(f"     - Author Search: https://scholar.google.com/scholar?q={first_author}\n")

            f.write(f"\n     [ ] Found PDF\n")
            f.write(f"     [ ] Downloaded\n")
            f.write("\n" + "-" * 80 + "\n\n")

        # NEXT 20 MEDIUM PRIORITY
        f.write("\n" + "=" * 80 + "\n")
        f.write("NEXT 20 MEDIUM-PRIORITY PAPERS\n")
        f.write("=" * 80 + "\n\n")

        for i, paper in enumerate(missing_pdfs[20:40], 21):
            f.write(f"[{i:2d}] {paper.title[:70]}...\n")
            f.write(f"     Score: {paper.priority_score:.0f} | Year: {paper.year} | Citations: {paper.citations}\n")
            if paper.doi:
                f.write(f"     DOI: https://doi.org/{paper.doi}\n")
            f.write(f"     [ ] Found\n\n")

        # REMAINING LOW PRIORITY
        if len(missing_pdfs) > 40:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"REMAINING {len(missing_pdfs) - 40} LOW-PRIORITY PAPERS\n")
            f.write("=" * 80 + "\n\n")

            for i, paper in enumerate(missing_pdfs[40:], 41):
                f.write(f"[{i:2d}] {paper.title[:60]}... (Score: {paper.priority_score:.0f})\n")

        # STATISTICS
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("STATISTICS\n")
        f.write("=" * 80 + "\n\n")

        # Priority distribution
        high_priority = sum(1 for p in missing_pdfs if p.priority_score >= 70)
        medium_priority = sum(1 for p in missing_pdfs if 50 <= p.priority_score < 70)
        low_priority = sum(1 for p in missing_pdfs if p.priority_score < 50)

        f.write(f"Priority Distribution:\n")
        f.write(f"  High (≥70):   {high_priority} papers\n")
        f.write(f"  Medium (50-69): {medium_priority} papers\n")
        f.write(f"  Low (<50):    {low_priority} papers\n\n")

        # Papers with DOIs
        with_doi = sum(1 for p in missing_pdfs if p.doi)
        f.write(f"Papers with DOI: {with_doi}/{len(missing_pdfs)} ({with_doi/len(missing_pdfs)*100:.1f}%)\n\n")

        # Year distribution
        years = {}
        for p in missing_pdfs:
            year = p.year or 0
            years[year] = years.get(year, 0) + 1

        f.write(f"Year Distribution:\n")
        for year in sorted(years.keys(), reverse=True):
            if year > 0:
                f.write(f"  {year}: {years[year]} papers\n")

        # TIPS
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("MANUAL SEARCH TIPS\n")
        f.write("=" * 80 + "\n\n")

        tips = [
            "Google Scholar:",
            "  - Use exact title in quotes",
            "  - Look for [PDF] link on right side",
            "  - Check 'All versions' for institutional repos",
            "",
            "ResearchGate:",
            "  - Search by exact title",
            "  - Use 'Request full-text' button",
            "  - Check author profiles",
            "",
            "Author Websites:",
            "  - Google 'FirstAuthor LastAuthor university'",
            "  - Check personal/lab websites",
            "  - Look for 'Publications' or 'Papers' page",
            "",
            "Publisher Websites:",
            "  - Use DOI link to go to publisher",
            "  - Look for 'Download PDF' or 'Free PDF'",
            "  - Check if paper is 'gold open access'",
            "",
            "Institutional Repositories:",
            "  - Extract university from author affiliation",
            "  - Search '{University} institutional repository'",
            "  - Try variations (DSpace, EPrints, etc.)",
            "",
            "Email Authors:",
            "  - Find email from author profile",
            "  - Polite request with research context",
            "  - Response rate ~30% within 1 week"
        ]

        for tip in tips:
            f.write(f"{tip}\n")

        f.write("\n" + "=" * 80 + "\n")


def print_summary(papers: List[PaperPriority]):
    """Print summary to console."""
    missing_pdfs = [p for p in papers if not p.has_pdf]

    print("\n" + "=" * 80)
    print("MANUAL PDF HUNT - PRIORITIES GENERATED")
    print("=" * 80)
    print()
    print(f"Total papers: {len(papers)}")
    print(f"Papers with PDFs: {len(papers) - len(missing_pdfs)} ({(len(papers)-len(missing_pdfs))/len(papers)*100:.1f}%)")
    print(f"Papers WITHOUT PDFs: {len(missing_pdfs)} ({len(missing_pdfs)/len(papers)*100:.1f}%)")
    print()

    # Show top 10
    print("TOP 10 PRIORITY PAPERS:")
    print("-" * 80)
    for i, paper in enumerate(missing_pdfs[:10], 1):
        print(f"{i:2d}. {paper.title[:60]}...")
        print(f"    Score: {paper.priority_score:.0f} | Year: {paper.year} | Citations: {paper.citations}")
        print(f"    Reason: {paper.priority_reason}")
        print()

    print("=" * 80)
    print(f"Full checklist saved to: {OUTPUT_FILE}")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Open the checklist file")
    print("2. Start with top 20 papers")
    print("3. Use provided search links for each paper")
    print("4. Mark papers as found/downloaded")
    print("5. Expected success: 15-25 PDFs from top 40 papers")
    print()


def main():
    """Main execution."""
    print("Analyzing papers and calculating priorities...")

    papers = load_and_prioritize()

    print(f"Loaded {len(papers)} papers")
    print("Generating manual hunt checklist...")

    generate_manual_hunt_guide(papers)

    print_summary(papers)


if __name__ == "__main__":
    main()
