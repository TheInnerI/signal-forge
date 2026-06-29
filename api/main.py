"""FastAPI backend for Signal Forge v2 — Agent-facing REST API with SSE streaming."""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from engine.config import ACP_OFFERINGS, LOOP_MODES, TONE_MODIFIERS, ASSET_TYPE_FOCUS
from engine.database import (
    get_stats, get_loop_laws, search_decodes, search_assets,
    get_decode_by_id, get_asset_by_id, get_recent_decodes, get_recent_assets,
)
from engine.infrastructure import check_infrastructure_sync, poa_score_sync, secure_scan_sync
from engine.loop_engine import decode_loop, get_loop_diagram
from engine.signal_forge import forge_signal

logger = logging.getLogger("signal_forge_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(
    title="Signal Forge v2 API",
    description="Second-order cybernetics decoder + asset engine. Agent-facing REST API for Virtuals Protocol.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all for now (ACP agents call from anywhere)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Auth ────────────────────────────────────────────────────────────────────

API_KEYS = set()  # Populated from env in production

def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """Verify API key if one is configured. Free tier works without key."""
    if not API_KEYS:
        return True  # No keys configured = open access
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ─── Request/Response Models ──────────────────────────────────────────────────

class DecodeRequest(BaseModel):
    mode: str = Field(..., description="Loop type to decode", example="Business Loop")
    situation: str = Field(..., min_length=10, description="The situation/pattern to decode")
    tier: str = Field(default="free", description="User tier: free or pro")
    verify: bool = Field(default=True, description="Run PoA + Secure Gateway verification")
    stream: bool = Field(default=False, description="Stream response via SSE")

class ForgeRequest(BaseModel):
    raw_signal: str = Field(..., min_length=5, description="The raw idea/signal to forge")
    asset_type: str = Field(default="Full Signal Pack", description="Type of asset pack")
    tone: str = Field(default="Inner I Default", description="Tone modifier")
    tier: str = Field(default="free", description="User tier: free or pro")
    verify: bool = Field(default=True, description="Run PoA + Secure Gateway verification")
    stream: bool = Field(default=False, description="Stream response via SSE")

class BatchForgeRequest(BaseModel):
    signals: list[ForgeRequest] = Field(..., min_length=1, max_length=10, description="Up to 10 signals to forge")

class BatchDecodeRequest(BaseModel):
    decodes: list[DecodeRequest] = Field(..., min_length=1, max_length=10, description="Up to 10 loops to decode")

class WebhookConfig(BaseModel):
    url: str = Field(..., description="Webhook URL to POST results to")
    secret: Optional[str] = Field(None, description="HMAC secret for webhook verification")


# ─── Middleware ───────────────────────────────────────────────────────────────

@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.2f}s)")
    return response


# ─── Health & Infrastructure ─────────────────────────────────────────────────

@app.get("/v1/health", tags=["System"])
async def health_check():
    """System health check — engine + infrastructure status."""
    infra = check_infrastructure_sync()
    stats = get_stats()
    return {
        "status": "ok",
        "version": "2.0.0",
        "infrastructure": infra,
        "stats": {
            "total_decodes": stats["total_decodes"],
            "total_assets": stats["total_assets"],
            "total_laws": stats["total_laws"],
        },
    }


@app.get("/v1/infrastructure", tags=["System"])
async def infrastructure_status():
    """Detailed infrastructure health — PoA, Secure Gateway, tier."""
    return check_infrastructure_sync()


# ─── Decode Endpoints ────────────────────────────────────────────────────────

