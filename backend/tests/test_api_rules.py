"""API rule tests: cancel window and free restart, profile save modes and immutability,
platform/post validation, trial rules, duplicate blocking, spec checks."""

from __future__ import annotations

import uuid

import pytest

from app.db import session_scope
from app.models import AdTest
from tests.conftest import Api, run_pending_jobs


@pytest.mark.asyncio
async def test_cancel_window_open_then_closed_and_single_free_restart(api: Api) -> None:
    await api.register_and_login()
    test = await api.create_ready_test(tier="quick")
    tid = test["id"]
    await api.confirm(tid)
    r = await api.post(f"/tests/{tid}/pay/card")
    assert r.status_code == 200 and r.json()["test_status"] == "queued"

    # queued: cancel is allowed, test goes back to a prepaid draft with one free restart
    r = await api.post(f"/tests/{tid}/cancel")
    assert r.status_code == 200, r.text
    assert (
        r.json()["status"] == "draft"
        and r.json()["free_restart_available"] is True
        and r.json()["cancel_count"] == 1
    )
    t = (await api.get(f"/tests/{tid}")).json()
    assert t["status"] == "draft" and t["paid_via"] == "mock" and t["free_restart_available"] is True
    # the job that was enqueued sees the cancel flag / status and stops
    results = await run_pending_jobs()
    assert results and results[0]["ok"] is False

    # restart (free, no new payment) -> queued again
    r = await api.post(f"/tests/{tid}/restart")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued" and r.json()["free_restart_available"] is False

    # simulate the worker having closed the cancel window (first run batch published)
    async with session_scope() as db:
        row = await db.get(AdTest, uuid.UUID(tid))
        row.status = "running"
        row.stage = "simulate"
        row.cancel_window_open = False
    r = await api.post(f"/tests/{tid}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "cancel_window_closed"
    t = (await api.get(f"/tests/{tid}")).json()
    assert t["cancel_window"] is False

    # reopen the window (still in react stage) -> second cancel allowed but no free restart
    async with session_scope() as db:
        row = await db.get(AdTest, uuid.UUID(tid))
        row.stage = "react"
        row.cancel_window_open = True
    r = await api.post(f"/tests/{tid}/cancel")
    assert (
        r.status_code == 200 and r.json()["free_restart_available"] is False and r.json()["cancel_count"] == 2
    )
    r = await api.post(f"/tests/{tid}/restart")
    assert r.status_code == 402 and r.json()["error"]["code"] == "payment_required"
    # the test needs a new payment: confirm -> awaiting_payment -> pay
    await api.confirm(tid)
    r = await api.post(f"/tests/{tid}/pay/card")
    assert r.status_code == 200 and r.json()["test_status"] == "queued"
    await run_pending_jobs()


@pytest.mark.asyncio
async def test_profile_versions_are_immutable_and_save_modes(api: Api) -> None:
    await api.register_and_login()
    profile = await api.create_profile(followers=500)
    pid = profile["id"]
    assert profile["current_version"] == 1

    # invalid data is rejected against the template
    r = await api.put(f"/profiles/{pid}", {"data": {**profile["data"], "price_level": "luxury"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "profile_invalid"

    # update -> new version, old version kept
    r = await api.put(f"/profiles/{pid}", {"data": {**profile["data"], "followers": 900}})
    assert r.status_code == 200 and r.json()["current_version"] == 2
    versions = (await api.get(f"/profiles/{pid}/versions")).json()
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[1]["data"]["followers"] == 500 and versions[0]["data"]["followers"] == 900
    # same data again -> no new version
    r = await api.put(f"/profiles/{pid}", {"data": {**profile["data"], "followers": 900}})
    assert r.json()["current_version"] == 2

    r = await api.post("/tests", {"title": "modes", "country_code": "TH", "tier_code": "quick"})
    tid = r.json()["id"]
    # preset mode: snapshot equals the current version
    r = await api.put(f"/tests/{tid}/profile", {"profile_id": pid, "mode": "preset"})
    assert (
        r.status_code == 200
        and r.json()["version"] == 2
        and r.json()["mode"] == "preset"
        and r.json()["snapshot"]["followers"] == 900
    )
    # one_time: changes only on the test, preset untouched
    r = await api.put(
        f"/tests/{tid}/profile", {"profile_id": pid, "mode": "one_time", "changes": {"followers": 1500}}
    )
    assert r.json()["mode"] == "one_time" and r.json()["snapshot"]["followers"] == 1500
    assert (await api.get(f"/profiles/{pid}")).json()["current_version"] == 2
    # update_preset: new preset version 3
    r = await api.put(
        f"/tests/{tid}/profile", {"profile_id": pid, "mode": "update_preset", "changes": {"followers": 2000}}
    )
    assert r.json()["version"] == 3 and r.json()["mode"] == "preset"
    assert (await api.get(f"/profiles/{pid}")).json()["data"]["followers"] == 2000
    # new_preset: new preset id
    r = await api.put(
        f"/tests/{tid}/profile",
        {
            "profile_id": pid,
            "mode": "new_preset",
            "changes": {"followers": 50},
            "new_preset_name": "Second shop",
        },
    )
    assert (
        r.status_code == 200
        and r.json()["profile_id"] != pid
        and r.json()["preset_name"] == "Second shop"
        and r.json()["version"] == 1
    )
    r = await api.put(f"/tests/{tid}/profile", {"profile_id": pid, "mode": "new_preset", "changes": {}})
    assert r.status_code == 422
    # version history lists the test that used it
    versions = (await api.get(f"/profiles/{pid}/versions")).json()
    assert (
        any(t["id"] == tid for v in versions for t in v["tests"]) is False
    )  # the test now uses the new preset
    profiles = (await api.get("/profiles")).json()
    assert {p["name"] for p in profiles} == {"Main preset", "Second shop"}
    # archive keeps snapshots
    r = await api.delete(f"/profiles/{pid}")
    assert r.status_code == 200
    assert all(p["id"] != pid for p in (await api.get("/profiles")).json())
    t = (await api.get(f"/tests/{tid}")).json()
    assert t["profile"]["snapshot"]["followers"] == 50


@pytest.mark.asyncio
async def test_platform_budget_split_post_rules_and_goal_support(api: Api) -> None:
    await api.register_and_login()
    r = await api.post("/tests", {"title": "rules", "country_code": "TH", "tier_code": "quick"})
    tid = r.json()["id"]
    # shares must add up to 100 for paid
    r = await api.put(
        f"/tests/{tid}/platforms",
        [
            {"code": "facebook", "placements": ["feed"], "budget_share": 70},
            {"code": "instagram", "placements": ["feed"], "budget_share": 40},
        ],
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "budget_shares_invalid"
    # unknown placement
    r = await api.put(
        f"/tests/{tid}/platforms", [{"code": "facebook", "placements": ["banner"], "budget_share": 100}]
    )
    assert r.status_code == 422
    # planned/unknown platform refused
    r = await api.put(f"/tests/{tid}/platforms", [{"code": "youtube", "placements": [], "budget_share": 100}])
    assert r.status_code == 422 and r.json()["error"]["code"] == "platform_not_available"
    r = await api.put(
        f"/tests/{tid}/platforms",
        [
            {"code": "facebook", "placements": ["feed"], "budget_share": 60},
            {"code": "instagram", "placements": ["feed"], "budget_share": 40},
        ],
    )
    assert r.status_code == 200
    # organic must not have a budget; paid/boosted need one
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "organic",
            "goal": "engagement",
            "budget_minor": 500,
            "currency": "USD",
            "schedule": {"observe_days": 3},
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "budget_not_allowed"
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "boosted",
            "goal": "engagement",
            "budget_minor": None,
            "currency": "USD",
            "schedule": {"days": 3},
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "budget_required"
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "organic",
            "goal": "engagement",
            "budget_minor": None,
            "currency": "USD",
            "schedule": {"observe_days": 9},
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] in ("schedule_invalid", "validation_error")
    # goal must be supported by the platform for the post type (boosted + sales is not on facebook)
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "boosted",
            "goal": "sales",
            "budget_minor": 1000,
            "currency": "USD",
            "schedule": {"days": 3},
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "goal_not_supported"
    # organic: budget shares ignored (set equal)
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "organic",
            "goal": "engagement",
            "budget_minor": None,
            "currency": "USD",
            "schedule": {"observe_days": 2},
        },
    )
    assert r.status_code == 200 and r.json()["budget_minor"] is None
    assert [p["budget_share"] for p in r.json()["platforms"]] == [50.0, 50.0]
    # start date in the past is rejected for paid
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "paid",
            "goal": "sales",
            "budget_minor": 1000,
            "currency": "USD",
            "schedule": {"days": 3, "start_date": "2020-01-01"},
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "schedule_invalid"


@pytest.mark.asyncio
async def test_confirm_spec_checks_and_warnings(api: Api) -> None:
    await api.register_and_login()
    # 1:1 image in stories (9:16) -> factual warning, organic with few followers -> warning, messages without message CTA
    profile = await api.create_profile(followers=20)
    test = await api.create_ready_test(
        tier="quick",
        post_type="organic",
        goal="engagement",
        budget_minor=None,
        profile_id=profile["id"],
        platforms=[{"code": "facebook", "placements": ["stories"], "budget_share": 100}],
    )
    tid = test["id"]
    r = await api.patch(
        f"/tests/{tid}", {"ad_copy": {"caption": "hello", "headline": "", "cta": "learn_more"}}
    )
    assert r.status_code == 200
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "paid",
            "goal": "messages",
            "budget_minor": 3000,
            "currency": "USD",
            "schedule": {"days": 3},
        },
    )
    assert r.status_code == 200
    r = await api.put(
        f"/tests/{tid}/platforms", [{"code": "facebook", "placements": ["stories"], "budget_share": 100}]
    )
    confirm = await api.confirm(tid)
    assert any(not sc["ok"] for sc in confirm["spec_checks"])
    assert any("message button" in w for w in confirm["warnings"])
    # organic + few followers
    r = await api.put(
        f"/tests/{tid}/post",
        {
            "post_type": "organic",
            "goal": "engagement",
            "budget_minor": None,
            "currency": "USD",
            "schedule": {"observe_days": 3},
        },
    )
    assert r.status_code == 200 and r.json()["status"] == "draft"  # editing after confirm returns to draft
    confirm = await api.confirm(tid)
    assert any("very small" in w for w in confirm["warnings"])
    # confirm fails without media
    r = await api.post("/tests", {"title": "empty", "country_code": "TH", "tier_code": "quick"})
    r = await api.post(f"/tests/{r.json()['id']}/confirm")
    assert r.status_code == 422 and "errors" in r.json()["error"]["details"]


