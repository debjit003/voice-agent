# app/llm.py
import httpx
import json
from .config import LLM_API_KEY, LLM_BASE_URL

SYSTEM_PROMPT = """
You are an AI voice agent that books appointments for businesses over the phone.
You must follow this process:
1. Greet the caller and say which business you're representing.
2. Collect: caller name, service type, preferred date and time, and phone number (if not obvious).
3. Confirm the details clearly in one short sentence.
4. Then say you'll send the details to the business and end the call politely.

You must always respond in short, clear sentences suitable for text-to-speech.
Output in JSON with keys: "stage", "state", "reply".
The "state" must contain keys: name, service_type, date_time, phone, confirmed (true/false).
"""

async def get_next_turn(state: dict, user_utterance: str) -> dict:
    """
    state: current dict, e.g. {"name": None, "service_type": None, ...}
    user_utterance: latest transcription from caller
    returns: {"stage": "...", "state": {...}, "reply": "..."}
    """
    if not state:
        state = {
            "name": None,
            "service_type": None,
            "date_time": None,
            "phone": None,
            "confirmed": False,
        }

    user_msg = {
        "role": "user",
        "content": json.dumps({
            "current_state": state,
            "latest_user_utterance": user_utterance
        })
    }

    payload = {
        "model": "gpt-4o-mini",   # openAI model
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            user_msg
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(LLM_BASE_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    result = json.loads(content)
    # Expected keys: stage, state, reply
    return result
