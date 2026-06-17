# StreamWave Call Report UI

This folder is a deployable static call-report page. It does not connect to MSSQL directly. The page reads a `callId` from the URL, calls the FastAPI backend, and renders the data returned from `call_analytics`.

## URL Format

Same domain as the API:

```text
https://your-domain.com/call-report/?callId=019ed3f0-39c2-7cc2-baef-eb5b3b343e8a
```

Static UI and API on different domains:

```text
https://your-static-domain.com/?callId=019ed3f0-39c2-7cc2-baef-eb5b3b343e8a&apiBase=https://your-api-domain.com
```

You can also set the API base once in `index.html`:

```html
<script>
  window.CALL_REPORT_API_BASE = "https://your-api-domain.com";
</script>
```

Then use:

```text
https://your-static-domain.com/?callId=019ed3f0-39c2-7cc2-baef-eb5b3b343e8a
```

## Backend Endpoint

The page expects this endpoint:

```text
GET /api/calls/{call_id}
```

Expected response shape:

```json
{
  "receivedAt": "2026-06-17T10:27:28",
  "eventType": "end-of-call-report",
  "timestamp": 1781672251799,
  "callId": "019ed3f0-39c2-7cc2-baef-eb5b3b343e8a",
  "customerNumber": "+12296823466",
  "transcript": "AI: Hello...\nUser: Hello...",
  "recordingUrl": "https://example.com/audio.wav",
  "sentiment": "positive",
  "durationSeconds": 50.099,
  "durationMinutes": 0.835,
  "durationMs": 50099,
  "cost": 0.0941,
  "summary": "The user inquired about..."
}
```

## CORS

If the static UI is deployed on a different domain than the API, set this in the FastAPI environment:

```text
ALLOWED_ORIGINS=https://your-static-domain.com
```

Use comma-separated values for multiple domains.

## Local Preview

From this folder:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8765/?demo=1
```

For real data, run the FastAPI backend and open:

```text
http://127.0.0.1:8765/?callId=YOUR_CALL_ID&apiBase=http://127.0.0.1:8002
```
