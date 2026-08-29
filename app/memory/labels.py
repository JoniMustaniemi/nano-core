from __future__ import annotations

MAX_TIMER_LABEL_LENGTH = 64


class InvalidTimerLabelError(ValueError):
    """Raised when a timer or stopwatch label fails validation."""


def normalize_timer_label(raw: str, default: str) -> str:
    """
    Normalize and validate a timer or stopwatch label.

    Args:
        raw: Raw label text from user input.
        default: Default label when raw is empty after trimming.

    Returns:
        Trimmed, validated label.

    Raises:
        InvalidTimerLabelError: When the label is too long or contains control characters.
    """
    label = str(raw).strip() or default
    if len(label) > MAX_TIMER_LABEL_LENGTH:
        raise InvalidTimerLabelError(f"Label must be at most {MAX_TIMER_LABEL_LENGTH} characters.")
    if any(ord(character) < 32 for character in label):
        raise InvalidTimerLabelError("Label cannot contain control characters.")
    return label
