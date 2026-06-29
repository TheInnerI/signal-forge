"""ACP Provider Loop — Event listener, job processor, deliverable submission for Virtuals Protocol."""

import json
import logging
import time
import threading
from datetime import datetime
from typing import Optional, Callable

import httpx

from engine.config import ACP_OFFERINGS
from engine.database import track_acp_job, update_acp_job_status
from engine.loop_engine import decode_loop
from engine.signal_forge import forge_signal

logger = logging.getLogger("signal_forge.acp")

# ─── Configuration ────────────────────────────────────────────────────────────

ACP_BASE_URL = "https://acp.virtuals.io/api"  # Virtuals ACP API base
POLL_INTERVAL = 30  # seconds between job polls
WEBHOOK_TIMEOUT = 15  # seconds for webhook delivery


# ─── Job Processor ───────────────────────────────────────────────────────────

def process_job(offering_key: str, requirement: dict) -> dict:
    """Process an ACP job and return the deliverable."""
    offering = ACP_OFFERINGS.get(offering_key)
    if not offering:
        return {"error": f"Unknown offering: {offering_key}"}

    if offering_key == "loop_decode":
        result = decode_loop(
            mode=requirement.get("mode", "Business Loop"),
            situation=requirement.get("situation", ""),
            tier="pro",  # ACP jobs are paid = pro tier
            verify=True,
            stream=False,
        )
        if result.get("error"):
            return {"error": result["error"]}
        return {
            "surface_signal": _extract_section(result["result"], "Surface Signal"),
            "system_loop": _extract_section(result["result"], "System Loop"),
            "observer_position": _extract_section(result["result"], "Observer Position"),
            "leverage_point": _extract_section(result["result"], "Leverage Point"),
            "operating_law": result.get("loop_law", ""),
            "correction_protocol": _extract_section(result["result"], "Correction Protocol"),
            "signal_score": result.get("signal_score"),
            "poa_grounding": result.get("poa"),
        }

    elif offering_key == "signal_forge":
        result = forge_signal(
            input_text=requirement.get("raw_signal", ""),
            asset_type=requirement.get("asset_type", "Full Signal Pack"),
            tone=requirement.get("tone", "Inner I Default"),
            tier="pro",
            verify=True,
            stream=False,
        )
        if result.get("error"):
            return {"error": result["error"]}
        return {
            "x_post": _extract_section(result["result"], "X Post"),
            "x_thread": _extract_section(result["result"], "X Thread"),
            "wordpress_article": _extract_section(result["result"], "WordPress Article"),
            "youtube_title": _extract_section(result["result"], "YouTube Title"),
            "shorts_script": _extract_section(result["result"], "Shorts/Reels Script"),
            "offer_angle": _extract_section(result["result"], "Offer Angle"),
            "signal_score": result.get("signal_score"),
            "poa_grounding": result.get("poa"),
        }

    elif offering_key == "full_pipeline":
        # Step 1: Decode
        decode_result = decode_loop(
            mode=requirement.get("mode", "Business Loop"),
            situation=requirement.get("situation", ""),
            tier="pro",
            verify=True,
            stream=False,
        )
        if decode_result.get("error"):
            return {"error": decode_result["error"]}

        # Step 2: Forge using the operating law as the signal
        law = decode_result.get("loop_law", requirement.get("situation", ""))
        forge_result = forge_signal(
            input_text=law,
            asset_type=requirement.get("asset_type", "Full Signal Pack"),
            tone=requirement.get("tone", "Inner I Default"),
            tier="pro",
            verify=True,
            stream=False,
        )
        if forge_result.get("error"):
            return {"error": forge_result["error"]}

        return {
            "decode": {
                "surface_signal": _extract_section(decode_result["result"], "Surface Signal"),
                "system_loop": _extract_section(decode_result["result"], "System Loop"),
                "leverage_point": _extract_section(decode_result["result"], "Leverage Point"),
            },
            "forge": {
                "x_post": _extract_section(forge_result["result"], "X Post"),
                "offer_angle": _extract_section(forge_result["result"], "Offer Angle"),
            },
            "operating_law": decode_result.get("loop_law", ""),
            "signal_score": decode_result.get("signal_score"),
            "poa_grounding": decode_result.get("poa"),
        }

    elif offering_key == "agent_audit":
        # Agent audit uses loop decode with Agent mode
        combined_input = requirement.get("agent_description", "")
        if requirement.get("tool_call_log"):
            combined_input += f"\n\nTool Call Log:\n{requirement['tool_call_log']}"
        if requirement.get("error_patterns"):
            combined_input += f"\n\nError Patterns:\n{requirement['error_patterns']}"
        if requirement.get("task_history"):
            combined_input += f"\n\nTask History:\n{requirement['task_history']}"

        result = decode_loop(
            mode="Agent Loop",
            situation=combined_input,
            tier="pro",
            verify=True,
            stream=False,
        )
        if result.get("error"):
            return {"error": result["error"]}
        return {
            "surface_signal": _extract_section(result["result"], "Surface Signal"),
            "system_loop": _extract_section(result["result"], "System Loop"),
            "failure_mode": _extract_section(result["result"], "Failure Mode"),
            "correction_protocol": _extract_section(result["result"], "Correction Protocol"),
            "operating_law": result.get("loop_law", ""),
            "signal_score": result.get("signal_score"),
            "poa_grounding": result.get("poa"),
        }

    return {"error": f"No processor for offering: {offering_key}"}


