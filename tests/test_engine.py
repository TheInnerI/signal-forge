"""Tests for Signal Forge v2 engine layer."""

import json
import os
import tempfile
import pytest

# Set up test environment before importing engine
os.environ["OPENROUTER_API_KEY"] = "test-key-for-unit-tests"


# ─── Config Tests ────────────────────────────────────────────────────────────

class TestConfig:
    def test_loop_modes_defined(self):
        from engine.config import LOOP_MODES
        assert len(LOOP_MODES) == 8
        assert "Business Loop" in LOOP_MODES
        assert "Agent Loop" in LOOP_MODES

    def test_tone_modifiers_defined(self):
        from engine.config import TONE_MODIFIERS
        assert len(TONE_MODIFIERS) == 8
        assert "Inner I Default" in TONE_MODIFIERS

    def test_asset_types_defined(self):
        from engine.config import ASSET_TYPE_FOCUS
        assert len(ASSET_TYPE_FOCUS) == 8
        assert "Full Signal Pack" in ASSET_TYPE_FOCUS

    def test_acp_offerings_structure(self):
        from engine.config import ACP_OFFERINGS
        assert len(ACP_OFFERINGS) == 4
        for key, offering in ACP_OFFERINGS.items():
            assert "name" in offering
            assert "price" in offering
            assert offering["price"] > 0
            assert "sla_minutes" in offering
            assert "requirements" in offering
            assert "deliverable" in offering


# ─── Database Tests ──────────────────────────────────────────────────────────

