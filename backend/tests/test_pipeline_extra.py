"""Pipeline extras: English-only comments with language groups, Full tier with audiences,
LLM not configured / daily cap errors, cost logging, stuck-test recovery, resume without repeating LLM calls."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import session_scope
from app.models import AdTest, ArchetypeReaction, LLMUsage
from app.security import now_utc
from app.workers.run_test import run_test_inline
from app.workers.worker import recover_stuck_tests
from tests.conftest import Api, run_pending_jobs


@pytest.mark.asyncio
async def test_comments_are_english_and_counted_per_language_group(api: Api) -> None:
    await api.register_and_login(country="MM")
    # Burmese caption, Myanmar market: agents carry language groups; comments and reasons are English
    profile = await api.create_profile(customer_languages=["my", "en"])
    r = await api.post(
        "/tests",
        {
            "title": "MM organic",
            "country_code": "MM",
            "tier_code": "quick",
            "ad_copy": {"caption": "ဒီအပတ် ၂၀% လျှော့ ပင်လယ်စာ ကင်", "headline": "20% off", "cta": "send_message"},
        },
    )
    tid = r.json()["id"]
    await api.put(f"/tests/{tid}/profile", {"profile_id": profile["id"], "mode": "preset"})
    await api.upload_image(tid)
    await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "paid",
            "goal": "messages",
            "budget_minor": 2000,
            "currency": "USD",
            "schedule": {"days": 2},
        },
    )
    await api.put(
        f"/tests/{tid}/platforms", [{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    await api.confirm(tid)
    order = (await api.post(f"/tests/{tid}/pay/manual")).json()
    assert order["test_status"] == "payment_review"
    # approve through the service as the admin would
    admin = Api(api.c)
    await admin.login_admin()
    r = await admin.post(f"/admin/payments/{order['payment']['id']}/approve")
    assert r.status_code == 200
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    report = (await api.get(f"/tests/{tid}/report")).json()
    assert report["summary"]["caption_language"] == "my"
    groups = {g["code"]: g for g in report["language_groups"]}
    assert "my" in groups and groups["my"]["seen"] > 0
    assert sum(g["comments"] for g in report["language_groups"]) == len(report["comments"])
    for c in report["comments"]:
        assert c["text"].isascii() and c["language_group"] in groups
    for reason in report["reasons"]:
        assert reason["statement"].isascii()
    assert any(e["type"] == "language" for e in report["evidence"])
    async with session_scope() as db:
        n = (
            await db.execute(
                select(func.count()).select_from(LLMUsage).where(LLMUsage.ad_test_id == uuid.UUID(tid))
            )
        ).scalar_one()
        stages = {
            s
            for (s,) in (
                await db.execute(
                    select(LLMUsage.stage).where(LLMUsage.ad_test_id == uuid.UUID(tid)).distinct()
                )
            ).all()
        }
    assert n >= 2 and "analyze_ad" in stages


@pytest.mark.asyncio
async def test_full_tier_audience_comparison(api: Api) -> None:
    await api.register_and_login()
    profile = await api.create_profile()
    r = await api.post(
        "/tests",
        {
            "title": "Full tier",
            "country_code": "TH",
            "tier_code": "full",
            "ad_copy": {"caption": "20% off grilled seafood", "cta": "send_message"},
            "audiences": [
                {"name": "Followers", "kind": "followers", "targeting": {"age_min": 18, "age_max": 60}},
                {
                    "name": "Locals new to the cuisine",
                    "targeting": {"age_min": 18, "age_max": 45, "interests": ["food"]},
                },
            ],
        },
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    await api.put(f"/tests/{tid}/profile", {"profile_id": profile["id"], "mode": "preset"})
    await api.upload_image(tid)
    await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "boosted",
            "goal": "messages",
            "budget_minor": 1500,
            "currency": "USD",
            "schedule": {"days": 2},
        },
    )
    await api.put(
        f"/tests/{tid}/platforms", [{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    c = await api.confirm(tid)
    assert c["price"]["total_usd_minor"] == 2500
    # shrink the tier for test speed: the engine is deterministic, so a smaller run is still a valid check
    async with session_scope() as db:
        from app.models import Tier

        full = await db.get(Tier, "full")
        full.runs_target, full.min_runs, full.agents, full.archetypes, full.scenarios = 10, 10, 3000, 40, 2
    try:
        await api.post(f"/tests/{tid}/pay/card")
        results = await run_pending_jobs()
        assert results[0]["ok"] is True, results
        report = (await api.get(f"/tests/{tid}/report")).json()
        assert len(report["audiences"]) == 2 and {a["name"] for a in report["audiences"]} == {
            "Followers",
            "Locals new to the cuisine",
        }
        assert len(report["platforms"]) == 2 and {p["audience_idx"] for p in report["platforms"]} == {0, 1}
        assert all(a["score"] for a in report["audiences"])
    finally:
        async with session_scope() as db:
            full = await db.get(Tier, "full")
            full.runs_target, full.min_runs, full.agents, full.archetypes, full.scenarios = (
                150,
                60,
                20000,
                200,
                5,
            )
    # tier audience limit
    r = await api.post(
        "/tests",
        {
            "title": "too many",
            "country_code": "TH",
            "tier_code": "standard",
            "audiences": [{"name": "a"}, {"name": "b"}],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "audience_invalid"


@pytest.mark.asyncio
async def test_llm_not_configured_fails_at_analyze_stage_with_free_rerun(api: Api, monkeypatch) -> None:  # noqa: ANN001
    await api.register_and_login()
    test = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    tid = test["id"]
    await api.confirm(tid)
    await api.post(f"/tests/{tid}/pay/card")
    s = get_settings()
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(s, "OPENAI_API_KEY", "")
    with pytest.raises(Exception):  # noqa: B017 - the job re-raises so Arq records the failure
        await run_test_inline(uuid.UUID(tid))
    monkeypatch.setattr(s, "LLM_PROVIDER", "mock")
    t = (await api.get(f"/tests/{tid}")).json()
    assert (
        t["status"] == "failed"
        and t["error"]["code"] == "llm_not_configured"
        and t["rerun_available"] is True
    )
    snap = (await api.get(f"/tests/{tid}/progress/snapshot")).json()
    assert snap["status"] == "failed" and snap["error"]["code"] == "llm_not_configured"
    # the user gets a free re-run
    r = await api.post(f"/tests/{tid}/restart")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "completed"


@pytest.mark.asyncio
async def test_daily_cap_blocks_new_tests(api: Api, monkeypatch) -> None:  # noqa: ANN001
    await api.register_and_login()
    test = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    await api.confirm(test["id"])
    await api.post(f"/tests/{test['id']}/pay/card")
    s = get_settings()
    monkeypatch.setattr(s, "DAILY_LLM_SPEND_CAP_USD", 0.0)
    from app.llm.client import LLMClient

    # the mock provider is free; force the cap check as the openai provider would see it
    orig = LLMClient.is_mock
    monkeypatch.setattr(LLMClient, "is_mock", property(lambda self: False))
    try:
        with pytest.raises(Exception):  # noqa: B017
            await run_test_inline(uuid.UUID(test["id"]))
    finally:
        monkeypatch.setattr(LLMClient, "is_mock", orig)
    t = (await api.get(f"/tests/{test['id']}")).json()
    assert t["status"] == "failed" and t["error"]["code"] == "llm_daily_cap_reached"
    from app.services.queue import inline_queue

    inline_queue.drain()


@pytest.mark.asyncio
async def test_stuck_running_recovery_and_resume(api: Api) -> None:
    await api.register_and_login()
    test = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    tid = test["id"]
    await api.confirm(tid)
    await api.post(f"/tests/{tid}/pay/card")
    await run_pending_jobs()
    async with session_scope() as db:
        reactions_before = (
            await db.execute(select(func.count()).select_from(ArchetypeReaction))
        ).scalar_one()
        calls_before = (
            await db.execute(
                select(func.count())
                .select_from(LLMUsage)
                .where(LLMUsage.ad_test_id == uuid.UUID(tid), LLMUsage.stage == "react")
            )
        ).scalar_one()
        # pretend the worker died after the react stage: status running, no heartbeat for an hour
        row = await db.get(AdTest, uuid.UUID(tid))
        state = dict(row.pipeline_state)
        state["stages"] = {
            k: v
            for k, v in state["stages"].items()
            if k in ("prepare", "analyze_ad", "population", "archetypes", "react")
        }
        row.pipeline_state = state
        row.status = "running"
        row.stage = "react"
        row.heartbeat_at = now_utc() - timedelta(hours=1)
    result = await recover_stuck_tests({})
    assert result["requeued"] == 1
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "queued"
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    async with session_scope() as db:
        calls_after = (
            await db.execute(
                select(func.count())
                .select_from(LLMUsage)
                .where(LLMUsage.ad_test_id == uuid.UUID(tid), LLMUsage.stage == "react")
            )
        ).scalar_one()
        reactions_after = (await db.execute(select(func.count()).select_from(ArchetypeReaction))).scalar_one()
    assert calls_after == calls_before, "resumed job must not repeat the archetype reaction calls"
    assert reactions_after == reactions_before
    # a second recovery attempt fails the test with a free re-run
    async with session_scope() as db:
        row = await db.get(AdTest, uuid.UUID(tid))
        row.status = "running"
        row.heartbeat_at = now_utc() - timedelta(hours=1)
    result = await recover_stuck_tests({})
    assert result["failed"] == 1
    t = (await api.get(f"/tests/{tid}")).json()
    assert t["status"] == "failed" and t["rerun_available"] is True and t["error"]["code"] == "stuck"
    from app.services.queue import inline_queue

    inline_queue.drain()


@pytest.mark.asyncio
async def test_video_upload_frames_and_transcript(api: Api, tmp_path) -> None:  # noqa: ANN001
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    video = tmp_path / "ad.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=10", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "6", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video)],
        check=True,
    )
    await api.register_and_login()
    profile = await api.create_profile()
    r = await api.post("/tests", {"title": "video", "country_code": "TH", "tier_code": "quick", "ad_copy": {"caption": "20% off this weekend", "cta": "shop_now"}})
    tid = r.json()["id"]
    await api.put(f"/tests/{tid}/profile", {"profile_id": profile["id"], "mode": "preset"})
    with video.open("rb") as fh:
        r = await api.c.post(f"/api/v1/tests/{tid}/assets", files={"file": ("ad.mp4", fh, "video/mp4")}, headers=api.h())
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["kind"] == "video" and asset["width"] == 720 and asset["height"] == 1280 and 5.5 <= asset["duration_s"] <= 6.5
    # a wrong extension does not matter: the type is sniffed
    r = await api.c.post(f"/api/v1/tests/{tid}/assets", files={"file": ("notes.txt", b"hello world", "text/plain")}, headers=api.h())
    assert r.status_code == 422 and r.json()["error"]["code"] == "asset_invalid"
    await api.put(f"/tests/{tid}/post", {"post_type": "paid", "goal": "traffic", "budget_minor": 3000, "currency": "USD", "schedule": {"days": 2}})
    await api.put(f"/tests/{tid}/platforms", [{"code": "tiktok", "placements": ["in_feed"], "budget_share": 100}])
    c = await api.confirm(tid)
    assert all(sc["ok"] for sc in c["spec_checks"]), c["spec_checks"]  # 9:16 video fits the TikTok in-feed spec
    await api.post(f"/tests/{tid}/pay/card")
    results = await run_pending_jobs()
    assert results[0]["ok"] is True, results
    report = (await api.get(f"/tests/{tid}/report")).json()
    assert report["summary"]["ad_features"]["is_video"] is True
    assert any(e["type"] == "dropoff" for e in report["evidence"])
    async with session_scope() as db:
        from app.models import AdAsset

        kinds = [k for (k,) in (await db.execute(select(AdAsset.kind).where(AdAsset.ad_test_id == uuid.UUID(tid)))).all()]
    assert kinds.count("frame") >= 4 and "audio" in kinds
    admin = Api(api.c)
    await admin.login_admin()
    detail = (await admin.get(f"/admin/tests/{tid}")).json()
    assert detail["stages"][0]["detail"]["transcript_chars"] > 0
