Cleanup and Re-Ingestion Plan

Overview
After standardizing chunking settings (768/128) and fixing date-aware query issues, we need to clean up existing data and re-ingest with the new optimized settings.

Prerequisites

1. ✅ Code updated with standardized chunking (768/128)
2. ✅ Query fixes deployed (date-aware transformation + header filtering)
3. ⏳ Cloud Build configs verified

Step 1: Verify Cloud Build Configuration

Ingestion Job Build (`private/cloudbuild.yaml`)
- ✅ Builds Docker image with updated chunking settings
- ✅ Pushes to Artifact Registry
- ✅ Updates Cloud Run Job

MCP Server Build (`cloudbuild.mcp.yaml`)
- ✅ Builds MCP server with query fixes
- ✅ Deploys to Cloud Run Service

**Status**: Both build configs look correct ✅

Step 2: Clean Up RAG Corpus

Since we've changed chunking settings, existing chunks were created with old settings (512/50). We should delete all RAG files and re-import.

Option A: Delete All RAG Files via Cloud Console (Recommended)
1. Go to: https://console.cloud.google.com/vertex-ai/rag/corpora?project=nvidia-blog
2. Select corpus: `nvidia_blogs_corpus` (ID: 8070450532247928832)
3. Go to "Files" tab
4. Select all files → Delete
5. Wait for deletion to complete

Option B: Delete via API (PowerShell)
```powershell
$token = gcloud auth print-access-token

$baseUrl = "https://europe-west3-aiplatform.googleapis.com/v1beta1"
$corpusPath = "projects/nvidia-blog/locations/europe-west3/ragCorpora/8070450532247928832"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$allFiles = @()
$pageToken = $null

do {
    $url = "$baseUrl/$corpusPath/ragFiles"
    if ($pageToken) {
        $url += "?pageToken=$pageToken"
    }
    
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $allFiles += $response.ragFiles
    
    $pageToken = $response.nextPageToken
} while ($pageToken)

Write-Host "Found $($allFiles.Count) files to delete"

foreach ($file in $allFiles) {
    $fileId = $file.name.Split('/')[-1]
    $deleteUrl = "$baseUrl/$corpusPath/ragFiles/$fileId"
    
    try {
        Invoke-RestMethod -Uri $deleteUrl -Headers $headers -Method Delete
        Write-Host "Deleted: $fileId"
        Start-Sleep -Milliseconds 200
    } catch {
        Write-Host "Error deleting $fileId : $_"
    }
}
```

Step 3: Clean Up GCS Bucket (Optional)

If you want a completely fresh start, you can clean up the processed_ids.json files:

Reset Processed IDs (Allows Re-processing)
```powershell
gsutil cp gs://nvidia-blogs-raw/dev/processed_ids.json gs://nvidia-blogs-raw/dev/processed_ids.json.backup
gsutil cp gs://nvidia-blogs-raw/official/processed_ids.json gs://nvidia-blogs-raw/official/processed_ids.json.backup

echo '{"ids": []}' | gsutil cp - gs://nvidia-blogs-raw/dev/processed_ids.json
echo '{"ids": []}' | gsutil cp - gs://nvidia-blogs-raw/official/processed_ids.json
```

**Note**: This will cause the ingestion job to re-process ALL RSS items. Only do this if you want to completely re-process everything.

Alternative: Keep Clean Files, Just Re-import to RAG
If your cleaned text files are good, you can:
1. Keep `processed_ids.json` files (prevents re-processing)
2. Delete only RAG Corpus files (done in Step 2)
3. Manually re-import cleaned files from GCS to RAG Corpus with new settings

Step 4: Deploy Updated Ingestion Job

Deploy the updated code with standardized chunking settings:

```powershell
cd z:\SynapGarden\nvidia_blog
gcloud builds submit --config=private/cloudbuild.yaml --project=nvidia-blog
```

This will:
- Build Docker image with updated `rag_ingest.py` (768/128 chunking)
- Push to Artifact Registry
- Update Cloud Run Job

Step 5: Re-Run Ingestion Job

Option A: Let Scheduled Job Run (Daily at 7:00 AM UTC)
- New items will automatically use 768/128 chunking

Option B: Manual Trigger (Immediate)
```powershell
gcloud run jobs execute rss-ingestion-job --region=europe-west3 --project=nvidia-blog
```

Option C: Re-import Existing Clean Files (If you reset processed_ids.json)
If you reset processed_ids.json, the job will re-process everything. This will:
- Re-fetch RSS feeds
- Re-download HTML
- Re-clean with current html_cleaner.py (with date headers)
- Re-import to RAG with 768/128 chunking
- Re-upsert to Vector Search

Step 6: Verify Re-Ingestion

Check RAG Corpus Files
```powershell
$token = gcloud auth print-access-token
$url = "https://europe-west3-aiplatform.googleapis.com/v1beta1/projects/nvidia-blog/locations/europe-west3/ragCorpora/8070450532247928832/ragFiles"
$headers = @{ "Authorization" = "Bearer $token" }
Invoke-RestMethod -Uri $url -Headers $headers | ConvertTo-Json -Depth 10
```

Check Ingestion Logs
```powershell
gcloud run jobs logs read rss-ingestion-job --region=europe-west3 --project=nvidia-blog --limit=100
```

Look for:
- "Import operation completed" messages
- "Imported: X files" (should be > 0)
- Chunking settings in logs (if logged)

Test Query
After re-ingestion, test date-aware queries:
- "What are the latest NVIDIA blogs from December 2025?"
- "Recent NVIDIA technology developments"

Recommended Approach

**For Minimal Disruption:**
1. ✅ Deploy updated ingestion job (Step 4)
2. ✅ Delete all RAG Corpus files (Step 2, Option A - Cloud Console)
3. ✅ Keep `processed_ids.json` files (don't reset)
4. ✅ Manually re-import cleaned files from GCS to RAG Corpus via Cloud Console with 768/128 settings
5. ✅ Future new items will use 768/128 automatically

**For Complete Fresh Start:**
1. ✅ Deploy updated ingestion job (Step 4)
2. ✅ Delete all RAG Corpus files (Step 2)
3. ✅ Reset `processed_ids.json` files (Step 3)
4. ✅ Manually trigger ingestion job (Step 5, Option B)
5. ✅ Wait for complete re-processing

Important Notes

- **RAG Corpus deletion**: Only deletes files, NOT the corpus itself
- **processed_ids.json**: Controls which RSS items get processed (prevents duplicates)
- **Clean files in GCS**: Can be re-used if they're already good
- **Chunking settings**: Only apply to NEW imports, existing chunks keep old settings
- **Rate limits**: Be careful with bulk operations (add delays if needed)

Verification Checklist

- [ ] Cloud Build configs verified
- [ ] Updated ingestion job deployed
- [ ] RAG Corpus files deleted
- [ ] Re-import completed (manual or via job)
- [ ] New chunks created with 768/128 settings
- [ ] Date-aware queries working correctly
- [ ] No empty text fields in query results