@app.post("/v1/decode", tags=["Loop Engineer"])
async def api_decode(req: DecodeRequest):
    """Decode a feedback loop — returns structured decode with operating law and signal scores."""
    if req.mode not in LOOP_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Valid: {list(LOOP_MODES.keys())}")

    result = decode_loop(
        mode=req.mode,
        situation=req.situation,
        tier=req.tier,
        verify=req.verify,
        stream=False,
    )

    if result.get("error"):
        return JSONResponse(status_code=429 if "limit" in result["error"] else 400, content=result)

    # Build structured response
    response = {
        "surface_signal": _extract_section(result["result"], "Surface Signal"),
        "system_loop": _extract_section(result["result"], "System Loop"),
        "observer_position": _extract_section(result["result"], "Observer Position"),
        "hidden_assumption": _extract_section(result["result"], "Hidden Assumption"),
        "reinforcement_mechanism": _extract_section(result["result"], "Reinforcement Mechanism"),
        "failure_mode": _extract_section(result["result"], "Failure Mode"),
        "leverage_point": _extract_section(result["result"], "Leverage Point"),
        "correction_protocol": _extract_section(result["result"], "Correction Protocol"),
        "operating_law": result.get("loop_law", ""),
        "asset_opportunity": _extract_section(result["result"], "Asset/Automation Opportunity"),
        "signal_score": result.get("signal_score"),
        "poa_grounding": result.get("poa"),
        "secure_scan": result.get("secure"),
        "raw_output": result["result"],
    }
    return response


@app.post("/v1/decode/stream", tags=["Loop Engineer"])
async def api_decode_stream(req: DecodeRequest):
    """Decode a feedback loop with SSE streaming — tokens arrive in real time."""
    if req.mode not in LOOP_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Valid: {list(LOOP_MODES.keys())}")

    def event_generator():
        for chunk in decode_loop(
            mode=req.mode,
            situation=req.situation,
            tier=req.tier,
            verify=req.verify,
            stream=True,
        ):
            if chunk.get("type") == "token":
                yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
            elif chunk.get("type") == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'loop_law': chunk.get('loop_law', ''), 'signal_score': chunk.get('signal_score'), 'poa': chunk.get('poa'), 'secure': chunk.get('secure')})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/v1/decode/diagram", tags=["Loop Engineer"])
async def api_decode_diagram(req: DecodeRequest):
    """Decode a loop and return an ASCII loop diagram."""
    result = decode_loop(mode=req.mode, situation=req.situation, tier=req.tier, verify=req.verify, stream=False)
    if result.get("error"):
        return JSONResponse(status_code=400, content=result)
    diagram = get_loop_diagram(result["result"])
    return {"diagram": diagram, "operating_law": result.get("loop_law", ""), "signal_score": result.get("signal_score")}


# ─── Forge Endpoints ─────────────────────────────────────────────────────────

@app.post("/v1/forge", tags=["Signal Forge"])
async def api_forge(req: ForgeRequest):
    """Forge a signal into monetizable assets — returns structured asset pack."""
    if req.asset_type not in ASSET_TYPE_FOCUS:
        raise HTTPException(status_code=400, detail=f"Invalid asset_type. Valid: {list(ASSET_TYPE_FOCUS.keys())}")
    if req.tone not in TONE_MODIFIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tone. Valid: {list(TONE_MODIFIERS.keys())}")

    result = forge_signal(
        input_text=req.raw_signal,
        asset_type=req.asset_type,
        tone=req.tone,
        tier=req.tier,
        verify=req.verify,
        stream=False,
    )

    if result.get("error"):
        return JSONResponse(status_code=429 if "limit" in result["error"] else 400, content=result)

    # Build structured response
    response = {
        "x_post": _extract_section(result["result"], "X Post"),
        "x_thread": _extract_section(result["result"], "X Thread"),
        "wordpress_article": _extract_section(result["result"], "WordPress Article"),
        "youtube_title": _extract_section(result["result"], "YouTube Title"),
        "youtube_description": _extract_section(result["result"], "YouTube Description"),
        "youtube_tags": _extract_section(result["result"], "YouTube Tags"),
        "shorts_script": _extract_section(result["result"], "Shorts/Reels Script"),
        "thumbnail_prompt": _extract_section(result["result"], "Thumbnail/Cover Prompt"),
        "offer_angle": _extract_section(result["result"], "Offer Angle"),
        "next_move": _extract_section(result["result"], "Next Best Monetization Move"),
        "signal_score": result.get("signal_score"),
        "poa_grounding": result.get("poa"),
        "secure_scan": result.get("secure"),
        "raw_output": result["result"],
    }
    return response