# ─── Webhook Delivery ────────────────────────────────────────────────────────

def deliver_webhook(url: str, payload: dict, secret: Optional[str] = None):
    """POST deliverable to a webhook URL."""
    headers = {"Content-Type": "application/json"}
    if secret:
        import hmac, hashlib
        body = json.dumps(payload)
        signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Signal-Forge-Signature"] = f"sha256={signature}"

    try:
        with httpx.Client(timeout=WEBHOOK_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=headers)
            logger.info(f"Webhook delivered to {url}: HTTP {resp.status_code}")
            return {"delivered": True, "status_code": resp.status_code}
    except Exception as e:
        logger.error(f"Webhook delivery failed: {e}")
        return {"delivered": False, "error": str(e)}


# ─── ACP Event Listener ──────────────────────────────────────────────────────

class ACPProviderLoop:
    """Background loop that polls for ACP jobs and processes them."""

    def __init__(self, agent_id: str, api_key: str, poll_interval: int = POLL_INTERVAL):
        self.agent_id = agent_id
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.running = False
        self._thread = None
        self.job_count = 0
        self.error_count = 0

    def start(self):
        """Start the ACP provider loop in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"ACP provider loop started (agent={self.agent_id}, interval={self.poll_interval}s)")

    def stop(self):
        """Stop the ACP provider loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ACP provider loop stopped")

    def get_status(self) -> dict:
        """Get current status of the provider loop."""
        return {
            "running": self.running,
            "agent_id": self.agent_id,
            "jobs_processed": self.job_count,
            "errors": self.error_count,
            "offerings": list(ACP_OFFERINGS.keys()),
        }

    def _loop(self):
        """Main loop — poll for jobs, process, submit."""
        while self.running:
            try:
                jobs = self._fetch_jobs()
                for job in jobs:
                    self._process_and_submit(job)
            except Exception as e:
                logger.error(f"ACP loop error: {e}")
                self.error_count += 1
            time.sleep(self.poll_interval)

    def _fetch_jobs(self) -> list[dict]:
        """Poll ACP for pending jobs for our agent."""
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{ACP_BASE_URL}/agents/{self.agent_id}/jobs",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("jobs", [])
                logger.warning(f"ACP job fetch: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"ACP job fetch failed: {e}")
        return []

    def _process_and_submit(self, job: dict):
        """Process a single ACP job and submit the deliverable."""
        job_id = job.get("job_id", job.get("id", "unknown"))
        offering_key = job.get("offering_key", job.get("offering", ""))
        requirement = job.get("requirement", {})
        webhook_url = job.get("webhook_url")

        logger.info(f"Processing ACP job {job_id} (offering={offering_key})")

        # Track in database
        track_acp_job(job_id, offering_key, requirement)

        try:
            # Process
            deliverable = process_job(offering_key, requirement)

            if "error" in deliverable:
                logger.error(f"Job {job_id} failed: {deliverable['error']}")
                update_acp_job_status(job_id, "failed", deliverable)
                self.error_count += 1
                return

            # Submit to ACP
            self._submit_deliverable(job_id, deliverable)

            # Update database
            update_acp_job_status(job_id, "completed", deliverable)

            # Deliver webhook if configured
            if webhook_url:
                deliver_webhook(webhook_url, {"job_id": job_id, "deliverable": deliverable})

            self.job_count += 1
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} exception: {e}")
            update_acp_job_status(job_id, "error", {"error": str(e)})
            self.error_count += 1

    def _submit_deliverable(self, job_id: str, deliverable: dict):
        """Submit a completed deliverable to ACP."""
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{ACP_BASE_URL}/jobs/{job_id}/submit",
                    json={"deliverable": deliverable},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code not in (200, 201):
                    logger.warning(f"ACP submit for job {job_id}: HTTP {resp.status_code}")
                else:
                    logger.info(f"ACP deliverable submitted for job {job_id}")
        except Exception as e:
            logger.error(f"ACP submit failed for job {job_id}: {e}")


# ─── Helper ──────────────────────────────────────────────────────────────────

def _extract_section(text: str, heading: str) -> str:
    """Extract content under a markdown heading."""
    if heading not in text:
        return ""
    try:
        parts = text.split(f"## {heading}")
        if len(parts) < 2:
            return ""
        content = parts[1]
        next_heading = content.find("\n## ")
        if next_heading != -1:
            content = content[:next_heading]
        return content.strip()
    except (IndexError, ValueError):
        return ""
