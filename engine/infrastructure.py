"""Infrastructure integration — PoA scoring and Secure Gateway scanning."""

import httpx
import json
from typing import Optional

from .config import POA_BASE_URL, SECURE_GATEWAY_URL


# ─── Proof of Awareness ─────────────────────────────────────────────────────

async def poa_score(text: str, context: str = "") -> dict:
    """
    Score text via Proof of Awareness API.
    Returns: {"score": float, "verified": bool, "receipt": str|None}
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{POA_BASE_URL}/score",
                json={"text": text, "context": context, "dimensions": ["truth", "groundedness", "fruit"]},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "score": data.get("score", 0.0),
                    "verified": True,
                    "receipt": data.get("receipt_id"),
                    "raw": data,
                }
            return {"score": 0.0, "verified": False, "receipt": None, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"score": 0.0, "verified": False, "receipt": None, "error": str(e)}


def poa_score_sync(text: str, context: str = "") -> dict:
    """Synchronous version of poa_score."""
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{POA_BASE_URL}/score",
                json={"text": text, "context": context, "dimensions": ["truth", "groundedness", "fruit"]},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "score": data.get("score", 0.0),
                    "verified": True,
                    "receipt": data.get("receipt_id"),
                    "raw": data,
                }
            return {"score": 0.0, "verified": False, "receipt": None, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"score": 0.0, "verified": False, "receipt": None, "error": str(e)}


# ─── Secure Gateway ──────────────────────────────────────────────────────────

async def secure_scan(text: str) -> dict:
    """
    Scan text via Inner I Secure Gateway for injection/exfiltration.
    Returns: {"safe": bool, "verdict": str, "findings": list}
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SECURE_GATEWAY_URL}/v1/scan",
                json={"text": text, "scan_types": ["injection", "exfiltration", "prompt_leak"]},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "safe": data.get("safe", True),
                    "verdict": data.get("verdict", "clean"),
                    "findings": data.get("findings", []),
                    "raw": data,
                }
            return {"safe": True, "verdict": "unknown", "findings": [], "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"safe": True, "verdict": "unavailable", "findings": [], "error": str(e)}


def secure_scan_sync(text: str) -> dict:
    """Synchronous version of secure_scan."""
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{SECURE_GATEWAY_URL}/v1/scan",
                json={"text": text, "scan_types": ["injection", "exfiltration", "prompt_leak"]},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "safe": data.get("safe", True),
                    "verdict": data.get("verdict", "clean"),
                    "findings": data.get("findings", []),
                    "raw": data,
                }
            return {"safe": True, "verdict": "unknown", "findings": [], "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"safe": True, "verdict": "unavailable", "findings": [], "error": str(e)}


# ─── Infrastructure Health ───────────────────────────────────────────────────

async def check_infrastructure() -> dict:
    """Check all infrastructure endpoints for availability."""
    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        # PoA
        try:
            resp = await client.get(f"{POA_BASE_URL}/")
            results["poa"] = {"status": "up" if resp.status_code == 200 else "degraded", "code": resp.status_code}
        except Exception:
            results["poa"] = {"status": "down"}

        # Secure Gateway
        try:
            resp = await client.get(f"{SECURE_GATEWAY_URL}/v1/audit")
            results["secure_gateway"] = {"status": "up" if resp.status_code in (200, 404) else "degraded", "code": resp.status_code}
        except Exception:
            results["secure_gateway"] = {"status": "down"}

    # Determine tier
    up_count = sum(1 for v in results.values() if v["status"] == "up")
    if up_count == 2:
        tier = "full"
    elif up_count > 0:
        tier = "degraded"
    else:
        tier = "offline"

    return {"endpoints": results, "tier": tier}


def check_infrastructure_sync() -> dict:
    """Synchronous version of infrastructure health check."""
    results = {}
    with httpx.Client(timeout=10.0) as client:
        try:
            resp = client.get(f"{POA_BASE_URL}/")
            results["poa"] = {"status": "up" if resp.status_code == 200 else "degraded", "code": resp.status_code}
        except Exception:
            results["poa"] = {"status": "down"}

        try:
            resp = client.get(f"{SECURE_GATEWAY_URL}/v1/audit")
            results["secure_gateway"] = {"status": "up" if resp.status_code in (200, 404) else "degraded", "code": resp.status_code}
        except Exception:
            results["secure_gateway"] = {"status": "down"}

    up_count = sum(1 for v in results.values() if v["status"] == "up")
    if up_count == 2:
        tier = "full"
    elif up_count > 0:
        tier = "degraded"
    else:
        tier = "offline"

    return {"endpoints": results, "tier": tier}
