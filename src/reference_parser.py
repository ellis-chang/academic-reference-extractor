import re
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ParsedReference:
    """Data class to hold parsed reference information"""
    citation_key: str  # e.g., "[Hill '79]"
    first_author: str
    last_author: str
    title: str
    year: str
    full_author_list: str  # Keep the complete author string
    venue: Optional[str] = None  # Journal/conference name
    raw_text: str = ""  # Keep original text for debugging

def extract_citation_key(reference):
    """
    Extract the citation key like [Hill '79] from the reference
    """
    citation_pattern = r'\[[^\]]+[\'\u2018\u2019]\d{2,4}(?:\s+[A-Z])?\]'
    match = re.search(citation_pattern, reference)
    return match.group(0) if match else ""

def extract_year(reference: str) -> str:
    """
    Extract publication year (the full year, not just from citation key)
    """
    # Look for 4-digit year in parentheses like (2021) or (1985)
    year_pattern = r'\((\d{4})\)'
    match = re.search(year_pattern, reference)
    
    if match:
        return match.group(1)
    
    # Also look for standalone 4-digit year (like in Bonferroni '36 case)
    standalone_year = re.search(r'\b(19\d{2}|20\d{2})\b', reference)
    if standalone_year:
        return standalone_year.group(1)
    
    # If not found, try to extract from citation key
    citation_key = extract_citation_key(reference)
    year_from_key = re.search(r'[\'\u2018\u2019](\d{2,4})', citation_key)
    if year_from_key:
        year = year_from_key.group(1)
        # Convert 2-digit year to 4-digit
        if len(year) == 2:
            year = "19" + year if int(year) > 50 else "20" + year
        return year
    
    return ""

def extract_authors(reference: str) -> Dict[str, str]:
    """
    Extract first and last authors from the reference.
    
    Returns dict with 'first_author', 'last_author', 'all_authors'
    """
    # Remove citation key first
    citation_key = extract_citation_key(reference)
    text_after_citation = reference[len(citation_key):].strip()
    
    # Special case: Check if this looks like an ancient text (e.g., "9th century")
    if "century)" in text_after_citation[:50]:
        # For ancient texts, take everything up to the period
        author_end = text_after_citation.find('.')
        if author_end > 0:
            author_text = text_after_citation[:author_end]
            # Remove the century part
            author_text = re.sub(r'\s*\([^)]*century\)', '', author_text).strip()
        else:
            author_text = text_after_citation.split('.')[0].strip()
    else:
        # Modern reference - look for year pattern
        # Authors typically come before (YEAR) or before the title
        
        # Try to find where authors end
        # Look for (YEAR) pattern
        year_match = re.search(r'\((?:19|20)\d{2}\)', text_after_citation)
        
        if year_match:
            author_text = text_after_citation[:year_match.start()].strip()
        else:
            # No clear year marker, need to be smarter
            # Look for a period followed by a capital letter (likely title start)
            # But not initials (like "N. Wiener")
            
            # For references like Bonferroni, authors are before the comma
            if ',' in text_after_citation[:30]:  # Check first 30 chars
                first_comma = text_after_citation.find(',')
                # Check if what's before the comma looks like author names
                potential_author = text_after_citation[:first_comma]
                if len(potential_author) < 50 and not '.' in potential_author[2:]:  # Not counting initials
                    author_text = potential_author.strip()
                else:
                    # Comma might be part of author list
                    author_text = text_after_citation.split('.')[0].strip()
            else:
                # Take everything up to first sentence-ending period
                author_text = text_after_citation.split('.')[0].strip()
    
    # Clean up author text
    author_text = author_text.strip('.,;')
    
    # Handle et al. and ... cases
    has_et_al = "et al" in author_text.lower() or "..." in author_text
    
    # Clean up for parsing
    author_text_clean = re.sub(r'\s*\.\.\.\s*', '', author_text)
    author_text_clean = re.sub(r'\s*et\s+al\.?\s*', '', author_text_clean, flags=re.IGNORECASE)
    
    # Parse authors based on delimiters
    authors = []
    
    # Check for semicolon-separated authors first
    if ';' in author_text_clean:
        parts = [a.strip() for a in author_text_clean.split(';')]
        for part in parts:
            if ',' in part:
                # Might be "Last, First" format
                authors.append(part.strip())
            else:
                authors.append(part.strip())
    # Check for & or "and" separated authors
    elif ' & ' in author_text_clean or ' and ' in author_text_clean:
        # Split by & or and
        parts = re.split(r'\s+(?:&|and)\s+', author_text_clean)
        
        for i, part in enumerate(parts):
            if i == 0 and ',' in part:
                # First part might have multiple comma-separated authors
                subparts = part.split(',')
                # Check if it's "Last, F." format or multiple authors
                if len(subparts) == 2 and len(subparts[1].strip()) <= 5:
                    # Likely "Last, F." format
                    authors.append(part.strip())
                else:
                    # Multiple authors
                    authors.extend([s.strip() for s in subparts if s.strip()])
            else:
                # Clean up the part
                part = part.strip().strip(',')
                if part:
                    authors.append(part)
    # Check for comma-separated authors
    elif ',' in author_text_clean:
        parts = author_text_clean.split(',')
        
        # Check if it's "Last, First" format (usually 2 parts with second being short)
        if len(parts) == 2 and len(parts[1].strip()) <= 10 and '.' in parts[1]:
            # Single author in "Last, F." format
            authors = [author_text_clean.strip()]
        else:
            # Multiple comma-separated authors
            authors = [p.strip() for p in parts if p.strip()]
    else:
        # Single author or couldn't parse
        authors = [author_text_clean.strip()] if author_text_clean.strip() else []
    
    # Clean up authors
    authors = [a for a in authors if a and len(a) > 1]
    
    # Get first and last
    first_author = authors[0] if authors else author_text.strip()
    last_author = authors[-1] if len(authors) > 1 else first_author
    
    return {
        'first_author': first_author,
        'last_author': last_author,
        'all_authors': author_text
    }

