"""Admin settings: versions (draft/publish/rollback), tests record versions, sandbox, AI category
draft with the mock LLM, new country creation, app settings, users, metrics, admin tests."""

from __future__ import annotations

import pytest

from tests.conftest import Api, run_pending_jobs


@pytest.mark.asyncio
async def test_country_versions_publish_rollback_and_tests_record_versions(api: Api, client) -> None:  # noqa: ANN001
    admin = Api(client)
    await admin.login_admin()
    # current published TH version is 1
    th = (await admin.get("/admin/countries/TH")).json()
    assert th["current_version"] == 1 and th["versions"][0]["status"] == "published"
    # editing the published version creates draft v2
    data = (await admin.get("/admin/countries/TH/versions")).json()[0]["data"]
    data["culture"]["sponsored_skepticism"] = 0.9
    r = await admin.put("/admin/countries/TH", {"data": data, "change_note": "more skeptical"})
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["status"] == "draft"
    draft_id = r.json()["id"]
    # drafts are not used by customer tests: the public endpoint still shows v1
    assert next(c for c in (await api.get("/countries")).json() if c["code"] == "TH")["version"] == 1
    # a customer test confirmed now records version 1
    await api.register_and_login()
    t1 = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    c1 = await api.confirm(t1["id"])
    assert c1["summary"]["settings_versions"]["country"] == {"code": "TH", "version": 1}
    # sandbox run compares draft vs published
    r = await admin.post(
        "/admin/sandbox/run",
        {
            "sample": "sample_test.json",
            "runs": 6,
            "agents": 1500,
            "use_drafts": True,
            "platform_codes": ["facebook"],
        },
    )
    assert r.status_code == 200, r.text
    sb = r.json()
    assert (
        sb["draft_versions"]["country"]["version"] == 2
        and sb["published_versions"]["country"]["version"] == 1
    )
    assert sb["comparison"] and "facebook" in sb["draft_result"]["platforms"]
    # publish v2 -> new tests use it
    r = await admin.post(f"/admin/settings/countries/{draft_id}/publish", {"change_note": "go live"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await admin.get("/admin/countries/TH")).json()["current_version"] == 2
    t2 = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    c2 = await api.confirm(t2["id"])
    assert c2["summary"]["settings_versions"]["country"] == {"code": "TH", "version": 2}
    # run t2 and check the stored versions on the completed test
    await api.post(f"/tests/{t2['id']}/pay/card")
    await run_pending_jobs()
    t = (await api.get(f"/tests/{t2['id']}")).json()
    assert t["status"] == "completed" and t["settings_versions"]["country"]["version"] == 2
    # rollback to v1
    r = await admin.post("/admin/settings/countries/TH/rollback", {"change_note": "revert"})
    assert r.status_code == 200 and r.json()["version"] == 1 and r.json()["status"] == "published"
    versions = (await admin.get("/admin/countries/TH")).json()["versions"]
    assert {v["version"]: v["status"] for v in versions} == {1: "published", 2: "archived"}
    # publishing an archived version is refused; rollback to it works
    r = await admin.post(f"/admin/settings/countries/{draft_id}/publish")
    assert r.status_code == 409
    r = await admin.post("/admin/settings/countries/TH/rollback", {"to_version": 2})
    assert r.status_code == 200 and r.json()["version"] == 2
    # back to v1 so other tests see the seed values
    await admin.post("/admin/settings/countries/TH/rollback", {"to_version": 1})


@pytest.mark.asyncio
async def test_new_country_and_ai_category_draft_publish_and_use(api: Api, client) -> None:  # noqa: ANN001
    admin = Api(client)
    await admin.login_admin()
    # new country (draft) -> publish -> visible
    th_data = (await admin.get("/admin/countries/TH/versions")).json()[0]["data"]
    r = await admin.post(
        "/admin/countries",
        {
            "code": "vn",
            "name": "Vietnam",
            "currency": "VND",
            "payment_methods": ["card"],
            "data": th_data,
            "change_note": "new market",
        },
    )
    assert r.status_code == 201 and r.json()["code"] == "VN" and r.json()["status"] == "draft"
    assert all(c["code"] != "VN" for c in (await api.get("/countries")).json())
    r = await admin.post(f"/admin/settings/countries/{r.json()['id']}/publish")
    assert r.status_code == 200
    assert any(c["code"] == "VN" for c in (await api.get("/countries")).json())
    # AI draft with the mock LLM
    r = await admin.post(
        "/admin/categories/draft-ai", {"name": "Yoga studio", "hints": "classes, memberships"}
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["code"] == "yoga_studio"
    assert any(q["key"] == "followers" for q in draft["data"]["questions"])
    assert draft["data"]["trait_dimensions"][0]["kind"] == "vector"
    assert all(c["code"] != "yoga_studio" for c in (await api.get("/categories")).json())
    # sandbox on the draft category
    r = await admin.post(
        "/admin/sandbox/run",
        {
            "sample": "sample_test.json",
            "runs": 6,
            "agents": 1500,
            "use_drafts": True,
            "category_code": "yoga_studio",
            "platform_codes": ["facebook"],
        },
    )
    assert r.status_code == 200 and r.json()["draft_versions"]["category"]["code"] == "yoga_studio"
    # publish and use in a customer profile + test
    r = await admin.post(f"/admin/settings/categories/{draft['id']}/publish", {"change_note": "publish yoga"})
    assert r.status_code == 200
    cat = (await api.get("/categories/yoga_studio")).json()
    assert cat["status"] == "published" and cat["version"] == 1
    await api.register_and_login()
    slider_key = next(q["key"] for q in cat["questions"] if q["type"] == "sliders")
    mix_key = next(q["options"][0] for q in cat["questions"] if q["key"] == "customer_mix")
    data = {
        "business_name": "Om Studio",
        "what_you_sell": "yoga classes",
        "price_level": "mid",
        slider_key: {},
        "customer_mix": mix_key,
        "followers": 300,
    }
    r = await api.post("/profiles", {"name": "Yoga", "category_code": "yoga_studio", "data": data})
    assert r.status_code == 201, r.text
    test = await api.create_ready_test(
        tier="quick",
        profile_id=r.json()["id"],
        platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
    )
    c = await api.confirm(test["id"])
    assert c["summary"]["settings_versions"]["category"] == {"code": "yoga_studio", "version": 1}
    await api.post(f"/tests/{test['id']}/pay/card")
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    report = (await api.get(f"/tests/{test['id']}/report")).json()
    assert report["settings_versions"]["category"]["code"] == "yoga_studio" and report["reasons"]
    # invalid category data is rejected
    r = await admin.post(
        "/admin/categories",
        {"code": "bad", "name": "Bad", "data": {"questions": [{"key": "x", "label": "X", "type": "select"}]}},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "settings_version_invalid"


@pytest.mark.asyncio
async def test_weights_scenarios_platforms_and_app_settings(api: Api, client) -> None:  # noqa: ANN001
    admin = Api(client)
    await admin.login_admin()
    w = (await admin.get("/admin/weights")).json()
    assert w["version"] == 2 and w["status"] == "published" and "sales" in w["score_by_goal"]
    r = await admin.put(
        "/admin/weights",
        {
            "behavior": {**w["behavior"], "w_hook": 2.5},
            "score_by_goal": w["score_by_goal"],
            "change_note": "stronger hook",
            "publish": False,
        },
    )
    assert r.status_code == 200 and r.json()["version"] == 2  # draft v3 exists, published still v2
    assert any(v["version"] == 3 and v["status"] == "draft" for v in r.json()["versions"])
    # scenarios: create draft + publish, then it is used for matching tests
    r = await admin.post(
        "/admin/scenarios",
        {
            "code": "heatwave_th",
            "name": "Heatwave (TH)",
            "data": {
                "modifiers": {"mood": -0.2, "activity": 1.1},
                "country_codes": ["TH"],
                "date_rules": {"months": [4, 5]},
                "weight": 0.99,
                "active": True,
            },
        },
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await admin.get(f"/admin/scenarios/{sid}")
    assert r.status_code == 200 and r.json()["status"] == "draft"
    r = await admin.put(f"/admin/scenarios/{sid}", {"data": {"weight": 0.98}, "change_note": "tweak"})
    assert r.status_code == 200 and r.json()["data"]["weight"] == 0.98
    r = await admin.post(f"/admin/settings/scenarios/{sid}/publish")
    assert r.status_code == 200
    assert any(
        s["code"] == "heatwave_th" and s["status"] == "published"
        for s in (await admin.get("/admin/scenarios")).json()
    )
    # platform status change + new settings version
    r = await admin.put("/admin/platforms/tiktok", {"status": "full", "change_note": "pilot compared"})
    assert r.status_code == 200 and r.json()["status"] == "full"
    assert next(p for p in (await api.get("/platforms")).json() if p["code"] == "tiktok")["status"] == "full"
    versions = (await admin.get("/admin/platforms/tiktok/versions")).json()
    g = versions[0]["data"]["global"]
    g["organic"]["reach_rate_of_followers"] = 0.2
    r = await admin.put("/admin/platforms/tiktok", {"global": g, "change_note": "more organic reach"})
    assert r.status_code == 200 and any(
        v["status"] == "draft" and v["version"] == 2 for v in r.json()["versions"]
    )
    r = await admin.put("/admin/platforms/tiktok", {"status": "beta"})
    assert r.json()["status"] == "beta"
    # app settings
    r = await admin.get("/admin/settings")
    assert r.status_code == 200 and "manual_payment" in r.json()["values"]
    r = await admin.put(
        "/admin/settings",
        {
            "values": {
                "social_links": {
                    "facebook": "https://www.facebook.com/example-advar-page",
                    "telegram": "https://t.me/example_advar",
                }
            },
            "change_note": "links",
        },
    )
    assert (
        r.status_code == 200
        and r.json()["values"]["social_links"]["telegram"] == "https://t.me/example_advar"
    )
    r = await admin.put("/admin/settings", {"values": {"not_a_key": 1}})
    assert r.status_code == 422
    # prices
    r = await admin.put(
        "/admin/prices",
        {"items": [{"tier_code": "quick", "amount_minor": 700}], "change_note": "quick price"},
    )
    assert (
        r.status_code == 200
        and next(i for i in r.json()["items"] if i["tier_code"] == "quick")["amount_minor"] == 700
    )
    assert next(t for t in (await api.get("/tiers")).json() if t["code"] == "quick")["price_usd_minor"] == 700
    await admin.put(
        "/admin/prices", {"items": [{"tier_code": "quick", "amount_minor": 500}], "change_note": "back"}
    )
    # fx rates listing
    rates = (await admin.get("/admin/fx-rates")).json()
    assert {r["currency"] for r in rates} >= {"THB", "MMK"}


@pytest.mark.asyncio
async def test_admin_users_tests_metrics(api: Api, client) -> None:  # noqa: ANN001
    user = await api.register_and_login()
    test = await api.create_ready_test(
        tier="quick", platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}]
    )
    await api.confirm(test["id"])
    await api.post(f"/tests/{test['id']}/pay/card")
    await run_pending_jobs()
    admin = Api(client)
    await admin.login_admin()
    users = (await admin.get(f"/admin/users?q={user['email']}")).json()["items"]
    assert len(users) == 1 and users[0]["tests_count"] == 1 and users[0]["is_blocked"] is False
    r = await admin.patch(f"/admin/users/{users[0]['id']}", {"is_blocked": True})
    assert r.json()["is_blocked"] is True
    assert (await api.get("/me")).status_code == 403
    r = await admin.patch(f"/admin/users/{users[0]['id']}", {"is_blocked": False, "reset_trial": True})
    assert r.json()["is_blocked"] is False and r.json()["trial_used"] is False
    tests = (await admin.get(f"/admin/tests?user_email={user['email']}")).json()["items"]
    assert tests[0]["status"] == "completed" and tests[0]["cost_usd"] >= 0
    detail = (await admin.get(f"/admin/tests/{test['id']}")).json()
    assert [s["status"] for s in detail["stages"]] == ["done"] * 8
    assert (
        detail["llm_calls"] > 0
        and detail["payment"]["status"] == "succeeded"
        and detail["settings_versions"]["weights"] == 2
    )
    assert any(a["action"] == "test.completed" for a in detail["audit"])
    r = await admin.post(f"/admin/tests/{test['id']}/rerun")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    metrics = (await admin.get("/admin/metrics")).json()
    assert (
        metrics["completed_tests"] >= 1
        and "stripe" in metrics["revenue_by_method"]
        and metrics["llm_daily_cap_usd"] == 50
    )
    payments = (await admin.get("/admin/payments?status=succeeded")).json()["items"]
    assert payments and payments[0]["user_email"]
