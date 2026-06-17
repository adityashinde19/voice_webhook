# Voice Webhook Pipeline

FastAPI service for receiving Vapi end-of-call webhook reports, storing call analytics in MSSQL, generating a report UI URL, serving the static report UI, and sending the report link to the customer by Twilio SMS.

## Functionality

- Receives Vapi webhook payloads at call end.
- Extracts call analytics:
  - Call ID
  - Customer phone number
  - Transcript
  - Recording URL
  - Sentiment
  - Duration
  - Cost
  - Summary
- Saves a local JSON backup in `vapi_webhook_calls`.
- Stores analytics in MSSQL table `call_analytics`.
- Generates a report URL for the call.
- Saves latest report URL in `latest_call_report_url.txt`.
- Appends all report URLs in `call_report_urls.txt`.
- Serves static report UI from the same FastAPI server.
- Sends SMS to the customer number found in the Vapi webhook JSON.
- Stores Twilio SMS result back into JSON backup and MSSQL analytics.

## Application URLs

Local backend base URL:

```text
http://127.0.0.1:8002
```

Static report UI:

```text
http://127.0.0.1:8002/call-report/
```

Generated report URL format:

```text
http://127.0.0.1:8002/call-report/?callId={CALL_ID}&apiBase=http://127.0.0.1:8002
```

## API Endpoints

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### Vapi Webhook

```http
POST /webhook/vapi
```

Used by Vapi for end-of-call report payloads.

Example response:

```json
{
  "received": true,
  "event_type": "end-of-call-report",
  "call_id": "CALL_ID",
  "saved_file": "D:\\voice_webhook\\vapi_webhook_calls\\file.json",
  "saved_db": true,
  "report_url": "https://your-domain/call-report/?callId=CALL_ID&apiBase=https://your-domain",
  "sms_result": {
    "sent": true,
    "sid": "SM...",
    "status": "accepted",
    "from": "+18555721203",
    "to": "+12296823466",
    "body": "Thank you for calling Aress..."
  }
}
```

### Get Call Analytics

```http
GET /api/calls/{call_id}
```

Returns analytics JSON stored in MSSQL for a specific call.

Example:

```text
http://127.0.0.1:8002/api/calls/019ed4c6-aeb2-7000-9864-4527326f92dc
```

If no record exists:

```json
{
  "detail": "Call analytics not found."
}
```

## Static Report UI

The report UI is served by FastAPI from:

```text
static/call-report
```

Open:

```text
http://127.0.0.1:8002/call-report/?callId={CALL_ID}&apiBase=http://127.0.0.1:8002
```

The UI fetches data from:

```text
/api/calls/{CALL_ID}
```

## Environment Variables

Environment file:

```text
app/utils/.env
```

Required MSSQL variables:

```env
MSSQL_DRIVER=ODBC Driver 18 for SQL Server
MSSQL_SERVER=tcp:your-server.database.windows.net,1433
MSSQL_DATABASE=your_database
MSSQL_USERNAME=your_username
MSSQL_PASSWORD=your_password
MSSQL_ENCRYPT=yes
MSSQL_TRUST_SERVER_CERTIFICATE=no
MSSQL_CONNECTION_TIMEOUT=30
MSSQL_CONNECT_RETRIES=3
MSSQL_CONNECT_RETRY_DELAY_SECONDS=2
```

Report URL variables:

```env
REPORT_UI_BASE_URL=http://127.0.0.1:8002/call-report
REPORT_API_BASE_URL=http://127.0.0.1:8002
```

Twilio SMS variables:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_MESSAGING_SERVICE_SID=your_twilio_messaging_service_sid
TWILIO_FROM_NUMBER=+18555721203
TWILIO_REPORT_SMS_BODY=Thank you for calling Aress. Below is the attached report of your demo call: {report_url}
```

Optional CORS variable:

```env
ALLOWED_ORIGINS=*
```

## MSSQL Table

Expected table:

```sql
CREATE TABLE call_analytics (
    call_id NVARCHAR(255) NOT NULL PRIMARY KEY,
    analytics NVARCHAR(MAX) NOT NULL
);
```

The app uses `MERGE` to upsert data by `call_id`.

## Local Setup

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
python vapi_sms_webhook.py
```

Open health check:

```text
http://127.0.0.1:8002/health
```

Open report UI:

```text
http://127.0.0.1:8002/call-report/
```

## Local HTTPS Testing With Ngrok

Use ngrok only for local testing because Vapi needs a public HTTPS webhook URL.

Run app:

```powershell
python vapi_sms_webhook.py
```

Expose local port:

```powershell
ngrok http 8002
```

Update `.env`:

```env
REPORT_UI_BASE_URL=https://YOUR-NGROK.ngrok-free.app/call-report
REPORT_API_BASE_URL=https://YOUR-NGROK.ngrok-free.app
```

Set Vapi webhook URL:

```text
https://YOUR-NGROK.ngrok-free.app/webhook/vapi
```

## Azure Deployment

When deployed to Azure Container Apps, ngrok is not needed.

Azure will provide an HTTPS URL like:

```text
https://your-app.region.azurecontainerapps.io
```

Set Azure environment variables:

```env
REPORT_UI_BASE_URL=https://your-app.region.azurecontainerapps.io/call-report
REPORT_API_BASE_URL=https://your-app.region.azurecontainerapps.io
```

Set Vapi webhook URL:

```text
https://your-app.region.azurecontainerapps.io/webhook/vapi
```

## Docker

Build image:

```powershell
docker build -t voice-webhook .
```

Run container locally:

```powershell
docker run --env-file app/utils/.env -p 8002:8002 voice-webhook
```

The Dockerfile installs Microsoft ODBC Driver 18 for SQL Server for `pyodbc` MSSQL connectivity.

## Twilio SMS Test

Standalone test file:

```text
twilio_sms_test.py
```

Run:

```powershell
python twilio_sms_test.py
```

It sends an SMS using Twilio credentials from `.env` and prints the Twilio API response.

## End-To-End Pipeline Test

1. Start FastAPI app:

```powershell
python vapi_sms_webhook.py
```

2. Expose with ngrok for local testing or use Azure HTTPS URL.

3. Configure Vapi webhook:

```text
https://YOUR-PUBLIC-DOMAIN/webhook/vapi
```

4. Complete a Vapi call.

5. Confirm terminal log shows:

```text
VAPI WEBHOOK RECEIVED
Saved DB: call_analytics
Report URL: ...
SMS Result: ...
```

6. Open latest generated URL from:

```text
latest_call_report_url.txt
```

7. Confirm SMS was sent to the customer number from the Vapi webhook JSON.

## Important Notes

- `.env` contains secrets and should not be committed.
- The customer SMS recipient is extracted from the Vapi webhook JSON.
- Twilio SMS failure does not stop report generation or database storage.
- If the report UI shows `not found`, confirm the call exists in MSSQL table `call_analytics`.
- For Azure, configure environment variables in Azure instead of relying on local `.env`.
