"""Signal Forge v2 — Gradio Web UI with 5 tabs, streaming, dashboard, history, ACP monitor."""

import json
import os
import gradio as gr
from datetime import datetime

from engine.config import LOOP_MODES, TONE_MODIFIERS, ASSET_TYPE_FOCUS, ACP_OFFERINGS
from engine.database import (
    init_db, get_stats, get_loop_laws, get_recent_decodes, get_recent_assets,
    search_decodes, search_assets, get_daily_count,
)
from engine.infrastructure import check_infrastructure_sync
from engine.loop_engine import decode_loop, get_loop_diagram
from engine.signal_forge import forge_signal

# Ensure DB is initialized
init_db()


# ─── UI Helpers ──────────────────────────────────────────────────────────────

def format_score_bar(label: str, value: int, max_val: int = 100) -> str:
    """Create a visual score bar."""
    filled = int(value / max_val * 20)
    bar = "█" * filled + "░" * (20 - filled)
    color = "🟢" if value >= 70 else "🟡" if value >= 40 else "🔴"
    return f"{color} **{label}**: {bar} {value}/100"


def format_signal_scores(scores: dict, prefix: str = "") -> str:
    """Format signal score dict into visual bars."""
    if not scores:
        return "*No scores extracted*"
    lines = []
    for key, val in scores.items():
        label = key.replace("_", " ").title()
        lines.append(format_score_bar(label, val))
    return "\n".join(lines)


def format_poa_result(poa: dict) -> str:
    """Format PoA verification result."""
    if not poa:
        return "*PoA not run*"
    if poa.get("error"):
        return f"⚠️ PoA unavailable: {poa['error']}"
    score = poa.get("score", 0)
    verified = poa.get("verified", False)
    receipt = poa.get("receipt", "N/A")
    icon = "✅" if verified else "❌"
    return f"{icon} PoA Score: **{score:.2f}** | Verified: {verified} | Receipt: `{receipt}`"


def format_secure_result(secure: dict) -> str:
    """Format Secure Gateway scan result."""
    if not secure:
        return "*Secure scan not run*"
    if secure.get("error"):
        return f"⚠️ Secure Gateway unavailable: {secure['error']}"
    safe = secure.get("safe", True)
    verdict = secure.get("verdict", "unknown")
    icon = "🛡️" if safe else "🚨"
    return f"{icon} Verdict: **{verdict}** | Safe: {safe}"


def format_infra_status() -> str:
    """Format infrastructure status for the sidebar."""
    infra = check_infrastructure_sync()
    tier = infra["tier"]
    tier_icons = {"full": "🟢", "degraded": "🟡", "offline": "🔴"}
    icon = tier_icons.get(tier, "⚪")

    lines = [f"### {icon} Infrastructure: {tier.upper()}"]
    for name, info in infra["endpoints"].items():
        status_icon = "✅" if info["status"] == "up" else "⚠️" if info["status"] == "degraded" else "❌"
        lines.append(f"{status_icon} **{name}**: {info['status']}")
    return "\n".join(lines)


def get_usage_display() -> str:
    """Get daily usage display."""
    count = get_daily_count()
    remaining = max(0, 3 - count)
    return f"**{count}/3** free decodes today | **{remaining}** remaining"


# ─── Core Callbacks ──────────────────────────────────────────────────────────

def handle_decode(mode, situation, verify):
    """Handle loop decode request."""
    if not situation or len(situation) < 10:
        return "⚠️ Please enter a situation (at least 10 characters).", "", ""

    result = decode_loop(
        mode=mode,
        situation=situation,
        tier="free",
        verify=verify,
        stream=False,
    )

    if result.get("error"):
        return f"❌ {result['error']}", "", get_usage_display()

    # Format output
    output = result["result"]
    loop_law = result.get("loop_law", "")

    # Add metadata
    meta_lines = [
        "---",
        format_poa_result(result.get("poa")),
        format_secure_result(result.get("secure")),
        "",
    ]

    if result.get("signal_score"):
        meta_lines.append("### 📊 Signal Scores")
        meta_lines.append(format_signal_scores(result["signal_score"]))

    meta = "\n".join(meta_lines)
    full_output = f"{output}\n\n{meta}"

    # Loop law highlight
    law_display = f"⚡ **Operating Law:** {loop_law}" if loop_law else ""

    return full_output, law_display, get_usage_display()