class TestDatabase:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Use a temp database for each test."""
        import engine.database as db_module
        original_db_path = db_module.DB_PATH
        test_db = str(tmp_path / "test_forge.db")
        db_module.DB_PATH = test_db
        db_module.init_db()
        yield
        db_module.DB_PATH = original_db_path

    def test_init_db(self):
        from engine.database import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in c.fetchall()}
        conn.close()
        assert "decodes" in tables
        assert "assets" in tables
        assert "daily_usage" in tables
        assert "loop_laws" in tables
        assert "acp_jobs" in tables

    def test_save_and_get_decode(self):
        from engine.database import save_decode, get_decode_by_id
        save_decode(
            mode="Business Loop",
            input_text="My business keeps stalling.",
            output_dict={"raw": "test output", "mode": "Business Loop"},
            loop_law="Stall cycles repeat when the observer is inside the loop.",
            signal_score={"clarity": 80, "loop_strength": 75},
            poa_score=0.85,
            secure_verdict="clean",
        )
        result = get_decode_by_id(1)
        assert result is not None
        assert result["mode"] == "Business Loop"
        assert result["loop_law"] == "Stall cycles repeat when the observer is inside the loop."
        assert result["poa_score"] == 0.85

    def test_save_and_get_asset(self):
        from engine.database import save_asset, get_asset_by_id
        save_asset(
            input_text="Inner I is the reference point.",
            output_dict={"raw": "test forge output"},
            tone="Inner I Default",
            asset_type="Full Signal Pack",
            signal_score={"clarity": 90},
            poa_score=0.92,
        )
        result = get_asset_by_id(1)
        assert result is not None
        assert result["tone"] == "Inner I Default"
        assert result["asset_type"] == "Full Signal Pack"

    def test_rate_limiting(self):
        from engine.database import check_rate_limit, increment_daily_count
        assert check_rate_limit("free") is True
        increment_daily_count()
        increment_daily_count()
        increment_daily_count()
        assert check_rate_limit("free") is False
        assert check_rate_limit("pro") is True

    def test_loop_laws(self):
        from engine.database import save_decode, get_loop_laws
        save_decode(
            mode="Business Loop",
            input_text="Test input",
            output_dict={"raw": "test"},
            loop_law="Test law one",
        )
        save_decode(
            mode="Agent Loop",
            input_text="Test input 2",
            output_dict={"raw": "test 2"},
            loop_law="Test law two",
        )
        laws = get_loop_laws(limit=10)
        assert len(laws) >= 2
        law_texts = [l[0] for l in laws]
        assert "Test law one" in law_texts
        assert "Test law two" in law_texts

    def test_search_decodes(self):
        from engine.database import save_decode, search_decodes
        save_decode(mode="Business Loop", input_text="Revenue is declining", output_dict={"raw": "test"}, loop_law="")
        save_decode(mode="Agent Loop", input_text="Agent keeps crashing", output_dict={"raw": "test"}, loop_law="")
        results = search_decodes("Revenue")
        assert len(results) >= 1
        assert "Revenue" in results[0]["input_text"]

    def test_search_assets(self):
        from engine.database import save_asset, search_assets
        save_asset(input_text="Create a meditation app", output_dict={"raw": "test"}, tone="Calm Teacher", asset_type="Agent/Product Idea")
        results = search_assets("meditation")
        assert len(results) >= 1

    def test_get_recent_decodes(self):
        from engine.database import save_decode, get_recent_decodes
        for i in range(5):
            save_decode(mode="Business Loop", input_text=f"Test {i}", output_dict={"raw": f"output {i}"}, loop_law="")
        results = get_recent_decodes(limit=3)
        assert len(results) == 3

    def test_acp_job_tracking(self):
        from engine.database import track_acp_job, update_acp_job_status
        track_acp_job("job-123", "loop_decode", {"mode": "Business Loop", "situation": "test"})
        update_acp_job_status("job-123", "completed", {"operating_law": "test law"})

    def test_stats(self):
        from engine.database import save_decode, save_asset, get_stats
        save_decode(mode="Business Loop", input_text="Test", output_dict={"raw": "test"}, loop_law="Test law", poa_score=0.8)
        stats = get_stats()
        assert stats["total_decodes"] >= 1
        assert stats["total_laws"] >= 1


# ─── Infrastructure Tests ───────────────────────────────────────────────────

class TestInfrastructure:
    def test_poa_score_sync_returns_dict(self):
        from engine.infrastructure import poa_score_sync
        # Without a real API, should return error gracefully
        result = poa_score_sync("test text", "test context")
        assert isinstance(result, dict)
        assert "score" in result
        assert "verified" in result

    def test_secure_scan_sync_returns_dict(self):
        from engine.infrastructure import secure_scan_sync
        result = secure_scan_sync("test text")
        assert isinstance(result, dict)
        assert "safe" in result
        assert "verdict" in result

    def test_check_infrastructure_returns_tier(self):
        from engine.infrastructure import check_infrastructure_sync
        result = check_infrastructure_sync()
        assert "tier" in result
        assert result["tier"] in ("full", "degraded", "offline")
        assert "endpoints" in result


# ─── LLM Tests ───────────────────────────────────────────────────────────────

class TestLLM:
    def test_select_model_routing(self):
        from engine.llm import select_model
        from engine.config import MODEL_DEFAULT, MODEL_FAST, MODEL_QUALITY
        assert select_model("default") == MODEL_DEFAULT
        assert select_model("fast") == MODEL_FAST
        assert select_model("quality") == MODEL_QUALITY

    def test_call_llm_with_bad_key(self):
        """LLM call should fail gracefully with a bad API key."""
        from engine.llm import call_llm
        result = call_llm("You are a test.", "Say hello.")
        # Should return error string, not crash
        assert isinstance(result, str)


# ─── Loop Engine Tests ───────────────────────────────────────────────────────

class TestLoopEngine:
    def test_extract_loop_law(self):
        from engine.loop_engine import _extract_loop_law
        text = "## New Operating Law\nStall cycles need a new observer.\n## Next"
        law = _extract_loop_law(text)
        assert "Stall cycles" in law

    def test_extract_loop_law_missing(self):
        from engine.loop_engine import _extract_loop_law
        assert _extract_loop_law("No law here") == ""

    def test_extract_signal_score(self):
        from engine.loop_engine import _extract_signal_score
        text = "## Signal Score\n- Clarity: 85/100\n- Loop Strength: 70/100\n- Risk: 40/100\n- Leverage: 90/100\n- Monetization Potential: 65/100"
        scores = _extract_signal_score(text)
        assert scores is not None
        assert scores["clarity"] == 85
        assert scores["leverage"] == 90

    def test_get_loop_diagram(self):
        from engine.loop_engine import get_loop_diagram
        text = "## Surface Signal\nBusiness stalling\n## System Loop\nRevenue cycle\n## Leverage Point\nNew offer\n## New Operating Law\nShift the observer"
        diagram = get_loop_diagram(text)
        assert "LOOP DIAGRAM" in diagram
        assert "OPERATING LAW" in diagram


# ─── Signal Forge Tests ──────────────────────────────────────────────────────

class TestSignalForge:
    def test_extract_signal_score(self):
        from engine.signal_forge import _extract_signal_score
        text = "## Signal Score\n- Clarity: 92/100\n- Originality: 78/100\n- Emotional Charge: 85/100\n- Monetization Potential: 70/100\n- Inner I Alignment: 95/100"
        scores = _extract_signal_score(text)
        assert scores is not None
        assert scores["clarity"] == 92
        assert scores["inner_i_alignment"] == 95
