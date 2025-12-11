"""
Vertex AI RAG Corpus Ingestion
Handles ingesting cleaned text and metadata into Vertex AI RAG Corpus.
Uses REST API since the Python SDK RAG module is not available in vertexai 1.43.0.
"""

import logging
import requests
from typing import Dict
from google.auth import default
from google.auth.transport.requests import Request
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RAGIngester:
    """Ingests content into Vertex AI RAG Corpus using REST API."""
    
    def __init__(self, rag_corpus_name: str, region: str, bucket_name: str):
        """
        Initialize RAG ingester.
        
        Args:
            rag_corpus_name: Full RAG corpus resource name
                e.g., projects/PROJECT/locations/REGION/ragCorpora/CORPUS_ID
            region: GCP region
            bucket_name: GCS bucket name where cleaned text files are stored
        """
        self.rag_corpus_name = rag_corpus_name
        self.region = region
        self.bucket_name = bucket_name
        
        # Extract project ID and corpus ID from rag_corpus_name
        # Format: projects/PROJECT/locations/REGION/ragCorpora/CORPUS_ID
        parts = rag_corpus_name.split('/')
        self.project_id = parts[1]
        self.corpus_id = parts[5]
        
        # Get credentials for API calls
        self.credentials, _ = default()
        
        # Base URL for RAG API
        self.base_url = f"https://{region}-aiplatform.googleapis.com/v1beta1"
        
        logger.info(f"Initialized RAG ingester for corpus: {rag_corpus_name}")
    
    def _get_access_token(self) -> str:
        """Get access token for API calls."""
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return self.credentials.token
    
    def _should_retry_on_concurrent_operation(self, response: requests.Response) -> bool:
        """Check if error is due to concurrent operation and should be retried."""
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "")
                if "other operations running" in error_message.lower():
                    return True
            except:
                pass
        return False
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    def ingest_to_rag(self, text: str, metadata: Dict):
        """
        Ingest text and metadata into RAG Corpus using REST API.
        The cleaned text file should already be uploaded to GCS.
        
        Args:
            text: Cleaned text content (already saved to GCS)
            metadata: Metadata dictionary with title, link, pubDate, item_id, feed, etc.
        """
        import time
        
        try:
            item_id = metadata.get('item_id', 'unknown')
            feed = metadata.get('feed', 'unknown')
            logger.info(f"Ingesting to RAG Corpus: {item_id}")
            
            # Construct GCS URI for the cleaned text file
            # Format: gs://bucket/folder/clean/item_id.txt
            gcs_uri = f"gs://{self.bucket_name}/{feed}/clean/{item_id}.txt"
            
            # Import RAG file using REST API
            # POST projects/{project}/locations/{location}/ragCorpora/{rag_corpus_id}/ragFiles:import
            import_url = (
                f"{self.base_url}/projects/{self.project_id}/locations/{self.region}/"
                f"ragCorpora/{self.corpus_id}/ragFiles:import"
            )
            
            # Prepare request body
            request_body = {
                "import_rag_files_config": {
                    "gcs_source": {
                        "uris": [gcs_uri]
                    },
                    "rag_file_chunking_config": {
                        "chunk_size": 768,  # words (optimized for technical blog content)
                        "chunk_overlap": 128  # words (~17% overlap for context preservation)
                    }
                }
            }
            
            # Make API call
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                import_url,
                headers=headers,
                json=request_body,
                timeout=300
            )
            
            # Handle concurrent operation errors with retry
            if response.status_code == 400 and self._should_retry_on_concurrent_operation(response):
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "")
                logger.warning(
                    f"Concurrent operation detected for {item_id}. "
                    f"Will retry after backoff. Error: {error_msg}"
                )
                # Raise exception to trigger retry
                raise Exception(f"Concurrent operation: {error_msg}")
            
            if response.status_code not in [200, 201]:
                error_msg = f"Failed to import RAG file: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            result = response.json()
            
            # The import endpoint returns a Long Running Operation (LRO)
            # We need to poll the operation until it completes
            operation_name = result.get("name")
            if not operation_name:
                error_msg = f"No operation name in import response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Import operation started: {operation_name}. Polling until completion...")
            
            # Poll operation until done
            max_poll_attempts = 120  # 10 minutes max (120 * 5 seconds)
            poll_attempt = 0
            imported_count = 0
            skipped_count = 0
            
            while poll_attempt < max_poll_attempts:
                poll_attempt += 1
                
                # Get operation status
                operation_url = f"{self.base_url}/{operation_name}"
                op_response = requests.get(
                    operation_url,
                    headers=headers,
                    timeout=60
                )
                
                if op_response.status_code != 200:
                    error_msg = (
                        f"Failed to poll operation: {op_response.status_code} - "
                        f"{op_response.text}"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                op_result = op_response.json()
                
                # Check if operation is done
                if op_result.get("done", False):
                    # Check for errors
                    if "error" in op_result:
                        error_details = op_result["error"]
                        error_msg = (
                            f"Import operation failed: {error_details.get('message', 'Unknown error')} "
                            f"(code: {error_details.get('code', 'unknown')})"
                        )
                        logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    # Get actual imported/skipped counts from response
                    response_data = op_result.get("response", {})
                    imported_count = response_data.get("imported_rag_files_count", 0)
                    skipped_count = response_data.get("skipped_rag_files_count", 0)
                    
                    logger.info(
                        f"Import operation completed for {item_id}. "
                        f"Imported: {imported_count} files, "
                        f"Skipped: {skipped_count} files"
                    )
                    break
                
                # Operation still in progress, wait before polling again
                if poll_attempt % 12 == 0:  # Log every minute
            logger.info(
                        f"Import operation still in progress (attempt {poll_attempt}/"
                        f"{max_poll_attempts})..."
                    )
                time.sleep(5)  # Wait 5 seconds before polling again
            else:
                # Max attempts reached
                error_msg = (
                    f"Import operation timed out after {max_poll_attempts} attempts "
                    f"({max_poll_attempts * 5} seconds)"
            )
                logger.error(error_msg)
                raise Exception(error_msg)
            
        except Exception as e:
            logger.error(f"Error ingesting to RAG Corpus: {e}")
            # Re-raise to trigger retry
            raise