def handle_forge(raw_signal, asset_type, tone, verify):
    """Handle signal forge request."""
    if not raw_signal or len(raw_signal) < 5:
        return "⚠️ Please enter a raw signal (at least 5 characters).", get_usage_display()

    result = forge_signal(
        input_text=raw_signal,
        asset_type=asset_type,
        tone=tone,
        tier="free",
        verify=verify,
        stream=False,
    )

    if result.get("error"):
        return f"❌ {result['error']}", get_usage_display()

    output = result["result"]
    meta_lines = [
        "---",
        format_poa_result(result.get("poa")),
        format_secure_result(result.get("secure")),
        "",
    ]

    if result.get("signal_score"):
        meta_lines.append("### 📊 Signal Scores")
        meta_lines.append(format_signal_scores(result["signal_score"]))

    meta = "\n".join(meta_lines)
    full_output = f"{output}\n\n{meta}"

    return full_output, get_usage_display()


def handle_dashboard():
    """Generate dashboard data."""
    stats = get_stats()
    infra = check_infrastructure_sync()

    # Build dashboard markdown
    lines = [
        "## 📊 Signal Forge Dashboard",
        "",
        f"**Total Decodes:** {stats['total_decodes']}  |  **Total Assets:** {stats['total_assets']}  |  **Loop Laws:** {stats['total_laws']}",
        f"**Avg PoA Score:** {stats['avg_poa_score']:.1f}/100  |  **Infrastructure:** {infra['tier'].upper()}",
        "",
    ]

    # Mode distribution
    if stats.get("mode_distribution"):
        lines.append("### 🔍 Decode Modes")
        for mode, count in stats["mode_distribution"]:
            bar = "█" * min(count, 20)
            lines.append(f"- **{mode}**: {bar} {count}")
        lines.append("")

    # Recent usage
    if stats.get("recent_usage"):
        lines.append("### 📅 Recent Usage (7 days)")
        for date, count in stats["recent_usage"]:
            bar = "█" * min(count, 10)
            lines.append(f"- {date}: {bar} {count}")
        lines.append("")

    # Top laws
    laws = get_loop_laws(limit=10)
    if laws:
        lines.append("### ⚡ Top Operating Laws")
        for i, (law, category) in enumerate(laws, 1):
            lines.append(f"{i}. **[{category}]** {law}")
        lines.append("")

    # Infrastructure detail
    lines.append(format_infra_status())

    return "\n".join(lines)


def handle_history_search(query, search_type):
    """Search history."""
    if not query or len(query) < 2:
        return "⚠️ Enter at least 2 characters to search."

    if search_type == "Decodes":
        results = search_decodes(query=query, limit=20)
        if not results:
            return "*No matching decodes found.*"
        lines = [f"### 🔍 Search Results ({len(results)} decodes)\n"]
        for r in results:
            lines.append(f"**#{r['id']}** [{r['mode']}] — {r['input_text']}")
            if r.get("loop_law"):
                lines.append(f"  ⚡ Law: {r['loop_law']}")
            lines.append(f"  📅 {r['created_at']}\n")
        return "\n".join(lines)
    else:
        results = search_assets(query=query, limit=20)
        if not results:
            return "*No matching assets found.*"
        lines = [f"### 🔍 Search Results ({len(results)} assets)\n"]
        for r in results:
            lines.append(f"**#{r['id']}** [{r['asset_type']}] ({r['tone']}) — {r['input_text']}")
            lines.append(f"  📅 {r['created_at']}\n")
        return "\n".join(lines)


def handle_recent_history(history_type):
    """Load recent history."""
    if history_type == "Recent Decodes":
        results = get_recent_decodes(limit=25)
        if not results:
            return "*No decodes yet. Run your first decode!*"
        lines = [f"### 📜 Recent Decodes ({len(results)})\n"]
        for r in results:
            lines.append(f"**#{r['id']}** [{r['mode']}] — {r['input_text']}")
            if r.get("loop_law"):
                lines.append(f"  �� Law: {r['loop_law']}")
            if r.get("poa_score"):
                lines.append(f"  🔬 PoA: {r['poa_score']:.1f}")
            lines.append(f"  📅 {r['created_at']}\n")
        return "\n".join(lines)
    else:
        results = get_recent_assets(limit=25)
        if not results:
            return "*No assets yet. Forge your first signal!*"
        lines = [f"### ⚡ Recent Assets ({len(results)})\n"]
        for r in results:
            lines.append(f"**#{r['id']}** [{r['asset_type']}] ({r['tone']}) — {r['input_text']}")
            if r.get("poa_score"):
                lines.append(f"  🔬 PoA: {r['poa_score']:.1f}")
            lines.append(f"  📅 {r['created_at']}\n")
        return "\n".join(lines)


