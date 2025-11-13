import pdfplumber
import re
from typing import List, Optional

def load_pdf(file_path: str):
    """ Load a PDF file and return a pdfplumber PDF object."""
    try:
        pdf = pdfplumber.open(file_path)
        return pdf
    except Exception as e:
        print(f"Error loading PDF file: {e}. Please check the file path and try again.")
        return None

def extract_text_from_pdf(pdf):
    """ Extract text from each page from the PDF."""
    if pdf is None:
        return ""
    
    complete_text = ""

    # Get text by page
    for i, page in enumerate(pdf.pages):
        page_text = page.extract_text()
        if page_text:
            complete_text += page_text
            complete_text += "\n"
        print(f"Processed page {i+1}/{len(pdf.pages)}")

    pdf.close()
    return complete_text

def remove_chapter_markers(text):
    """
    Remove chapter markers to prepare references processing
    """
    # Use regex to find all chapter markers
    chapter_pattern = r'[—\-]{3,}.*?Chapter\s+\d+.*?[—\-]{3,}'

    # Remove chapter markers
    cleaned_text = re.sub(chapter_pattern, '', text)

    # Also remove standalone lines of just dashes
    standalone_dashes = r'\n[—\-]{4,}\n'
    cleaned_text = re.sub(standalone_dashes, '\n', cleaned_text)
    
    return cleaned_text

def split_into_references(text):
    """
    Split the text into individual references.

    Pattern to match: [Author 'YY] or [Author 'YYYY]
    Examples: [Hill '79], [Wiener '48], [Van der Maaten '08]
    """
    references = []

    # Use regex to find all reference markers
    reference_pattern = r'\[[^\]]+[\'\u2018\u2019]\d{2,4}(?:\s+[A-Z])?\]'

    # clean text
    text = remove_chapter_markers(text)
    text = text.replace("\n", " ")

    # Find all matches and their positions
    matches = list(re.finditer(reference_pattern, text))

    print(f"Found {len(matches)} reference markers")

    # Extract full reference text between markers
    for i in range(len(matches)):
        start = matches[i].start()
        if i + 1 < len(matches):
            end = matches[i+1].start()
        else:
            end = len(text)

        # Extract the reference
        references.append(text[start:end].strip())

    return references

if __name__ == "__main__":
    pdf_path = "./data/input/References.pdf"

    # Load pdf
    pdf = load_pdf(pdf_path)
    if pdf is None:
        exit(1)

    # Extract text
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(pdf)
    print(f"Extracted {len(text)} characters")

    # Split into references
    print("\nSplitting into references...")
    references = split_into_references(text)

    # Display results
    print(f"\nFound {len(references)} references")
    print("\nFirst 3 references:")
    for i, ref in enumerate(references[:3]):
        print(f"\n--- Reference {i+1} ---")
        print(ref[:200] + "..." if len(ref) > 200 else ref)