@pytest.mark.asyncio
async def test_trial_rules(api: Api) -> None:
    # unverified account cannot use the trial
    user = await api.register_and_login(verify=False)
    me = (await api.get("/me")).json()
    assert me["email_verified"] is False and me["trial_available"] is False
    test = await api.create_ready_test(tier="standard", post_type="paid", goal="messages")
    await api.confirm(test["id"])
    r = await api.post(f"/tests/{test['id']}/pay/trial")
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"
    # verify via resend
    from app.services.email_service import get_mailer

    r = await api.post("/auth/resend-verification", {"email": user["email"]})
    token = get_mailer().last_to(user["email"]).headers["X-ADVAR-Token"]
    assert (await api.post("/auth/verify-email", {"token": token})).status_code == 200
    checkout = (await api.get(f"/tests/{test['id']}/checkout")).json()
    assert checkout["trial_available"] is True and "trial" in checkout["methods"]
    r = await api.post(f"/tests/{test['id']}/pay/trial")
    assert (
        r.status_code == 200
        and r.json()["test_status"] == "queued"
        and r.json()["payment"]["method"] == "trial"
    )
    # second trial refused
    test2 = await api.create_ready_test(tier="standard", post_type="paid", goal="sales")
    await api.confirm(test2["id"])
    r = await api.post(f"/tests/{test2['id']}/pay/trial")
    assert r.status_code == 409 and r.json()["error"]["code"] == "trial_not_available"
    assert (await api.get("/me")).json()["trial_available"] is False
    # trial only for the standard tier
    test3 = await api.create_ready_test(tier="quick", post_type="paid", goal="sales")
    await api.confirm(test3["id"])
    assert (await api.get(f"/tests/{test3['id']}/checkout")).json()["trial_available"] is False
    # a used trial token cannot be reused, invalid tokens rejected
    r = await api.post("/auth/verify-email", {"token": token})
    assert r.status_code == 400
    await run_pending_jobs()


