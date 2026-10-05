"""Full happy path through the API: register -> profile -> test -> confirm -> pay (mock) -> run -> report."""

from __future__ import annotations

import json

import pytest

from tests.conftest import Api, run_pending_jobs


@pytest.mark.asyncio
async def test_full_happy_path(api: Api) -> None:
    user = await api.register_and_login()
    r = await api.get("/me")
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == user["email"] and me["email_verified"] is True and me["trial_available"] is True

    # config endpoints
    countries = (await api.get("/countries")).json()
    assert {c["code"] for c in countries} >= {"TH", "MM", "US"}
    th = next(c for c in countries if c["code"] == "TH")
    assert th["payment_methods"] == ["card"] and any(g["code"] == "my" for g in th["language_groups"])
    platforms = (await api.get("/platforms")).json()
    fb = next(p for p in platforms if p["code"] == "facebook")
    assert fb["status"] == "full" and "feed" in fb["ad_specs"] and fb["supported_goals"]["paid"]
    tiers = (await api.get("/tiers?country=TH&platforms=2")).json()
    std = next(t for t in tiers if t["code"] == "standard")
    assert std["price_usd_minor"] == 1200 and std["local"]["currency"] == "THB"
    cat = (await api.get("/categories/restaurant")).json()
    assert any(q["key"] == "taste_profile" for q in cat["questions"])

    test = await api.create_ready_test(tier="quick", post_type="paid", goal="messages")
    tid = test["id"]
    assert (
        test["status"] == "draft"
        and len(test["assets"]) == 1
        and test["profile"]["preset_name"] == "Main preset"
    )

    confirm = await api.confirm(tid)
    assert confirm["status"] == "awaiting_payment"
    assert confirm["duplicate"] is None
    assert confirm["price"]["total_usd_minor"] == 500 + 600
    assert confirm["summary"]["settings_versions"]["country"]["version"] == 1
    assert all(sc["ok"] is False or sc["ok"] is True for sc in confirm["spec_checks"])

    checkout = (await api.get(f"/tests/{tid}/checkout")).json()
    assert (
        checkout["payment_mode"] == "mock"
        and "card" in checkout["methods"]
        and "manual" not in checkout["methods"]
    )
    assert checkout["total_usd_minor"] == 1100 and checkout["local"]["currency"] == "THB"

    r = await api.post(f"/tests/{tid}/pay/card")
    assert r.status_code == 200, r.text
    pay = r.json()
    assert pay["mode"] == "mock" and pay["status"] == "succeeded" and pay["test_status"] == "queued"

    # stream token + snapshot work before the run
    r = await api.post(f"/tests/{tid}/progress/token")
    assert r.status_code == 200 and r.json()["stream_token"]
    snap = (await api.get(f"/tests/{tid}/progress/snapshot")).json()
    assert snap["status"] == "queued" and snap["cancel_window"] is True

    results = await run_pending_jobs()
    assert results and results[0]["ok"] is True, results

    t = (await api.get(f"/tests/{tid}")).json()
    assert t["status"] == "completed" and t["progress"]["pct"] == 100 and t["score"] is not None
    assert t["settings_versions"]["platforms"] == {"facebook": 1, "tiktok": 1}

    report = (await api.get(f"/tests/{tid}/report")).json()
    assert report["headline_metric"]["metric"] == "messages"
    assert report["reasons"], "reasons must not be empty"
    evidence_ids = {e["id"] for e in report["evidence"]}
    for reason in report["reasons"]:
        assert reason["evidence_ids"] and set(reason["evidence_ids"]) <= evidence_ids
        low = reason["statement"].lower()
        for banned in ("should", "need to", "recommend", "remove", " add ", " try "):
            assert banned not in f" {low} ", reason["statement"]
    assert {p["code"] for p in report["platforms"]} == {"facebook", "tiktok"}
    assert all(12 <= p["runs"] <= 20 for p in report["platforms"]), [p["runs"] for p in report["platforms"]]
    assert report["language_groups"] and all(g["code"] for g in report["language_groups"])
    assert report["pdf_available"] is True
    for c in report["comments"]:
        assert c["language_group"] and c["text"].isascii(), c

    pdf = (await api.get(f"/tests/{tid}/report.pdf")).json()
    assert pdf["url"].startswith("http")

    # payments history and snapshot after completion
    history = (await api.get("/payments")).json()
    assert history["items"][0]["status"] == "succeeded" and history["items"][0]["method"] == "stripe"
    snap = (await api.get(f"/tests/{tid}/progress/snapshot")).json()
    assert snap["status"] == "completed" and snap["pct"] == 100

    # list with cursor pagination
    lst = (await api.get("/tests?limit=1")).json()
    assert len(lst["items"]) == 1 and lst["items"][0]["id"] == tid

    # duplicate -> confirm reports it as a duplicate (same inputs, same engine)
    dup = (await api.post(f"/tests/{tid}/duplicate")).json()
    assert dup["status"] == "draft" and dup["parent_test_id"] == tid and len(dup["assets"]) == 1
    c2 = await api.confirm(dup["id"])
    assert (
        c2["duplicate"] is not None
        and c2["duplicate"]["is_duplicate"] is True
        and c2["duplicate"]["test_id"] == tid
    )

    # duplicate again, switch to organic (no budget), run it, compare
    dup2 = (await api.post(f"/tests/{tid}/duplicate")).json()
    r = await api.put(
        f"/tests/{dup2['id']}/post",
        {
            "post_type": "organic",
            "goal": "engagement",
            "budget_minor": None,
            "currency": "USD",
            "schedule": {"observe_days": 3},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["budget_minor"] is None
    c3 = await api.confirm(dup2["id"])
    assert (
        c3["duplicate"] is None or c3["duplicate"]["is_duplicate"] is False
    ) and "post type or goal" in c3["changed_fields"]
    r = await api.post(f"/tests/{dup2['id']}/pay/card")
    assert r.status_code == 200, r.text
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    cmp = (await api.get(f"/tests/compare?a={tid}&b={dup2['id']}")).json()
    assert cmp["a"]["post_type"] == "paid" and cmp["b"]["post_type"] == "organic"
    assert any("post type" in d for d in cmp["differences"])
    assert any(m["metric"] == "stop_rate" for m in cmp["metrics"])
    json.dumps(cmp)  # serialisable
