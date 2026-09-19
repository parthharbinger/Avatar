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

# Character / sub-phoneme → Viseme lookup table (15-Viseme Phonetic Standard)
_CHAR_TO_VISEME: dict[str, VisemeShape] = {
    # Open Vowels
    "a": VisemeShape.AA,
    "e": VisemeShape.E,
    "i": VisemeShape.I,
    # Rounded Vowels & Approximants
    "o": VisemeShape.O,
    "u": VisemeShape.U,
    "w": VisemeShape.U,
    "q": VisemeShape.O,
    # Bilabials (lips together)
    "m": VisemeShape.PP,
    "b": VisemeShape.PP,
    "p": VisemeShape.PP,
    # Labiodentals (lip to teeth)
    "f": VisemeShape.FF,
    "v": VisemeShape.FF,
    # Dentals / Alveolars
    "t": VisemeShape.DD,
    "d": VisemeShape.DD,
    "n": VisemeShape.DD,
    "l": VisemeShape.DD,
    # Sibilants / Fricatives
    "s": VisemeShape.SS,
    "z": VisemeShape.SS,
    "c": VisemeShape.SS,
    "x": VisemeShape.SS,
    # Velar (back of throat)
    "k": VisemeShape.KK,
    "g": VisemeShape.KK,
    # Affricates
    "j": VisemeShape.CH,
    # Rhotic / Glides
    "r": VisemeShape.RR,
    "y": VisemeShape.I,
    "h": VisemeShape.AA,
    # Space / punctuation → neutral
    " ": VisemeShape.NEUTRAL,
    ",": VisemeShape.NEUTRAL,
    ".": VisemeShape.NEUTRAL,
    "!": VisemeShape.NEUTRAL,
    "?": VisemeShape.NEUTRAL,
    ";": VisemeShape.NEUTRAL,
    ":": VisemeShape.NEUTRAL,
    "-": VisemeShape.NEUTRAL,
}


def map_text_to_visemes(text: str, start_offset_ms: int = 0) -> List[VisemeEvent]:
    """
    Estimate a viseme timeline from plain text when no word boundaries are available.

    Args:
        text: The text being spoken.
        start_offset_ms: Time offset to add (useful when audio starts with silence).

    Returns:
        List of VisemeEvents sorted by time.
    """
    events: List[VisemeEvent] = []
    current_time = start_offset_ms

    for char in text.lower():
        shape = _CHAR_TO_VISEME.get(char, VisemeShape.AA)
        # Only add event if shape differs from last (avoids redundant keyframes)
        if not events or events[-1].shape != shape:
            events.append(VisemeEvent(time_ms=current_time, shape=shape))
        current_time += _MS_PER_CHAR

    # Always end with neutral (mouth closes)
    events.append(VisemeEvent(time_ms=current_time, shape=VisemeShape.NEUTRAL))
    return events


def from_word_boundaries(
    word_boundaries: List[tuple[str, float, float]], start_offset_ms: int = 0
) -> List[VisemeEvent]:
    """
    Build an ultra-precise viseme timeline from TTS WordBoundary metadata.

    Args:
        word_boundaries: List of (word_text, offset_ms, duration_ms) tuples.
        start_offset_ms: Global start time offset.

    Returns:
        Chronologically sorted list of VisemeEvents matching exact speech timings.
    """
    if not word_boundaries:
        return [VisemeEvent(time_ms=start_offset_ms, shape=VisemeShape.NEUTRAL)]

    events: List[VisemeEvent] = []
    last_end_ms = start_offset_ms

    for word_text, offset_ms, duration_ms in word_boundaries:
        clean = "".join(c for c in word_text.lower() if c.isalnum())
        if not clean:
            continue

        word_start = offset_ms + start_offset_ms
        # If there is a natural pause (> 40ms) between words, close mouth
        if word_start > last_end_ms + 40:
            if not events or events[-1].shape != VisemeShape.NEUTRAL:
                events.append(VisemeEvent(time_ms=int(last_end_ms), shape=VisemeShape.NEUTRAL))

        # Distribute word duration across its constituent letters
        char_dur = duration_ms / max(1, len(clean))
        for i, char in enumerate(clean):
            t = int(word_start + (i * char_dur))
            shape = _CHAR_TO_VISEME.get(char, VisemeShape.AA)
            if not events or events[-1].shape != shape:
                events.append(VisemeEvent(time_ms=t, shape=shape))

        last_end_ms = word_start + duration_ms

    # Close mouth at completion
    if events:
        events.append(VisemeEvent(time_ms=int(last_end_ms), shape=VisemeShape.NEUTRAL))
    else:
        events.append(VisemeEvent(time_ms=start_offset_ms, shape=VisemeShape.NEUTRAL))

    return events


def from_alignment_data(
    alignment: List[dict], start_offset_ms: int = 0
) -> List[VisemeEvent]:
    """
    Build a viseme timeline from character alignment data.

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
        shape = _CHAR_TO_VISEME.get(char, VisemeShape.AA)
        if not events or events[-1].shape != shape:
            events.append(VisemeEvent(time_ms=time_ms, shape=shape))

    if events:
        last_time = events[-1].time_ms + _MS_PER_CHAR
        events.append(VisemeEvent(time_ms=last_time, shape=VisemeShape.NEUTRAL))
    return events
