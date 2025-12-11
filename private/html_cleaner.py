"""
HTML Cleaner and Text Extractor
Cleans HTML content, removes scripts/ads/footers, and extracts readable article text.
"""

import logging
import re
from bs4 import BeautifulSoup, Comment
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class HTMLCleaner:
    """Cleans HTML and extracts readable text."""
    
    def __init__(self):
        # Common selectors for content to remove
        self.remove_selectors = [
            'script',
            'style',
            'nav',
            'header',
            'footer',
            'aside',
            '.advertisement',
            '.ad',
            '.ads',
            '.social-share',
            '.share-buttons',
            '.related-posts',
            '.comments',
            '.comment-section',
            '[class*="ad"]',
            '[class*="share"]',
            '[id*="ad"]',
            '[id*="share"]',
        ]
    
    def clean_html(self, html: str, metadata: Optional[Dict] = None) -> str:
        """
        Clean HTML and extract readable article text.
        
        Args:
            html: Raw HTML content
            metadata: Optional metadata dict with title, pubDate, etc. to prepend to text
            
        Returns:
            Cleaned plain text with optional metadata header
        """
        if not html:
            return ""
        
        logger.info("Cleaning HTML content")
        
        # Parse HTML
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style elements
        for element in soup(['script', 'style']):
            element.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Remove common unwanted elements by class/id patterns
        for selector in self.remove_selectors:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except Exception as e:
                logger.debug(f"Error removing selector {selector}: {e}")
        
        # Try to find main article content
        # Common article container selectors
        article_selectors = [
            'article',
            'main',
            '[role="main"]',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.content',
            '.post-body',
            '.article-body',
            '#content',
            '#main-content',
            '.blog-post-content',
        ]
        
        article_content = None
        for selector in article_selectors:
            try:
                found = soup.select_one(selector)
                if found:
                    article_content = found
                    logger.debug(f"Found article content using selector: {selector}")
                    break
            except Exception:
                continue
        
        # If no article container found, use body
        if not article_content:
            article_content = soup.find('body') or soup
        
        # Extract text
        text = article_content.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        text = self._clean_whitespace(text)
        
        # Remove common footer/header patterns
        text = self._remove_footer_header_patterns(text)
        
        # Prepend metadata header if provided (for date awareness in RAG)
        if metadata:
            header_parts = []
            
            # Add publication date if available
            if metadata.get('pubDate'):
                header_parts.append(f"Publication Date: {metadata['pubDate']}")
            
            # Add title if available
            if metadata.get('title'):
                header_parts.append(f"Title: {metadata['title']}")
            
            # Add source/feed if available
            if metadata.get('feed'):
                feed_name = metadata['feed']
                if feed_name == 'dev':
                    header_parts.append("Source: NVIDIA Developer Blog")
                elif feed_name == 'official':
                    header_parts.append("Source: NVIDIA Official Blog")
                else:
                    header_parts.append(f"Source: {feed_name}")
            
            # Prepend header to text
            if header_parts:
                header = '\n'.join(header_parts) + '\n\n---\n\n'
                text = header + text
                logger.info(f"Prepended metadata header with {len(header_parts)} fields")
        
        logger.info(f"Extracted {len(text)} characters of cleaned text")
        return text
    
    def _clean_whitespace(self, text: str) -> str:
        """Clean up excessive whitespace."""
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        # Strip leading/trailing whitespace
        text = text.strip()
        return text
    
    def _remove_footer_header_patterns(self, text: str) -> str:
        """Remove common footer and header text patterns."""
        # Common patterns to remove
        patterns = [
            r'Subscribe.*?Newsletter.*?\n',
            r'Follow us on.*?\n',
            r'Share this.*?\n',
            r'Related.*?Articles.*?\n',
            r'©.*?All rights reserved.*?\n',
            r'Privacy Policy.*?\n',
            r'Terms of Service.*?\n',
            r'Cookie Policy.*?\n',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        return text

