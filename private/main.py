#!/usr/bin/env python3
"""
Cloud Run Job: RSS Feed Ingestion and RAG Processing
Main entry point that coordinates RSS fetching, HTML cleaning, GCS storage,
RAG corpus ingestion, and vector search upserts.
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from typing import Dict, List

# Try to import Cloud Logging, but fall back gracefully if not available
try:
    from google.cloud import logging as cloud_logging
    from google.cloud.logging.handlers import CloudLoggingHandler
    CLOUD_LOGGING_AVAILABLE = True
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False

from mcp.config import (
    BUCKET_NAME,
    REGION,
    RAG_CORPUS,
    VECTOR_SEARCH_ENDPOINT_ID,
    VECTOR_SEARCH_INDEX_ID,
    EMBEDDING_MODEL,
    RSS_FEEDS,
    LOG_LEVEL,
    MIN_TEXT_LENGTH
)
from gcs_utils import GCSManager
from html_cleaner import HTMLCleaner
from rag_ingest import RAGIngester
from rss_fetcher import RSSFetcher
from vector_search_ingest import VectorSearchIngester

# Configure structured JSON logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Use Cloud Logging if available (in Cloud Run)
if CLOUD_LOGGING_AVAILABLE:
    try:
        client = cloud_logging.Client()
        handler = CloudLoggingHandler(client)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(handler)
    except Exception:
        pass  # Fallback to stdout logging

logger = logging.getLogger(__name__)


def log_structured(level: str, message: str, **kwargs):
    """Emit structured JSON log entry."""
    log_entry = {
        "severity": level.upper(),
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **kwargs
    }
    logger.log(getattr(logging, level.upper(), logging.INFO), json.dumps(log_entry))


def process_feed(feed_name: str, feed_config: Dict, gcs: GCSManager, 
                 rss_fetcher: RSSFetcher, html_cleaner: HTMLCleaner,
                 rag_ingester: RAGIngester, vector_ingester: VectorSearchIngester):
    """Process a single RSS feed: fetch, detect new items, process, and ingest."""
    
    folder = feed_config["folder"]
    url = feed_config["url"]
    
    log_structured("info", f"Processing feed: {feed_name}", feed=feed_name, url=url)
    
    try:
        # Fetch and parse RSS
        log_structured("info", "Fetching RSS feed", feed=feed_name)
        rss_xml = rss_fetcher.fetch_rss(url)
        items = rss_fetcher.parse_rss(rss_xml)
        log_structured("info", f"Parsed {len(items)} RSS items", feed=feed_name, count=len(items))
        
        # Load processed IDs
        processed_ids_path = f"{folder}/processed_ids.json"
        processed_ids = gcs.read_json(processed_ids_path) or {"ids": []}
        existing_ids = set(processed_ids.get("ids", []))
        log_structured("info", f"Loaded {len(existing_ids)} processed IDs", feed=feed_name)
        
        # Detect new items
        new_items = rss_fetcher.get_new_items(items, existing_ids)
        log_structured("info", f"Found {len(new_items)} new items", feed=feed_name, count=len(new_items))
        
        if not new_items:
            log_structured("info", "No new items to process", feed=feed_name)
            return
        
        # Process each new item
        new_processed_ids = []
        processed_count = 0
        error_count = 0
        
        for item in new_items:
            # Generate a safe item_id for file names
            # Use GUID if available, otherwise extract from link, fallback to timestamp
            raw_id = item.get("guid") or item.get("link", "")
            if raw_id:
                # Sanitize ID for use in file paths (remove special chars, limit length)
                item_id = re.sub(r'[^\w\-_\.]', '_', raw_id)[:200]  # Limit to 200 chars
                if not item_id or item_id == '_':
                    item_id = f"item_{int(datetime.utcnow().timestamp())}"
            else:
                item_id = f"item_{int(datetime.utcnow().timestamp())}"
            
            try:
                log_structured("info", "Processing item", feed=feed_name, item_id=item_id, title=item.get("title", "")[:100])
                
                # Save raw XML
                xml_path = f"{folder}/raw_xml/{item_id}.xml"
                gcs.upload_file(xml_path, rss_fetcher.get_item_xml(item))
                log_structured("info", "Saved raw XML", feed=feed_name, item_id=item_id, path=xml_path)
                
                # Fetch full HTML
                article_url = item.get("link")
                if not article_url:
                    log_structured("warning", "Item missing link, skipping", feed=feed_name, item_id=item_id)
                    continue
                
                log_structured("info", "Fetching article HTML", feed=feed_name, item_id=item_id, url=article_url)
                html_content = rss_fetcher.fetch_html(article_url)
                
                # Save raw HTML
                html_path = f"{folder}/raw_html/{item_id}.html"
                gcs.upload_file(html_path, html_content)
                log_structured("info", "Saved raw HTML", feed=feed_name, item_id=item_id, path=html_path)
                
                # Prepare metadata (before cleaning so we can include it in the text)
                metadata = {
                    "title": item.get("title", ""),
                    "link": article_url,
                    "pubDate": item.get("pubDate", ""),
                    "feed": feed_name,
                    "item_id": item_id,
                    "processed_at": datetime.utcnow().isoformat() + "Z"
                }
                
                # Clean HTML to text (with metadata header for date awareness)
                clean_text = html_cleaner.clean_html(html_content, metadata=metadata)
                if not clean_text or len(clean_text.strip()) < MIN_TEXT_LENGTH:
                    log_structured("warning", "Cleaned text too short, skipping", feed=feed_name, item_id=item_id, length=len(clean_text) if clean_text else 0)
                    continue
                
                # Save cleaned text
                text_path = f"{folder}/clean/{item_id}.txt"
                gcs.upload_file(text_path, clean_text)
                log_structured("info", "Saved cleaned text", feed=feed_name, item_id=item_id, path=text_path, text_length=len(clean_text))
                
                # Ingest to RAG Corpus
                log_structured("info", "Ingesting to RAG Corpus", feed=feed_name, item_id=item_id)
                rag_ingester.ingest_to_rag(clean_text, metadata)
                log_structured("info", "RAG ingestion complete", feed=feed_name, item_id=item_id)
                
                # Small delay to reduce concurrent RAG operation conflicts
                time.sleep(2)  # 2 second delay between RAG imports
                
                # Embed and upsert to Vector Search
                log_structured("info", "Embedding text", feed=feed_name, item_id=item_id)
                embedding = vector_ingester.embed_text(clean_text)
                log_structured("info", "Upserting vector", feed=feed_name, item_id=item_id, embedding_dim=len(embedding))
                vector_ingester.upsert_vector(embedding, item_id, metadata)
                log_structured("info", "Vector upsert complete", feed=feed_name, item_id=item_id)
                
                # Mark as processed
                new_processed_ids.append(item_id)
                processed_count += 1
                log_structured("info", "Item processing complete", feed=feed_name, item_id=item_id)
                
            except Exception as e:
                error_count += 1
                log_structured("error", "Error processing item", feed=feed_name, item_id=item_id, error=str(e), error_type=type(e).__name__)
                continue
        
        # Update processed_ids.json
        if new_processed_ids:
            processed_ids["ids"].extend(new_processed_ids)
            gcs.write_json(processed_ids_path, processed_ids)
            log_structured("info", "Updated processed_ids.json", feed=feed_name, new_count=len(new_processed_ids), total_count=len(processed_ids["ids"]))
        
        log_structured("info", f"Feed processing complete", feed=feed_name, processed=processed_count, errors=error_count)
        
    except Exception as e:
        log_structured("error", f"Error processing feed", feed=feed_name, error=str(e), error_type=type(e).__name__)
        raise


def main():
    """Main entry point for Cloud Run Job."""
    log_structured("info", "Starting RSS ingestion job", 
                   bucket=BUCKET_NAME, region=REGION, feeds=list(RSS_FEEDS.keys()))
    
    try:
        # Initialize components
        gcs = GCSManager(BUCKET_NAME)
        rss_fetcher = RSSFetcher()
        html_cleaner = HTMLCleaner()
        rag_ingester = RAGIngester(RAG_CORPUS, REGION, BUCKET_NAME)
        vector_ingester = VectorSearchIngester(
            endpoint_id=VECTOR_SEARCH_ENDPOINT_ID,
            index_id=VECTOR_SEARCH_INDEX_ID,
            region=REGION,
            model=EMBEDDING_MODEL
        )
        
        # Process each feed
        for feed_name, feed_config in RSS_FEEDS.items():
            process_feed(feed_name, feed_config, gcs, rss_fetcher, html_cleaner, 
                        rag_ingester, vector_ingester)
        
        log_structured("info", "RSS ingestion job completed successfully")
        sys.exit(0)
        
    except Exception as e:
        log_structured("error", "RSS ingestion job failed", error=str(e), error_type=type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()

