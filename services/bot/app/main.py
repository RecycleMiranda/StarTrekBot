import os
from fastapi import FastAPI

app = FastAPI(title="bot-service", version="0.0.1")

@app.get("/health")
def health():
    return {"code": 0, "message": "ok", "data": {"ok": True, "env": os.getenv("APP_ENV", "dev")}}
