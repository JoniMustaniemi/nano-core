from __future__ import annotations

import secrets

_VARIATION_HINTS: tuple[str, ...] = (
    "Vary your opening phrase; do not begin with a stock assistant introduction.",
    "Keep the reply to one or two sentences and lead with attitude rather than a feature list.",
    "Frame yourself through your supervisory, clinical tone instead of listing duties.",
    "Use a dry observational angle about the question or the moment.",
    "Answer compactly, as if the question is mildly redundant but tolerable.",
    "Let the personality show through word choice, not through repeating the same outline.",
    "Sound composed and specific rather than generic.",
)


def choose_variation_hint() -> str:
    """
    Return a random phrasing angle for personality-driven replies.

    Returns:
        Variation guidance for answer drafting prompts.
    """
    return secrets.choice(_VARIATION_HINTS)
