import uuid
import os
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _new_uuid():
    return str(uuid.uuid4())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    key_hash = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    credit_balance = Column(Integer, default=10000)
    tier = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(String, default="active")

    tasks = relationship("Task", back_populates="api_key")
    usage = relationship("CreditUsage", back_populates="api_key")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    model = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    input = Column(JSON, nullable=False)
    output_url = Column(Text, nullable=True)
    output_urls = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    progress = Column(Integer, default=0)
    webhook_url = Column(Text, nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)

    api_key = relationship("ApiKey", back_populates="tasks")
    usage = relationship("CreditUsage", back_populates="task")


class CreditUsage(Base):
    __tablename__ = "credit_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    model = Column(String, nullable=True)
    credits = Column(Integer, default=0)
    used_at = Column(DateTime, default=datetime.utcnow)

    api_key = relationship("ApiKey", back_populates="usage")
    task = relationship("Task", back_populates="usage")
