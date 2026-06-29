"""Loop Engineer — Second-order cybernetics decoder."""

import json
from typing import Generator, Optional

from .config import LOOP_MODES
from .llm import call_llm, stream_llm, select_model
from .database import save_decode, check_rate_limit, increment_daily_count
from .infrastructure import poa_score_sync, secure_scan_sync


# ─── System Prompt ───────────────────────────────────────────────────────────

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


# ─── Core Functions ──────────────────────────────────────────────────────────

def decode_loop(mode: str, situation: str, tier: str = "free",
                verify: bool = True, stream: bool = False) -> dict | Generator:
    """
    Decode a feedback loop.

    Args:
        mode: Loop type (Personal, Business, Agent, etc.)
        situation: The situation/pattern to decode
        tier: User tier for rate limiting
        verify: Whether to run PoA + Secure Gateway verification
        stream: Whether to stream the response

    Returns:
        dict with 'result', 'loop_law', 'signal_score', 'poa', 'secure'
        OR Generator yielding tokens if stream=True
    """
    # Rate limit check
    if not check_rate_limit(tier):
        return {
            "error": "Free tier limit reached (3 decodes/day). Upgrade to Pro for unlimited.",
            "result": "",
            "loop_law": "",
            "signal_score": None,
            "poa": None,
            "secure": None,
        }

    # Security scan on input
    secure_result = None
    if verify:
        secure_result = secure_scan_sync(situation)
        if not secure_result.get("safe", True):
            return {
                "error": f"Input flagged by Secure Gateway: {secure_result.get('verdict', 'unknown')}",
                "result": "",
                "loop_law": "",
                "signal_score": None,
                "poa": None,
                "secure": secure_result,
            }

    # Build the prompt
    mode_context = LOOP_MODES.get(mode, "")
    user_msg = f"Mode: {mode}\n\n{mode_context}\n\nSituation:\n{situation}"

    if stream:
        return _stream_decode(mode, situation, user_msg, verify, secure_result)

    # Synchronous call
    result = call_llm(LOOP_SYSTEM, user_msg)

    # Extract loop law
    loop_law = _extract_loop_law(result)

    # Extract signal score
    signal_score = _extract_signal_score(result)

    # PoA verification
    poa_result = None
    if verify and result:
        poa_result = poa_score_sync(result, context=f"Loop decode: {mode}")

    # Save to database
    save_decode(
        mode=mode,
        input_text=situation,
        output_dict={"raw": result, "mode": mode, "situation": situation},
        loop_law=loop_law,
        signal_score=signal_score,
        poa_score=poa_result.get("score") if poa_result else None,
        secure_verdict=secure_result.get("verdict") if secure_result else None,
    )
    increment_daily_count()

    return {
        "result": result,
        "loop_law": loop_law,
        "signal_score": signal_score,
        "poa": poa_result,
        "secure": secure_result,
        "error": None,
    }


def _stream_decode(mode, situation, user_msg, verify, secure_result):
    """Generator that yields tokens, then returns the full result."""
    full_text = ""
    for token in stream_llm(LOOP_SYSTEM, user_msg):
        full_text += token
        yield {"type": "token", "content": token}

    # Post-processing
    loop_law = _extract_loop_law(full_text)
    signal_score = _extract_signal_score(full_text)

    poa_result = None
    if verify and full_text:
        poa_result = poa_score_sync(full_text, context=f"Loop decode: {mode}")

    save_decode(
        mode=mode,
        input_text=situation,
        output_dict={"raw": full_text, "mode": mode, "situation": situation},
        loop_law=loop_law,
        signal_score=signal_score,
        poa_score=poa_result.get("score") if poa_result else None,
        secure_verdict=secure_result.get("verdict") if secure_result else None,
    )
    increment_daily_count()

    yield {
        "type": "complete",
        "loop_law": loop_law,
        "signal_score": signal_score,
        "poa": poa_result,
        "secure": secure_result,
    }


def _extract_loop_law(text: str) -> str:
    """Extract the operating law from the decode output."""
    if "New Operating Law" not in text:
        return ""
    try:
        law_section = text.split("New Operating Law")[1].split("\n")[1].strip()
        if law_section.startswith("**"):
            law_section = law_section.strip("*")
        return law_section
    except (IndexError, ValueError):
        return ""


def _extract_signal_score(text: str) -> Optional[dict]:
    """Extract the signal scores from the decode output."""
    scores = {}
    score_fields = ["Clarity", "Loop Strength", "Risk", "Leverage", "Monetization Potential"]

    if "Signal Score" not in text:
        return None

    try:
        score_section = text.split("Signal Score")[1]
        for field in score_fields:
            # Look for patterns like "Clarity: 85/100" or "Clarity: 85"
            for line in score_section.split("\n"):
                if field in line:
                    # Extract number before /100 or at end
                    import re
                    match = re.search(r'(\d+)(?:/100)?', line.split(":")[-1])
                    if match:
                        key = field.lower().replace(" ", "_").replace("/", "_")
                        scores[key] = int(match.group(1))
                    break
    except (IndexError, ValueError):
        pass

    return scores if scores else None


def get_loop_diagram(loop_text: str) -> str:
    """Generate an ASCII loop diagram from the decode output."""
    # Extract key sections for the diagram
    surface = ""
    loop = ""
    leverage = ""
    law = ""

    try:
        if "Surface Signal" in loop_text:
            surface = loop_text.split("Surface Signal")[1].split("\n")[1].strip()[:60]
        if "System Loop" in loop_text:
            loop = loop_text.split("System Loop")[1].split("\n")[1].strip()[:60]
        if "Leverage Point" in loop_text:
            leverage = loop_text.split("Leverage Point")[1].split("\n")[1].strip()[:60]
        if "New Operating Law" in loop_text:
            law = _extract_loop_law(loop_text)[:60]
    except (IndexError, ValueError):
        pass

    diagram = f"""
┌─────────────────────────────────────────────┐
│            ⟲ LOOP DIAGRAM                   │
├─────────────────────────────────────────────┤
│                                             │
│   ┌──────────┐    ┌──────────┐             │
│   │ SURFACE  │───▶│  LOOP    │             │
│   │ SIGNAL   │    │  CYCLE   │             │
│   └──────────┘    └────┬─────┘             │
│                        │                    │
│                        ▼                    │
│   ┌──────────┐    ┌──────────┐             │
│   │LEVERAGE  │◀───│FAILURE   │             │
│   │  POINT   │    │  MODE    │             │
│   └────┬─────┘    └──────────┘             │
│        │                                    │
│        ▼                                    │
│   ┌──────────────────────────┐             │
│   │  ⚡ OPERATING LAW        │             │
│   │  {law:<28}│             │
│   └──────────────────────────┘             │
│                                             │
└─────────────────────────────────────────────┘
"""
    return diagram
