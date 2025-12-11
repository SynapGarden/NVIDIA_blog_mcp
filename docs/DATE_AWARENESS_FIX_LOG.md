# Date Awareness Fix Log

## Problem Statement
The MCP's RAG search functions cannot easily identify and find date-relevant documentation from the Vertex AI RAG Corpus. When users ask for "blogs from today" or "recent NVIDIA blogs from December 11, 2025", the system fails to return relevant results even though the content exists.

## Root Cause Analysis
1. **Date metadata was not embedded in the text content** - The RAG Corpus only had access to the article text without publication date information
2. **Query transformer lacked temporal awareness** - The system couldn't interpret temporal queries like "today" or "recent"
3. **Vector distance threshold was too strict** - Semantically relevant results (distance ~0.67) were being filtered out by the 0.5 threshold

---

## Fix Attempts

### Attempt 1: Ingestion Pipeline Enhancement (COMPLETED)
**Date:** December 11, 2025
**Branch:** `fix/date-awareness-in-search`

#### Changes Made:
1. **`private/html_cleaner.py`**
   - Modified `clean_html()` function to accept optional `metadata` dictionary
   - Added header prepending with "Publication Date", "Title", and "Source" to cleaned text
   - This ensures date context is physically present in text chunks sent to RAG

2. **`private/main.py`**
   - Moved metadata dictionary preparation to occur BEFORE `clean_html()` call
   - Pass `pubDate` from RSS feed to the cleaner
   - Fixed import: Changed `from mcp.config import` to `from config import` (Docker flat file structure)

3. **`private/Dockerfile`**
   - Changed `COPY mcp/ ./mcp/` to `COPY mcp/config.py ./`
   - Aligned with MCP server's flat file copy pattern

4. **`private/cloudbuild.yaml`**
   - Added `-f private/Dockerfile` flag to explicitly specify Dockerfile path

#### Deployment:
- Built and deployed ingestion job successfully
- Executed job: `rss-ingestion-job-jpclz` and subsequent runs
- Confirmed files imported to RAG Corpus (e.g., `https___developer.nvidia.com_blog__p_110310.txt` on Dec 11, 2025)

#### Test Results:
❌ **FAILED** - MCP still unable to find date-specific blogs when queried
- Query: "What are the latest NVIDIA blogs from December 11 2025?"
- Result: Returned empty or irrelevant contexts

---

### Attempt 2: Query Transformer Enhancement (COMPLETED)
**Date:** December 11, 2025
**Branch:** `fix/date-awareness-in-search`

#### Changes Made:
1. **`mcp/rag_query_transformer.py`**
   - Added `datetime` import
   - Updated `transform_query()` method to include current date context in Gemini prompt
   - Added guidelines for transforming temporal queries:
     - "today" → specific date (e.g., "December 11, 2025")
     - "recent" → current month/year context
   - Adjusted line length and logging format for code style

#### Test Results:
❌ **FAILED** - Query transformation alone insufficient without proper retrieval

---

### Attempt 3: RAG Vector Distance Threshold Increase (FAILED - ROLLED BACK)
**Date:** December 11, 2025 (~11:30 AM - 12:15 PM EST)
**Branch:** `fix/date-awareness-in-search`

#### Rationale:
- Logs showed RAG API returning contexts with distances ~0.67
- Default threshold of 0.5 was filtering out semantically relevant results
- RAG API was withholding text content for contexts that didn't meet threshold

#### Changes Made:
1. **`mcp/config.py`**
   - Changed `RAG_VECTOR_DISTANCE_THRESHOLD` from `0.5` to `0.8`

2. **`mcp/query_rag.py`**
   - Updated default `vector_distance_threshold` parameter in `_retrieve_contexts()` from `0.7` to `0.8`
   - Updated default `vector_distance_threshold` parameter in `query()` from `0.7` to `0.8`

#### Deployment:
- Built and deployed MCP server
- Revision: `nvidia-blog-mcp-server-00063-6rb`

#### Test Results:
❌ **CRITICAL FAILURE** - System returned ZERO contexts for ALL queries
- Production outage
- MCP completely non-functional

#### Rollback:
**HOTFIX deployed immediately**
- Reverted `RAG_VECTOR_DISTANCE_THRESHOLD` back to `0.5` in `mcp/config.py`
- Reverted default parameters back to `0.5` in `mcp/query_rag.py`
- Commit: `81c7dc3` - "HOTFIX: Revert RAG threshold to 0.5 - broken threshold causing zero results"
- Status: Currently deploying (Build ID: pending)

---

## Current Status
- **Ingestion Pipeline:** ✅ Enhanced with date metadata embedding
- **Query Transformer:** ✅ Enhanced with temporal query understanding
- **Vector Threshold:** 🔄 Reverted to 0.5, deployment in progress

## Next Steps
1. ✅ Complete hotfix deployment to restore service
2. ⏳ Test date-aware queries with threshold at 0.5
3. ⏳ Investigate why 0.8 threshold caused zero results
4. ⏳ Consider alternative approaches:
   - Metadata filtering in RAG API (if supported)
   - Hybrid search combining vector + keyword matching
   - Custom re-ranking based on date relevance
   - Adjusting embedding strategy to emphasize dates

## Notes
- The "Imported: 0 files" log message from RAG Corpus is misleading - files ARE being imported successfully
- RAG Corpus currently contains 130+ files with date metadata embedded
- Scheduled ingestion jobs run daily and are working correctly
- The core issue appears to be retrieval/ranking, not ingestion

---

## Testing Queries to Use
1. "What are the latest NVIDIA blogs from December 11 2025?"
2. "Show me blogs that came out today"
3. "What are recent NVIDIA blog posts?"
4. "NVIDIA blogs from this week"
5. "Latest CUDA blog posts"

## Success Criteria
- MCP returns relevant blogs when queried with date-specific requests
- Results include content published on the specified date
- System maintains performance for non-date queries
- No production outages or zero-result scenarios
