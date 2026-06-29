"""Signal Forge — Transform one idea into 10 monetizable assets."""

import json
from typing import Generator, Optional

from .config import TONE_MODIFIERS, ASSET_TYPE_FOCUS
from .llm import call_llm, stream_llm
from .database import save_asset, check_rate_limit, increment_daily_count
from .infrastructure import poa_score_sync, secure_scan_sync


# ─── System Prompt ───────────────────────────────────────────────────────────

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


# ─── Core Functions ──────────────────────────────────────────────────────────

def forge_signal(input_text: str, asset_type: str = "Full Signal Pack",
                 tone: str = "Inner I Default", tier: str = "free",
                 verify: bool = True, stream: bool = False) -> dict | Generator:
    """
    Forge a signal into 10 monetizable assets.

    Args:
        input_text: The raw idea/signal to forge
        asset_type: Type of asset pack to generate
        tone: Tone modifier for the output
        tier: User tier for rate limiting
        verify: Whether to run PoA + Secure Gateway verification
        stream: Whether to stream the response

    Returns:
        dict with 'result', 'signal_score', 'poa', 'secure'
        OR Generator yielding tokens if stream=True
    """
    # Rate limit check
    if not check_rate_limit(tier):
        return {
            "error": "Free tier limit reached (3 packs/day). Upgrade to Pro for unlimited.",
            "result": "",
            "signal_score": None,
            "poa": None,
            "secure": None,
        }

    # Security scan on input
    secure_result = None
    if verify:
        secure_result = secure_scan_sync(input_text)
        if not secure_result.get("safe", True):
            return {
                "error": f"Input flagged by Secure Gateway: {secure_result.get('verdict', 'unknown')}",
                "result": "",
                "signal_score": None,
                "poa": None,
                "secure": secure_result,
            }

    # Build the prompt
    tone_instruction = TONE_MODIFIERS.get(tone, TONE_MODIFIERS["Inner I Default"])
    focus = ASSET_TYPE_FOCUS.get(asset_type, ASSET_TYPE_FOCUS["Full Signal Pack"])
    user_msg = f"Asset Type: {asset_type}\nTone: {tone}\n{focus}\n\nInput:\n{input_text}"

    system = FORGE_SYSTEM + f"\n\n## Tone Instruction\n{tone_instruction}"

    if stream:
        return _stream_forge(input_text, asset_type, tone, system, user_msg, verify, secure_result)

    # Synchronous call
    result = call_llm(system, user_msg)

    # Extract signal score
    signal_score = _extract_signal_score(result)

    # PoA verification
    poa_result = None
    if verify and result:
        poa_result = poa_score_sync(result, context=f"Signal forge: {asset_type}")

    # Save to database
    save_asset(
        input_text=input_text,
        output_dict={"raw": result, "type": asset_type, "tone": tone, "input": input_text},
        tone=tone,
        asset_type=asset_type,
        signal_score=signal_score,
        poa_score=poa_result.get("score") if poa_result else None,
    )
    increment_daily_count()

    return {
        "result": result,
        "signal_score": signal_score,
        "poa": poa_result,
        "secure": secure_result,
        "error": None,
    }


def _stream_forge(input_text, asset_type, tone, system, user_msg, verify, secure_result):
    """Generator that yields tokens, then returns the full result."""
    full_text = ""
    for token in stream_llm(system, user_msg):
        full_text += token
        yield {"type": "token", "content": token}

    signal_score = _extract_signal_score(full_text)

    poa_result = None
    if verify and full_text:
        poa_result = poa_score_sync(full_text, context=f"Signal forge: {asset_type}")

    save_asset(
        input_text=input_text,
        output_dict={"raw": full_text, "type": asset_type, "tone": tone, "input": input_text},
        tone=tone,
        asset_type=asset_type,
        signal_score=signal_score,
        poa_score=poa_result.get("score") if poa_result else None,
    )
    increment_daily_count()

    yield {
        "type": "complete",
        "signal_score": signal_score,
        "poa": poa_result,
        "secure": secure_result,
    }


def _extract_signal_score(text: str) -> Optional[dict]:
    """Extract signal scores from the forge output."""
    scores = {}
    score_fields = ["Clarity", "Originality", "Emotional Charge", "Monetization Potential", "Inner I Alignment"]

    if "Signal Score" not in text:
        return None

    try:
        score_section = text.split("Signal Score")[1]
        for field in score_fields:
            for line in score_section.split("\n"):
                if field in line:
                    import re
                    match = re.search(r'(\d+)(?:/100)?', line.split(":")[-1])
                    if match:
                        key = field.lower().replace(" ", "_").replace("/", "_")
                        scores[key] = int(match.group(1))
                    break
    except (IndexError, ValueError):
        pass

    return scores if scores else None
