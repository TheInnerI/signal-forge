"""Database layer for Signal Forge v2."""

import json
import sqlite3
from datetime import date, datetime
from typing import Optional

from .config import DB_PATH, OUTPUTS_DIR


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all database tables."""
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS decodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            input_text TEXT NOT NULL,
            output_json TEXT NOT NULL,
            loop_law TEXT,
            signal_score_json TEXT,
            poa_score REAL,
            secure_scan_verdict TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_text TEXT NOT NULL,
            output_json TEXT NOT NULL,
            tone TEXT,
            asset_type TEXT,
            signal_score_json TEXT,
            poa_score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            date TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS loop_laws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            law TEXT UNIQUE,
            category TEXT,
            source_input TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS acp_jobs (
            job_id TEXT PRIMARY KEY,
            offering_name TEXT,
            status TEXT DEFAULT 'open',
            requirement_json TEXT,
            deliverable_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ─── Usage Tracking ──────────────────────────────────────────────────────────

def get_daily_count() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT count FROM daily_usage WHERE date=?", (str(date.today()),))
    row = c.fetchone()
    conn.close()
    return row["count"] if row else 0


def increment_daily_count():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO daily_usage (date, count) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET count = count + 1
    """, (str(date.today()),))
    conn.commit()
    conn.close()


def check_rate_limit(tier: str = "free") -> bool:
    """Returns True if under rate limit (allowed), False if over."""
    if tier == "pro":
        return True  # Unlimited
    return get_daily_count() < 3


# ─── Decode Storage ─────────────────────────────────────────────────────────

def save_decode(mode: str, input_text: str, output_dict: dict, loop_law: str = "",
                signal_score: Optional[dict] = None, poa_score: Optional[float] = None,
                secure_verdict: Optional[str] = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO decodes (mode, input_text, output_json, loop_law, signal_score_json, poa_score, secure_scan_verdict)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        mode, input_text, json.dumps(output_dict), loop_law,
        json.dumps(signal_score) if signal_score else None,
        poa_score,
        secure_verdict,
    ))
    if loop_law:
        c.execute("""
            INSERT OR IGNORE INTO loop_laws (law, category, source_input) VALUES (?, ?, ?)
        """, (loop_law, mode, input_text[:200]))
    conn.commit()
    conn.close()


def save_asset(input_text: str, output_dict: dict, tone: str = "",
               asset_type: str = "", signal_score: Optional[dict] = None,
               poa_score: Optional[float] = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO assets (input_text, output_json, tone, asset_type, signal_score_json, poa_score)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        input_text, json.dumps(output_dict), tone, asset_type,
        json.dumps(signal_score) if signal_score else None,
        poa_score,
    ))
    conn.commit()
    conn.close()


# ─── Loop Law Library ────────────────────────────────────────────────────────

