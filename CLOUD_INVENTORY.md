# Google Cloud Project Inventory - NVIDIA Blog MCP

**Last Updated**: December 11, 2024  
**Project**: `nvidia-blog`  
**Project Number**: `56324449160`  
**Account**: `dylant@synapgarden.com`  
**Region**: `europe-west3` (Frankfurt, Germany)

---

## 1. Cloud Run Services

### ✅ MCP Server Service
- **Name**: `nvidia-blog-mcp-server`
- **Region**: `europe-west3`
- **URL**: `https://nvidia-blog-mcp-server-56324449160.europe-west3.run.app`
- **Status**: ✅ Active
- **Last Deployed**: 2025-12-11T15:37:27.741282Z
- **Purpose**: Query API for NVIDIA blog search (public endpoint for Cursor)
- **Configuration**:
  - Memory: 1Gi
  - CPU: 1
  - Min instances: 0 (scales to zero)
  - Max instances: 10
  - Timeout: 300s (5 minutes)
  - Port: 8080
  - Authentication: Public (--allow-unauthenticated)

---

## 2. Cloud Run Jobs

### ✅ RSS Ingestion Job
- **Name**: `rss-ingestion-job`
- **Region**: `europe-west3`
- **Status**: ✅ Active
- **Last Run**: 2025-12-11 07:00:04 UTC
- **Created**: 2025-12-02 02:29:46 UTC
- **Purpose**: Daily RSS feed ingestion and RAG/Vector Search processing
- **Configuration**:
  - Timeout: 3600s (1 hour)
  - Task timeout: 3600s
  - Schedule: Daily at 7:00 AM UTC
  - Image: `europe-west3-docker.pkg.dev/nvidia-blog/rss-ingestion/rss-ingestion-job:latest`

---

## 3. Cloud Storage Buckets

### ✅ Raw Blog Data
- **Name**: `nvidia-blogs-raw`
- **Location**: `EUROPE-WEST3` (regional)
- **Purpose**: Raw HTML, XML, and cleaned text files
- **Access**: Public Access Prevention - Enforced
- **Structure**:
  ```
  gs://nvidia-blogs-raw/
  ├── dev/
  │   ├── raw_xml/
  │   ├── raw_html/
  │   ├── clean/
  │   └── processed_ids.json
  └── official/
      ├── raw_xml/
      ├── raw_html/
      ├── clean/
      └── processed_ids.json
  ```

### ✅ CloudBuild Artifacts
- **Name**: `nvidia-blog_cloudbuild`
- **Location**: `US` (multi-region)
- **Purpose**: CloudBuild source code and logs
- **Size**: N/A (auto-managed)

### ✅ CloudBuild Regional
- **Name**: `nvidia-blog_cloudbuild_europe-west3`
- **Location**: `EUROPE-WEST3` (regional)
- **Purpose**: Regional CloudBuild artifacts
- **Size**: N/A (auto-managed)

---

## 4. Artifact Registry

### ✅ Docker Repository
- **Name**: `rss-ingestion`
- **Format**: DOCKER
- **Location**: `europe-west3`
- **Mode**: STANDARD_REPOSITORY
- **Encryption**: Google-managed key
- **Created**: 2025-12-01T21:09:09
- **Last Updated**: 2025-12-11T10:37:41
- **Size**: 7952.094 MB
- **Images**:
  - `europe-west3-docker.pkg.dev/nvidia-blog/rss-ingestion/nvidia-blog-mcp-server:latest`
  - `europe-west3-docker.pkg.dev/nvidia-blog/rss-ingestion/rss-ingestion-job:latest`

---

## 5. Vertex AI - Vector Search

### ✅ Vector Search Index
- **Name**: `processed_nvidia_blogs`
- **Index ID**: `3602747760501063680`
- **Region**: `europe-west3`
- **Status**: ✅ Active
- **Created**: 2025-12-02T00:21:49.465601Z
- **Last Updated**: 2025-12-11T15:38:01.545375Z
- **Configuration**:
  - **Dimensions**: 768
  - **Distance Metric**: DOT_PRODUCT_DISTANCE
  - **Feature Norm**: UNIT_L2_NORM
  - **Algorithm**: Brute Force
  - **Shard Size**: Medium
  - **Update Method**: STREAM_UPDATE
- **Index Endpoint ID**: `8740721616633200640`
- **Deployed Index ID**: `processed_nvidia_blogs_1764634989262`
- **Statistics**:
  - **Vectors Count**: 794
  - **Shards Count**: 1

### ✅ RAG Corpus
- **Corpus Name**: `projects/nvidia-blog/locations/europe-west3/ragCorpora/8070450532247928832`
- **Location**: `europe-west3`
- **Status**: ✅ Active
- **Purpose**: Semantic search for blog articles
- **Configuration**:
  - Chunking: 512 tokens with 50 token overlap
  - Vector distance threshold: 0.5

