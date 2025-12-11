"""
Google Cloud Storage Utilities
Handles reading/writing JSON and uploading files to GCS with retry logic.
"""

import json
import logging
from typing import Dict, Optional, Union
from google.cloud import storage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class GCSManager:
    """Manages GCS operations with retry logic."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize GCS manager.
        
        Args:
            bucket_name: GCS bucket name
        """
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def read_json(self, blob_path: str) -> Optional[Dict]:
        """
        Read JSON file from GCS.
        
        Args:
            blob_path: Path to JSON file in bucket
            
        Returns:
            Parsed JSON as dictionary, or None if file doesn't exist
        """
        try:
            blob = self.bucket.blob(blob_path)
            if not blob.exists():
                logger.info(f"JSON file does not exist: {blob_path}")
                return None
            
            content = blob.download_as_text()
            data = json.loads(content)
            logger.info(f"Read JSON from: {blob_path}")
            return data
            
        except storage.exceptions.NotFound:
            logger.info(f"JSON file not found: {blob_path}")
            return None
        except Exception as e:
            logger.error(f"Error reading JSON from {blob_path}: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def write_json(self, blob_path: str, data: Dict):
        """
        Write JSON file to GCS.
        
        Args:
            blob_path: Path to JSON file in bucket
            data: Dictionary to serialize as JSON
        """
        try:
            blob = self.bucket.blob(blob_path)
            content = json.dumps(data, indent=2, ensure_ascii=False)
            blob.upload_from_string(content, content_type='application/json')
            logger.info(f"Wrote JSON to: {blob_path}")
            
        except Exception as e:
            logger.error(f"Error writing JSON to {blob_path}: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def upload_file(self, blob_path: str, content: Union[str, bytes], content_type: Optional[str] = None):
        """
        Upload file content to GCS.
        
        Args:
            blob_path: Path to file in bucket
            content: File content as string or bytes
            content_type: Optional MIME type (auto-detected if not provided)
        """
        try:
            blob = self.bucket.blob(blob_path)
            
            # Auto-detect content type if not provided
            if content_type is None:
                if blob_path.endswith('.xml'):
                    content_type = 'application/xml'
                elif blob_path.endswith('.html'):
                    content_type = 'text/html'
                elif blob_path.endswith('.txt'):
                    content_type = 'text/plain'
                elif blob_path.endswith('.json'):
                    content_type = 'application/json'
                else:
                    content_type = 'application/octet-stream'
            
            # Convert string to bytes if needed
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            blob.upload_from_string(content, content_type=content_type)
            logger.info(f"Uploaded file to: {blob_path} ({len(content)} bytes)")
            
        except Exception as e:
            logger.error(f"Error uploading file to {blob_path}: {e}")
            raise

