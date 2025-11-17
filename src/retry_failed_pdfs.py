#!/usr/bin/env python3
"""
Retry failed PDF downloads with improved error handling.

This script attempts to download the 5 PDFs that failed in the initial
extraction, using alternative methods and better error handling.
"""

import time
import logging
import requests
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Failed PDFs to retry
FAILED_PDFS = [
    {
        'title': 'A Study on the Current Learning Situation and Enhancement Strategies',
        'year': 2025,
        'url': 'https://doi.org/10.22158/wjer.v12n1p72',
        'filename': 'Kang_2025_Study_Learning_Situation_Enhancement.pdf',
        'reason': '503 Service Unavailable'
    },
    {
        'title': 'DEVELOPMENT OF WEB PROGRAMMING LEARNING MEDIA USING LARAVEL',
        'year': 2023,
        'url': 'https://doi.org/10.26858/jnp.v11i2.62852',
        'filename': 'Unknown_2023_Web_Programming_Laravel.pdf',
        'reason': '403 Forbidden'
    },
    {
        'title': 'Design and Build a Web-Based E-Learning Application System',
        'year': 2023,
        'url': 'https://journal.formosapublisher.org/index.php/ijis/article/download/4862/4965',
        'filename': 'Unknown_2023_Web_Based_ELearning.pdf',
        'reason': '404 Not Found'
    },
    {
        'title': 'Collaborative Learning: Design and Reflections in a Web Programming Course',
        'year': 2016,
        'url': 'http://www.journaleet.org/index.php/jeet/article/download/85667/65763',
        'filename': 'Umadevi_2016_Collaborative_Learning_Web_Programming.pdf',
        'reason': 'Invalid PDF format'
    },
    {
        'title': 'Reform of the web design and construction teaching',
        'year': 2012,
        'url': 'https://doi.org/10.2991/icetms.2013.153',
        'filename': 'Wang_2012_Reform_Web_Design_Teaching.pdf',
        'reason': 'Invalid PDF format'
    }
]

OUTPUT_DIR = Path('data/semantic_scholar/papers')


