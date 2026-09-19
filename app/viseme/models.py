"""
Viseme data models.
A viseme is a visual representation of a phoneme (mouth shape).
"""
from dataclasses import dataclass
from enum import Enum


class VisemeShape(str, Enum):
    """
    15-Viseme phonetic standard matching Oculus / Disney / Preston Blair mapping.
    """
    NEUTRAL = "neutral"       # Resting / silence
    SIL = "sil"
    AA = "aa"                 # Wide open: A, AH, AY
    E = "E"                   # Wide smile teeth: E, EE, EH
    I = "I"                   # Stretched: I, IH, Y
    O = "O"                   # Round open: O, OW, AO
    U = "U"                   # Tight pucker: U, UW, OO, W
    PP = "PP"                 # Bilabial closed: P, B, M
    FF = "FF"                 # Labiodental: F, V
    TH = "TH"                 # Tongue between teeth: TH, DH
    DD = "DD"                 # Alveolar: T, D, N, L
    KK = "kk"                 # Velar: K, G, NG
    CH = "CH"                 # Pursed/Fricative: CH, J, SH, ZH
    SS = "SS"                 # Dental sibilant: S, Z
    NN = "nn"                 # Nasal: N, NG
    RR = "RR"                 # Rhotic: R, ER

    # Legacy aliases for backwards compatibility
    OPEN = "open"
    ROUND = "round"
    BILABIAL = "bilabial"
    LABIODENTAL = "labiodental"
    DENTAL = "dental"


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
