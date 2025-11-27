# app/twilio_routes.py
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse, Gather

from .db import SessionLocal
from .models import Business, CallSession, Appointment
from .excel import append_appointment_to_excel
from .llm import get_next_turn

router = APIRouter(prefix="/voice", tags=["voice"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/incoming", response_class=PlainTextResponse)
async def incoming_call(
    request: Request,
    db: Session = Depends(get_db),
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """
    Called by Twilio when call is answered.
    """
    # Find business by Twilio number
    business = db.query(Business).filter(Business.phone_number == To).first()
    if not business:
        # Default business or error
        # For now, create dummy business if missing
        business = Business(name="Default Business", phone_number=To)
        db.add(business)
        db.commit()
        db.refresh(business)

    # Create call session
    # See if session exists
    session = db.query(CallSession).filter(CallSession.call_sid == CallSid).first()

    if not session:
    # First time this call is seen
        session = CallSession(
            call_sid=CallSid,
            business_id=business.id,
            state={},   # important!
            stage="start"
        )
        db.add(session)
        db.commit()
        db.refresh(session)


    # Greet and ask first open question via LLM
    # For first turn, we can seed the LLM with empty state and generic text
    result = await get_next_turn(session.state or {}, "The call has just started.")

    session.state = result["state"]
    session.stage = result["stage"]
    db.commit()


    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action="https://unslicked-brittni-wiggly.ngrok-free.dev/voice/gather",
        method="POST",
        timeout=5
    )
    gather.say(result.get("reply", "Hello, how can I help you with your appointment today?"))
    vr.append(gather)

    # If no input, end politely
    vr.say("I did not receive any input. Goodbye.")
    vr.hangup()
    return PlainTextResponse(str(vr))


@router.post("/gather", response_class=PlainTextResponse)
async def handle_gather(
    request: Request,
    db: Session = Depends(get_db),
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    From: str = Form(...),
    To: str = Form(...)
):
    """
    Called after each Gather with transcribed speech.
    """
    session = db.query(CallSession).filter(CallSession.call_sid == CallSid).first()
    if not session:
        vr = VoiceResponse()
        vr.say("Sorry, something went wrong. Goodbye.")
        vr.hangup()
        return PlainTextResponse(str(vr))

    # Get next turn from LLM
    result = await get_next_turn(session.state or {}, SpeechResult)

    session.stage = result.get("stage", session.stage)
    session.state = result.get("state", session.state)
    db.commit()

    state = session.state or {}
    reply = result.get("reply", "Could you please repeat that?")

    # If confirmed and all fields present → save appointment & end call
    is_done = state.get("confirmed") is True and all(
        [state.get("name"), state.get("service_type"), state.get("date_time"), state.get("phone")]
    )

    vr = VoiceResponse()

    if is_done:
        # Create appointment
        appt = Appointment(
            business_id=session.business_id,
            customer_name=state.get("name"),
            service_type=state.get("service_type"),
            date_time_str=state.get("date_time"),
            phone_number=state.get("phone"),
            notes=None
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

        # Append to Excel
        append_appointment_to_excel(appt)

        vr.say(reply)
        vr.say("Thank you. Your appointment has been recorded. Goodbye.")
        vr.hangup()
    else:
        gather = Gather(
            input="speech",
            action="https://unslicked-brittni-wiggly.ngrok-free.dev/voice/gather",
            method="POST",
            timeout=5
        )
        gather.say(reply)
        vr.append(gather)
        vr.say("I did not receive any input. Goodbye.")
        vr.hangup()

    return PlainTextResponse(str(vr))
