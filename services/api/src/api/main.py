from fund_core.bootstrap import bootstrap

bootstrap()

import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.graph import stream_chat
from api.access import AccessDecision
from api.policy import access_decision
from fund_core.config import get_settings
from fund_core.tracing import langsmith_enabled

settings = get_settings()
logger = logging.getLogger("luna.api")
from fund_core.db import async_session_factory, get_session
from fund_core.models import Conversation, Message
from fund_core.scheduler import BackgroundSyncScheduler
from fund_core.sync_runner import run_all_syncs

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    settings = get_settings()
    logger = logging.getLogger("luna.api")

    scheduler: BackgroundSyncScheduler | None = None
    if settings.sync_enabled:
        scheduler = BackgroundSyncScheduler(settings)
        if settings.sync_run_on_startup:
            logger.info("Running startup sync")
            results = await scheduler.run_once()
            for job, outcome in results.items():
                logger.info("Startup %s: %s", job, outcome)
        await scheduler.start()
        logger.info(
            "Background sync on (sheets=%sm portfolio=%sm)",
            settings.sync_sheets_interval_minutes,
            settings.sync_portfolio_interval_minutes,
        )
    else:
        logger.info("Background sync disabled (SYNC_ENABLED=false)")

    yield

    if scheduler is not None:
        await scheduler.stop()


app = FastAPI(title="Luna Fund AI", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: str


@app.get("/health")
async def health():
    return {"status": "ok", "langsmith": langsmith_enabled()}


@app.post("/v1/chat")
async def chat(body: ChatRequest):
    conv_id = body.conversation_id or uuid.uuid4()

    async def event_stream():
        history: list[tuple[str, str]]
        decision: AccessDecision

        async with async_session_factory() as prep:
            try:
                conv = await prep.get(Conversation, conv_id)
                if conv is None:
                    prep.add(Conversation(id=conv_id))
                    await prep.flush()

                history_rows = await prep.execute(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at)
                )
                history = [(m.role, m.content) for m in history_rows.scalars().all()]
                decision = access_decision(body.message, history)

                prep.add(
                    Message(conversation_id=conv_id, role="user", content=body.message)
                )
                await prep.commit()
            except Exception:
                await prep.rollback()
                raise

        full = ""
        tool_results: list = []
        async with async_session_factory() as session:
            try:
                async for event in stream_chat(
                    session,
                    body.message,
                    history=history,
                    conversation_id=str(conv_id),
                    decision=decision,
                ):
                    if event["type"] == "token":
                        full += event["content"]
                        yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
                    elif event["type"] == "done":
                        full = event["content"]
                        tool_results = event.get("tool_results", [])
                        # Persist the assistant turn BEFORE emitting `done`. The web
                        # BFF closes the upstream connection the instant it sees
                        # `done`, which cancels this generator — any code after the
                        # final yield may never run. Committing first guarantees the
                        # reply is saved, so a follow-up never reads a bare,
                        # user-only history and answers every past question at once.
                        # (A disconnect mid-token-stream can still leave a trailing
                        # user turn; _history_to_messages drops it on the next read.)
                        if full:
                            session.add(
                                Message(
                                    conversation_id=conv_id,
                                    role="assistant",
                                    content=full,
                                    tool_calls=tool_results,
                                )
                            )
                            await session.commit()
                        yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conv_id)})}\n\n"
            except Exception:
                await session.rollback()
                raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Conversation-Id": str(conv_id)},
    )


@app.get("/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return {
        "id": str(conversation_id),
        "messages": [
            {"role": m.role, "content": m.content, "tool_calls": m.tool_calls} for m in messages
        ],
    }


@app.post("/admin/jobs/sync")
async def admin_sync(
    session: AsyncSession = Depends(get_session),
    x_admin_secret: str | None = Header(default=None),
):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(401, "Invalid admin secret")
    return await run_all_syncs(session)


def run():
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
