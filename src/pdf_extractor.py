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
    complete_text = ""
    for page in pdf.pages:
        complete_text += page.extract_text()

    print(complete_text)
    return complete_text

if __name__ == "__main__":
    pdf_path = "./data/input/References.pdf"
    pdf = load_pdf(pdf_path)
    text = extract_text_from_pdf(pdf)