---

## 6. Configuration Summary

### Code Configuration (from `mcp/config.py`)
```python
PROJECT_ID = "nvidia-blog"
REGION = "europe-west3"
BUCKET_NAME = "nvidia-blogs-raw"
RAG_CORPUS = "projects/nvidia-blog/locations/europe-west3/ragCorpora/8070450532247928832"
VECTOR_SEARCH_ENDPOINT_ID = "8740721616633200640"
VECTOR_SEARCH_INDEX_ID = "3602747760501063680"
EMBEDDING_MODEL = "text-embedding-004"
GEMINI_MODEL_LOCATION = "europe-west4"
GEMINI_MODEL_NAME = "gemini-2.0-flash"
```

---

## 7. Deployment Commands

### Deploy MCP Server (Query Pipeline)
```bash
cd z:\SynapGarden\nvidia_blog
gcloud builds submit --config cloudbuild.mcp.yaml --project=nvidia-blog
```

### Deploy Ingestion Job (Data Pipeline)
```bash
cd z:\SynapGarden\nvidia_blog
gcloud builds submit --config private/cloudbuild.yaml --project=nvidia-blog
```

### Manual Trigger Ingestion Job
```bash
gcloud run jobs execute rss-ingestion-job --region=europe-west3 --project=nvidia-blog
```

---

## 8. Status Check Commands

### Verify MCP Server is Running
```bash
curl https://nvidia-blog-mcp-server-56324449160.europe-west3.run.app/health
```

### Check Ingestion Job Status
```bash
gcloud run jobs describe rss-ingestion-job --region=europe-west3 --project=nvidia-blog
```

### View Recent Ingestion Logs
```bash
gcloud run jobs logs read rss-ingestion-job --region=europe-west3 --project=nvidia-blog --limit=50
```

### List Vector Search Index Stats
```bash
gcloud ai indexes describe 3602747760501063680 --region=europe-west3 --project=nvidia-blog
```

---

## 9. Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ INGESTION PIPELINE (Cloud Run Job)                      │
├─────────────────────────────────────────────────────────┤
│ 1. RSS Feeds (NVIDIA Developer + Official)              │
│    ↓                                                    │
│ 2. rss-ingestion-job fetches and parses RSS            │
│    ↓                                                    │
│ 3. HTML downloaded and cleaned                          │
│    ↓                                                    │
│ 4. Files stored in gs://nvidia-blogs-raw/               │
│    ├── raw_xml/                                         │
│    ├── raw_html/                                        │
│    └── clean/                                           │
│    ↓                                                    │
│ 5. Chunks indexed to RAG Corpus                         │
│    ↓                                                    │
│ 6. Vectors embedded (text-embedding-004)               │
│    ↓                                                    │
│ 7. Upserted to Vector Search Index (794 vectors)        │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ QUERY PIPELINE (Cloud Run Service)                      │
├─────────────────────────────────────────────────────────┤
│ 1. User asks question via Cursor                        │
│    ↓                                                    │
│ 2. nvidia-blog-mcp-server receives query                │
│    ↓                                                    │
│ 3. Query transformer enhances query (Gemini 2.0)        │
│    ↓                                                    │
│ 4. RAG Corpus retrieves matching chunks                 │
│    ↓                                                    │
│ 5. Answer grader evaluates relevance                    │
│    ↓                                                    │
│ 6. Returns grounded response to Cursor                  │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Important URLs

| Component | URL |
|-----------|-----|
| **MCP Server** | https://nvidia-blog-mcp-server-56324449160.europe-west3.run.app |
| **GCS Bucket** | gs://nvidia-blogs-raw/ |
| **Artifact Registry** | europe-west3-docker.pkg.dev/nvidia-blog/rss-ingestion/ |
| **CloudBuild** | https://console.cloud.google.com/cloud-build?project=nvidia-blog |
| **Vector Search** | https://console.cloud.google.com/vertex-ai/datasets/indexes?project=nvidia-blog |
| **Cloud Run** | https://console.cloud.google.com/run?project=nvidia-blog |

---

## 11. Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails with "requirements.txt not found" | Run build from root directory: `cd nvidia_blog && gcloud builds submit` |
| MCP Server returns 503 errors | Check Cloud Run service status: `gcloud run services describe nvidia-blog-mcp-server --region=europe-west3` |
| Ingestion job fails | Check job logs: `gcloud run jobs logs read rss-ingestion-job --region=europe-west3 --limit=100` |
| Vector Search index empty | Run manual ingestion: `gcloud run jobs execute rss-ingestion-job --region=europe-west3` |
| Query transformer errors | Verify Gemini API is enabled: `gcloud services enable aiplatform.googleapis.com` |

---

**Everything is properly configured and ready for deployment!** ✅