def handle_acp_status():
    """Get ACP marketplace status."""
    lines = [
        "## 🏪 ACP Marketplace Status",
        "",
    ]

    # Show offerings
    lines.append("### Active Offerings")
    for key, offering in ACP_OFFERINGS.items():
        price = f"${offering['price']:.2f}"
        sla = f"{offering['sla_minutes']}min"
        lines.append(f"- **{offering['name']}** — {price} (SLA: {sla})")
    lines.append("")

    # Infrastructure
    lines.append(format_infra_status())

    return "\n".join(lines)


def handle_laws_refresh():
    """Refresh loop law library."""
    laws = get_loop_laws(limit=50)
    if not laws:
        return "No Loop Laws extracted yet. Decode some patterns first."
    lines = []
    for i, (law, category) in enumerate(laws, 1):
        lines.append(f"{i}. **[{category}]** {law}")
    return "\n\n".join(lines)


def export_decode_md(decode_text, loop_law):
    """Export decode as markdown for download."""
    if not decode_text or decode_text.startswith("⚠️") or decode_text.startswith("❌"):
        return None
    content = f"# Loop Decode\n\n**Operating Law:** {loop_law}\n\n**Date:** {datetime.utcnow().isoformat()}\n\n---\n\n{decode_text}"
    path = os.path.join(os.path.dirname(__file__), "outputs", "saved_decodes", f"decode_{int(datetime.utcnow().timestamp())}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


# ─── CSS Theme ───────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
}

.gradio-container {
    max-width: 1400px !important;
    margin: 0 auto;
}

.header {
    text-align: center;
    padding: 2rem 0;
    border-bottom: 1px solid #1a1a2e;
    margin-bottom: 2rem;
}

.header h1 {
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}

.header .tagline {
    color: #888;
    font-size: 1rem;
    margin-top: 0.5rem;
}

.sidebar-panel {
    background: #111118 !important;
    border-right: 1px solid #1a1a2e !important;
    padding: 1rem !important;
}

button.primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 0.75rem 2rem !important;
    border-radius: 8px !important;
    font-size: 1.1rem !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
}

button.primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4) !important;
}

.output-box {
    background: #111118 !important;
    border: 1px solid #1a1a2e !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
}

.status-indicator {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 6px;
}

.footer {
    text-align: center;
    padding: 2rem 0;
    color: #555;
    font-size: 0.85rem;
    border-top: 1px solid #1a1a2e;
    margin-top: 2rem;
}