def download_with_retry(url: str, filename: str, max_retries: int = 3) -> Optional[Path]:
    """
    Download PDF with retry logic and improved error handling.

    Args:
        url: URL to download from
        filename: Filename to save as
        max_retries: Maximum number of retry attempts

    Returns:
        Path to downloaded file or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/pdf,application/octet-stream,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }

    output_path = OUTPUT_DIR / filename

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: {filename}")
            logger.info(f"  URL: {url}")

            # Make request with timeout
            response = requests.get(
                url,
                headers=headers,
                timeout=30,
                allow_redirects=True,
                stream=True
            )

            logger.info(f"  Status: {response.status_code}")
            logger.info(f"  Content-Type: {response.headers.get('Content-Type', 'unknown')}")

            # Check status code
            if response.status_code == 200:
                # Check content type
                content_type = response.headers.get('Content-Type', '').lower()

                # Download content
                content = response.content

                # Check if it's actually a PDF
                is_pdf = content.startswith(b'%PDF') or 'pdf' in content_type

                if is_pdf:
                    # Save file
                    with open(output_path, 'wb') as f:
                        f.write(content)

                    logger.info(f"  ✓ Downloaded successfully: {output_path}")
                    logger.info(f"  Size: {len(content) / 1024:.1f} KB")
                    return output_path
                else:
                    logger.warning(f"  ✗ Content is not a PDF (starts with: {content[:20]})")
                    logger.warning(f"  Content type: {content_type}")

                    # Save for inspection
                    debug_path = output_path.with_suffix('.html')
                    with open(debug_path, 'wb') as f:
                        f.write(content)
                    logger.info(f"  Saved non-PDF content to: {debug_path}")

            elif response.status_code == 403:
                logger.error(f"  ✗ 403 Forbidden - Access denied")
                break  # Don't retry 403

            elif response.status_code == 404:
                logger.error(f"  ✗ 404 Not Found - URL invalid")
                break  # Don't retry 404

            elif response.status_code >= 500:
                logger.error(f"  ✗ {response.status_code} Server Error - Will retry")
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    logger.info(f"  Waiting {wait}s before retry...")
                    time.sleep(wait)

            else:
                logger.error(f"  ✗ Unexpected status code: {response.status_code}")

        except requests.exceptions.Timeout:
            logger.error(f"  ✗ Request timeout")
            if attempt < max_retries - 1:
                logger.info(f"  Waiting 10s before retry...")
                time.sleep(10)

        except requests.exceptions.ConnectionError as e:
            logger.error(f"  ✗ Connection error: {e}")
            if attempt < max_retries - 1:
                logger.info(f"  Waiting 10s before retry...")
                time.sleep(10)

        except Exception as e:
            logger.error(f"  ✗ Unexpected error: {e}")
            break

    logger.error(f"  ✗ Failed to download after {max_retries} attempts")
    return None


def try_doi_resolution(doi_url: str) -> Optional[str]:
    """
    Try to resolve DOI to find alternative PDF URLs.

    Args:
        doi_url: DOI URL to resolve

    Returns:
        Alternative PDF URL if found, None otherwise
    """
    if 'doi.org' not in doi_url:
        return None

    logger.info(f"Attempting DOI resolution: {doi_url}")

    try:
        # Follow redirects manually to see where it goes
        response = requests.head(doi_url, allow_redirects=True, timeout=10)
        final_url = response.url

        logger.info(f"  DOI resolves to: {final_url}")

        # Check if final URL is different and might have a PDF
        if final_url != doi_url:
            # Try to find PDF link on the landing page
            response = requests.get(final_url, timeout=10)
            content = response.text

            # Look for PDF links
            if 'pdf' in content.lower():
                logger.info(f"  Landing page contains 'pdf' - might have download link")
                # Could parse HTML here to find PDF link
                # For now, return the landing page URL
                return final_url

    except Exception as e:
        logger.debug(f"  DOI resolution failed: {e}")

    return None


def main():
    """Main retry function."""
    print("=" * 80)
    print("RETRY FAILED PDF DOWNLOADS")
    print("=" * 80)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        'attempted': 0,
        'successful': 0,
        'failed': 0
    }

    for paper in FAILED_PDFS:
        print(f"\nRetrying: {paper['title'][:60]}...")
        print(f"Year: {paper['year']}")
        print(f"Original failure reason: {paper['reason']}")
        print()

        stats['attempted'] += 1

        # Try direct download
        result = download_with_retry(paper['url'], paper['filename'])

        if result:
            stats['successful'] += 1
            print(f"✓ SUCCESS: Downloaded to {result}")
        else:
            stats['failed'] += 1
            print(f"✗ FAILED: Could not download")

            # Try DOI resolution for DOI URLs
            if 'doi.org' in paper['url']:
                print("\nTrying DOI resolution to find alternative URL...")
                alt_url = try_doi_resolution(paper['url'])
                if alt_url and alt_url != paper['url']:
                    print(f"Found alternative URL: {alt_url}")
                    print("(Manual follow-up needed to locate PDF link)")

        print("-" * 80)

        # Wait between attempts
        if stats['attempted'] < len(FAILED_PDFS):
            time.sleep(3)

    # Print summary
    print("\n" + "=" * 80)
    print("RETRY SUMMARY")
    print("=" * 80)
    print(f"Attempted: {stats['attempted']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Success rate: {stats['successful']/stats['attempted']*100:.1f}%")
    print()

    if stats['successful'] > 0:
        print(f"✓ {stats['successful']} PDF(s) successfully downloaded!")
        print(f"Location: {OUTPUT_DIR}")
    else:
        print("✗ No PDFs successfully downloaded")
        print("\nRecommended next steps:")
        print("1. Manually visit the URLs in a browser")
        print("2. Check if papers are available through institutional access")
        print("3. Try alternative PDF sources (Unpaywall, CORE, ResearchGate)")


if __name__ == "__main__":
    main()
