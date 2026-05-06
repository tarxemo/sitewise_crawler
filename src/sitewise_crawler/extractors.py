import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Set
from bs4 import BeautifulSoup
import trafilatura

class LinkExtractor:
    @staticmethod
    def normalize_url(url: str, base_url: str) -> str:
        """Normalize URL and remove fragments."""
        parsed = urlparse(url)
        if not parsed.netloc:
            url = urljoin(base_url, url)
            parsed = urlparse(url)
        
        # Remove fragments and normalize
        parsed = parsed._replace(fragment='')
        normalized = urlunparse(parsed)
        return normalized.rstrip('/')

    @staticmethod
    def is_same_domain(url: str, base_url: str) -> bool:
        return urlparse(url).netloc == urlparse(base_url).netloc

    @staticmethod
    def extract_links(html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, 'lxml')
        links = set()
        for a in soup.find_all('a', href=True):
            links.add(a['href'])
        
        normalized = []
        for link in links:
            try:
                norm = LinkExtractor.normalize_url(link, base_url)
                normalized.append(norm)
            except:
                continue
        return list(set(normalized))

class ContentExtractor:
    @staticmethod
    def clean_text(html: str) -> str:
        """Extract main content text, removing boilerplates."""
        # Use trafilatura for high-quality extraction
        content = trafilatura.extract(html, include_comments=False, include_tables=True, no_fallback=False)
        if not content:
            # Fallback to BeautifulSoup if trafilatura fails
            soup = BeautifulSoup(html, 'lxml')
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            content = soup.get_text(separator=' ')
        
        # Final cleanup
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    @staticmethod
    def extract_from_binary(content: bytes, content_type: str) -> str:
        """Extract text from non-HTML binary files (PDF, Docx)."""
        import io
        
        # Handle PDF
        if 'pdf' in content_type:
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
            except Exception as e:
                return f"Error extracting PDF: {e}"
        
        # Handle Word Documents
        elif 'word' in content_type or 'officedocument.wordprocessingml' in content_type:
            try:
                from docx import Document
                doc = Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text.strip()
            except Exception as e:
                return f"Error extracting Word doc: {e}"
                
        return "Unsupported binary format"

class SPADetector:
    FRAMEWORK_PATTERNS = {
        'react': [r'react-root', r'_reactRootContainer', r'data-reactid', r'data-reactroot'],
        'vue': [r'v-bind:', r'v-on:', r'__vue__', r'data-v-'],
        'angular': [r'ng-version', r'ng-app', r'ng-controller', r'ng-repeat'],
        'nextjs': [r'__NEXT_DATA__', r'_next/static'],
        'nuxt': [r'__NUXT__'],
    }

    @staticmethod
    def is_spa(html: str) -> bool:
        """Detect if the page is likely a Single Page Application."""
        for framework, patterns in SPADetector.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return True
        
        # Check for empty body with lots of scripts
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
            # If body is mostly empty but has many script tags
            clean_body = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
            if len(clean_body.strip()) < 200 and '<script' in body_content:
                return True
                
        return False
