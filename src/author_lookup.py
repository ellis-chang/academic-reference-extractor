"""
Author Information Lookup Module
Uses web search and LLM to find author affiliations and contact details
"""

import os
import re
import json
import time
import requests
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from urllib.parse import quote_plus


@dataclass
class AuthorInfo:
    """Data class for author information"""
    name: str = ""
    affiliation: str = ""
    department: str = ""
    email: str = ""
    institution_url: str = ""
    confidence: float = 0.0
    source: str = ""


class SemanticScholarAPI:
    """Interface to Semantic Scholar API for author lookup"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers['x-api-key'] = api_key
    
    def search_paper(self, title: str, year: str = "") -> Optional[Dict]:
        """Search for a paper by title"""
        query = title
        if year:
            query = f"{title} {year}"
        
        params = {
            'query': query,
            'limit': 5,
            'fields': 'title,authors,year,venue'
        }
        
        try:
            response = requests.get(
                f"{self.BASE_URL}/paper/search",
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    return data['data'][0]
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"Semantic Scholar API error: {e}")
        
        return None
    
    def get_author_details(self, author_id: str) -> Optional[Dict]:
        """Get detailed author information"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/author/{author_id}",
                params={'fields': 'name,affiliations,url,homepage,paperCount,citationCount'},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Semantic Scholar author lookup error: {e}")
        
        return None
    
    def search_author(self, name: str) -> Optional[Dict]:
        """Search for an author by name"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/author/search",
                params={
                    'query': name,
                    'limit': 5,
                    'fields': 'name,affiliations,url,homepage,paperCount'
                },
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    return data['data'][0]
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Semantic Scholar author search error: {e}")
        
        return None


class LLMAuthorExtractor:
    """Use LLM to extract and validate author information"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.anthropic_client = None
        
        if self.api_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                print("Warning: anthropic package not installed")
    
    def extract_author_info(self, author_name: str, paper_title: str, 
                           paper_year: str, raw_reference: str) -> AuthorInfo:
        """Use LLM to extract author information from reference and general knowledge"""
        
        if not self.anthropic_client:
            return AuthorInfo(name=author_name, confidence=0.0)
        
        prompt = f"""Based on the following academic reference, please provide information about the author "{author_name}".

Reference: {raw_reference}
Paper Title: {paper_title}
Year: {paper_year}

Please extract or infer the following information about this author. If information is not available or cannot be reliably determined, indicate "Unknown".

Respond in JSON format:
{{
    "name": "Full name of the author",
    "affiliation": "University or organization name",
    "department": "Department or school name if known",
    "email": "Email address if it can be determined from institutional patterns",
    "confidence": 0.0 to 1.0 indicating how confident you are in this information
}}

Important: 
- For well-known researchers, use your knowledge about their affiliations
- For less known authors, try to infer from the publication venue or co-authors
- Email patterns often follow formats like firstname.lastname@university.edu
- Only provide information you're reasonably confident about"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return AuthorInfo(
                    name=data.get('name', author_name),
                    affiliation=data.get('affiliation', ''),
                    department=data.get('department', ''),
                    email=data.get('email', ''),
                    confidence=float(data.get('confidence', 0.5)),
                    source='LLM'
                )
                
        except Exception as e:
            print(f"LLM extraction error: {e}")
        
        return AuthorInfo(name=author_name, confidence=0.0)


class WebSearchAuthorLookup:
    """Search the web for author information"""
    
    def __init__(self, google_api_key: Optional[str] = None, 
                 google_cse_id: Optional[str] = None):
        self.google_api_key = google_api_key or os.environ.get('GOOGLE_API_KEY')
        self.google_cse_id = google_cse_id or os.environ.get('GOOGLE_CSE_ID')
    
    def search_dblp(self, author_name: str) -> Optional[Dict]:
        """Search DBLP for author information"""
        try:
            encoded_name = quote_plus(author_name)
            url = f"https://dblp.org/search/author/api?q={encoded_name}&format=json"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                hits = data.get('result', {}).get('hits', {}).get('hit', [])
                if hits:
                    # Return first match
                    author_data = hits[0].get('info', {})
                    return {
                        'name': author_data.get('author', ''),
                        'url': author_data.get('url', ''),
                        'affiliations': author_data.get('notes', {}).get('note', [])
                    }
        except Exception as e:
            print(f"DBLP search error: {e}")
        
        return None
    
    def search_google_scholar_profile(self, author_name: str) -> Optional[str]:
        """Try to find Google Scholar profile URL"""
        if not self.google_api_key or not self.google_cse_id:
            return None
        
        try:
            query = f"{author_name} site:scholar.google.com"
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.google_cse_id,
                'q': query,
                'num': 3
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                for item in items:
                    link = item.get('link', '')
                    if 'scholar.google.com/citations' in link:
                        return link
        except Exception as e:
            print(f"Google search error: {e}")
        
        return None


class AuthorLookupService:
    """Main service for looking up author information"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None,
                 google_api_key: Optional[str] = None,
                 google_cse_id: Optional[str] = None,
                 s2_api_key: Optional[str] = None):
        
        self.semantic_scholar = SemanticScholarAPI(s2_api_key)
        self.llm_extractor = LLMAuthorExtractor(anthropic_api_key)
        self.web_search = WebSearchAuthorLookup(google_api_key, google_cse_id)
        
    def lookup_author(self, author_name: str, paper_title: str = "", 
                     paper_year: str = "", raw_reference: str = "") -> AuthorInfo:
        """Look up author information using multiple sources"""
        
        best_info = AuthorInfo(name=author_name)
        
        # 1. Try Semantic Scholar first
        s2_result = self._lookup_semantic_scholar(author_name, paper_title)
        if s2_result and s2_result.affiliation:
            best_info = s2_result
            best_info.source = "Semantic Scholar"
        
        # 2. Try DBLP
        if not best_info.affiliation:
            dblp_result = self.web_search.search_dblp(author_name)
            if dblp_result:
                affiliations = dblp_result.get('affiliations', [])
                if affiliations:
                    if isinstance(affiliations, list) and affiliations:
                        best_info.affiliation = str(affiliations[0])
                    elif isinstance(affiliations, str):
                        best_info.affiliation = affiliations
                    best_info.source = "DBLP"
                    best_info.confidence = 0.7
        
        # 3. Use LLM for enrichment or as fallback
        if not best_info.affiliation or best_info.confidence < 0.6:
            llm_result = self.llm_extractor.extract_author_info(
                author_name, paper_title, paper_year, raw_reference
            )
            
            # Merge results, preferring higher confidence
            if llm_result.confidence > best_info.confidence:
                if llm_result.affiliation:
                    best_info.affiliation = llm_result.affiliation
                if llm_result.department:
                    best_info.department = llm_result.department
                if llm_result.email and '@' in llm_result.email:
                    best_info.email = llm_result.email
                best_info.confidence = max(best_info.confidence, llm_result.confidence)
                if not best_info.source:
                    best_info.source = "LLM"
        
        return best_info
    
    def _lookup_semantic_scholar(self, author_name: str, 
                                  paper_title: str = "") -> Optional[AuthorInfo]:
        """Look up author on Semantic Scholar"""
        
        # First try searching by paper
        if paper_title:
            paper = self.semantic_scholar.search_paper(paper_title)
            if paper:
                authors = paper.get('authors', [])
                for author in authors:
                    if self._names_match(author.get('name', ''), author_name):
                        author_id = author.get('authorId')
                        if author_id:
                            details = self.semantic_scholar.get_author_details(author_id)
                            if details:
                                affiliations = details.get('affiliations', [])
                                return AuthorInfo(
                                    name=details.get('name', author_name),
                                    affiliation=affiliations[0] if affiliations else '',
                                    institution_url=details.get('homepage', ''),
                                    confidence=0.9
                                )
        
        # Direct author search
        author_data = self.semantic_scholar.search_author(author_name)
        if author_data:
            affiliations = author_data.get('affiliations', [])
            return AuthorInfo(
                name=author_data.get('name', author_name),
                affiliation=affiliations[0] if affiliations else '',
                institution_url=author_data.get('homepage', ''),
                confidence=0.8
            )
        
        return None
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two author names likely refer to the same person"""
        # Normalize names
        n1 = name1.lower().replace('.', '').replace(',', ' ').split()
        n2 = name2.lower().replace('.', '').replace(',', ' ').split()
        
        # Check if last names match
        if n1 and n2:
            # Compare last word (usually last name)
            if n1[-1] == n2[-1]:
                return True
            # Check first word too
            if n1[0] == n2[0]:
                return True
        
        return False
    
    def batch_lookup(self, authors: List[Tuple[str, str, str, str]], 
                    progress_callback=None) -> List[AuthorInfo]:
        """
        Batch lookup for multiple authors
        
        Args:
            authors: List of tuples (author_name, paper_title, paper_year, raw_reference)
            progress_callback: Optional function to report progress
            
        Returns:
            List of AuthorInfo objects
        """
        results = []
        total = len(authors)
        
        for i, (name, title, year, raw_ref) in enumerate(authors):
            info = self.lookup_author(name, title, year, raw_ref)
            results.append(info)
            
            if progress_callback:
                progress_callback(i + 1, total, name)
            
            # Rate limiting
            time.sleep(0.3)
        
        return results


def create_lookup_service_from_env() -> AuthorLookupService:
    """Create AuthorLookupService using environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    return AuthorLookupService(
        anthropic_api_key=os.environ.get('ANTHROPIC_API_KEY'),
        google_api_key=os.environ.get('GOOGLE_API_KEY'),
        google_cse_id=os.environ.get('GOOGLE_CSE_ID'),
        s2_api_key=os.environ.get('S2_API_KEY')
    )


if __name__ == "__main__":
    # Test the service
    service = create_lookup_service_from_env()
    
    test_authors = [
        ("Geoffrey Hinton", "Deep Learning", "2016", ""),
        ("Yoshua Bengio", "Deep Learning", "2016", ""),
    ]
    
    for name, title, year, _ in test_authors:
        info = service.lookup_author(name, title, year)
        print(f"\n{info.name}:")
        print(f"  Affiliation: {info.affiliation}")
        print(f"  Email: {info.email}")
        print(f"  Confidence: {info.confidence}")
        print(f"  Source: {info.source}")
