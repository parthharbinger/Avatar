"""
Viseme data models.
A viseme is a visual representation of a phoneme (mouth shape).
"""
from dataclasses import dataclass
from enum import Enum


class VisemeShape(str, Enum):
    """
    6 core viseme mouth shapes covering all English phonemes.
    Map to sprite names in the frontend renderer.
    """
    NEUTRAL = "neutral"       # Resting / silence
    OPEN = "open"             # Vowels: A, E  (ah, eh)
    ROUND = "round"           # Vowels: O, U  (oh, oo)
    BILABIAL = "bilabial"     # Consonants: M, B, P (lips together)
    LABIODENTAL = "labiodental"  # Consonants: F, V
    DENTAL = "dental"         # Consonants: L, N, T, D, S, Z


@dataclass
class VisemeEvent:
    """A single viseme keyframe in the animation timeline."""
    time_ms: int        # Time offset from speech start in milliseconds
    shape: VisemeShape  # Mouth shape to display at this time

    def to_dict(self) -> dict:
        return {
            "t": self.time_ms,
            "v": self.shape.value,
        }