@app.post("/v1/forge/stream", tags=["Signal Forge"])
async def api_forge_stream(req: ForgeRequest):
    """Forge a signal with SSE streaming — tokens arrive in real time."""
    if req.asset_type not in ASSET_TYPE_FOCUS:
        raise HTTPException(status_code=400, detail=f"Invalid asset_type. Valid: {list(ASSET_TYPE_FOCUS.keys())}")

    def event_generator():
        for chunk in forge_signal(
            input_text=req.raw_signal,
            asset_type=req.asset_type,
            tone=req.tone,
            tier=req.tier,
            verify=req.verify,
            stream=True,
        ):
            if chunk.get("type") == "token":
                yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
            elif chunk.get("type") == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'signal_score': chunk.get('signal_score'), 'poa': chunk.get('poa'), 'secure': chunk.get('secure')})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Batch Endpoints ─────────────────────────────────────────────────────────

@app.post("/v1/batch/decode", tags=["Batch"])
async def api_batch_decode(req: BatchDecodeRequest):
    """Batch decode up to 10 loops. Returns array of results."""
    results = []
    for item in req.decodes:
        result = decode_loop(mode=item.mode, situation=item.situation, tier=item.tier, verify=item.verify, stream=False)
        results.append(result)
    return {"results": results, "count": len(results)}


@app.post("/v1/batch/forge", tags=["Batch"])
async def api_batch_forge(req: BatchForgeRequest):
    """Batch forge up to 10 signals. Returns array of asset packs."""
    results = []
    for item in req.signals:
        result = forge_signal(
            input_text=item.raw_signal, asset_type=item.asset_type,
            tone=item.tone, tier=item.tier, verify=item.verify, stream=False,
        )
        results.append(result)
    return {"results": results, "count": len(results)}


# ─── Library Endpoints ────────────────────────────────────────────────────────

@app.get("/v1/laws", tags=["Library"])
async def api_laws(limit: int = Query(default=50, ge=1, le=200)):
    """Browse extracted operating laws."""
    laws = get_loop_laws(limit=limit)
    return {"laws": [{"law": law, "category": cat} for law, cat in laws], "count": len(laws)}


@app.get("/v1/stats", tags=["Library"])
async def api_stats():
    """Aggregate statistics — decodes, assets, scores, usage."""
    return get_stats()


@app.get("/v1/offerings", tags=["ACP"])
async def api_offerings():
    """List available ACP marketplace offerings with schemas."""
    return {"offerings": ACP_OFFERINGS, "count": len(ACP_OFFERINGS)}


# ─── History Endpoints ────────────────────────────────────────────────────────