def get_loop_laws(limit: int = 50) -> list[tuple[str, str]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT law, category FROM loop_laws ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [(row["law"], row["category"]) for row in rows]


# ─── Stats ───────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Get aggregate stats for the dashboard."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as cnt FROM decodes")
    decode_count = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM assets")
    asset_count = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM loop_laws")
    law_count = c.fetchone()["cnt"]

    c.execute("SELECT AVG(poa_score) as avg FROM decodes WHERE poa_score IS NOT NULL")
    row = c.fetchone()
    avg_poa = row["avg"] if row["avg"] else 0.0

    c.execute("""
        SELECT mode, COUNT(*) as cnt FROM decodes
        GROUP BY mode ORDER BY cnt DESC
    """)
    mode_counts = [(row["mode"], row["cnt"]) for row in c.fetchall()]

    c.execute("""
        SELECT date, count FROM daily_usage
        ORDER BY date DESC LIMIT 7
    """)
    recent_usage = [(row["date"], row["count"]) for row in c.fetchall()]

    conn.close()

    return {
        "total_decodes": decode_count,
        "total_assets": asset_count,
        "total_laws": law_count,
        "avg_poa_score": round(avg_poa, 1),
        "mode_distribution": mode_counts,
        "recent_usage": recent_usage,
    }


# ─── ACP Job Tracking ────────────────────────────────────────────────────────

def track_acp_job(job_id: str, offering_name: str, requirement: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO acp_jobs (job_id, offering_name, requirement_json, status)
        VALUES (?, ?, ?, 'open')
    """, (job_id, offering_name, json.dumps(requirement)))
    conn.commit()
    conn.close()


def update_acp_job_status(job_id: str, status: str, deliverable: Optional[dict] = None):
    conn = get_connection()
    c = conn.cursor()
    completed_at = datetime.utcnow().isoformat() if status in ("completed", "submitted") else None
    c.execute("""
        UPDATE acp_jobs SET status=?, deliverable_json=?, completed_at=?
        WHERE job_id=?
    """, (status, json.dumps(deliverable) if deliverable else None, completed_at, job_id))
    conn.commit()
    conn.close()


# ─── History & Search ─────────────────────────────────────────────────────────

def get_recent_decodes(limit: int = 20, offset: int = 0) -> list[dict]:
    """Get recent loop decodes with pagination."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, mode, input_text, loop_law, signal_score_json, poa_score,
               secure_scan_verdict, created_at
        FROM decodes ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "mode": row["mode"],
            "input_text": row["input_text"][:200] + ("..." if len(row["input_text"]) > 200 else ""),
            "loop_law": row["loop_law"],
            "signal_score": json.loads(row["signal_score_json"]) if row["signal_score_json"] else None,
            "poa_score": row["poa_score"],
            "secure_verdict": row["secure_scan_verdict"],
            "created_at": row["created_at"],
        })
    return results


def get_recent_assets(limit: int = 20, offset: int = 0) -> list[dict]:
    """Get recent forged assets with pagination."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, input_text, tone, asset_type, signal_score_json, poa_score, created_at
        FROM assets ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "input_text": row["input_text"][:200] + ("..." if len(row["input_text"]) > 200 else ""),
            "tone": row["tone"],
            "asset_type": row["asset_type"],
            "signal_score": json.loads(row["signal_score_json"]) if row["signal_score_json"] else None,
            "poa_score": row["poa_score"],
            "created_at": row["created_at"],
        })
    return results


def get_decode_by_id(decode_id: int) -> Optional[dict]:
    """Get a full decode record by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM decodes WHERE id=?", (decode_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "mode": row["mode"],
        "input_text": row["input_text"],
        "output_json": row["output_json"],
        "loop_law": row["loop_law"],
        "signal_score": json.loads(row["signal_score_json"]) if row["signal_score_json"] else None,
        "poa_score": row["poa_score"],
        "secure_verdict": row["secure_scan_verdict"],
        "created_at": row["created_at"],
    }


def get_asset_by_id(asset_id: int) -> Optional[dict]:
    """Get a full asset record by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM assets WHERE id=?", (asset_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "input_text": row["input_text"],
        "output_json": row["output_json"],
        "tone": row["tone"],
        "asset_type": row["asset_type"],
        "signal_score": json.loads(row["signal_score_json"]) if row["signal_score_json"] else None,
        "poa_score": row["poa_score"],
        "created_at": row["created_at"],
    }


def search_decodes(query: str, limit: int = 20) -> list[dict]:
    """Search decodes by keyword in input text or output."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, mode, input_text, loop_law, created_at
        FROM decodes
        WHERE input_text LIKE ? OR output_json LIKE ? OR loop_law LIKE ?
        ORDER BY created_at DESC LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "mode": row["mode"],
            "input_text": row["input_text"][:200] + ("..." if len(row["input_text"]) > 200 else ""),
            "loop_law": row["loop_law"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def search_assets(query: str, limit: int = 20) -> list[dict]:
    """Search assets by keyword in input text or output."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, input_text, tone, asset_type, created_at
        FROM assets
        WHERE input_text LIKE ? OR output_json LIKE ?
        ORDER BY created_at DESC LIMIT ?
    """, (f"%{query}%", f"%{query}%", limit))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "input_text": row["input_text"][:200] + ("..." if len(row["input_text"]) > 200 else ""),
            "tone": row["tone"],
            "asset_type": row["asset_type"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
