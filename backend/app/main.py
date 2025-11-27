# app/main.py
from fastapi import FastAPI
from .db import Base, engine
from .twilio_routes import router as twilio_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Voice Appointment Agent")

app.include_router(twilio_router)

@app.get("/")
def health_check():
    return {"status": "ok"}
