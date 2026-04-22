"""FastAPI app for the paid financing agent.

Endpoints:
    GET  /health     liveness check
    POST /verify     standalone payment verification (debugging)
    POST /analyze    verify payment → store PDF → run agent → stream SSE
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from financing_api import agent, ledger, storage
from financing_api.config import load_settings
from financing_api.payments import PaymentError, verify_payment
from financing_api.schemas import AnalyzeRequest, VerifyRequest, VerifyResponse

settings = load_settings()

app = FastAPI(title="financing-api", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest) -> VerifyResponse:
    try:
        payment = await verify_payment(
            rpc_url=settings.tempo_rpc_url,
            tx_hash=req.tx_hash,
            usdc_address=settings.usdc_address,
            usdc_decimals=settings.usdc_decimals,
            expected_to=settings.treasury_address,
            expected_amount_usdc=Decimal(settings.price_usdc),
        )
    except PaymentError as e:
        return VerifyResponse(ok=False, error=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"verify failed: {e}")

    return VerifyResponse(
        ok=True,
        from_address=payment.from_address,
        to_address=payment.to_address,
        amount_usdc=str(payment.amount_usdc),
        block_number=payment.block_number,
    )


def _sse(event: str, data: dict | str) -> str:
    """Format a Server-Sent Events frame. Data is always JSON-encoded."""
    body = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {body}\n\n"


@app.post("/analyze")
async def analyze(req: AnalyzeRequest) -> StreamingResponse:
    # 1. Verify payment on Tempo
    try:
        payment = await verify_payment(
            rpc_url=settings.tempo_rpc_url,
            tx_hash=req.tx_hash,
            usdc_address=settings.usdc_address,
            usdc_decimals=settings.usdc_decimals,
            expected_to=settings.treasury_address,
            expected_amount_usdc=Decimal(settings.price_usdc),
        )
    except PaymentError as e:
        raise HTTPException(status_code=402, detail=str(e))

    # 2. Store PDF (deduped) + 3. claim payment atomically + 4. create run doc
    try:
        stored = await asyncio.to_thread(
            storage.store_pdf,
            project=settings.gcp_project,
            bucket_name=settings.pdf_bucket,
            pdf_base64=req.pdf_base64,
        )
        run_id = await asyncio.to_thread(
            ledger.create_run,
            project=settings.gcp_project,
            collection=settings.runs_collection,
            tx_hash=payment.tx_hash,
            payer_address=payment.from_address,
            gcs_uri=stored.gcs_uri,
            content_hash=stored.content_hash,
            pdf_is_new=stored.is_new,
        )
        await asyncio.to_thread(
            ledger.consume_payment,
            project=settings.gcp_project,
            collection=settings.payments_collection,
            tx_hash=payment.tx_hash,
            from_address=payment.from_address,
            to_address=payment.to_address,
            amount_usdc=str(payment.amount_usdc),
            run_id=run_id,
        )
    except ledger.PaymentAlreadyConsumed:
        raise HTTPException(status_code=409, detail="tx already consumed")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"setup failed: {e}")

    # 5. Stream the agent's output back as SSE
    async def event_stream() -> AsyncIterator[bytes]:
        accumulated_text = ""
        tool_calls: list[dict] = []
        input_tokens = 0
        output_tokens = 0
        error_msg: str | None = None

        yield _sse("run", {"run_id": run_id, "gcs_uri": stored.gcs_uri}).encode()

        try:
            # The agent SDK is sync; hop to a thread and pump events into a queue.
            queue: asyncio.Queue[dict | None] = asyncio.Queue()

            def produce() -> None:
                try:
                    for ev in agent.analyze_pdf_stream(
                        agent_id=settings.agent_id,
                        environment_id=settings.environment_id,
                        vault_id=settings.vault_id,
                        pdf_base64=req.pdf_base64,
                        message=agent.DEFAULT_PROMPT,
                        title=req.title,
                    ):
                        queue.put_nowait(ev)
                finally:
                    queue.put_nowait(None)  # sentinel

            producer = asyncio.create_task(asyncio.to_thread(produce))

            while True:
                ev = await queue.get()
                if ev is None:
                    break
                if ev["type"] == "text":
                    accumulated_text += ev["content"]
                    yield _sse("text", ev["content"]).encode()
                elif ev["type"] == "tool_use":
                    tool_calls.append({"name": ev["name"], "input": ev.get("input", {})})
                    yield _sse("tool_use", {"name": ev["name"], "input": ev.get("input", {})}).encode()
                elif ev["type"] == "done":
                    input_tokens = ev.get("input_tokens", 0)
                    output_tokens = ev.get("output_tokens", 0)
                    yield _sse(
                        "done",
                        {"input_tokens": input_tokens, "output_tokens": output_tokens},
                    ).encode()
                elif ev["type"] == "error":
                    error_msg = ev["content"]
                    yield _sse("error", ev["content"]).encode()

            await producer
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            yield _sse("error", error_msg).encode()
        finally:
            status = "failed" if error_msg else "completed"
            try:
                await asyncio.to_thread(
                    ledger.update_run,
                    project=settings.gcp_project,
                    collection=settings.runs_collection,
                    run_id=run_id,
                    status=status,
                    full_text=accumulated_text,
                    tool_calls=tool_calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error=error_msg,
                )
            except Exception:  # noqa: BLE001
                # Don't mask the primary error with a bookkeeping failure.
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
