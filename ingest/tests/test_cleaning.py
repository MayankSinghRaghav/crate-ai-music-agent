"""Data-cleaning guardrails: HTML entities, emoji, URLs, and non-English /
boilerplate chatter must not reach the dashboard as 'representative quotes'."""
from ingest.pipeline import _representative_quotes
from ingest.sources.base import clean_text, is_quality_text


class _Doc:
    def __init__(self, text: str):
        self.text = text


def test_clean_decodes_entities_and_strips_nbsp():
    assert clean_text("press play.&nbsp; find new artists") == "press play. find new artists"
    assert clean_text("rock &amp; soul") == "rock & soul"
    assert clean_text("don&#39;t stop") == "don't stop"


def test_clean_strips_emoji_and_urls():
    out = clean_text("great discovery \U0001F607 see https://community.spotify.com/t5/x thanks")
    assert "\U0001F607" not in out
    assert "http" not in out
    assert "great discovery" in out and "thanks" in out


def test_clean_is_idempotent():
    once = clean_text("rock &amp; soul \U0001F3B5")
    assert clean_text(once) == once


def test_quality_drops_non_english():
    # predominantly non-Latin script -> not a usable English quote
    assert is_quality_text("音楽の発見はとても難しいです、新しい曲が全然見つかりません") is False
    assert is_quality_text("Stuck on repeat with the same comfort songs every day") is True


def test_quality_drops_greeting_chatter():
    assert is_quality_text("Hi there, welcome to the Community, glad to have you here") is False


def test_clean_strips_reply_prefix():
    assert clean_text("Re: No green checkmarks in playlists") == "No green checkmarks in playlists"
    assert clean_text("RE:  discovery is broken") == "discovery is broken"


def test_quality_drops_forum_intro_and_promo():
    # the exact junk from the dashboard screenshot
    assert is_quality_text("Let's introduce ourselves! I discover tracks through playlists") is False
    assert is_quality_text("Artists Wanted Edition 19 has over 60 artists to be discovered") is False


def test_quality_drops_too_short():
    assert is_quality_text("great app") is False


def test_representative_quotes_dedupe_and_cap():
    docs = [_Doc(f"Discovery feels too repetitive and safe for me, take {i}") for i in range(12)]
    docs += [_Doc("Discovery feels too repetitive and safe for me, take 0")]  # dup
    quotes = _representative_quotes(docs)
    assert len(quotes) <= 8
    assert len(quotes) == len(set(quotes))  # no duplicates
