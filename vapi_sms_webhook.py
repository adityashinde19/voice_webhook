import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pyodbc
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from twilio.rest import Client
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


app = FastAPI(title="Vapi Webhook Receiver")
BASE_DIR = Path(__file__).resolve().parent
WEBHOOK_OUTPUT_DIR = BASE_DIR / "vapi_webhook_calls"
STATIC_REPORT_DIR = BASE_DIR / "static" / "call-report"
LATEST_REPORT_URL_FILE = BASE_DIR / "latest_call_report_url.txt"
REPORT_URL_HISTORY_FILE = BASE_DIR / "call_report_urls.txt"
ENV_PATH = BASE_DIR / "app" / "utils" / ".env"
load_dotenv(ENV_PATH)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
if STATIC_REPORT_DIR.exists():
    app.mount("/call-report", StaticFiles(directory=STATIC_REPORT_DIR, html=True), name="call-report")


def _safe_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _get_db_connection() -> pyodbc.Connection:
    connection_string = (
        f"Driver={{{os.getenv('MSSQL_DRIVER', 'ODBC Driver 18 for SQL Server')}}};"
        f"Server={os.getenv('MSSQL_SERVER', '')};"
        f"Database={os.getenv('MSSQL_DATABASE', '')};"
        f"Uid={os.getenv('MSSQL_USERNAME', '')};"
        f"Pwd={os.getenv('MSSQL_PASSWORD', '')};"
        f"Encrypt={os.getenv('MSSQL_ENCRYPT', 'yes')};"
        f"TrustServerCertificate={os.getenv('MSSQL_TRUST_SERVER_CERTIFICATE', 'no')};"
        f"Connection Timeout={os.getenv('MSSQL_CONNECTION_TIMEOUT', '30')};"
    )
    retries = int(os.getenv("MSSQL_CONNECT_RETRIES", "3"))
    retry_delay_seconds = float(os.getenv("MSSQL_CONNECT_RETRY_DELAY_SECONDS", "2"))
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            return pyodbc.connect(connection_string)
        except pyodbc.Error as error:
            last_error = error
            print(f"Database connection attempt {attempt}/{retries} failed: {error}", flush=True)
            if attempt < retries:
                time.sleep(retry_delay_seconds)

    raise RuntimeError(f"Unable to connect to MSSQL after {retries} attempts.") from last_error


def _store_call_analytics(call_id: str, analytics: dict[str, Any]) -> None:
    analytics_json = json.dumps(analytics, ensure_ascii=False)
    query = """
    MERGE call_analytics AS target
    USING (SELECT ? AS call_id, ? AS analytics) AS source
    ON target.call_id = source.call_id
    WHEN MATCHED THEN
        UPDATE SET analytics = source.analytics
    WHEN NOT MATCHED THEN
        INSERT (call_id, analytics)
        VALUES (source.call_id, source.analytics);
    """

    with _get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query, call_id, analytics_json)
        connection.commit()


def _build_report_url(call_id: str) -> str:
    report_ui_base_url = os.getenv("REPORT_UI_BASE_URL", "http://127.0.0.1:8002/call-report").rstrip("/")
    report_api_base_url = os.getenv("REPORT_API_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
    return f"{report_ui_base_url}/?callId={call_id}&apiBase={report_api_base_url}"


def _save_report_url(report_url: str) -> None:
    LATEST_REPORT_URL_FILE.write_text(report_url, encoding="utf-8")
    with REPORT_URL_HISTORY_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{datetime.now().isoformat(timespec='seconds')} {report_url}\n")


def _send_report_sms(customer_number: Optional[str], report_url: str) -> dict[str, Any]:
    if not customer_number:
        return {"sent": False, "reason": "Customer number not found in webhook payload."}

    required_env_vars = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_MESSAGING_SERVICE_SID",
        "TWILIO_FROM_NUMBER",
    ]
    missing_env_vars = [name for name in required_env_vars if not os.getenv(name)]
    if missing_env_vars:
        return {"sent": False, "reason": f"Missing Twilio environment variables: {', '.join(missing_env_vars)}"}

    sms_body_template = os.getenv(
        "TWILIO_REPORT_SMS_BODY",
        "Thank you for calling Aress. Below is the attached report of your demo call: {report_url}",
    )
    sms_body = sms_body_template.format(report_url=report_url)

    try:
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        message = client.messages.create(
            body=sms_body,
            messaging_service_sid=os.environ["TWILIO_MESSAGING_SERVICE_SID"],
            from_=os.environ["TWILIO_FROM_NUMBER"],
            to=customer_number,
        )
    except Exception as error:
        return {"sent": False, "to": customer_number, "reason": str(error)}

    return {
        "sent": True,
        "sid": message.sid,
        "status": message.status,
        "from": message.from_,
        "to": message.to,
        "body": message.body,
        "errorCode": message.error_code,
        "errorMessage": message.error_message,
    }


