# NetworkError Fix Documentation

## Problem: "TypeError: NetworkError when attempting to fetch resource"

### Error Description
Users experienced network errors when:
1. **Quality Checking** student videos (`/student-data/{dept}/{year}/quality-check`)
2. **Processing Pending Videos** (`/student-data/{dept}/{year}/process`)

### Root Causes

#### 1. **Server Request Timeouts** ⏱️
- Video processing and quality checks are **long-running operations** (can take 5-15 minutes for large batches)
- Default HTTP timeout (30-60 seconds) was too short
- No explicit timeout configuration in uvicorn
- Requests were timing out before operations completed

#### 2. **Synchronous Blocking Operations** 🚫
- Both endpoints processed videos **synchronously** in the request handler
- This blocked the worker thread for the entire duration
- No other requests could be handled while processing
- Browser connections timed out waiting for response

#### 3. **Memory/Resource Exhaustion** 💾
From logs:
```
WORKER TIMEOUT (pid:2453578)
Worker (pid:2453578) was sent SIGKILL! Perhaps out of memory?
```
- Video processing is memory-intensive
- Processing multiple students exhausted available memory
- Workers crashed, causing network errors

#### 4. **No Progress Feedback** 📊
- Frontend had no way to know if processing was still ongoing
- No intermediate status updates
- Users couldn't tell if request failed or was still processing

---

## Solutions Implemented

### 1. **Increased Server Timeouts** ⚙️

**File:** `src/main.py`

Added explicit timeout configuration to uvicorn:
```python
uvicorn.run(
    "main:app", 
    host=HOST, 
    port=PORT, 
    workers=WORKERS,
    timeout_keep_alive=300,  # 5 minutes keep-alive
    timeout_graceful_shutdown=30
)
```

### 2. **Converted to Asynchronous Background Tasks** 🔄

**File:** `src/api/routes.py`

#### Quality Check Endpoint
**Before:** Synchronous blocking
```python
async def check_student_data_quality(dept: str, year: str):
    quality_checker = get_quality_checker()
    result = quality_checker.check_student_data_quality(dept, year, STUDENT_DATA_DIR)
    return result  # Blocks until complete
```

**After:** Background task with immediate response
```python
async def check_student_data_quality(dept: str, year: str, background_tasks: BackgroundTasks):
    def run_quality_check():
        quality_checker = get_quality_checker()
        result = quality_checker.check_student_data_quality(dept, year, STUDENT_DATA_DIR)
        # Store result for later retrieval
        result_file = os.path.join(STUDENT_DATA_DIR, f"{dept}_{year}", "quality_check_result.json")
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
    
    background_tasks.add_task(run_quality_check)
    return {"success": True, "message": "Quality check started", "status": "processing"}
```

#### Video Processing Endpoint
Similar changes applied to `/student-data/{dept}/{year}/process`

### 3. **Added Status Polling Endpoints** 📡

**New Endpoints:**

#### Quality Check Status
```
GET /student-data/{dept}/{year}/quality-check/status
```
Returns:
- `status`: "processing", "completed", or "error"
- Full results when completed

#### Processing Status
```
GET /student-data/{dept}/{year}/process/status
```
Returns:
- `status`: "processing" or "completed"
- Processing results when completed

### 4. **Frontend Polling Implementation** 🔄

**File:** `static/js/app.js`

#### Quality Check with Polling
```javascript
async function handleQualityCheck() {
    // Start quality check (returns immediately)
    const response = await fetch(`${API_BASE_URL}/student-data/${dept}/${year}/quality-check`, {
        method: 'POST'
    });
    
    // Poll for results every 5 seconds
    await pollForQualityResults(dept, year, resultContainer);
}

async function pollForQualityResults(dept, year, resultContainer) {
    const maxAttempts = 60; // 5 minutes max
    const pollInterval = setInterval(async () => {
        const response = await fetch(`${API_BASE_URL}/student-data/${dept}/${year}/quality-check/status`);
        const result = await response.json();
        
        if (result.status === 'completed') {
            clearInterval(pollInterval);
            displayQualityResults(result);
        }
    }, 5000); // Poll every 5 seconds
}
```

#### Video Processing with Polling
Similar implementation for `handleProcessStudentVideos()`

---

## Architecture Changes

### Before (Synchronous)
```
[Browser] --request--> [Server] --blocks for 10 mins--> [Response]
                                      ❌ TIMEOUT
```

### After (Async + Polling)
```
[Browser] --start request--> [Server] --immediate response--> [Browser]
    ↓                            ↓
    Poll every 5s         Process in background
    ↓                            ↓
    Get status              Save results to file
    ↓                            ↓
    ← status: processing ←  Still working...
    ← status: completed  ←  ✅ Done!
```

---

## Benefits

### 1. **No More Timeouts** ✅
- Requests return immediately
- Background processing can run indefinitely
- No connection timeouts

### 2. **Better User Experience** 😊
- Clear feedback during processing
- Users know operation is in progress
- Can monitor real-time status

### 3. **Resource Efficiency** 🚀
- Worker threads not blocked
- Can handle other requests during processing
- Better server utilization

### 4. **Scalability** 📈
- Can process multiple departments simultaneously
- Each operation tracked independently
- Results cached for retrieval

---

## Testing the Fix

### 1. Restart the Server
```bash
cd /home/zypher/PROJECT/Face-Data-collection-and-Gallery-management-application
# Kill existing process
pkill -f "python.*main.py"

# Start server
python src/main.py
```

### 2. Test Quality Check
1. Open the application
2. Select department and year
3. Click "Check Quality First"
4. Should see: "Analyzing Video Quality... This may take several minutes"
5. Status polls every 5 seconds
6. Results displayed when complete

### 3. Test Video Processing
1. Click "Process Pending Videos"
2. Should see: "Processing student videos... Please wait..."
3. Status polls every 5 seconds
4. Results displayed when complete

---

## Additional Improvements (Optional)

### For Production:

1. **Use Redis for Job Queue**
   - More robust than file-based status
   - Better for multiple workers
   - Can track progress percentage

2. **WebSocket for Real-time Updates**
   - Instead of polling
   - Instant status updates
   - Lower server load

3. **Progress Bar**
   - Show percentage complete
   - Estimated time remaining
   - Current student being processed

4. **Database-backed Status**
   - Store task status in database
   - Better for multi-server setup
   - Can query historical tasks

---

## Troubleshooting

### If errors still occur:

1. **Check logs:**
   ```bash
   tail -f logs/logs.txt
   ```

2. **Verify status files are created:**
   ```bash
   ls -la data/student_data/*/quality_check_result.json
   ls -la data/student_data/*/processing_result.json
   ```

3. **Check server is running:**
   ```bash
   ps aux | grep "python.*main.py"
   ```

4. **Monitor memory usage:**
   ```bash
   free -h
   ```

5. **Check for stuck processes:**
   ```bash
   ps aux | grep python | grep -E 'quality|process'
   ```

---

## Files Modified

1. ✅ `src/main.py` - Added timeout configuration
2. ✅ `src/api/routes.py` - Converted to background tasks, added status endpoints
3. ✅ `static/js/app.js` - Added polling logic for both operations

---

## Summary

The NetworkError was caused by long-running synchronous operations timing out. The solution:
- **Immediate response** - Start operation in background
- **Status polling** - Check completion every 5 seconds
- **Result caching** - Store results in files for retrieval
- **Increased timeouts** - Server configured for longer connections

This architecture pattern should be applied to any other long-running operations in the application.
