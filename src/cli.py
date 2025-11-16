"""
Command-line interface for Scholar Extractor.
"""

import sys
import logging
from pathlib import Path

import click
from colorama import init as colorama_init, Fore, Style

from .config import Config
from .storage import Storage
from .search import ScholarSearcher
from .downloader import PDFDownloader


# Initialize colorama for cross-platform colored output
colorama_init(autoreset=True)


def setup_logging(verbose: bool = False):
    """
    Set up logging configuration.

    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # File handler
    Config.ensure_directories()
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(Config.LOG_FORMAT)
    file_handler.setFormatter(file_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def print_banner():
    """Print application banner."""
    banner = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════╗
║         Scholar Extractor v0.1.0                     ║
║    Google Scholar Metadata & Paper Extraction Tool   ║
╚═══════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def print_stats(stats: dict):
    """
    Print statistics in a formatted way.

    Args:
        stats: Statistics dictionary
    """
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Statistics:{Style.RESET_ALL}")
    print(f"{'='*60}")

    for key, value in stats.items():
        key_formatted = key.replace('_', ' ').title()
        if isinstance(value, float):
            print(f"  {key_formatted}: {value:.2f}")
        else:
            print(f"  {key_formatted}: {value}")

    print(f"{'='*60}\n")


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """Scholar Extractor - Extract metadata and papers from Google Scholar."""
    pass


@cli.command()
@click.option('--url', '-u', required=True, help='Google Scholar search URL')
@click.option('--max-papers', '-n', type=int, default=100,
              help='Maximum number of papers to extract (default: 100)')
@click.option('--delay', '-d', type=float, default=Config.REQUEST_DELAY,
              help=f'Delay between requests in seconds (default: {Config.REQUEST_DELAY})')
@click.option('--download-pdfs/--no-download-pdfs', default=False,
              help='Download PDFs automatically (default: no)')
@click.option('--resume/--no-resume', default=False,
              help='Resume from previous state (default: no)')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Custom output directory (default: data/)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def extract(url, max_papers, delay, download_pdfs, resume, output, verbose):
    """
    Extract metadata from Google Scholar search results.

    Example:
        scholarextractor extract --url "https://scholar.google.com/scholar?q=..."
    """
    print_banner()
    setup_logging(verbose)

    logger = logging.getLogger(__name__)
    logger.info("Starting Scholar Extractor")

    # Update config if needed
    if delay != Config.REQUEST_DELAY:
        Config.REQUEST_DELAY = delay
        logger.info(f"Using custom delay: {delay}s")

    # Initialize components
    storage = Storage()
    searcher = ScholarSearcher(storage, max_papers=max_papers)

    try:
        # Execute search
        print(f"{Fore.CYAN}Starting search...{Style.RESET_ALL}")
        print(f"URL: {url}")
        print(f"Max papers: {max_papers}")
        print(f"Delay: {delay}s")
        print(f"Resume: {resume}")
        print()

        papers = searcher.search(url, resume=resume)

        # Print results
        print(f"\n{Fore.GREEN}✓ Extraction completed!{Style.RESET_ALL}")
        print(f"Extracted {len(papers)} papers")

        # Get statistics
        stats = searcher.get_statistics()
        print_stats(stats)

        # Download PDFs if requested
        if download_pdfs:
            print(f"{Fore.CYAN}Starting PDF downloads...{Style.RESET_ALL}\n")
            downloader = PDFDownloader(storage)
            download_stats = downloader.download_all()
            print(f"\n{Fore.GREEN}✓ Downloads completed!{Style.RESET_ALL}")
            print_stats(download_stats)
            downloader.close()

        # Print output locations
        print(f"{Fore.YELLOW}Output files:{Style.RESET_ALL}")
        print(f"  Metadata (JSON): {Config.METADATA_JSON}")
        print(f"  Metadata (CSV):  {Config.METADATA_CSV}")
        if download_pdfs:
            print(f"  PDFs:            {Config.PAPERS_DIR}")
        print()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠ Interrupted by user{Style.RESET_ALL}")
        logger.warning("Interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n{Fore.RED}✗ Error: {e}{Style.RESET_ALL}")
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        searcher.close()

    print(f"{Fore.GREEN}✓ Done!{Style.RESET_ALL}\n")


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def download(verbose):
    """
    Download PDFs for papers that don't have them yet.

    This command reads the metadata from previous extractions
    and downloads PDFs for papers with available PDF links.
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    print_banner()
    print(f"{Fore.CYAN}Loading metadata...{Style.RESET_ALL}\n")

    # Load existing metadata
    storage = Storage()
    if not storage.load_metadata_json():
        print(f"{Fore.RED}✗ No metadata found. Run 'extract' command first.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"Loaded {len(storage.papers)} papers")

    # Download PDFs
    downloader = PDFDownloader(storage)

    try:
        papers_to_download = storage.get_papers_without_pdf()
        print(f"Papers without PDFs: {len(papers_to_download)}\n")

        if not papers_to_download:
            print(f"{Fore.YELLOW}No papers to download.{Style.RESET_ALL}")
            return

        print(f"{Fore.CYAN}Starting downloads...{Style.RESET_ALL}\n")
        stats = downloader.download_all()

        print(f"\n{Fore.GREEN}✓ Downloads completed!{Style.RESET_ALL}")
        print_stats(stats)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠ Interrupted by user{Style.RESET_ALL}")
        sys.exit(1)

    except Exception as e:
        print(f"\n{Fore.RED}✗ Error: {e}{Style.RESET_ALL}")
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        downloader.close()


@cli.command()
def status():
    """
    Show status of current extraction.

    Displays statistics about extracted papers and downloads.
    """
    print_banner()

    # Load metadata
    storage = Storage()
    if not storage.load_metadata_json():
        print(f"{Fore.YELLOW}No data found. Run 'extract' command first.{Style.RESET_ALL}")
        return

    # Display statistics
    stats = storage.get_statistics()
    stats['total_papers'] = len(storage.papers)

    print(f"{Fore.CYAN}Current Status:{Style.RESET_ALL}\n")
    print_stats(stats)

    # Show query info
    if storage.query_info:
        print(f"{Fore.YELLOW}Query Information:{Style.RESET_ALL}")
        print(f"  URL: {storage.query_info.get('url', 'N/A')}")
        print(f"  Executed: {storage.query_info.get('executed_at', 'N/A')}")
        print()


@cli.command()
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'both']),
              default='both', help='Export format (default: both)')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path (default: data/metadata/)')
def export(format, output):
    """
    Export metadata to different formats.

    Exports the extracted metadata to JSON and/or CSV formats.
    """
    print_banner()

    # Load metadata
    storage = Storage()
    if not storage.load_metadata_json():
        print(f"{Fore.RED}✗ No metadata found. Run 'extract' command first.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"Loaded {len(storage.papers)} papers\n")

    # Export
    try:
        if format in ['json', 'both']:
            output_path = Path(output) if output else Config.METADATA_JSON
            if storage.save_metadata_json(output_path):
                print(f"{Fore.GREEN}✓ Exported JSON to: {output_path}{Style.RESET_ALL}")

        if format in ['csv', 'both']:
            output_path = Path(output) if output else Config.METADATA_CSV
            if storage.save_metadata_csv(output_path):
                print(f"{Fore.GREEN}✓ Exported CSV to: {output_path}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}✗ Export failed: {e}{Style.RESET_ALL}")
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()
