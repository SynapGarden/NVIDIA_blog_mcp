# Date Awareness Fix for NVIDIA Blog MCP

## Problem Statement

The NVIDIA Blog MCP was unable to retrieve articles based on temporal queries (e.g., "What blogs were published today?", "Latest NVIDIA articles", "Recent announcements"). This was because:

1. **Date metadata was not included in the chunked text** - When articles were ingested into the RAG Corpus, the publication date was extracted from RSS feeds but not embedded in the actual text that gets chunked and indexed
2. **Query transformation didn't handle temporal queries** - The query transformer didn't recognize or transform date-related queries into searchable terms

## Root Cause Analysis

### Ingestion Pipeline Flow
```
RSS Feed → Parse Metadata (including pubDate) → Fetch HTML → Clean HTML → 
Upload to GCS → Ingest to RAG Corpus (chunks created here)
```

**Issue**: The `pubDate` metadata was extracted but never made it into the cleaned text. When RAG Corpus created chunks (512 tokens with 50 token overlap), those chunks had no date context.

### Query Pipeline Flow
```
User Query → Query Transformer → RAG Corpus Retrieval → Answer Grader → Results
```

**Issue**: The query transformer didn't understand temporal queries like "today" or "recent", so it couldn't transform them into date-specific searches.

## Solution Implemented

### 1. Prepend Date Metadata to Cleaned Text (`private/html_cleaner.py`)

**Changes**:
- Modified `clean_html()` method to accept optional `metadata` parameter
- Added metadata header to the beginning of cleaned text with:
  - Publication Date
  - Title
  - Source (NVIDIA Developer Blog or NVIDIA Official Blog)

**Example Output**:
```
Publication Date: December 11, 2024
Title: Accelerating AI Inference with TensorRT
Source: NVIDIA Developer Blog

---

[Article content follows...]
```

**Impact**: Every chunk created by RAG Corpus now contains date context in its text, making temporal searches possible.

### 2. Pass Metadata to HTML Cleaner (`private/main.py`)

**Changes**:
- Moved metadata preparation before HTML cleaning
- Passed metadata dict to `html_cleaner.clean_html()` method

**Impact**: Ensures date information flows through the cleaning process.

### 3. Enhanced Query Transformer for Temporal Queries (`mcp/rag_query_transformer.py`)

**Changes**:
- Added current date context to transformation prompt
- Included specific guidance for handling temporal queries:
  - "today" → specific date (e.g., "December 11, 2024")
  - "recent", "latest", "newest" → current month/year
  - Time period conversions (e.g., "this month" → "December 2024")
- Added examples of temporal query transformations

**Example Transformations**:
- "What's new today?" → "NVIDIA blog posts and announcements published on December 11, 2024"
- "Recent developments" → "Latest NVIDIA technology developments and announcements from December 2024"
- "Latest articles" → "Most recent NVIDIA blog articles from December 2024"

**Impact**: Temporal queries are now transformed into date-specific searches that can match against the publication dates embedded in chunks.

## Files Modified

1. **`private/html_cleaner.py`**
   - Added `metadata: Optional[Dict]` parameter to `clean_html()`
   - Added `Dict` to imports
   - Implemented metadata header prepending logic

2. **`private/main.py`**
   - Moved metadata preparation before HTML cleaning
   - Passed metadata to `html_cleaner.clean_html()`

3. **`mcp/rag_query_transformer.py`**
   - Added datetime import for current date context
   - Enhanced transformation prompt with temporal query handling
   - Fixed code style issues (line length, f-string formatting)

## Testing Required

After deploying these changes, the ingestion pipeline needs to re-process articles to include the date headers. Then test with queries like:

1. "What NVIDIA blog posts were published today?"
2. "Latest NVIDIA announcements from December 2024"
3. "Most recent NVIDIA blog articles"
4. "What's new with NVIDIA this week?"
5. "Recent GPU developments"

## Deployment Steps

1. **Deploy Updated Ingestion Job**:
   ```bash
   cd private/
   gcloud builds submit --config cloudbuild.yaml
   ```

2. **Deploy Updated MCP Server**:
   ```bash
   cd ../
   gcloud builds submit --config cloudbuild.mcp.yaml
   ```

3. **Trigger Re-ingestion** (Optional but recommended):
   - Run the ingestion job manually to re-process existing articles with date headers
   - Or wait for the next scheduled daily run

## Expected Improvements

- ✅ Temporal queries will now retrieve relevant articles
- ✅ Date-specific searches will work (e.g., "December 2024")
- ✅ "Today", "recent", "latest" queries will be properly transformed
- ✅ Each chunk will have publication date context
- ✅ Better answer grading for date-related queries

## Notes

- The fix is backward compatible - articles without date headers will still work
- Date format in RSS feeds is preserved (typically RFC 2822 format)
- Query transformer uses UTC time for "today" calculations
- Metadata header adds ~100-150 characters to each article

## Future Enhancements

Consider these improvements for even better date awareness:

1. Add structured metadata fields to RAG Corpus (when API supports it)
2. Implement date-based filtering in retrieval
3. Add relative date parsing ("last week", "3 days ago")
4. Include article age in answer grading logic
5. Add date sorting to search results