def _get_call_analytics(call_id: str) -> Optional[dict[str, Any]]:
    query = "SELECT analytics FROM call_analytics WHERE call_id = ?;"

    with _get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query, call_id)
        row = cursor.fetchone()

    if row is None:
        return None

    raw_analytics = row[0]
    if isinstance(raw_analytics, bytes):
        raw_analytics = raw_analytics.decode("utf-8")

    return json.loads(raw_analytics)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/calls/{call_id}")
async def get_call_report(call_id: str) -> JSONResponse:
    try:
        analytics = _get_call_analytics(call_id)
    except Exception as error:
        print(f"Unable to load analytics for call_id={call_id}: {error}", flush=True)
        raise HTTPException(status_code=500, detail="Unable to load call analytics.") from error

    if analytics is None:
        raise HTTPException(status_code=404, detail="Call analytics not found.")

    return JSONResponse(analytics)


@app.post("/webhook/vapi")
async def receive_vapi_webhook(request: Request) -> JSONResponse:
    payload = await request.json()

    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    artifact = message.get("artifact", {}) if isinstance(message, dict) else {}
    analysis = message.get("analysis", {}) if isinstance(message, dict) else {}
    structured_data = analysis.get("structuredData", {}) if isinstance(analysis, dict) else {}

    event_type = _safe_get(payload, "message", "type")
    timestamp = _safe_get(payload, "message", "timestamp")
    call_id = _safe_get(payload, "message", "call", "id") or _safe_get(payload, "message", "artifact", "variables", "call", "id")
    customer_number = (
        _safe_get(payload, "message", "call", "customer", "number")
        or _safe_get(payload, "message", "customer", "number")
        or _safe_get(payload, "message", "artifact", "variableValues", "customer", "number")
        or _safe_get(payload, "message", "artifact", "variables", "customer", "number")
    )
    recording_url = artifact.get("recordingUrl") if isinstance(artifact, dict) else None
    transcript = artifact.get("transcript") if isinstance(artifact, dict) else None
    sentiment = structured_data.get("sentiment") if isinstance(structured_data, dict) else None
    duration_seconds = message.get("durationSeconds") if isinstance(message, dict) else None
    duration_minutes = message.get("durationMinutes") if isinstance(message, dict) else None
    duration_ms = message.get("durationMs") if isinstance(message, dict) else None
    cost = message.get("cost") if isinstance(message, dict) else None
    summary = (message.get("summary") or analysis.get("summary")) if isinstance(message, dict) and isinstance(analysis, dict) else None
    received_at = datetime.now().isoformat(timespec="seconds")
    safe_call_id = "".join(character if character.isalnum() or character in ("-", "_") else "_" for character in str(call_id or "unknown"))
    db_call_id = str(call_id or safe_call_id)
    report_url = _build_report_url(db_call_id)
    sms_result: dict[str, Any] = {"sent": False, "reason": "SMS not attempted yet."}
    output_data = {
        "receivedAt": received_at,
        "eventType": event_type,
        "timestamp": timestamp,
        "callId": call_id,
        "customerNumber": customer_number,
        "transcript": transcript,
        "recordingUrl": recording_url,
        "sentiment": sentiment,
        "durationSeconds": duration_seconds,
        "durationMinutes": duration_minutes,
        "durationMs": duration_ms,
        "cost": cost,
        "summary": summary,
        "reportUrl": report_url,
        "smsResult": sms_result,
    }
    WEBHOOK_OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = WEBHOOK_OUTPUT_DIR / f"{received_at.replace(':', '-')}_{safe_call_id}.json"
    output_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    _store_call_analytics(db_call_id, output_data)
    _save_report_url(report_url)
    sms_result = _send_report_sms(customer_number, report_url)
    output_data["smsResult"] = sms_result
    output_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    _store_call_analytics(db_call_id, output_data)

    print("\n" + "=" * 80, flush=True)
    print("VAPI WEBHOOK RECEIVED", flush=True)
    print("=" * 80, flush=True)
    print(f"Received At: {received_at}", flush=True)
    print(f"Event Type: {event_type}", flush=True)
    print(f"Timestamp: {timestamp}", flush=True)
    print(f"Call ID: {call_id}", flush=True)
    print(f"Customer Number: {customer_number}", flush=True)
    print(f"Recording URL: {recording_url}", flush=True)
    print(f"Sentiment: {sentiment}", flush=True)
    print(f"Duration Seconds: {duration_seconds}", flush=True)
    print(f"Cost: {cost}", flush=True)
    print("\nVapi Summary:", flush=True)
    print(summary or "No summary received.", flush=True)
    print("\nTranscript:", flush=True)
    print(transcript or "No transcript received.", flush=True)
    print(f"\nSaved File: {output_file}", flush=True)
    print("Saved DB: call_analytics", flush=True)
    print(f"Report URL: {report_url}", flush=True)
    print(f"Report URL File: {LATEST_REPORT_URL_FILE}", flush=True)
    print(f"SMS Result: {json.dumps(sms_result, ensure_ascii=False)}", flush=True)
    print("=" * 80 + "\n", flush=True)

    return JSONResponse({"received": True, "event_type": event_type, "call_id": call_id, "saved_file": str(output_file), "saved_db": True, "report_url": report_url, "sms_result": sms_result})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
