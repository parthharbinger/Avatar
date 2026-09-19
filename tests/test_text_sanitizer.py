"""
Unit tests for the Text Sanitizer Service.
Verifies removal of emojis, logos, symbols, and markdown for Text-to-Speech (TTS).
"""
import pytest
from app.services.text_sanitizer import clean_text_for_speech, PLAIN_TEXT_SPEECH_DIRECTIVE


def test_clean_empty_or_none():
    assert clean_text_for_speech("") == ""
    assert clean_text_for_speech(None) == ""


def test_strip_common_emojis():
    raw = "Hello! 🤖 Here is your flight ✈️ to Paris ✨ with a great discount! 👍 Have fun! 😊"
    expected = "Hello! Here is your flight to Paris with a great discount! Have fun!"
    assert clean_text_for_speech(raw) == expected


def test_strip_extended_emojis_and_flags():
    raw = "Welcome to 🇺🇸 New York! 🍕 Enjoy your stay 🚀 🔥 💯"
    expected = "Welcome to New York! Enjoy your stay"
    assert clean_text_for_speech(raw) == expected


def test_strip_markdown_formatting():
    raw = "**Welcome** to *Apex Travel*! We have `cheap` tickets for you. Check [Apex Flights](https://apex.com)."
    expected = "Welcome to Apex Travel! We have cheap tickets for you. Check Apex Flights."
    assert clean_text_for_speech(raw) == expected


def test_strip_markdown_headers_and_bullets():
    raw = """### Flight Options
- Nonstop to London
* 1 stop in Paris
• Premium Economy available"""
    expected = "Flight Options Nonstop to London 1 stop in Paris Premium Economy available"
    assert clean_text_for_speech(raw) == expected


def test_strip_symbols_and_logos():
    raw = "Apple  products and Windows ™ are registered ® trademarks © 2026."
    expected = "Apple products and Windows are registered trademarks 2026."
    assert clean_text_for_speech(raw) == expected


def test_plain_text_directive_exists():
    assert "Text-to-Speech" in PLAIN_TEXT_SPEECH_DIRECTIVE
    assert "plain text" in PLAIN_TEXT_SPEECH_DIRECTIVE
