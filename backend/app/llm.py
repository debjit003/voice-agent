# app/llm.py
import httpx
import json
from httpx import HTTPStatusError
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


def _init_state_if_needed(state: dict | None) -> dict:
    if not state:
        state = {
            "name": None,
            "service_type": None,
            "date_time": None,
            "phone": None,
            "confirmed": False,
        }
    return state


def _clean_text(text: str) -> str:
    return text.strip().strip(".,!?").strip()


def _extract_name(text: str) -> str:
    """
    Very simple heuristic: remove common prefixes like
    'my name is', 'this is', 'i am', etc.
    """
    t = text.strip()
    low = t.lower()
    prefixes = ["my name is", "this is", "i am", "it's", "it is"]
    for p in prefixes:
        if low.startswith(p):
            return _clean_text(t[len(p):])
    return _clean_text(t)


def _simple_fallback_logic(state: dict, user_utterance: str) -> dict:
    """
    Very simple, sequential slot-filling logic that actually
    uses the user's utterance to update the state.
    """
    state = _init_state_if_needed(state)
    text = user_utterance.strip()

    # Ignore the synthetic message we send from /incoming
    if text.lower().startswith("the call has just started"):
        text = ""

    # 1) NAME
    if not state.get("name"):
        if text:
            # Treat whatever the caller said as their name (with basic cleaning)
            name = _extract_name(text)
            state["name"] = name or "Guest"
            reply = f"Thanks {state['name']}. What service would you like to book?"
            stage = "ask_service"
        else:
            reply = "Hello, this is the appointment assistant. May I know your name?"
            stage = "ask_name"

        return {
            "stage": stage,
            "state": state,
            "reply": reply,
        }

    # 2) SERVICE TYPE
    if not state.get("service_type"):
        if text:
            state["service_type"] = _clean_text(text)
            reply = (
                f"Great. When would you like to schedule the "
                f"{state['service_type']} appointment?"
            )
            stage = "ask_date_time"
        else:
            reply = "What service would you like to book?"
            stage = "ask_service"

        return {
            "stage": stage,
            "state": state,
            "reply": reply,
        }

    # 3) DATE/TIME
    if not state.get("date_time"):
        if text:
            state["date_time"] = _clean_text(text)
            reply = "Please tell me your phone number so we can confirm the booking."
            stage = "ask_phone"
        else:
            reply = "When would you like to schedule the appointment?"
            stage = "ask_date_time"

        return {
            "stage": stage,
            "state": state,
            "reply": reply,
        }

    # 4) PHONE
    if not state.get("phone"):
        if text:
            state["phone"] = _clean_text(text)
            # All fields collected, move to confirmation
            state["confirmed"] = True
            reply = (
                f"Thank you. I will record your appointment for "
                f"{state['service_type']} on {state['date_time']} "
                f"for {state['name']}. We will contact you at {state['phone']}. Goodbye."
            )
            stage = "confirm"
        else:
            reply = "Please say your phone number slowly."
            stage = "ask_phone"

        return {
            "stage": stage,
            "state": state,
            "reply": reply,
        }

    # Already confirmed – just end politely
    reply = (
        f"Your appointment for {state['service_type']} on "
        f"{state['date_time']} is already recorded. Goodbye."
    )
    state["confirmed"] = True
    stage = "done"

    return {
        "stage": stage,
        "state": state,
        "reply": reply,
    }


async def get_next_turn(state: dict, user_utterance: str) -> dict:
    """
    Tries to use LLM. If key missing, rate-limited, or any error happens,
    falls back to simple rule-based logic.
    """
    state = _init_state_if_needed(state)

    # If no key configured, just use fallback
    if not LLM_API_KEY:
        return _simple_fallback_logic(state, user_utterance)

    user_msg = {
        "role": "user",
            "content": json.dumps(
            {"current_state": state, "latest_user_utterance": user_utterance}
        ),
    }

    payload = {
        "model": "gpt-4o-mini",  # adjust to a valid model for your provider
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            user_msg,
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(LLM_BASE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        return result

    except HTTPStatusError:
        # Any HTTP error from the LLM → fallback
        return _simple_fallback_logic(state, user_utterance)
    except Exception:
        # Any unknown error → fallback
        return _simple_fallback_logic(state, user_utterance)