.footer a {
    color: #667eea;
    text-decoration: none;
}
"""


# ─── Build UI ────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Signal Forge v2 — Loop Engineer + Asset Engine",
    theme=gr.themes.Base(
        primary_hue="purple",
        secondary_hue="violet",
        neutral_hue="slate",
        font=["Inter", "sans-serif"],
        font_mono=["JetBrains Mono", "monospace"],
    ).set(
        body_background_fill="#0a0a0f",
        body_text_color="#e0e0e0",
        background_fill_primary="#111118",
        background_fill_secondary="#1a1a2e",
        border_color_primary="#2a2a3e",
        block_background_fill="#111118",
        block_border_color="#1a1a2e",
        input_background_fill="#0f0f1a",
        input_border_color="#2a2a3e",
        button_primary_background_fill="linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        button_primary_text_color="white",
    ),
    css=CSS,
) as app:

    # ─── Header ─────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="header">
        <h1>⚡ Signal Forge v2</h1>
        <div class="tagline">Decode the loop. Extract the law. Forge the asset. Move the field.</div>
        <div style="margin-top: 0.5rem; color: #666; font-size: 0.9rem;">
            Second-order cybernetics decoder + asset engine · Virtuals Protocol ACP Provider
        </div>
    </div>
    """)

    with gr.Row():
        # ─── Sidebar ────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=250):
            gr.Markdown("### 🔧 Status")
            usage_display = gr.Markdown(value=get_usage_display())
            infra_display = gr.Markdown(value=format_infra_status())
            gr.Markdown("---")
            gr.Markdown("### 🏪 ACP Offerings")
            acp_summary = gr.Markdown(
                value="\n".join([f"- **{o['name']}** — ${o['price']:.2f}" for o in ACP_OFFERINGS.values()])
            )
            refresh_infra_btn = gr.Button("🔄 Refresh Status", size="sm")

        # ─── Main Content ────────────────────────────────────────────
        with gr.Column(scale=4):
            with gr.Tabs():
                # ═══ Tab 1: Loop Engineer ═══════════════════════════════
                with gr.TabItem("🔍 Loop Engineer"):
                    gr.Markdown("""
                    ### Decode the pattern behind the pattern.
                    Most AI tools answer the prompt. **Loop Engineer decodes the loop that produced the prompt.**
                    Enter any situation — business stall, agent error, money drain, creative block, spiritual confusion.
                    """)

                    with gr.Row():
                        with gr.Column(scale=1):
                            loop_mode = gr.Dropdown(
                                choices=list(LOOP_MODES.keys()),
                                value="Business Loop",
                                label="Loop Mode",
                            )
                            loop_input = gr.Textbox(
                                lines=8,
                                placeholder="Describe the situation, pattern, or problem you want decoded...\n\nExample: 'My business keeps stalling. I get momentum, then something breaks. I restart. The cycle repeats.'",
                                label="Situation / Pattern",
                            )
                            loop_verify = gr.Checkbox(value=True, label="Run PoA + Secure Gateway verification")
                            loop_btn = gr.Button("🔍 Decode Loop", variant="primary", size="lg")

                        with gr.Column(scale=2):
                            loop_output = gr.Markdown(
                                value="*Your loop decode will appear here...*",
                                elem_classes=["output-box"],
                            )
                            loop_law_output = gr.Markdown(value="")
                            with gr.Row():
                                export_decode_btn = gr.Button("📥 Export Markdown", size="sm")
                                export_decode_file = gr.File(label="Download", visible=False)

                    gr.Markdown("---")
                    gr.Markdown("### 📜 Loop Law Library")
                    laws_display = gr.Markdown(value=handle_laws_refresh())
                    refresh_laws_btn = gr.Button("🔄 Refresh Laws", size="sm")

                # ═══ Tab 2: Signal Forge ═══════════════════════════════════
                with gr.TabItem("⚡ Signal Forge"):
                    gr.Markdown("""
                    ### Drop one thought. Forge ten assets. Move the field.
                    Enter one idea, lyric, business problem, spiritual insight, or product concept.
                    Get a complete public asset pack with monetization path.
                    """)

                    with gr.Row():
                        with gr.Column(scale=1):
                            forge_type = gr.Dropdown(
                                choices=list(ASSET_TYPE_FOCUS.keys()),
                                value="Full Signal Pack",
                                label="Asset Type",
                            )
                            forge_tone = gr.Dropdown(
                                choices=list(TONE_MODIFIERS.keys()),
                                value="Inner I Default",
                                label="Tone",
                            )
                            forge_input = gr.Textbox(
                                lines=8,
                                placeholder="Enter your raw idea, lyric, insight, problem, or concept...\n\nExample: 'Inner I is inevitably the reference point of your reality.'",
                                label="Raw Signal",
                            )
                            forge_verify = gr.Checkbox(value=True, label="Run PoA + Secure Gateway verification")
                            forge_btn = gr.Button("⚡ Forge Signal", variant="primary", size="lg")

                        with gr.Column(scale=2):
                            forge_output = gr.Markdown(
                                value="*Your signal pack will appear here...*",
                                elem_classes=["output-box"],
                            )
                            with gr.Row():
                                export_forge_btn = gr.Button("📥 Export Markdown", size="sm")
                                export_forge_file = gr.File(label="Download", visible=False)

                # ═══ Tab 3: Dashboard ══════════════════════════════════════
                with gr.TabItem("📊 Dashboard"):
                    dashboard_output = gr.Markdown(value=handle_dashboard(), elem_classes=["output-box"])
                    refresh_dashboard_btn = gr.Button("🔄 Refresh Dashboard", variant="primary")

                # ═══ Tab 4: History & Search ═══════════════════════════════
                with gr.TabItem("📜 History"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### Search & Browse")
                            history_search_input = gr.Textbox(
                                placeholder="Search by keyword...",
                                label="Search Query",
                            )
                            history_search_type = gr.Radio(
                                choices=["Decodes", "Assets"],
                                value="Decodes",
                                label="Search In",
                            )
                            search_btn = gr.Button("🔍 Search", variant="primary")
                            gr.Markdown("---")
                            history_browse_type = gr.Radio(
                                choices=["Recent Decodes", "Recent Assets"],
                                value="Recent Decodes",
                                label="Browse",
                            )
                            browse_btn = gr.Button("📋 Load Recent", size="sm")

                        with gr.Column(scale=2):
                            history_output = gr.Markdown(
                                value="*Search or browse your decode/asset history...*",
                                elem_classes=["output-box"],
                            )

                # ═══ Tab 5: ACP Marketplace ═════════════════════════════════
                with gr.TabItem("🏪 ACP Marketplace"):
                    acp_output = gr.Markdown(value=handle_acp_status(), elem_classes=["output-box"])
                    refresh_acp_btn = gr.Button("🔄 Refresh ACP Status", variant="primary")

                # ═══ Tab 6: About ══════════════════════════════════════════
                with gr.TabItem("🌀 About"):
                    gr.Markdown("""
                    ## Signal Forge v2 — Second-Order Cybernetics Decoder + Asset Engine

                    **Two engines. One mission. Turn awareness into assets.**

                    ### 🔍 Loop Engineer
                    A second-order cybernetics decoder. It doesn't just tell you what's wrong — it reveals the feedback loop creating the problem, the observer position trapped inside it, and the leverage point that breaks the cycle.

                    Every decode extracts a **Loop Law** — a reusable operating principle for your life, business, or agents.

                    ### ⚡ Signal Forge
                    A creator/business cognition engine. One raw idea becomes 10 public assets: X posts, threads, WordPress articles, YouTube packs, Shorts scripts, cover prompts, offer angles, and monetization moves.

                    ### The Stack
                    ```
                    Loop Engineer (Decode) → Extract Operating Law → Signal Forge (Assets) → Income
                    ```

                    ### Infrastructure
                    - **Proof of Awareness** — Truth, grounding, and fruit scoring for every output
                    - **Secure Gateway** — Injection and exfiltration scanning on all inputs
                    - **ACP Marketplace** — 4 offerings for agent-to-agent service delivery

                    ### REST API
                    ```
                    POST /v1/decode     — Decode a feedback loop
                    POST /v1/forge      — Forge a signal into assets
                    POST /v1/batch/*    — Batch processing (up to 10)
                    GET  /v1/health     — System health check
                    GET  /v1/laws       — Browse operating laws
                    GET  /v1/stats      — Aggregate statistics
                    GET  /v1/history/*  — Browse & search history
                    GET  /v1/export/*   — Export as Markdown/JSON
                    ```

                    ### Pricing
                    | Tier | Price | Features |
                    |------|-------|----------|
                    | Free | $0 | 3 decodes/packs per day |
                    | Pro | $33/month | Unlimited + saved library |
                    | Custom | $333 | Full business/agent decode + automation blueprint |

                    ---
                    **Inner I Network** — Turn awareness into assets.
                    """)

    # Footer
    gr.HTML("""
    <div class="footer">
        Built by <a href="https://innerinetcompany.com">Inner I Network</a> ·
        <a href="https://github.com/TheInnerI">GitHub</a> ·
        <a href="/docs">API Docs</a> ·
        The Observer before the story
    </div>
    """)

    # ─── Event Handlers ─────────────────────────────────────────────────

    # Loop Engineer
    loop_btn.click(
        fn=handle_decode,
        inputs=[loop_mode, loop_input, loop_verify],
        outputs=[loop_output, loop_law_output, usage_display],
    )

    refresh_laws_btn.click(
        fn=handle_laws_refresh,
        outputs=[laws_display],
    )

    export_decode_btn.click(
        fn=export_decode_md,
        inputs=[loop_output, loop_law_output],
        outputs=[export_decode_file],
    )

    # Signal Forge
    forge_btn.click(
        fn=handle_forge,
        inputs=[forge_input, forge_type, forge_tone, forge_verify],
        outputs=[forge_output, usage_display],
    )

    # Dashboard
    refresh_dashboard_btn.click(
        fn=handle_dashboard,
        outputs=[dashboard_output],
    )

    # History
    search_btn.click(
        fn=handle_history_search,
        inputs=[history_search_input, history_search_type],
        outputs=[history_output],
    )

    browse_btn.click(
        fn=handle_recent_history,
        inputs=[history_browse_type],
        outputs=[history_output],
    )

    # ACP
    refresh_acp_btn.click(
        fn=handle_acp_status,
        outputs=[acp_output],
    )

    # Infrastructure refresh
    refresh_infra_btn.click(
        fn=lambda: (format_infra_status(), get_usage_display()),
        outputs=[infra_display, usage_display],
    )


# ─── Launch ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )
