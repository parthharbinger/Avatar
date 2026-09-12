"""
Unit tests for the viseme mapper.
"""
import pytest
from app.viseme.mapper import map_text_to_visemes
from app.viseme.models import VisemeShape


def test_neutral_appended_at_end():
    """Last viseme event must always be NEUTRAL (mouth closes)."""
    events = map_text_to_visemes("Hello")
    assert events[-1].shape == VisemeShape.NEUTRAL


def test_events_are_chronologically_ordered():
    events = map_text_to_visemes("Hello world")
    times = [e.time_ms for e in events]
    assert times == sorted(times)


def test_bilabial_for_m_b_p():
    events = map_text_to_visemes("map")
    shapes = {e.shape for e in events}
    assert VisemeShape.BILABIAL in shapes


def test_open_vowel_for_a():
    events = map_text_to_visemes("aaa")
    # First event should be OPEN for vowel 'a'
    assert events[0].shape == VisemeShape.OPEN


def test_empty_text_returns_neutral():
    events = map_text_to_visemes("")
    # Should at minimum return the trailing NEUTRAL
    assert len(events) >= 1
    assert events[-1].shape == VisemeShape.NEUTRAL


def test_no_consecutive_duplicate_shapes():
    """Consecutive identical shapes should be merged."""
    events = map_text_to_visemes("mama")
    for i in range(len(events) - 1):
        assert events[i].shape != events[i + 1].shape, \
            f"Duplicate shape {events[i].shape} at indices {i} and {i+1}"


def test_to_dict_format():
    events = map_text_to_visemes("hi")
    d = events[0].to_dict()
    assert "t" in d
    assert "v" in d
    assert isinstance(d["t"], int)
    assert isinstance(d["v"], str)
