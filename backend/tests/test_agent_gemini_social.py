import time

import pytest

from agents.gemini_social import GeminiSocialEngine, SocialPost, _enforce_length


def test_enforce_length_truncates_long_text():
    text = " ".join(["word"] * 60)
    truncated = _enforce_length(text, min_words=5, max_words=20)
    assert len(truncated.split()) <= 21 


def test_fallback_post_is_non_empty():
    engine = GeminiSocialEngine()
    post = engine._fallback_post("system")
    assert isinstance(post, str)
    assert post.strip()


@pytest.mark.asyncio
async def test_generate_post_cycle_adds_post_and_broadcasts(monkeypatch):
    engine = GeminiSocialEngine()
    seen = []

    async def fake_call(*args, **kwargs):
        return "WBTC looks strong. Buying breakouts with tight risk controls."

    async def fake_broadcast(msg):
        seen.append(msg)

    monkeypatch.setattr("agents.gemini_social.random.random", lambda: 0.9)
    monkeypatch.setattr(engine, "_call_gemini", fake_call)
    monkeypatch.setattr(engine, "_broadcast", fake_broadcast)

    await engine._generate_post_cycle()

    assert len(engine._posts) == 1
    assert seen
    assert seen[0]["type"] == "post"


@pytest.mark.asyncio
async def test_generate_comment_cycle_appends_comment(monkeypatch):
    engine = GeminiSocialEngine()
    base_post = SocialPost(
        id=1,
        agent_name="AlphaWave",
        content="Momentum still strong on WBTC.",
        timestamp=time.time(),
        sentiment="bullish",
        token="WBTC",
        likes=1,
        comments=[],
        is_ai=True,
    )
    engine._posts = [base_post]

    async def fake_call(*args, **kwargs):
        return "@AlphaWave I agree with momentum, but volatility risk is rising."

    async def fake_broadcast(_msg):
        return None

    monkeypatch.setattr(engine, "_call_gemini", fake_call)
    monkeypatch.setattr(engine, "_broadcast", fake_broadcast)

    await engine._generate_comment_cycle()

    assert len(engine._posts[0].comments) == 1
    assert engine._posts[0].comments[0]["content"].startswith("@")
