"""
test_replay.py — Record a demo run, then replay it offline with identical model answers.
"""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Approval, Run
from app.db.session import session_scope
from app.demo.samples import get_sample
from app.llm.router import LLMBackendError, LLMRequest, LLMRouter, get_router
from app.runs.service import create_run


async def _run_sample(sample_id: str) -> tuple[dict, str]:
    """Run a sample and return (final state, approval draft text)."""
    sample = get_sample(sample_id)
    run_id = await create_run(message=sample.message, channel=sample.channel, background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        approval = await db.scalar(select(Approval).where(Approval.run_id == run_id))
    return run.state, approval.payload["text"]


async def test_recorded_run_replays_identically(db_ready, monkeypatch):
    """Record with the fake model, then replay: same quote, same draft, provider=replay."""
    monkeypatch.setenv("LLM_RECORD", "true")
    get_settings.cache_clear()
    get_router.cache_clear()
    recorded_state, recorded_text = await _run_sample("en_brass_runners")
    assert get_settings().llm_cassette.exists()

    monkeypatch.setenv("LLM_RECORD", "false")
    monkeypatch.setenv("LLM_PROFILE", "replay")
    get_settings.cache_clear()
    get_router.cache_clear()
    replay_state, replay_text = await _run_sample("en_brass_runners")

    assert replay_text == recorded_text
    money_keys = ("lines", "charges", "goods_total_aed", "charges_total_aed", "total_aed", "total_inr", "incoterm")
    assert {k: replay_state["quote"][k] for k in money_keys} == {k: recorded_state["quote"][k] for k in money_keys}
    assert replay_state["drafts"][0]["model"].startswith("replay:")


async def test_replay_fails_clearly_for_unrecorded_requests(monkeypatch):
    """A request that was never recorded raises instead of inventing an answer."""
    monkeypatch.setenv("LLM_PROFILE", "replay")
    get_settings.cache_clear()
    with pytest.raises(LLMBackendError, match="No recorded answer"):
        await LLMRouter().complete(LLMRequest(role="worker", prompt="never recorded", purpose="x"))


async def test_real_data_is_never_recorded(monkeypatch):
    """Cassettes are demo assets: requests labelled 'real' are not written."""
    monkeypatch.setenv("LLM_RECORD", "true")
    get_settings.cache_clear()
    await LLMRouter().complete(LLMRequest(role="worker", prompt="pilot message", data_class="real"))
    assert not get_settings().llm_cassette.exists()
