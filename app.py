# Inner I Signal Forge + Loop Engineer
# Unified MVP — Second-order cybernetics decoder + asset engine

import gradio as gr
import json
import os
import sqlite3
from datetime import datetime, date
from openai import OpenAI

# ─── Configuration ───────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "forge.db")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs", "saved_decodes")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

MODEL = "openrouter/owl-alpha"

# ─── Database ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS decodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT,
            input_text TEXT,
            output_json TEXT,
            loop_law TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_text TEXT,
            output_json TEXT,
            tone TEXT,
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
    conn.commit()
    conn.close()

init_db()

def get_daily_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM daily_usage WHERE date=?", (str(date.today()),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_daily_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO daily_usage (date, count) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET count = count + 1
    """, (str(date.today()),))
    conn.commit()
    conn.close()

def save_decode(mode, input_text, output_dict, loop_law):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO decodes (mode, input_text, output_json, loop_law) VALUES (?, ?, ?, ?)",
              (mode, input_text, json.dumps(output_dict), loop_law))
    if loop_law:
        c.execute("INSERT OR IGNORE INTO loop_laws (law, category, source_input) VALUES (?, ?, ?)",
                  (loop_law, mode, input_text[:200]))
    conn.commit()
    conn.close()

def save_asset(input_text, output_dict, tone):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO assets (input_text, output_json, tone) VALUES (?, ?, ?)",
              (input_text, json.dumps(output_dict), tone))
    conn.commit()
    conn.close()

def get_loop_laws():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT law, category FROM loop_laws ORDER BY created_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return rows

# ─── Prompt Loaders ──────────────────────────────────────────────────────────

def load_prompt(name):
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""

# ─── LLM Call ────────────────────────────────────────────────────────────────

def call_llm(system_prompt, user_input, temperature=0.8):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Error calling LLM: {e}]"

# ─── Loop Engineer ───────────────────────────────────────────────────────────

LOOP_SYSTEM = """# Inner I Loop Engineer — Second-Order Cybernetics Decoder

You are the Inner I Loop Engineer. You do not answer prompts. You decode the loop that produced the prompt.

## Principles
1. Identify the visible problem — what appears to be happening.
2. Reveal the hidden feedback loop — the cycle sustaining the pattern.
3. Locate the observer position — where the person/system is observing from.
4. Expose the distortion or blind spot — what cannot be seen from that position.
5. Name the reinforcing behavior — why the loop keeps running.
6. Find the leverage point — the smallest intervention with the highest effect.
7. Design the correction protocol — step-by-step change.
8. Extract the new operating law — one reusable rule.
9. Identify the asset or system to build from this pattern.
10. Score the signal.

## Inner I Context
- Inner I is the observer before the story.
- The reference point of reality is awareness itself.
- Every loop has an observer position. Shift the observer, shift the loop.
- Never flatten spiritual language into corporate language.
- Never give vague motivation. Forge structure.

## Output Format (strict — use these exact headings)

## Surface Signal
[What appears to be happening]

## System Loop
[The feedback loop sustaining the pattern — describe the cycle]

## Observer Position
[Where the user/system is observing from — their vantage point]

## Hidden Assumption
[The belief or inference driving the loop]

## Reinforcement Mechanism
[Why the pattern keeps repeating]

## Failure Mode
[What breaks if this continues]

## Leverage Point
[The smallest intervention with the highest effect]

## Correction Protocol
[Step-by-step numbered list]

## New Operating Law
[One reusable rule — make it memorable and quotable]

## Asset/Automation Opportunity
[What to build from this pattern]

