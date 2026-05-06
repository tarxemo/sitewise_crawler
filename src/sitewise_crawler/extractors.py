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

class DomainClassifier:
    """
    Fast, zero-network domain-level category lookup.
    Avoids unnecessary scraping/AI calls for well-known websites.
    Add to KNOWN_CATEGORIES to expand coverage.
    """
    KNOWN_CATEGORIES: dict = {
        # Development & Tech
        "github.com": "Development", "gitlab.com": "Development",
        "stackoverflow.com": "Development", "developer.mozilla.org": "Development",
        "docs.python.org": "Development", "npmjs.com": "Development",
        "pypi.org": "Development", "huggingface.co": "AI/ML",
        "kaggle.com": "AI/ML", "colab.research.google.com": "AI/ML",
        "openai.com": "AI/ML", "anthropic.com": "AI/ML",
        # Social Media
        "twitter.com": "Social Media", "x.com": "Social Media",
        "instagram.com": "Social Media", "facebook.com": "Social Media",
        "tiktok.com": "Social Media", "snapchat.com": "Social Media",
        "reddit.com": "Social Media", "linkedin.com": "Professional Networking",
        # Entertainment
        "youtube.com": "Entertainment", "netflix.com": "Entertainment",
        "twitch.tv": "Entertainment", "spotify.com": "Entertainment",
        "disneyplus.com": "Entertainment", "primevideo.com": "Entertainment",
        # Education
        "coursera.org": "Education", "udemy.com": "Education",
        "edx.org": "Education", "khanacademy.org": "Education",
        "wikipedia.org": "Reference", "britannica.com": "Reference",
        # News & Media
        "bbc.com": "News", "cnn.com": "News", "reuters.com": "News",
        "theguardian.com": "News", "nytimes.com": "News",
        # Shopping / Commerce
        "amazon.com": "Shopping", "ebay.com": "Shopping",
        "aliexpress.com": "Shopping", "shopify.com": "E-Commerce",
        # Finance
        "binance.com": "Crypto/Finance", "coinbase.com": "Crypto/Finance",
        "investing.com": "Finance", "bloomberg.com": "Finance",
        # Gaming
        "store.steampowered.com": "Gaming", "epicgames.com": "Gaming",
        "roblox.com": "Gaming",
        # NSFW / High-Risk
        "pornhub.com": "NSFW", "xvideos.com": "NSFW",
        "xhamster.com": "NSFW", "onlyfans.com": "NSFW",
        # Productivity
        "notion.so": "Productivity", "trello.com": "Productivity",
        "slack.com": "Productivity", "zoom.us": "Productivity",
        "mail.google.com": "Communication", "outlook.live.com": "Communication",
    }

    RISK_LEVELS: dict = {
        "NSFW": 1.0,
        "Social Media": 0.4,
        "Entertainment": 0.3,
        "Gaming": 0.35,
        "Shopping": 0.2,
        "Development": 0.0,
        "Education": 0.0,
        "AI/ML": 0.0,
        "Productivity": 0.0,
    }

    @staticmethod
    def classify(url: str) -> Optional[str]:
        """Returns a category string or None if the domain is not in the known list."""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            return DomainClassifier.KNOWN_CATEGORIES.get(domain)
        except Exception:
            return None

    @staticmethod
    def get_risk_score(url: str) -> float:
        """Returns a 0.0–1.0 risk score based on known domain category. Returns 0.0 for unknown."""
        category = DomainClassifier.classify(url)
        if category is None:
            return 0.0
        return DomainClassifier.RISK_LEVELS.get(category, 0.0)

    @staticmethod
    def is_known_nsfw(url: str) -> bool:
        """Quick check if URL belongs to a known NSFW domain."""
        return DomainClassifier.classify(url) == "NSFW"


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
