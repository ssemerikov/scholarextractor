#!/usr/bin/env python3
"""
Run PDF hunt on missing papers.

This script uses the PDF hunter to find PDFs from Unpaywall, CORE, and CrossRef APIs.
"""

import json
import logging
import time
import requests
from pathlib import Path
from typing import List

from .pdf_hunter import PDFHunter, PDFSource
from .storage import PaperMetadata

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/semantic_scholar")
METADATA_FILE = DATA_DIR / "metadata" / "final_64_papers.json"
PDF_DIR = DATA_DIR / "papers"
RESULTS_FILE = DATA_DIR / "metadata" / "pdf_hunt_results.json"


def load_papers() -> List[PaperMetadata]:
    """Load papers from metadata file."""
    logger.info(f"Loading papers from {METADATA_FILE}")

    with open(METADATA_FILE) as f:
        data = json.load(f)

    papers = []
    for paper_dict in data['papers']:
        paper = PaperMetadata(**{
            k: v for k, v in paper_dict.items()
            if k in ['id', 'title', 'authors', 'year', 'venue', 'abstract',
                     'citations', 'url', 'pdf_url', 'doi']
        })
        papers.append(paper)

    logger.info(f"Loaded {len(papers)} papers")
    return papers


def download_pdf(pdf_source: PDFSource, filename: str) -> bool:
    """
    Download PDF from source.

    Args:
        pdf_source: PDF source information
        filename: Filename to save as

    Returns:
        True if successful, False otherwise
    """
    output_path = PDF_DIR / filename

    # Skip if already downloaded
    if output_path.exists():
        logger.info(f"  PDF already exists: {filename}")
        return True

    try:
        logger.info(f"  Downloading from {pdf_source.source_name}...")
        logger.info(f"  URL: {pdf_source.url[:80]}...")

        # Download with regular requests
        response = requests.get(
            pdf_source.url,
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )

        if response.status_code == 200:
            content = response.content

            # Verify it's a PDF
            if content.startswith(b'%PDF'):
                with open(output_path, 'wb') as f:
                    f.write(content)

                size_kb = len(content) / 1024
                logger.info(f"  ✓ Downloaded: {output_path} ({size_kb:.1f} KB)")
                return True
            else:
                logger.warning(f"  ✗ Content is not a PDF")
                return False
        else:
            logger.warning(f"  ✗ HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"  ✗ Download failed: {e}")
        return False


def main():
    """Main PDF hunt execution."""
    print("\n" + "=" * 80)
    print("PDF HUNT - FINDING MISSING PDFS")
    print("=" * 80)
    print()

    # Load papers
    papers = load_papers()

    # Filter to only papers without PDFs
    missing_pdfs = [p for p in papers if not p.pdf_url]

    logger.info(f"Papers with PDF URLs: {len(papers) - len(missing_pdfs)}")
    logger.info(f"Papers WITHOUT PDF URLs: {len(missing_pdfs)}")
    print()

    if not missing_pdfs:
        logger.info("No missing PDFs to hunt for!")
        return

    # Create hunter
    hunter = PDFHunter(email="researcher@example.com")

    # Hunt for PDFs
    print(f"Hunting for PDFs across {len(hunter.sources)} sources...")
    print("Sources: Unpaywall, CORE, CrossRef")
    print()

    found_pdfs = hunter.hunt_batch(missing_pdfs)

    # Print statistics
    print("\n" + "=" * 80)
    print("HUNT STATISTICS")
    print("=" * 80)

    stats = hunter.get_statistics()
    print(f"Papers searched: {stats['attempted']}")
    print(f"PDFs found: {stats['found']}")
    print(f"PDFs not found: {stats['not_found']}")
    print(f"Success rate: {stats['found']/max(stats['attempted'], 1)*100:.1f}%")
    print()

    if stats['by_source']:
        print("By source:")
        for source, count in stats['by_source'].items():
            print(f"  - {source}: {count}")
        print()

    # Download found PDFs
    if found_pdfs:
        print("=" * 80)
        print(f"DOWNLOADING {len(found_pdfs)} FOUND PDFs")
        print("=" * 80)
        print()

        download_stats = {
            'attempted': 0,
            'successful': 0,
            'failed': 0
        }

        for paper_id, pdf_source in found_pdfs.items():
            # Find the paper
            paper = next((p for p in missing_pdfs if p.id == paper_id), None)

            if not paper:
                continue

            download_stats['attempted'] += 1

            # Generate filename
            author = paper.authors[0].split()[0] if paper.authors else "Unknown"
            year = paper.year or "XXXX"
            title_words = paper.title.split()[:5]
            title_part = "_".join(title_words).replace("/", "_").replace("\\", "_")
            filename = f"{author}_{year}_{title_part}.pdf"[:100] + ".pdf"

            print(f"\n[{download_stats['attempted']}/{len(found_pdfs)}] {paper.title[:60]}...")

            success = download_pdf(pdf_source, filename)

            if success:
                download_stats['successful'] += 1

                # Update paper with new PDF URL
                paper.pdf_url = pdf_source.url
            else:
                download_stats['failed'] += 1

        # Save results
        results = {
            'hunt_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'papers_searched': stats['attempted'],
            'pdfs_found': stats['found'],
            'pdfs_downloaded': download_stats['successful'],
            'sources_used': list(stats['by_source'].keys()),
            'found_papers': [
                {
                    'paper_id': paper_id,
                    'pdf_url': pdf_source.url,
                    'source': pdf_source.source_name,
                    'is_open_access': pdf_source.is_open_access,
                    'license': pdf_source.license
                }
                for paper_id, pdf_source in found_pdfs.items()
            ]
        }

        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"\nResults saved to: {RESULTS_FILE}")

        print("\n" + "=" * 80)
        print("DOWNLOAD SUMMARY")
        print("=" * 80)
        print(f"Attempted: {download_stats['attempted']}")
        print(f"Successful: {download_stats['successful']}")
        print(f"Failed: {download_stats['failed']}")
        print(f"Success rate: {download_stats['successful']/max(download_stats['attempted'], 1)*100:.1f}%")
        print()

        total_pdfs = len([p for p in papers if p.pdf_url]) + download_stats['successful']
        print(f"Total PDFs now: {total_pdfs}/{len(papers)} ({total_pdfs/len(papers)*100:.1f}%)")

    else:
        print("\n✗ No PDFs found from any source")
        print("\nRecommended next steps:")
        print("1. Try ResearchGate manual search")
        print("2. Contact authors directly")
        print("3. Check institutional repositories")
        print("4. Consider paid options (DeepDyve, ILL)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