@pytest.mark.asyncio
async def test_duplicate_blocks_checkout(api: Api) -> None:
    await api.register_and_login()
    test = await api.create_ready_test(tier="quick")
    await api.confirm(test["id"])
    await api.post(f"/tests/{test['id']}/pay/card")
    await run_pending_jobs()
    dup = (await api.post(f"/tests/{test['id']}/duplicate")).json()
    c = await api.confirm(dup["id"])
    assert c["duplicate"]["is_duplicate"] is True
    r = await api.get(f"/tests/{dup['id']}/checkout")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_test"
    r = await api.post(f"/tests/{dup['id']}/pay/card")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_test"
    # changing the caption makes it a different test
    r = await api.patch(
        f"/tests/{dup['id']}",
        {"ad_copy": {"caption": "different caption", "headline": "x", "cta": "send_message"}},
    )
    assert r.status_code == 200
    c = await api.confirm(dup["id"])
    assert c["duplicate"] is None or c["duplicate"]["is_duplicate"] is False
    assert "caption / headline / CTA" in c["changed_fields"]
    assert (await api.get(f"/tests/{dup['id']}/checkout")).status_code == 200


@pytest.mark.asyncio
async def test_ownership_and_auth_guards(api: Api, client) -> None:  # noqa: ANN001
    await api.register_and_login()
    test = await api.create_ready_test(tier="quick")
    other = Api(client)
    await other.register_and_login()
    r = await other.get(f"/tests/{test['id']}")
    assert r.status_code == 404
    r = await other.post(f"/tests/{test['id']}/confirm")
    assert r.status_code == 404
    r = await client.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    r = await other.get("/admin/metrics")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    # refresh cookie rotation
    r = await client.post(
        "/api/v1/auth/login", json={"email": (await api.get("/me")).json()["email"], "password": "secret123"}
    )
    assert r.status_code == 200
    cookie = r.cookies.get("advar_refresh")
    assert cookie
    r2 = await client.post("/api/v1/auth/refresh", cookies={"advar_refresh": cookie})
    assert r2.status_code == 200 and r2.json()["access_token"]
    r3 = await client.post("/api/v1/auth/refresh", cookies={"advar_refresh": cookie})
    assert r3.status_code == 401  # rotated token cannot be reused


@pytest.mark.asyncio
async def test_rate_limits(api: Api, client) -> None:  # noqa: ANN001
    for _ in range(10):
        await client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-pass1"}
        )
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-pass1"}
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    for _ in range(5):
        await client.post(
            "/api/v1/auth/register",
            json={"email": f"rl-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"},
        )
    r = await client.post(
        "/api/v1/auth/register", json={"email": "rl-last@example.com", "password": "secret123"}
    )
    assert r.status_code == 429
