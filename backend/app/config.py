# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/chat/completions")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voice_agent.db")

EXCEL_BASE_DIR = os.getenv("EXCEL_BASE_DIR", "./excel_sheets")
os.makedirs(EXCEL_BASE_DIR, exist_ok=True)
