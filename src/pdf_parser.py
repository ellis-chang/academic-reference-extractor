"""
PDF Reference Parser Module
Extracts reference entries from academic PDFs

Handles various citation formats:
- Standard: Author, A., & Author, B. (YYYY). Title. Venue.
- Semicolon-separated: Author, A.; Author, B. (YYYY).
- Translations: Original Author. Title. Translated by Translator (YYYY).
- Et al: Author, A., ... & Author, Z. (YYYY).
- Full names: Author FirstName (YYYY)
- Various punctuation styles
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import pdfplumber
from pypdf import PdfReader


@dataclass
class Reference:
    """Data class for a parsed reference entry"""
    citation_key: str = ""
    raw_text: str = ""
    title: str = ""
    year: str = ""
    authors: List[str] = field(default_factory=list)
    first_author: str = ""
    last_author: str = ""
    venue: str = ""
    chapter: str = ""


class PDFReferenceParser:
    """Parser for extracting references from academic PDF bibliographies"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.raw_text = ""
        self.references: List[Reference] = []
        
    def extract_text(self) -> str:
        """Extract text from PDF using pdfplumber for better layout preservation"""
        text_parts = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            self.raw_text = "\n".join(text_parts)
        except Exception as e:
            # Fallback to pypdf
            reader = PdfReader(self.pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            self.raw_text = "\n".join(text_parts)
        return self.raw_text
    
    def parse_references(self) -> List[Reference]:
        """Parse individual reference entries from the extracted text"""
        if not self.raw_text:
            self.extract_text()
        
        # Split text by chapter markers
        chapter_pattern = r'————\s*Chapter\s*(\d+)\s*————'
        
        # Find all chapters
        chapters = re.split(chapter_pattern, self.raw_text)
        
        current_chapter = "Unknown"
        
        for i, chunk in enumerate(chapters):
            # Odd indices are chapter numbers, even indices are content
            if i % 2 == 1:
                current_chapter = f"Chapter {chunk}"
                continue
            
            if i == 0 and "Bibliography" in chunk:
                continue
                
            # Find all references in this chunk
            lines = chunk.strip().split('\n')
            current_ref_text = []
            current_key = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Check if line starts with a citation key
                key_match = re.match(r'^\[([^\]]+)\]', line)
                
                if key_match:
                    # Save previous reference if exists
                    if current_key and current_ref_text:
                        ref = self._parse_single_reference(
                            current_key, 
                            ' '.join(current_ref_text),
                            current_chapter
                        )
                        if ref:
                            self.references.append(ref)
                    
                    # Start new reference
                    current_key = key_match.group(1)
                    # Get text after the citation key
                    remaining = line[key_match.end():].strip()
                    current_ref_text = [remaining] if remaining else []
                else:
                    # Continue current reference
                    if current_key:
                        current_ref_text.append(line)
            
            # Don't forget the last reference
            if current_key and current_ref_text:
                ref = self._parse_single_reference(
                    current_key,
                    ' '.join(current_ref_text),
                    current_chapter
                )
                if ref:
                    self.references.append(ref)
        
        return self.references
    
    def _parse_single_reference(self, key: str, text: str, chapter: str) -> Optional[Reference]:
        """Parse a single reference entry to extract structured information"""
        ref = Reference(
            citation_key=key,
            raw_text=text.strip(),
            chapter=chapter
        )
        
        # Extract year from citation key (e.g., "Author '99" or "Author '2019")
        # Handle both straight (') and curly (') apostrophes
        year_match = re.search(r"[''](\d{2,4})", key)
        if year_match:
            year = year_match.group(1)
            if len(year) == 2:
                year_int = int(year)
                if year_int > 50:
                    ref.year = f"19{year}"
                else:
                    ref.year = f"20{year}"
            else:
                ref.year = year
        
        # Try to extract year from text if not in key
        if not ref.year:
            # Match (YYYY) or (YYYY, Month) or (YYYY,
            text_year_match = re.search(r'\((\d{4})(?:[,\)])', text)
            if text_year_match:
                ref.year = text_year_match.group(1)
        
        # Try year at end of reference: ", YYYY." or ", YYYY"
        if not ref.year:
            end_year_match = re.search(r',\s*(\d{4})\.?\s*$', text)
            if end_year_match:
                ref.year = end_year_match.group(1)
        
        # Try year in full date format: "(Month Day, YYYY)"
        if not ref.year:
            date_year_match = re.search(r'\([A-Za-z]+\s+\d+,\s*(\d{4})\)', text)
            if date_year_match:
                ref.year = date_year_match.group(1)
        
        # Detect special reference formats and extract authors accordingly
        ref.authors = self._extract_authors_smart(text, key)
        
        if ref.authors:
            ref.first_author = ref.authors[0]
            ref.last_author = ref.authors[-1] if len(ref.authors) > 1 else ref.authors[0]
        
        # Extract title
        ref.title = self._extract_title(text)
        
        return ref if ref.raw_text else None
    
    def _extract_authors_smart(self, text: str, citation_key: str) -> List[str]:
        """
        Smart author extraction that handles various formats:
        1. Standard: Author, A., & Author, B. (YYYY)
        2. Semicolon: Author, A.; Author, B. (YYYY)
        3. Translation: ... Translated by Author (YYYY)
        4. Et al: Author, A., ... & Author, Z. (YYYY)
        5. Full name: Author FirstName (YYYY)
        """
        
        # Check for translation format: "Translated by Author (YYYY)"
        translation_match = re.search(r'[Tt]ranslated\s+by\s+([^(]+)\s*\((\d{4})\)', text)
        if translation_match:
            translator = translation_match.group(1).strip()
            return [self._normalize_author_name(translator)]
        
        # Check for editor format: "Edited by" or "(Ed.)" or "(Eds.)"
        editor_match = re.search(r'[Ee]dited\s+by\s+([^(]+)\s*\((\d{4})\)', text)
        if editor_match:
            editor = editor_match.group(1).strip()
            return self._parse_author_list(editor)
        
        # Find the year parenthesis to locate end of author section
        year_match = re.search(r'\((\d{4})\)', text)
        if not year_match:
            # Try year without parentheses at start
            year_match = re.search(r'^([^(]+?)(\d{4})', text)
            if year_match:
                authors_text = year_match.group(1)
            else:
                # Fallback: take text before first period
                first_period = text.find('.')
                if first_period > 0:
                    authors_text = text[:first_period]
                else:
                    authors_text = text[:50]  # Just take first part
        else:
            authors_text = text[:year_match.start()].strip()
        
        # Clean up authors text
        authors_text = authors_text.strip().rstrip(',').rstrip('.')
        
        # Remove any title-like content that might have been included
        # (titles usually start after a period following the year)
        
        return self._parse_author_list(authors_text)
    
    def _parse_author_list(self, authors_text: str) -> List[str]:
        """Parse a string containing author names into a list"""
        authors = []
        
        if not authors_text:
            return authors
        
        # Handle "... &" pattern (indicates skipped middle authors)
        authors_text = re.sub(r'\.\.\.\s*&', ',', authors_text)
        authors_text = re.sub(r'\.{3}\s*&', ',', authors_text)
        
        # Normalize separators
        # Replace semicolons with a unique marker
        authors_text = authors_text.replace(';', '|||')
        
        # Replace " & " and " and " with marker (but not within names)
        authors_text = re.sub(r'\s+&\s+', '|||', authors_text)
        authors_text = re.sub(r'\s+and\s+', '|||', authors_text, flags=re.IGNORECASE)
        
        # Now split by the marker first (these are definite author separators)
        major_parts = authors_text.split('|||')
        
        for part in major_parts:
            part = part.strip()
            if not part:
                continue
            
            # Each part might still contain multiple authors separated by commas
            # But commas also separate "Last, First" - need to be smart about this
            extracted = self._extract_authors_from_comma_separated(part)
            authors.extend(extracted)
        
        # Clean up and normalize
        cleaned_authors = []
        for author in authors:
            author = self._normalize_author_name(author)
            if author and len(author) > 1:
                # Filter out obvious non-names
                if not re.match(r'^[\d\s.,]+$', author):  # Not just numbers/punctuation
                    cleaned_authors.append(author)
        
        return cleaned_authors
    
    def _extract_authors_from_comma_separated(self, text: str) -> List[str]:
        """
        Extract authors from comma-separated text, handling 'Last, First' format
        """
        authors = []
        
        # Split by comma
        parts = [p.strip() for p in text.split(',')]
        
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            
            if not part:
                i += 1
                continue
            
            # Check if next part looks like initials or a short first name
            # that belongs with this last name
            if i + 1 < len(parts):
                next_part = parts[i + 1].strip()
                
                # Patterns that indicate "next_part" is initials/first name for "part"
                # - Single letter(s) with dots: "A.", "A. B.", "A.B.", "C.J.C.H."
                # - Single short word that's capitalized
                # - Initials like "J.P." or "M.P"
                
                # More flexible initials pattern: one or more capital letters optionally followed by periods
                is_initials = bool(re.match(r'^(?:[A-Z]\.?)+$', next_part.replace(' ', '')))
                is_short_first = (len(next_part) > 0 and len(next_part) <= 3 and 
                                  next_part[0].isupper() and not next_part.endswith('.'))
                is_first_name_initial = bool(re.match(r'^[A-Z][a-z]*\.?$', next_part) and 
                                            len(next_part) <= 10)
                
                # Check if current part looks like a last name (capitalized word)
                looks_like_last_name = bool(re.match(r'^[A-Z][a-z]+$', part) or 
                                           re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', part) or  # Van Der etc
                                           re.match(r"^[A-Z]'[A-Z][a-z]+$", part) or  # O'Brien
                                           re.match(r'^[A-Z][a-z]+-[A-Z][a-z]+$', part))  # Hyphenated
                
                if looks_like_last_name and (is_initials or is_short_first or is_first_name_initial):
                    # Combine: "Last, First" -> author
                    full_name = f"{part}, {next_part}"
                    authors.append(full_name)
                    i += 2
                    continue
            
            # Check if this part is a complete name (First Last or single name)
            # First Last pattern: starts with capital, has space, both parts capitalized
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', part):
                # Looks like "First Last" already
                authors.append(part)
                i += 1
                continue
            
            # Single capitalized word - could be a single-name author
            if re.match(r'^[A-Z][a-z]+$', part) and len(part) > 2:
                # Check if it's likely a standalone name vs a last name waiting for first
                # If we're at the end or next part is also a full word, treat as standalone
                if i + 1 >= len(parts):
                    authors.append(part)
                elif not re.match(r'^[A-Z]\.?(\s*[A-Z]\.?)*$', parts[i + 1].strip()):
                    # Next part isn't initials, so this might be standalone
                    authors.append(part)
                else:
                    # Will be handled in next iteration
                    pass
                i += 1
                continue
            
            # Default: add as-is if it looks like a name
            if part and re.search(r'[A-Za-z]{2,}', part):
                authors.append(part)
            i += 1
        
        return authors
    
    def _normalize_author_name(self, name: str) -> str:
        """Normalize author name to 'First Last' format"""
        if not name:
            return ""
        
        name = name.strip()
        
        # Remove trailing/leading punctuation
        name = name.strip('.,;:')
        
        # Collapse whitespace
        name = re.sub(r'\s+', ' ', name)
        
        # Handle "Last, First" -> "First Last"
        if ',' in name:
            parts = name.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip() if len(parts) > 1 else ""
            if first and last:
                # Make sure first part looks like initials/first name
                if re.match(r'^[A-Z]', first):
                    name = f"{first} {last}"
                else:
                    name = last  # Just use last name if first is weird
            else:
                name = last
        else:
            # Handle "LastName Initials" pattern without comma (e.g., "Ong C.S.")
            # Pattern: Word followed by initials like A.B. or A.B or A. B.
            match = re.match(r'^([A-Z][a-z]+)\s+([A-Z]\.?\s*[A-Z]?\.?\s*[A-Z]?\.?)$', name)
            if match:
                last = match.group(1)
                first = match.group(2).strip()
                name = f"{first} {last}"
        
        # Clean up any remaining issues
        name = name.strip('.,;: ')
        
        return name
    
    def _extract_title(self, text: str) -> str:
        """Extract the paper/book title from reference text"""
        
        # Special case: Translation format
        # "Original Author (date). Title. Translated by Translator (year)"
        translation_match = re.search(r'[Tt]ranslated\s+by\s+[^(]+\((\d{4})\)', text)
        if translation_match:
            # Find title between first period and "Translated by"
            first_period = text.find('.')
            translated_pos = text.lower().find('translated by')
            if first_period > 0 and translated_pos > first_period:
                title = text[first_period + 1:translated_pos].strip()
                title = title.rstrip('.')
                if title:
                    return self._clean_title(title)
        
        # Find year in parentheses - title usually starts after
        # Look for a 4-digit year, handle (YYYY), (YYYY, Month), (Month Day, YYYY), etc.
        year_match = re.search(r'\((?:[A-Za-z]+\s+\d+,\s*)?(\d{4})(?:,\s*[A-Za-z]+)?\)[.,]?\s*', text)
        
        if year_match:
            after_year = text[year_match.end():]
            # Strip leading punctuation from after_year
            after_year = re.sub(r'^[,.\s]+', '', after_year)
            
            title = self._extract_title_from_text(after_year)
            if title:
                return self._clean_title(title)
        
        # Fallback for formats without parenthesized year
        title = self._extract_title_fallback(text)
        if title:
            return self._clean_title(title)
        
        return ""
    
    def _extract_title_from_text(self, text: str) -> str:
        """Extract title from text that starts with the title"""
        
        # First, check for comma-separated title/journal (unusual format)
        # Pattern: "Title, Journal of..." or "Title, Venue Name"
        comma_journal_patterns = [
            r',\s*Journal\s+of',
            r',\s*Annals\s+of',
            r',\s*Transactions\s+on',
            r',\s*Proceedings\s+of',
            r',\s*IEEE\s+',
            r',\s*ACM\s+',
            r',\s*Journal\s+für',  # German
        ]
        for pattern in comma_journal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = text[:match.start()].strip()
                return title
        
        # Check for consecutive short sentences that might indicate:
        # Title. Section/Subtitle. Journal.
        # We want to stop at the first short sentence that's followed by a journal
        parts = re.split(r'\.\s+', text)
        if len(parts) >= 3:
            # Check if second part is short (likely section name) and third is journal-like
            second_part = parts[1] if len(parts) > 1 else ""
            third_part = parts[2] if len(parts) > 2 else ""
            
            # If second part is short (1-3 words) and third part starts with journal-like pattern
            if second_part and len(second_part.split()) <= 4:
                journal_patterns = [
                    r'^(?:Annals|Journal|Proceedings|IEEE|ACM|SIAM|The\s+[A-Z]|[A-Z][a-z]+\s+Journal)',
                    r'^(?:Transactions|Communications|Reviews?|Bulletin|Archives?)',
                    r'^\d+\s*[\(:]',  # Volume/issue number
                ]
                for jp in journal_patterns:
                    if re.match(jp, third_part, re.IGNORECASE):
                        # Return just the first part as title
                        return parts[0].strip()
        
        # Comprehensive list of venue/publication markers that indicate end of title
        # These should come AFTER a period
        venue_markers = [
            # Specific publications/venues - "In X" patterns
            r'(?:In\s+)?Proceedings',
            r'(?:In\s+)?Conference',
            r'(?:In\s+)?Workshop',
            r'(?:In\s+)?Advances\s+in',
            r'(?:In\s+)?International',
            r'(?:In\s+)?(?:\d{4}\s+)?IEEE',  # "In IEEE" or "In 2014 IEEE"
            r'(?:In\s+)?ACM',
            r'(?:In\s+)?SIAM',
            r'(?:In\s+)?NIPS',
            r'(?:In\s+)?NeurIPS',
            r'(?:In\s+)?ICML',
            r'(?:In\s+)?ICLR',
            r'(?:In\s+)?CVPR',
            r'(?:In\s+)?ICCV',
            r'(?:In\s+)?ECCV',
            r'(?:In\s+)?AAAI',
            r'(?:In\s+)?IJCAI',
            r'(?:In\s+)?KDD',
            r'(?:In\s+)?WWW\s+\d',
            r'(?:In\s+)?SIGMOD',
            r'(?:In\s+)?VLDB',
            r'(?:In\s+)?(?:The\s+)?(?:\w+\s+)+Symposium',  # "The X Y Z Symposium"
            r'(?:In\s+)?The\s+(?:\w+\s+)+(?:for|on)\s+',  # "The X Y for/on Z" pattern
            r'In\s+[A-Z][a-z]+\s+(?:and|&)\s+',  # "In X and Y" 
            r'In\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s|:)',  # "In Computers Games:" or "In European Conference"
            r'In\s+[A-Z][a-z]+\s+Algebra',  # "In Linear Algebra"
            r'\"\s*In\s+',  # quoted title ending with In
            r'arXiv',
            r'Nature\b',
            r'Science\b',
            r'PNAS',
            r'PLoS',
            r'JMLR',
            # Generic publication types - these can catch journal names
            r'Journal\s+of',
            r'Annals\s+of',
            r'Transactions\s+on',
            r'Communications\s+of',
            r'Proceedings\s+of',
            r'Reviews?\s+of',
            r'Bulletin\s+of',
            r'Archives?\s+of',
            r'Reports?\s+of',
            r'The\s+[A-Z][a-z]+\s+Journal',  # "The Computer Journal" etc.
            r'[A-Z][a-z]+\s+Journal',  # "Computer Journal" etc.
            r'British\s+',
            r'American\s+',
            r'European\s+',
            r'International\s+Journal',
            r'Biometrika',
            r'Psycholog',
            r'Statistical',
            # Publishers
            r'Springer',
            r'Cambridge',
            r'Oxford',
            r'MIT\s+[Pp]ress',
            r'O\'Reilly',
            r'Wiley',
            r'Elsevier',
            r'McGraw',
            r'Prentice',
            r'Academic\s+Press',
            r'Morgan\s+Kaufmann',
            r'Addison.Wesley',
            r'CRC\s+[Pp]ress',
            r'Pearson',
            r'Hachette',
            r'Manning',
            r'Packt',
            r'Graphics\s+[Pp]ress',
            # Location indicators
            r'(?:New\s+York|Boston|London|Berlin|San\s+Francisco|Cambridge,?\s+MA|Redmond|Cheshire)',
            # Other markers
            r'Ph\.?D\.?\s+[Tt]hesis',
            r'Master\'?s?\s+[Tt]hesis',
            r'Technical\s+[Rr]eport',
            r'Working\s+[Pp]aper',
            r'Paper\s+[A-Z]?\-?\d',
            r'Chapter\s+\d',
            r'pp\.\s*\d',
            r'\d+\s*\(\d+\)',  # Volume(Issue) pattern like "25(4)"
            r'Vol\.\s*\d',
            r'Volume\s+\d',
            r'[Ee]dited\s+by',
            r'[Ee]ditor',
            r'Series\s+[A-Z]',
            r'Part\s+[A-Z\d]',
            r'\d+:\s*\d+',  # Page range like "197-219" or volume:pages
        ]
        
        # Build pattern to find first venue marker after a period
        venue_pattern = r'\.\s*(?:' + '|'.join(venue_markers) + ')'
        
        match = re.search(venue_pattern, text, re.IGNORECASE)
        if match:
            title = text[:match.start()].strip()
            return title
        
        # Check for pattern: sentence ending in period, followed by another sentence
        # that starts with a capitalized word that could be a section/journal name
        # Look for: ". Capitalized Word(s). " which suggests end of title
        section_pattern = r'\.\s+([A-Z][a-z]+(?:\s+[a-z]+)*)\.\s+[A-Z]'
        section_match = re.search(section_pattern, text)
        if section_match:
            # Check if the captured group looks like a section name or journal
            potential_section = section_match.group(1)
            # If it's short (1-3 words) and followed by more content, likely a section
            if len(potential_section.split()) <= 4:
                title = text[:section_match.start()].strip()
                return title
        
        # If no venue marker, try to find a reasonable stopping point
        # Look for period followed by location or year
        location_pattern = r'\.\s*(?:[A-Z][a-z]+,\s*[A-Z]{2}|[A-Z][a-z]+:\s*[A-Z])'
        match = re.search(location_pattern, text)
        if match:
            title = text[:match.start()].strip()
            return title
        
        # Look for volume/issue numbers that indicate end of title
        # But don't match version numbers like "4.0:" - require space before period
        vol_pattern = r'(?<!\d)\.\s+\d+\s*[\(:]'
        match = re.search(vol_pattern, text)
        if match:
            title = text[:match.start()].strip()
            return title
        
        # Take up to first sentence (period followed by space and capital letter)
        # But be careful not to cut at abbreviations or initials
        sentence_end = re.search(r'(?<![A-Z])(?<!\s[A-Z])(?<!vs)(?<!etc)(?<!al)(?<!No)\.\s+[A-Z]', text)
        if sentence_end:
            # Double-check this isn't cutting a subtitle
            before = text[:sentence_end.start()]
            after = text[sentence_end.end()-1:sentence_end.end()+30]
            # If what follows looks like a continuation (lowercase after first word), might be subtitle
            # But if it looks like a journal name or section, stop here
            if re.match(r'[A-Z][a-z]+\s+(of|and|in|on|for)\s', after):
                # Looks like a journal name, stop here
                title = before.strip()
                return title
            # Otherwise take the first sentence
            title = before.strip()
            return title
        
        # Last resort: take everything up to first period
        period_pos = text.find('.')
        if period_pos > 0:
            title = text[:period_pos].strip()
            return title
        
        return text.strip()
    
    def _extract_title_fallback(self, text: str) -> str:
        """Fallback title extraction for non-standard formats"""
        
        # Check for full-name format with "and": "LastName, FirstName, ..., and LastName, FirstName."
        full_name_author_end = re.search(r'and\s+[A-Z][a-z]+,\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?\.\s+', text)
        if full_name_author_end:
            after_author = text[full_name_author_end.end():]
            return self._extract_title_from_text(after_author)
        
        # Simple format: "LastName, Initial. Title. Venue..."
        simple_author = re.match(r'^([A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)*)\s+', text)
        if simple_author:
            after_author = text[simple_author.end():]
            return self._extract_title_from_text(after_author)
        
        # Another fallback: Find text between first period and venue
        first_period = text.find('. ')
        if first_period > 0:
            after_first_period = text[first_period + 2:]
            return self._extract_title_from_text(after_first_period)
        
        # Fallback: look for title in quotes
        quote_match = re.search(r'"([^"]+)"', text)
        if quote_match:
            return quote_match.group(1)
        
        return ""
    
    def _clean_title(self, title: str) -> str:
        """Clean up extracted title"""
        if not title:
            return ""
        
        # Remove leading/trailing whitespace and punctuation
        title = title.strip().strip('.,;:')
        
        # Collapse multiple spaces
        title = re.sub(r'\s+', ' ', title)
        
        # Remove leading article numbers like "LII."
        title = re.sub(r'^[IVXLC]+\.\s*', '', title)
        
        # Remove surrounding quotes
        title = title.strip('"\'""''')
        
        # Remove incomplete parenthetical content at the end
        # E.g., "(Vol" should be removed, but "(Vol. 1)" should stay
        # Remove "(Vol" or "(No" at the end if not closed
        title = re.sub(r'\s*\((?:Vol|No|pp|Chapter)\.?\s*$', '', title, flags=re.IGNORECASE)
        
        # Remove trailing incomplete edition info
        title = re.sub(r'\s*\(\d+(?:st|nd|rd|th)?\s*$', '', title, flags=re.IGNORECASE)
        
        # If title ends with unclosed parenthesis, try to close or remove it
        if '(' in title and ')' not in title:
            # Check if it's a meaningful parenthetical that got cut off
            paren_pos = title.rfind('(')
            paren_content = title[paren_pos+1:]
            # If it's just "Vol", "No", numbers, remove it
            if re.match(r'^(?:Vol|No|pp|ed|Chapter|\d+)\.?\s*$', paren_content, re.IGNORECASE):
                title = title[:paren_pos].strip()
        
        # Remove trailing punctuation again after cleanup
        title = title.strip().strip('.,;:')
        
        # Remove hyphenation artifacts from PDF line breaks
        title = re.sub(r'(\w)-\s+(\w)', r'\1\2', title)
        
        return title
    
    def get_references_summary(self) -> List[Dict]:
        """Get a summary of all parsed references"""
        return [
            {
                'citation_key': ref.citation_key,
                'title': ref.title,
                'year': ref.year,
                'first_author': ref.first_author,
                'last_author': ref.last_author,
                'num_authors': len(ref.authors),
                'chapter': ref.chapter
            }
            for ref in self.references
        ]


def extract_references_from_pdf(pdf_path: str) -> List[Reference]:
    """Convenience function to extract references from a PDF"""
    parser = PDFReferenceParser(pdf_path)
    parser.extract_text()
    return parser.parse_references()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        refs = extract_references_from_pdf(pdf_path)
        print(f"Found {len(refs)} references")
        for ref in refs[:15]:
            print(f"\n{ref.citation_key}:")
            print(f"  Title: {ref.title}")
            print(f"  First Author: {ref.first_author}")
            print(f"  Last Author: {ref.last_author}")
            print(f"  Year: {ref.year}")
            print(f"  All Authors: {ref.authors}")
