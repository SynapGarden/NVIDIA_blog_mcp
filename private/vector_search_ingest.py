"""
Vertex AI Vector Search Ingestion
Handles embedding text using text-multilingual-embedding-002 and upserting vectors into Vector Search index.
"""

import logging
from typing import Dict, List
from google.cloud import aiplatform
from google.cloud.aiplatform import matching_engine
from google.cloud.aiplatform.matching_engine import matching_engine_index_endpoint
from vertexai.language_models import TextEmbeddingModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class VectorSearchIngester:
    """Embeds text and upserts vectors to Vertex AI Vector Search."""
    
    def __init__(self, endpoint_id: str, index_id: str, region: str, model: str = "text-multilingual-embedding-002"):
        """
        Initialize Vector Search ingester.
        
        Args:
            endpoint_id: Vector Search endpoint ID
            index_id: Vector Search index ID
            region: GCP region
            model: Embedding model name (default: text-multilingual-embedding-002)
        """
        self.endpoint_id = endpoint_id
        self.index_id = index_id
        self.region = region
        self.model = model
        
        aiplatform.init(location=region)
        
        # Get project ID
        project = aiplatform.initializer.global_config.project
        
        # Initialize index endpoint
        endpoint_name = f"projects/{project}/locations/{region}/indexEndpoints/{endpoint_id}"
        self.endpoint = matching_engine_index_endpoint.MatchingEngineIndexEndpoint(
            index_endpoint_name=endpoint_name
        )
        
        # Initialize index
        index_name = f"projects/{project}/locations/{region}/indexes/{index_id}"
        self.index = matching_engine.MatchingEngineIndex(index_name=index_name)
        
        # Initialize embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained(model)
        
        logger.info(f"Initialized Vector Search ingester - Endpoint: {endpoint_id}, Index: {index_id}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text using text-multilingual-embedding-002.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats (768 dimensions)
        """
        try:
            logger.info(f"Generating embedding using {self.model}")
            
            # Get embeddings
            embeddings = self.embedding_model.get_embeddings([text])
            
            if not embeddings or len(embeddings) == 0:
                raise ValueError("No embeddings returned from model")
            
            embedding_vector = embeddings[0].values
            
            logger.info(f"Generated embedding with {len(embedding_vector)} dimensions")
            return embedding_vector
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def upsert_vector(self, vector: List[float], doc_id: str, metadata: Dict):
        """
        Upsert vector into Vector Search index.
        
        Args:
            vector: Embedding vector (list of floats)
            doc_id: Unique document ID
            metadata: Metadata dictionary (stored as restricts/allowlist)
        """
        try:
            logger.info(f"Upserting vector for doc_id: {doc_id}")
            
            # Create datapoint dictionary for upsert
            # Format matches Vertex AI Vector Search API expectations
            datapoint = {
                "datapoint_id": doc_id,
                "feature_vector": vector,
            }
            
            # Upsert datapoints to the index
            # This uses the streaming update method
            self.index.upsert_datapoints(
                datapoints=[datapoint]
            )
            
            logger.info(f"Successfully upserted vector for doc_id: {doc_id}")
            
        except Exception as e:
            logger.error(f"Error upserting vector: {e}")
            raise