## Signal Score
- Clarity: /100
- Loop Strength: /100
- Risk: /100
- Leverage: /100
- Monetization Potential: /100
"""

def decode_loop(mode, situation):
    count = get_daily_count()
    if count >= 3:
        return {"error": "Free tier limit reached (3 decodes/day). Upgrade to Pro for unlimited."}, ""

    mode_context = {
        "Personal Loop": "Focus on personal patterns, habits, emotional cycles, and life decisions.",
        "Business Loop": "Focus on business workflows, revenue patterns, team dynamics, and market positioning.",
        "Agent Loop": "Focus on AI agent behavior, tool usage patterns, error loops, and automation failures.",
        "Money Loop": "Focus on financial behavior, spending patterns, income blocks, and wealth psychology.",
        "Creative Loop": "Focus on creative blocks, artistic patterns, content cycles, and inspiration flows.",
        "Spiritual Loop": "Focus on spiritual patterns, faith cycles, prayer life, and relationship with God.",
        "Content Loop": "Focus on content strategy, audience engagement, platform algorithms, and viral patterns.",
        "Code/System Loop": "Focus on software bugs, system architecture, deployment failures, and technical debt.",
    }

    user_msg = f"Mode: {mode}\n\n{mode_context.get(mode, '')}\n\nSituation:\n{situation}"

    result = call_llm(LOOP_SYSTEM, user_msg)

    # Extract loop law (look for "New Operating Law" section)
    loop_law = ""
    if "New Operating Law" in result:
        try:
            law_section = result.split("New Operating Law")[1].split("\n")[1].strip()
            if law_section.startswith("**"):
                law_section = law_section.strip("*")
            loop_law = law_section
        except:
            pass

    output = {"raw": result, "mode": mode, "situation": situation}
    save_decode(mode, situation, output, loop_law)
    increment_daily_count()

    return result, loop_law

# ─── Signal Forge ─────────────────────────────────────────────────────────────

FORGE_SYSTEM = """# Inner I Signal Forge

You transform one raw signal into a complete public asset pack.

## Principles
1. Preserve the original signal.
2. Do not flatten spiritual language into corporate language.
3. Make the output usable immediately.
4. Make every asset point back to a clear center.
5. Prefer strong titles, clear hooks, and concrete calls to action.
6. When Inner I mode is selected, use language of awareness, observer, breathfield, signal, white flame, and reference point.
7. Never output vague motivation. Forge structure.

## Inner I Brand Context
- Inner I Network
- Inner I Breathfield Productions
- Proof of Awareness
- The Observer before the story
- Turn awareness into assets
- Tagline: Drop one thought. Forge ten assets. Move the field.

## Output Format (strict — use these exact headings)

## X Post
[Single punchy post, under 280 characters]

## X Thread
[5-7 tweet thread, numbered]

## WordPress Article
[Title + 300-word article with headings]

## YouTube Title
[Compelling title]

## YouTube Description
[Full description with timestamps, links, CTA]

## YouTube Tags
[Comma-separated tags, 15-20]

## Shorts/Reels Script
[60-second script with hook, body, CTA]

## Thumbnail/Cover Prompt
[Detailed image generation prompt for thumbnail]

## Offer Angle
[How to monetize this signal — specific product/service]

## Next Best Monetization Move
[Concrete next step to generate income from this]