def extract_title(reference: str) -> str:
    """
    Extract the paper title from the reference.
    """
    # Remove citation key
    citation_key = extract_citation_key(reference)
    text_after_citation = reference[len(citation_key):].strip()
    
    # Check for ancient texts (special case)
    if "century)" in text_after_citation[:50]:
        # Find the title after the century marker
        century_end = text_after_citation.find(')')
        if century_end > 0:
            text_after_century = text_after_citation[century_end + 1:].strip()
            # Title is usually up to "Translated by" or the first period
            if "Translated" in text_after_century:
                title = text_after_century[:text_after_century.find("Translated")].strip('. ')
            else:
                title = text_after_century.split('.')[0].strip()
            return title
    
    # Try to find title in quotes
    quote_patterns = [
        r'[""]([^""]+)[""]',
        r'"([^"]+)"',
        r'"([^"]+)"'
    ]
    
    for pattern in quote_patterns:
        match = re.search(pattern, reference)
        if match:
            return match.group(1).strip()
    
    # Look for title after year in parentheses
    year_match = re.search(r'\((?:19|20)\d{2}\)\.?\s*', reference)
    if year_match:
        text_after_year = reference[year_match.end():].strip()
        
        # Find where title ends (usually at journal info or "In")
        title_end_patterns = [
            r'\.\s+(?:In\s+)',
            r'\.\s+(?:Proceedings)',
            r'\.\s+(?:Journal)',
            r'\.\s+(?:IEEE|ACM|PMLR)',
            r'\.\s+(?:[A-Z][a-z]+\s+(?:of|on)\s+)',  # "Annals of", "Conference on"
        ]
        
        for pattern in title_end_patterns:
            match = re.search(pattern, text_after_year)
            if match:
                return text_after_year[:match.start()].strip()
        
        # If no clear end marker, take first sentence
        if '. ' in text_after_year:
            return text_after_year[:text_after_year.find('. ')].strip()
    
    # For references without year in parentheses (like Bonferroni)
    # Title usually comes after author names
    if ',' in text_after_citation:
        parts = text_after_citation.split(',', 1)
        if len(parts) > 1:
            # Check if second part looks like a title
            potential_title = parts[1].strip()
            # Remove publication info
            if "Pubblicazioni" in potential_title or "Publisher" in potential_title:
                title_parts = potential_title.split("Pubblicazioni")
                return title_parts[0].strip(', ')
            return potential_title.strip()
    
    return ""

def parse_reference(reference: str) -> ParsedReference:
    """
    Main function to parse a single reference
    """
    # Combine all extraction functions
    citation_key = extract_citation_key(reference)
    year = extract_year(reference)
    authors = extract_authors(reference)
    title = extract_title(reference)

    # Return ParsedReference object
    return ParsedReference(
        citation_key=citation_key,
        first_author=authors['first_author'],
        last_author=authors['last_author'],
        title=title,
        year=year,
        full_author_list=authors['all_authors'],
        venue=None,
        raw_text=reference
    )

if __name__ == "__main__":
    # Test with different reference styles
    test_refs = [
        "[Hill '79] Banu Musa brothers (9th century). The book of ingenious devices (Kitab al-hiyal). Translated by D. R. Hill (1979), Springer, p. 44, ISBN 90-277-0833-9.",
        "[Bonferroni '36] Bonferroni, C. E., Teoria statistica delle classi e calcolo delle probabilità, Pubblicazioni del R Istituto Superiore di Scienze Economiche e Commerciali di Firenze 1936",
        "[Wiener '48] N. Wiener (1948). Time, communication, and the nervous system. Teleological mechanisms. Annals of the N.Y. Acad. Sci. 50 (4): 197-219.",
        "[Van der Maaten '08] Van der Maaten, L.J.P.; Hinton, G.E. (2008). Visualizing Data Using t-SNE. Journal of Machine Learning Research. 9: 2579–2605.",
        "[Chen '20 A] Chen, T., Kornblith, S., Norouzi, M., & Hinton, G. (2020). A simple framework for contrastive learning of visual representations. International conference on machine learning (pp. 1597-1607). PMLR."
    ]
    
    for ref in test_refs:
        parsed = parse_reference(ref)
        print(f"\nCitation: {parsed.citation_key}")
        print(f"First Author: {parsed.first_author}")
        print(f"Last Author: {parsed.last_author}")
        print(f"Title: {parsed.title}")
        print(f"Year: {parsed.year}")