@app.get("/v1/history/decodes", tags=["History"])
async def api_history_decodes(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    """Browse recent loop decodes."""
    decodes = get_recent_decodes(limit=limit, offset=offset)
    return {"decodes": decodes, "count": len(decodes)}


@app.get("/v1/history/assets", tags=["History"])
async def api_history_assets(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    """Browse recent forged assets."""
    assets = get_recent_assets(limit=limit, offset=offset)
    return {"assets": assets, "count": len(assets)}


@app.get("/v1/history/decodes/{decode_id}", tags=["History"])
async def api_decode_detail(decode_id: int):
    """Get a specific decode by ID."""
    decode = get_decode_by_id(decode_id)
    if not decode:
        raise HTTPException(status_code=404, detail="Decode not found")
    return decode


@app.get("/v1/history/assets/{asset_id}", tags=["History"])
async def api_asset_detail(asset_id: int):
    """Get a specific asset by ID."""
    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@app.get("/v1/search/decodes", tags=["History"])
async def api_search_decodes(q: str = Query(..., min_length=2), limit: int = Query(default=20, ge=1, le=100)):
    """Search decodes by keyword."""
    results = search_decodes(query=q, limit=limit)
    return {"results": results, "count": len(results)}


@app.get("/v1/search/assets", tags=["History"])
async def api_search_assets(q: str = Query(..., min_length=2), limit: int = Query(default=20, ge=1, le=100)):
    """Search assets by keyword."""
    results = search_assets(query=q, limit=limit)
    return {"results": results, "count": len(results)}


# ─── Export Endpoints ────────────────────────────────────────────────────────

@app.get("/v1/export/decode/{decode_id}/markdown", tags=["Export"])
async def api_export_decode_md(decode_id: int):
    """Export a decode as Markdown file."""
    decode = get_decode_by_id(decode_id)
    if not decode:
        raise HTTPException(status_code=404, detail="Decode not found")
    md_content = _decode_to_markdown(decode)
    return StreamingResponse(
        iter([md_content]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=decode_{decode_id}.md"},
    )


@app.get("/v1/export/decode/{decode_id}/json", tags=["Export"])
async def api_export_decode_json(decode_id: int):
    """Export a decode as JSON file."""
    decode = get_decode_by_id(decode_id)
    if not decode:
        raise HTTPException(status_code=404, detail="Decode not found")
    return JSONResponse(
        content=decode,
        headers={"Content-Disposition": f"attachment; filename=decode_{decode_id}.json"},
    )


@app.get("/v1/export/asset/{asset_id}/markdown", tags=["Export"])
async def api_export_asset_md(asset_id: int):
    """Export an asset as Markdown file."""
    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    md_content = _asset_to_markdown(asset)
    return StreamingResponse(
        iter([md_content]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=asset_{asset_id}.md"},
    )


@app.get("/v1/export/asset/{asset_id}/json", tags=["Export"])
async def api_export_asset_json(asset_id: int):
    """Export an asset as JSON file."""
    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return JSONResponse(
        content=asset,
        headers={"Content-Disposition": f"attachment; filename=asset_{asset_id}.json"},
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_section(text: str, heading: str) -> str:
    """Extract content under a markdown heading from LLM output."""
    if heading not in text:
        return ""
    try:
        parts = text.split(f"## {heading}")
        if len(parts) < 2:
            return ""
        content = parts[1]
        # Find the next ## heading
        next_heading = content.find("\n## ")
        if next_heading != -1:
            content = content[:next_heading]
        return content.strip()
    except (IndexError, ValueError):
        return ""


def _decode_to_markdown(decode: dict) -> str:
    """Convert a decode record to markdown."""
    lines = [
        f"# Loop Decode — {decode.get('mode', 'Unknown')}",
        f"",
        f"**Mode:** {decode.get('mode', 'N/A')}  ",
        f"**Date:** {decode.get('created_at', 'N/A')}  ",
        f"**Operating Law:** {decode.get('loop_law', 'N/A')}  ",
        f"",
        "---",
        "",
    ]
    output = decode.get("output_json", "")
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = {"raw": output}
    lines.append(output.get("raw", str(output)))
    return "\n".join(lines)


def _asset_to_markdown(asset: dict) -> str:
    """Convert an asset record to markdown."""
    lines = [
        f"# Signal Forge — {asset.get('asset_type', 'Unknown')}",
        f"",
        f"**Tone:** {asset.get('tone', 'N/A')}  ",
        f"**Type:** {asset.get('asset_type', 'N/A')}  ",
        f"**Date:** {asset.get('created_at', 'N/A')}  ",
        f"",
        "---",
        "",
    ]
    output = asset.get("output_json", "")
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = {"raw": output}
    lines.append(output.get("raw", str(output)))
    return "\n".join(lines)


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Signal Forge v2 API starting up")
    infra = check_infrastructure_sync()
    logger.info(f"Infrastructure tier: {infra['tier']} — {infra['endpoints']}")