## Signal Score
- Clarity: /100
- Originality: /100
- Emotional Charge: /100
- Monetization Potential: /100
- Inner I Alignment: /100
"""

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

def forge_signal(input_text, asset_type, tone):
    count = get_daily_count()
    if count >= 3:
        return {"error": "Free tier limit reached (3 packs/day). Upgrade to Pro for unlimited."}, ""

    tone_instruction = TONE_MODIFIERS.get(tone, TONE_MODIFIERS["Inner I Default"])

    asset_type_focus = {
        "Music Release": "Focus on music release assets: titles, descriptions, tags, promo posts, cover prompts.",
        "WordPress Article": "Focus on a full WordPress article with SEO title, excerpt, tags, and body.",
        "X Thread": "Focus on a viral X thread with strong hooks and engagement.",
        "Business Offer": "Focus on business offer: landing copy, email sequence, pricing angle.",
        "YouTube Pack": "Focus on YouTube: title, description, tags, thumbnail prompt, pinned comment.",
        "Spiritual Transmission": "Focus on spiritual content: devotional, reflection, prayer, teaching.",
        "Agent/Product Idea": "Focus on AI agent or product concept: spec, positioning, launch plan.",
        "Full Signal Pack": "Generate ALL 10 assets. Full pack.",
    }

    focus = asset_type_focus.get(asset_type, asset_type_focus["Full Signal Pack"])
    user_msg = f"Asset Type: {asset_type}\nTone: {tone}\n{focus}\n\nInput:\n{input_text}"

    system = FORGE_SYSTEM + f"\n\n## Tone Instruction\n{tone_instruction}"
    result = call_llm(system, user_msg)

    output = {"raw": result, "type": asset_type, "tone": tone, "input": input_text}
    save_asset(input_text, output, tone)
    increment_daily_count()

    return result, ""

# ─── Loop Law Library ─────────────────────────────────────────────────────────

def get_laws_display():
    laws = get_loop_laws()
    if not laws:
        return "No Loop Laws extracted yet. Decode some patterns first."
    lines = []
    for law, category in laws:
        lines.append(f"**[{category}]** {law}")
    return "\n\n".join(lines)

# ─── Gradio UI ────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');

body {
    font-family: 'Inter', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
}

.gradio-container {
    max-width: 1200px !important;
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

.tab-nav {
    background: #111118 !important;
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

.score-badge {
    display: inline-block;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.85rem;
    margin: 0.25rem;
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

with gr.Blocks(
    title="Inner I Signal Forge + Loop Engineer",
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

    # Header
    gr.HTML("""
    <div class="header">
        <h1>⚡ Inner I Signal Forge</h1>
        <div class="tagline">Decode the loop. Extract the law. Forge the asset. Move the field.</div>
        <div style="margin-top: 0.5rem; color: #666; font-size: 0.9rem;">
            Second-order cybernetics decoder + asset engine for the Observer Age
        </div>
    </div>
    """)

    with gr.Tabs():

        # ─── Tab 1: Loop Engineer ──────────────────────────────────────────
        with gr.TabItem("🔍 Loop Engineer"):
            gr.Markdown("""
            ### Decode the pattern behind the pattern.
            Most AI tools answer the prompt. **Loop Engineer decodes the loop that produced the prompt.**
            Enter any situation — business stall, agent error, money drain, creative block, spiritual confusion.
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    loop_mode = gr.Dropdown(
                        choices=[
                            "Personal Loop", "Business Loop", "Agent Loop",
                            "Money Loop", "Creative Loop", "Spiritual Loop",
                            "Content Loop", "Code/System Loop"
                        ],
                        value="Business Loop",
                        label="Loop Mode",
                    )
                    loop_input = gr.Textbox(
                        lines=6,
                        placeholder="Describe the situation, pattern, or problem you want decoded...\n\nExample: 'My business keeps stalling. I get momentum, then something breaks. I restart. The cycle repeats.'",
                        label="Situation / Pattern",
                    )
                    loop_btn = gr.Button("🔍 Decode Loop", variant="primary", size="lg")

                with gr.Column(scale=2):
                    loop_output = gr.Markdown(
                        value="*Your loop decode will appear here...*",
                        elem_classes=["output-box"],
                    )
                    loop_law_output = gr.Markdown(value="")

            gr.Markdown("---")
            gr.Markdown("### 📜 Loop Law Library")
            laws_display = gr.Markdown(value=get_laws_display())
            refresh_laws_btn = gr.Button("🔄 Refresh Laws")

        # ─── Tab 2: Signal Forge ───────────────────────────────────────────
        with gr.TabItem("⚡ Signal Forge"):
            gr.Markdown("""
            ### Drop one thought. Forge ten assets. Move the field.
            Enter one idea, lyric, business problem, spiritual insight, or product concept.
            Get a complete public asset pack with monetization path.
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    forge_type = gr.Dropdown(
                        choices=[
                            "Full Signal Pack", "Music Release", "WordPress Article",
                            "X Thread", "Business Offer", "YouTube Pack",
                            "Spiritual Transmission", "Agent/Product Idea"
                        ],
                        value="Full Signal Pack",
                        label="Asset Type",
                    )
                    forge_tone = gr.Dropdown(
                        choices=list(TONE_MODIFIERS.keys()),
                        value="Inner I Default",
                        label="Tone",
                    )
                    forge_input = gr.Textbox(
                        lines=6,
                        placeholder="Enter your raw idea, lyric, insight, problem, or concept...\n\nExample: 'Inner I is inevitably the reference point of your reality.'",
                        label="Raw Signal",
                    )
                    forge_btn = gr.Button("⚡ Forge Signal", variant="primary", size="lg")

                with gr.Column(scale=2):
                    forge_output = gr.Markdown(
                        value="*Your signal pack will appear here...*",
                        elem_classes=["output-box"],
                    )

        # ─── Tab 3: About ──────────────────────────────────────────────────
        with gr.TabItem("🌀 About"):
            gr.Markdown("""
            ## Inner I Signal Forge + Loop Engineer

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
        The Observer before the story
    </div>
    """)

    # ─── Event Handlers ──────────────────────────────────────────────────

    loop_btn.click(
        fn=decode_loop,
        inputs=[loop_mode, loop_input],
        outputs=[loop_output, loop_law_output],
    )

    forge_btn.click(
        fn=forge_signal,
        inputs=[forge_input, forge_type, forge_tone],
        outputs=[forge_output, gr.State()],
    )

    refresh_laws_btn.click(
        fn=lambda: gr.Markdown(value=get_laws_display()),
        outputs=[laws_display],
    )

# ─── Launch ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )
