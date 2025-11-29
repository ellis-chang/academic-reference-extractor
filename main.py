#!/usr/bin/env python3
"""
Reference Extractor - Main Application
Extracts author affiliations and contact details from academic reference PDFs

Usage:
    python main.py input.pdf [output.xlsx]
    python main.py --help
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Optional

from src.pdf_parser import PDFReferenceParser, Reference
from src.author_lookup import AuthorLookupService, AuthorInfo, create_lookup_service_from_env
from src.excel_output import ExcelOutputGenerator, create_output_data


def print_progress(current: int, total: int, author_name: str):
    """Print progress update"""
    percent = (current / total) * 100
    bar_length = 30
    filled = int(bar_length * current // total)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f'\r  [{bar}] {percent:.0f}% - Processing: {author_name[:30]:<30}', end='', flush=True)


def process_references(pdf_path: str, output_path: str, 
                       use_llm: bool = True, 
                       max_refs: Optional[int] = None,
                       verbose: bool = True) -> str:
    """
    Process a PDF file to extract references and author information
    
    Args:
        pdf_path: Path to input PDF file
        output_path: Path for output Excel file
        use_llm: Whether to use LLM for author information extraction
        max_refs: Maximum number of references to process (for testing)
        verbose: Print progress information
        
    Returns:
        Path to the generated Excel file
    """
    
    if verbose:
        print(f"\n{'='*60}")
        print("  Reference Extractor - Author Information Extraction")
        print(f"{'='*60}")
        print(f"\n  Input:  {pdf_path}")
        print(f"  Output: {output_path}")
        print(f"  LLM:    {'Enabled' if use_llm else 'Disabled'}")
        print(f"\n{'-'*60}")
    
    # Step 1: Parse PDF
    if verbose:
        print("\n[1/4] Parsing PDF...")
    
    parser = PDFReferenceParser(pdf_path)
    parser.extract_text()
    references = parser.parse_references()
    
    if verbose:
        print(f"       Found {len(references)} references")
    
    if max_refs:
        references = references[:max_refs]
        if verbose:
            print(f"       Processing first {max_refs} references")
    
    # Step 2: Create lookup service
    if verbose:
        print("\n[2/4] Initializing author lookup service...")
    
    if use_llm:
        try:
            lookup_service = create_lookup_service_from_env()
        except Exception as e:
            if verbose:
                print(f"       Warning: Could not initialize LLM service: {e}")
                print("       Falling back to web-only lookup")
            lookup_service = AuthorLookupService()
    else:
        lookup_service = AuthorLookupService()
    
    # Step 3: Look up author information
    if verbose:
        print("\n[3/4] Looking up author information...")
        print("       (This may take a while for large bibliographies)")
        print()
    
    first_author_info = {}
    last_author_info = {}
    
    # Collect unique authors to avoid duplicate lookups
    author_cache = {}
    
    total = len(references)
    for i, ref in enumerate(references):
        # Progress
        if verbose:
            print_progress(i + 1, total, ref.first_author or "Unknown")
        
        # Look up first author
        if ref.first_author:
            if ref.first_author not in author_cache:
                info = lookup_service.lookup_author(
                    ref.first_author,
                    ref.title,
                    ref.year,
                    ref.raw_text
                )
                author_cache[ref.first_author] = info
            first_author_info[i] = author_cache[ref.first_author]
        
        # Look up last author (if different from first)
        if ref.last_author and ref.last_author != ref.first_author:
            if ref.last_author not in author_cache:
                info = lookup_service.lookup_author(
                    ref.last_author,
                    ref.title,
                    ref.year,
                    ref.raw_text
                )
                author_cache[ref.last_author] = info
            last_author_info[i] = author_cache[ref.last_author]
        elif ref.last_author == ref.first_author:
            # Same author for single-author papers
            last_author_info[i] = first_author_info.get(i)
    
    if verbose:
        print("\n")  # New line after progress bar
    
    # Step 4: Generate Excel output
    if verbose:
        print("[4/4] Generating Excel output...")
    
    output_data = create_output_data(references, first_author_info, last_author_info)
    
    generator = ExcelOutputGenerator()
    generator.write_reference_data(output_data, output_path)
    
    # Calculate statistics
    first_count = sum(1 for info in first_author_info.values() if info and info.affiliation)
    last_count = sum(1 for info in last_author_info.values() if info and info.affiliation)
    
    if verbose:
        print(f"\n{'-'*60}")
        print("\n  Summary:")
        print(f"    Total references processed: {len(references)}")
        print(f"    First authors with affiliation: {first_count} ({first_count/len(references)*100:.1f}%)")
        print(f"    Last authors with affiliation: {last_count} ({last_count/len(references)*100:.1f}%)")
        print(f"\n  Output saved to: {output_path}")
        print(f"\n{'='*60}\n")
    
    return output_path


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Extract author affiliations and contact details from academic reference PDFs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py references.pdf
  python main.py references.pdf output.xlsx
  python main.py references.pdf --no-llm --max-refs 10

Environment Variables:
  ANTHROPIC_API_KEY    - API key for Claude LLM (recommended)
  GOOGLE_API_KEY       - Google Custom Search API key (optional)
  GOOGLE_CSE_ID        - Google Custom Search Engine ID (optional)
  S2_API_KEY           - Semantic Scholar API key (optional)
        """
    )
    
    parser.add_argument('pdf_path', help='Path to input PDF file')
    parser.add_argument('output_path', nargs='?', help='Path for output Excel file (optional)')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM-based extraction')
    parser.add_argument('--max-refs', type=int, help='Maximum number of references to process')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress progress output')
    parser.add_argument('--csv', action='store_true', help='Also export to CSV format')
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.pdf_path):
        print(f"Error: Input file not found: {args.pdf_path}")
        sys.exit(1)
    
    # Generate default output path if not provided
    if args.output_path:
        output_path = args.output_path
    else:
        base_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"{base_name}_authors_{timestamp}.xlsx"
    
    try:
        # Process references
        result_path = process_references(
            pdf_path=args.pdf_path,
            output_path=output_path,
            use_llm=not args.no_llm,
            max_refs=args.max_refs,
            verbose=not args.quiet
        )
        
        # Export CSV if requested
        if args.csv:
            csv_path = result_path.replace('.xlsx', '.csv')
            # Re-read and export to CSV
            import pandas as pd
            df = pd.read_excel(result_path)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            if not args.quiet:
                print(f"  CSV export saved to: {csv_path}")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        if os.environ.get('DEBUG'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
