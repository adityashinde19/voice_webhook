import os
from pathlib import Path

from dotenv import load_dotenv
from twilio.rest import Client


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "app" / "utils" / ".env"
load_dotenv(ENV_PATH)


required_env_vars = [
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_MESSAGING_SERVICE_SID",
    "TWILIO_FROM_NUMBER",
    "TWILIO_TO_NUMBER",
]
missing_env_vars = [name for name in required_env_vars if not os.getenv(name)]

if missing_env_vars:
    raise RuntimeError(f"Missing Twilio environment variables: {', '.join(missing_env_vars)}")

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

message = client.messages.create(
    body=os.getenv("TWILIO_SMS_BODY", "Revenge of the Sith was the best of the prequel trilogy."),
    messaging_service_sid=os.environ["TWILIO_MESSAGING_SERVICE_SID"],
    from_=os.environ["TWILIO_FROM_NUMBER"],
    to=os.environ["TWILIO_TO_NUMBER"],
)

print("Twilio API Response")
print(f"SID: {message.sid}")
print(f"Account SID: {message.account_sid}")
print(f"Messaging Service SID: {message.messaging_service_sid}")
print(f"From: {message.from_}")
print(f"To: {message.to}")
print(f"Body: {message.body}")
print(f"Status: {message.status}")
print(f"Direction: {message.direction}")
print(f"Price: {message.price}")
print(f"Price Unit: {message.price_unit}")
print(f"Error Code: {message.error_code}")
print(f"Error Message: {message.error_message}")
print(f"Date Created: {message.date_created}")
print(f"Date Updated: {message.date_updated}")
print(f"URI: {message.uri}")



