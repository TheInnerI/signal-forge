"""Configuration for Signal Forge v2."""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── LLM Configuration ──────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL_DEFAULT = "openrouter/owl-alpha"
MODEL_FAST = "openai/gpt-4o-mini"  # Cheaper model for simple tasks
MODEL_QUALITY = "anthropic/claude-sonnet-4"  # Best quality for deep decodes

# ─── Infrastructure ──────────────────────────────────────────────────────────

POA_BASE_URL = os.environ.get("POA_BASE_URL", "https://proofofawareness.org")
SECURE_GATEWAY_URL = os.environ.get("SECURE_GATEWAY_URL", "https://secure.innerinetcompany.com")

# ─── Database ────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "forge.db")
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs", "saved_decodes")

# ─── Rate Limits ────────────────────────────────────────────────────────────

FREE_TIER_DAILY_LIMIT = 3
PRO_TIER_DAILY_LIMIT = -1  # Unlimited

# ─── ACP Marketplace ─────────────────────────────────────────────────────────

ACP_OFFERINGS = {
    "loop_decode": {
        "name": "Loop Decode",
        "description": "Decode any feedback loop — business, personal, agent, financial, creative, or spiritual. Reveals hidden patterns, leverage points, and extracts a reusable operating law.",
        "price": 0.50,
        "sla_minutes": 30,
        "requirements": {"type": "object", "properties": {"mode": {"type": "string", "enum": ["Personal Loop", "Business Loop", "Agent Loop", "Money Loop", "Creative Loop", "Spiritual Loop", "Content Loop", "Code/System Loop"]}, "situation": {"type": "string", "minLength": 10}}, "required": ["mode", "situation"]},
        "deliverable": {"type": "object", "properties": {"surface_signal": {"type": "string"}, "system_loop": {"type": "string"}, "observer_position": {"type": "string"}, "leverage_point": {"type": "string"}, "correction_protocol": {"type": "string"}, "operating_law": {"type": "string"}, "signal_score": {"type": "object", "properties": {"clarity": {"type": "integer"}, "loop_strength": {"type": "integer"}, "risk": {"type": "integer"}, "leverage": {"type": "integer"}, "monetization": {"type": "integer"}}}, "poa_grounding": {"type": "object", "properties": {"score": {"type": "number"}, "verified": {"type": "boolean"}}}}, "required": ["surface_signal", "system_loop", "observer_position", "leverage_point", "operating_law", "signal_score"]},
    },
    "signal_forge": {
        "name": "Signal Forge Pack",
        "description": "Transform one idea into 10 monetizable assets: X posts, threads, WordPress articles, YouTube packs, Shorts scripts, offer angles, and more. With PoA-verified grounding.",
        "price": 1.00,
        "sla_minutes": 45,
        "requirements": {"type": "object", "properties": {"raw_signal": {"type": "string", "minLength": 5}, "asset_type": {"type": "string", "enum": ["Full Signal Pack", "Music Release", "WordPress Article", "X Thread", "Business Offer", "YouTube Pack", "Spiritual Transmission", "Agent/Product Idea"]}, "tone": {"type": "string", "enum": ["Inner I Default", "White Flame", "Trap Gospel", "Jesus-Only", "Business Sharp", "Viral X", "Calm Teacher", "Cosmic Outlaw"]}}, "required": ["raw_signal", "asset_type"]},
        "deliverable": {"type": "object", "properties": {"x_post": {"type": "string"}, "x_thread": {"type": "string"}, "wordpress_article": {"type": "string"}, "youtube_title": {"type": "string"}, "shorts_script": {"type": "string"}, "offer_angle": {"type": "string"}, "signal_score": {"type": "object"}, "poa_grounding": {"type": "object"}}, "required": ["x_post", "offer_angle", "signal_score"]},
    },
    "full_pipeline": {
        "name": "Full Decode + Forge Pipeline",
        "description": "The complete Signal Forge pipeline: Decode the loop → Extract the operating law → Forge 10 assets from the insight. Best value — two engines, one output.",
        "price": 2.00,
        "sla_minutes": 60,
        "requirements": {"type": "object", "properties": {"mode": {"type": "string"}, "situation": {"type": "string", "minLength": 10}, "asset_type": {"type": "string"}, "tone": {"type": "string"}}, "required": ["mode", "situation"]},
        "deliverable": {"type": "object", "properties": {"decode": {"type": "object"}, "forge": {"type": "object"}, "operating_law": {"type": "string"}, "signal_score": {"type": "object"}, "poa_grounding": {"type": "object"}}, "required": ["decode", "forge", "operating_law", "signal_score"]},
    },
    "agent_audit": {
        "name": "Agent Behavior Audit",
        "description": "Decode an AI agent's behavior loops — error cycles, tool misuse patterns, decision-making flaws. Extracts operating laws and provides a correction protocol with signal scores.",
        "price": 3.00,
        "sla_minutes": 120,
        "requirements": {"type": "object", "properties": {"agent_description": {"type": "string"}, "tool_call_log": {"type": "string"}, "error_patterns": {"type": "string"}, "task_history": {"type": "string"}}, "required": ["agent_description"]},
        "deliverable": {"type": "object", "properties": {"surface_signal": {"type": "string"}, "system_loop": {"type": "string"}, "failure_mode": {"type": "string"}, "correction_protocol": {"type": "string"}, "operating_law": {"type": "string"}, "signal_score": {"type": "object"}, "poa_grounding": {"type": "object"}}, "required": ["surface_signal", "system_loop", "failure_mode", "correction_protocol", "operating_law", "signal_score"]},
    },
}

