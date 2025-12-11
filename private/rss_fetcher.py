"""
RSS Feed Fetcher and Parser
Handles fetching RSS feeds, parsing XML, extracting metadata, and detecting new items.
"""

import feedparser
import logging
import requests
from typing import Dict, List, Set
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RSSFetcher:
    """Fetches and parses RSS feeds."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; RSSIngestor/1.0; +https://nvidia-blog-ingestor)"
        })
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError))
    )
    def fetch_rss(self, url: str) -> bytes:
        """
        Fetch RSS feed from URL with retry logic.
        
        Args:
            url: RSS feed URL
            
        Returns:
            Raw RSS XML as bytes
        """
        logger.info(f"Fetching RSS feed: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        # Ensure we have bytes
        if isinstance(response.content, bytes):
            return response.content
        return response.content.encode('utf-8')
    
    def parse_rss(self, xml_content: bytes) -> List[Dict]:
        """
        Parse RSS XML and extract item metadata.
        
        Args:
            xml_content: Raw RSS XML bytes
            
        Returns:
            List of item dictionaries with keys: title, link, guid, pubDate, description
        """
        logger.info("Parsing RSS XML")
        feed = feedparser.parse(xml_content)
        
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"RSS parsing warnings: {feed.bozo_exception}")
        
        items = []
        for entry in feed.entries:
            item = {
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "guid": entry.get("id", entry.get("link", "")).strip(),
                "pubDate": entry.get("published", entry.get("updated", "")).strip(),
                "description": entry.get("description", "").strip()
            }
            items.append(item)
        
        logger.info(f"Parsed {len(items)} items from RSS feed")
        return items
    
    def get_new_items(self, items: List[Dict], processed_ids: Set[str]) -> List[Dict]:
        """
        Filter items to only those not yet processed.
        
        Args:
            items: List of item dictionaries
            processed_ids: Set of already processed IDs (GUIDs or links)
            
        Returns:
            List of new items not in processed_ids
        """
        new_items = []
        for item in items:
            # Use GUID if available, otherwise use link
            item_id = item.get("guid") or item.get("link", "")
            if item_id and item_id not in processed_ids:
                new_items.append(item)
        
        logger.info(f"Found {len(new_items)} new items out of {len(items)} total")
        return new_items
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError))
    )
    def fetch_html(self, url: str) -> str:
        """
        Fetch full article HTML from URL with retry logic.
        
        Args:
            url: Article URL
            
        Returns:
            HTML content as string
        """
        logger.info(f"Fetching HTML from: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text
    
    def get_item_xml(self, item: Dict) -> str:
        """
        Convert item dictionary back to XML string for storage.
        
        Args:
            item: Item dictionary
            
        Returns:
            XML string representation
        """
        xml = f"""<item>
    <title><![CDATA[{item.get('title', '')}]]></title>
    <link>{item.get('link', '')}</link>
    <guid>{item.get('guid', item.get('link', ''))}</guid>
    <pubDate>{item.get('pubDate', '')}</pubDate>
    <description><![CDATA[{item.get('description', '')}]]></description>
</item>"""
        return xml

