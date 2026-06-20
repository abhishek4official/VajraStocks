"""Conversation thread CRUD — persistent chat history for the AI Research page."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.db.models import ConversationMessage, ConversationSummary, ConversationThread

router = APIRouter(prefix="/conversations", tags=["AI Conversations"])


# ─── Request / response schemas ───────────────────────────────────────────────

class ThreadCreate(BaseModel):
    agent_type: str
    title: str = "New conversation"


class ThreadResponse(BaseModel):
    id: str
    agent_type: str
    title: str
    message_count: int
    last_active_at: str
    is_archived: bool

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    thread_id: str
    role: str
    content: str
    recommendation: str | None
    confidence: str | None
    annotation: str | None
    is_summarized: bool
    created_at: str

    model_config = {"from_attributes": True}


class SummaryResponse(BaseModel):
    id: int
    summary_text: str
    key_tickers: list | None
    key_decisions: list | None
    generated_at: str

    model_config = {"from_attributes": True}


class SaveMessageRequest(BaseModel):
    thread_id: str
    role: str  # 'user' | 'agent'
    content: str
    recommendation: str | None = None
    confidence: str | None = None


class ThreadUpdate(BaseModel):
    title: str | None = None


class AnnotationUpdate(BaseModel):
    annotation: str


# ─── Thread endpoints ─────────────────────────────────────────────────────────

@router.get("/threads", response_model=list[ThreadResponse])
def list_threads(
    agent_type: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    q = select(ConversationThread).order_by(ConversationThread.last_active_at.desc())
    if agent_type:
        q = q.where(ConversationThread.agent_type == agent_type)
    if not include_archived:
        q = q.where(ConversationThread.is_archived == False)  # noqa: E712
    threads = db.scalars(q).all()
    return [_thread_to_response(t) for t in threads]


@router.post("/threads", response_model=ThreadResponse, status_code=201)
def create_thread(body: ThreadCreate, db: Session = Depends(get_db)):
    thread = ConversationThread(
        id=str(uuid.uuid4()),
        agent_type=body.agent_type,
        title=body.title,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _thread_to_response(thread)


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
def get_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.get(ConversationThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _thread_to_response(thread)


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
def update_thread(thread_id: str, body: ThreadUpdate, db: Session = Depends(get_db)):
    thread = db.get(ConversationThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if body.title is not None:
        thread.title = body.title
    db.commit()
    db.refresh(thread)
    return _thread_to_response(thread)


@router.patch("/threads/{thread_id}/archive")
def archive_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.get(ConversationThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.is_archived = True
    db.commit()
    return {"ok": True}


# ─── Message endpoints ────────────────────────────────────────────────────────

@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
def list_messages(
    thread_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    thread = db.get(ConversationThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    msgs = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.thread_id == thread_id)
        .order_by(ConversationMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_msg_to_response(m) for m in msgs]


@router.post("/messages", response_model=MessageResponse, status_code=201)
def save_message(body: SaveMessageRequest, db: Session = Depends(get_db)):
    thread = db.get(ConversationThread, body.thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    msg = ConversationMessage(
        thread_id=body.thread_id,
        role=body.role,
        content=body.content,
        recommendation=body.recommendation,
        confidence=body.confidence,
    )
    db.add(msg)
    thread.message_count += 1
    db.commit()
    db.refresh(msg)
    return _msg_to_response(msg)


@router.patch("/messages/{message_id}/annotation")
def update_annotation(message_id: int, body: AnnotationUpdate, db: Session = Depends(get_db)):
    msg = db.get(ConversationMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.annotation = body.annotation
    db.commit()
    return {"ok": True}


# ─── Summary endpoints ────────────────────────────────────────────────────────

@router.get("/threads/{thread_id}/summaries", response_model=list[SummaryResponse])
def list_summaries(thread_id: str, db: Session = Depends(get_db)):
    summaries = db.scalars(
        select(ConversationSummary)
        .where(ConversationSummary.thread_id == thread_id)
        .order_by(ConversationSummary.generated_at.asc())
    ).all()
    return [_summary_to_response(s) for s in summaries]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _thread_to_response(t: ConversationThread) -> ThreadResponse:
    return ThreadResponse(
        id=t.id,
        agent_type=t.agent_type,
        title=t.title,
        message_count=t.message_count,
        last_active_at=t.last_active_at.isoformat(),
        is_archived=t.is_archived,
    )


def _msg_to_response(m: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        thread_id=m.thread_id,
        role=m.role,
        content=m.content,
        recommendation=m.recommendation,
        confidence=m.confidence,
        annotation=m.annotation,
        is_summarized=m.is_summarized,
        created_at=m.created_at.isoformat(),
    )


def _summary_to_response(s: ConversationSummary) -> SummaryResponse:
    return SummaryResponse(
        id=s.id,
        summary_text=s.summary_text,
        key_tickers=s.key_tickers,
        key_decisions=s.key_decisions,
        generated_at=s.generated_at.isoformat(),
    )
