"""Financing Proxy API.

Client-facing API that wraps the Managed Agent.
Handles registration, authentication, analysis, and usage tracking.
"""

import json

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from financing_proxy.agent import analyze_pdf_stream, analyze_pdf_sync
from financing_proxy.auth import generate_api_key
from financing_proxy.firestore import (
    get_eval_run_detail,
    get_eval_runs,
    get_usage,
    increment_usage,
    log_run,
    register_client,
    validate_api_key,
)

app = FastAPI(
    title="Financing Analyzer API",
    description="Analyze SMB financing offers — MCA, term loans, PO financing, receivables",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    company: str


class RegisterResponse(BaseModel):
    api_key: str
    name: str
    email: str
    company: str
    message: str


class AnalyzeRequest(BaseModel):
    pdf: str  # base64-encoded PDF
    message: str = "Analyze this financing offer. Extract all key terms, calculate the effective APR, check for predatory terms, and compare to market benchmarks."
    title: str = "offer.pdf"


class AnalyzeResponse(BaseModel):
    analysis: str
    tool_calls: list[dict]


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def require_api_key(x_api_key: str = Header(...)) -> dict:
    """Validate API key and return client record."""
    client = validate_api_key(x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return client


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "financing-proxy"}


@app.post("/v1/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    """Self-serve registration. Returns an API key (shown once)."""
    api_key = generate_api_key()
    client_data = register_client(
        name=req.name,
        email=req.email,
        company=req.company,
        api_key=api_key,
    )
    return RegisterResponse(
        api_key=api_key,
        name=client_data["name"],
        email=client_data["email"],
        company=client_data["company"],
        message="Save this API key — it will not be shown again.",
    )


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


@app.post("/v1/analyze")
async def analyze_streaming(
    req: AnalyzeRequest,
    x_api_key: str = Header(...),
):
    """Analyze a financing offer. Returns an SSE stream."""
    client = validate_api_key(x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    doc_id = client["doc_id"]

    def event_stream():
        total_input = 0
        total_output = 0
        full_text = []
        tool_names = []
        mcp_inputs = []

        for event in analyze_pdf_stream(req.pdf, req.message, req.title):
            if event["type"] == "text":
                full_text.append(event["content"])
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "tool_use":
                tool_names.append({"name": event["name"]})
                if event.get("input"):
                    mcp_inputs.append({"tool": event["name"], "input": event["input"]})
                # Don't send tool inputs to client
                yield f"data: {json.dumps({'type': 'tool_use', 'name': event['name']})}\n\n"
            elif event["type"] == "done":
                total_input = event.get("input_tokens", 0)
                total_output = event.get("output_tokens", 0)
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

        increment_usage(doc_id, total_input, total_output)
        log_run(
            client_doc_id=doc_id,
            pdf_title=req.title,
            pdf_base64=req.pdf,
            message=req.message,
            output="".join(full_text),
            tool_calls=tool_names,
            mcp_tool_inputs=mcp_inputs,
            input_tokens=total_input,
            output_tokens=total_output,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/analyze/sync", response_model=AnalyzeResponse)
async def analyze_sync(
    req: AnalyzeRequest,
    x_api_key: str = Header(...),
):
    """Analyze a financing offer. Returns the full result as JSON."""
    client = validate_api_key(x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    result = analyze_pdf_sync(req.pdf, req.message, req.title)
    increment_usage(
        client["doc_id"], result.input_tokens, result.output_tokens
    )
    log_run(
        client_doc_id=client["doc_id"],
        pdf_title=req.title,
        pdf_base64=req.pdf,
        message=req.message,
        output=result.full_text,
        tool_calls=result.tool_calls,
        mcp_tool_inputs=result.mcp_tool_inputs,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    return AnalyzeResponse(
        analysis=result.full_text,
        tool_calls=result.tool_calls,
    )


@app.get("/v1/usage")
async def usage(x_api_key: str = Header(...)):
    """Get usage stats for the authenticated client."""
    client = validate_api_key(x_api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    stats = get_usage(client["doc_id"])
    if stats is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return stats


# ---------------------------------------------------------------------------
# Admin endpoints — eval dashboard
# Protected by ADMIN_API_KEY env var (separate from client keys)
# ---------------------------------------------------------------------------

import os

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


def require_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Validate admin key."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoints not configured")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@app.get("/admin/evals")
async def list_evals(
    status: str | None = None,
    limit: int = 20,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """List eval runs. Filter by status: pending, evaluated."""
    require_admin(x_admin_key)
    return get_eval_runs(status=status, limit=limit)


@app.get("/admin/evals/{run_id}")
async def get_eval(
    run_id: str,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Get detailed eval result for a specific run."""
    require_admin(x_admin_key)
    detail = get_eval_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return detail