# ─── Tone Modifiers ────────────────────────────────────���─────────────────────

TONE_MODIFIERS = {
    "Inner I Default": "Use standard Inner I voice — aware, grounded, builder-focused.",
    "White Flame": "Intense, prophetic, burning away illusion. Short sentences. High heat.",
    "Trap Gospel": "Street language meets spiritual truth. Hard beats, soft heart.",
    "Jesus-Only": "Christ-centered, scripture-grounded, no secular framing.",
    "Business Sharp": "Direct, ROI-focused, no fluff. Speak to founders and operators.",
    "Viral X": "Designed for maximum engagement. Hooks, controversy, shareability.",
    "Calm Teacher": "Gentle, explanatory, patient. Like a wise mentor.",
    "Cosmic Outlaw": "Reality-questioning, paradigm-breaking, slightly dangerous.",
}

# ─── Loop Mode Contexts ─────────────────────────────────────────────────────

LOOP_MODES = {
    "Personal Loop": "Focus on personal patterns, habits, emotional cycles, and life decisions.",
    "Business Loop": "Focus on business workflows, revenue patterns, team dynamics, and market positioning.",
    "Agent Loop": "Focus on AI agent behavior, tool usage patterns, error loops, and automation failures.",
    "Money Loop": "Focus on financial behavior, spending patterns, income blocks, and wealth psychology.",
    "Creative Loop": "Focus on creative blocks, artistic patterns, content cycles, and inspiration flows.",
    "Spiritual Loop": "Focus on spiritual patterns, faith cycles, prayer life, and relationship with God.",
    "Content Loop": "Focus on content strategy, audience engagement, platform algorithms, and viral patterns.",
    "Code/System Loop": "Focus on software bugs, system architecture, deployment failures, and technical debt.",
}

ASSET_TYPE_FOCUS = {
    "Music Release": "Focus on music release assets: titles, descriptions, tags, promo posts, cover prompts.",
    "WordPress Article": "Focus on a full WordPress article with SEO title, excerpt, tags, and body.",
    "X Thread": "Focus on a viral X thread with strong hooks and engagement.",
    "Business Offer": "Focus on business offer: landing copy, email sequence, pricing angle.",
    "YouTube Pack": "Focus on YouTube: title, description, tags, thumbnail prompt, pinned comment.",
    "Spiritual Transmission": "Focus on spiritual content: devotional, reflection, prayer, teaching.",
    "Agent/Product Idea": "Focus on AI agent or product concept: spec, positioning, launch plan.",
    "Full Signal Pack": "Generate ALL 10 assets. Full pack.",
}
