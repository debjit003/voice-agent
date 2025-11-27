# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True)  # Twilio number

    appointments = relationship("Appointment", back_populates="business")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String, unique=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    state = Column(JSON, default={})        # e.g. {"name": "...", "service": "..."}
    stage = Column(String, default="start") # greeting, ask_name, ask_date_time, confirm, done
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    customer_name = Column(String)
    service_type = Column(String)
    date_time_str = Column(String)   # simple string for now
    phone_number = Column(String)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="appointments")
