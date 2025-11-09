import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import create_document
from schemas import Contactsubmission

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# --- Email utility ---

def send_email_notification(name: str, email: str, message: str, submitted_at: datetime) -> Optional[str]:
    """Send an email using SMTP settings from environment variables.
    Returns None on success, or an error string if sending failed or not configured.
    """
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "0") or 0)
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    to_addr = os.getenv("EMAIL_TO") or user

    if not (host and port and user and password and to_addr):
        return "Email not configured (set EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS, EMAIL_TO)."

    subject = "New Portfolio Contact Submission"
    body = f"""
You have a new contact form submission:

Name: {name}
Email: {email}
Submitted At: {submitted_at.isoformat()}

Message:
{message}
""".strip()

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return None
    except Exception as e:
        return str(e)

# --- API: Contact submissions ---

@app.post("/api/contact")
def submit_contact(payload: Contactsubmission):
    try:
        server_time = datetime.now(timezone.utc)
        data = payload.model_dump()
        data["server_received_at"] = server_time
        inserted_id = create_document("contactsubmission", data)

        email_error = send_email_notification(
            name=payload.name,
            email=payload.email,
            message=payload.message,
            submitted_at=payload.submitted_at or server_time,
        )
        return {
            "ok": True,
            "id": inserted_id,
            "email_status": "sent" if email_error is None else f"not_sent: {email_error}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
