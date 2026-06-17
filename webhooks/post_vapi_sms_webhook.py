import json
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


app = FastAPI(title="Vapi Webhook Receiver")
WEBHOOK_OUTPUT_DIR = Path(__file__).resolve().parent / "vapi_webhook_calls"


def _safe_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/vapi")
async def receive_vapi_webhook(request: Request) -> JSONResponse:
    payload = await request.json()

    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    call = message.get("call", {}) if isinstance(message, dict) else {}
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
    summary = message.get("summary") or analysis.get("summary") if isinstance(message, dict) and isinstance(analysis, dict) else None
    received_at = datetime.now().isoformat(timespec="seconds")
    safe_call_id = "".join(character if character.isalnum() or character in ("-", "_") else "_" for character in str(call_id or "unknown"))
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
    }
    WEBHOOK_OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = WEBHOOK_OUTPUT_DIR / f"{received_at.replace(':', '-')}_{safe_call_id}.json"
    output_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")

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
    print("=" * 80 + "\n", flush=True)

    return JSONResponse({"received": True, "event_type": event_type, "call_id": call_id, "saved_file": str(output_file)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
