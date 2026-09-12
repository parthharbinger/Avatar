"""
Viseme mapper: converts text to a timeline of VisemeEvents.

Strategy (MVP / Zero-GPU):
  - Iterate over characters in the text.
  - Estimate per-character duration from average speaking rate (~13 chars/sec).
  - Map each character to its viseme group via a lookup table.
  - Merge consecutive identical visemes for smoother animation.

When using ElevenLabs with alignment data, pass the character timestamps
directly instead of estimating — see `from_alignment_data()`.
"""
from typing import List, Optional

from app.viseme.models import VisemeEvent, VisemeShape


# Average speaking rate: ~13 characters per second = ~77ms per character
_MS_PER_CHAR = 77

# Character → Viseme lookup table (covers all common English phonemes)
_CHAR_TO_VISEME: dict[str, VisemeShape] = {
    # Open vowels
    "a": VisemeShape.OPEN, "e": VisemeShape.OPEN,
    # Round vowels
    "o": VisemeShape.ROUND, "u": VisemeShape.ROUND,
    # Bilabial (lips close)
    "m": VisemeShape.BILABIAL, "b": VisemeShape.BILABIAL, "p": VisemeShape.BILABIAL,
    # Labiodental
    "f": VisemeShape.LABIODENTAL, "v": VisemeShape.LABIODENTAL,
    # Dental / alveolar
    "l": VisemeShape.DENTAL, "n": VisemeShape.DENTAL, "t": VisemeShape.DENTAL,
    "d": VisemeShape.DENTAL, "s": VisemeShape.DENTAL, "z": VisemeShape.DENTAL,
    "r": VisemeShape.DENTAL, "th": VisemeShape.DENTAL,
    # Space / punctuation → neutral
    " ": VisemeShape.NEUTRAL, ",": VisemeShape.NEUTRAL,
    ".": VisemeShape.NEUTRAL, "!": VisemeShape.NEUTRAL,
    "?": VisemeShape.NEUTRAL, ";": VisemeShape.NEUTRAL,
}


def map_text_to_visemes(text: str, start_offset_ms: int = 0) -> List[VisemeEvent]:
    """
    Estimate a viseme timeline from plain text.

    Args:
        text: The text being spoken.
        start_offset_ms: Time offset to add (useful when audio starts with silence).

    Returns:
        List of VisemeEvents sorted by time.
    """
    events: List[VisemeEvent] = []
    current_time = start_offset_ms

    for char in text.lower():
        shape = _CHAR_TO_VISEME.get(char, VisemeShape.OPEN)
        # Only add event if shape differs from last (avoids redundant keyframes)
        if not events or events[-1].shape != shape:
            events.append(VisemeEvent(time_ms=current_time, shape=shape))
        current_time += _MS_PER_CHAR

    # Always end with neutral (mouth closes)
    events.append(VisemeEvent(time_ms=current_time, shape=VisemeShape.NEUTRAL))
    return events


def from_alignment_data(
    alignment: List[dict], start_offset_ms: int = 0
) -> List[VisemeEvent]:
    """
    Build a viseme timeline from ElevenLabs character alignment data.

    Args:
        alignment: List of {"character": str, "start_time": float (seconds)} dicts.
        start_offset_ms: Time offset in ms.

    Returns:
        List of VisemeEvents sorted by time.
    """
    events: List[VisemeEvent] = []
    for item in alignment:
        char = item.get("character", " ").lower()
        time_ms = int(item.get("start_time", 0) * 1000) + start_offset_ms
        shape = _CHAR_TO_VISEME.get(char, VisemeShape.OPEN)
        if not events or events[-1].shape != shape:
            events.append(VisemeEvent(time_ms=time_ms, shape=shape))

    if events:
        last_time = events[-1].time_ms + _MS_PER_CHAR
        events.append(VisemeEvent(time_ms=last_time, shape=VisemeShape.NEUTRAL))
    return events
