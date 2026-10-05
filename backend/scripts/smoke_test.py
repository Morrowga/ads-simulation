"""End-to-end smoke test against a running stack (LLM_PROVIDER=mock, PAYMENT_MODE=mock).

    python -m scripts.smoke_test            # inside the api container (make smoke)

Flow (acceptance checklist item 7): register -> verification e-mail from the Mailpit API -> verify ->
login -> create profile (restaurant) -> create test -> post type paid + goal messages -> upload sample
image -> platforms facebook 60 / tiktok 40 -> confirm -> pay by card (mock) -> SSE: stage, run_batch and
completed events -> report with reasons and evidence -> PDF URL -> duplicate reported as duplicate ->
duplicate as organic (no budget), run, compare -> Myanmar test: card not offered, manual offered,
manual order, admin approve by payment code -> completed.

Environment: SMOKE_API_URL (default http://localhost:8000), SMOKE_MAILPIT_URL (default http://mailpit:8025),
SMOKE_TIER (default quick; use standard for the full 150-run pipeline), SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD.
Prints PASS or FAIL and exits with 0 / 1.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

API = os.environ.get("SMOKE_API_URL", "http://localhost:8000").rstrip("/") + os.environ.get(
    "API_PREFIX", "/api/v1"
)
MAILPIT = os.environ.get("SMOKE_MAILPIT_URL", "http://mailpit:8025").rstrip("/")
TIER = os.environ.get("SMOKE_TIER", "quick")
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@advar.local")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "admin12345")
SAMPLE_IMAGE = Path(__file__).resolve().parent.parent / "samples" / "sample_ad.jpg"
RUN_TIMEOUT = int(os.environ.get("SMOKE_RUN_TIMEOUT", "900"))


class Smoke:
    def __init__(self) -> None:
        self.c = httpx.Client(timeout=60)
        self.token: str | None = None
        self.steps: list[str] = []

    # ------------------------------------------------------------------ helpers
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def req(self, method: str, path: str, ok: tuple[int, ...] = (200, 201), **kw: Any) -> Any:
        r = self.c.request(method, API + path, headers=self.h(), **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        return r.json() if r.content else None

    def step(self, name: str) -> None:
        self.steps.append(name)
        print(f"  ok  {name}", flush=True)

    def expect(self, cond: bool, msg: str) -> None:
        if not cond:
            raise RuntimeError(f"expectation failed: {msg}")

    def mailpit_token(self, email: str, kind: str = "verify") -> str:
        """Read the verification token from the Mailpit API (the e-mail carries an X-ADVAR-Token header and the link)."""
        deadline = time.time() + 30
        while time.time() < deadline:
            r = self.c.get(f"{MAILPIT}/api/v1/search", params={"query": f"to:{email}", "limit": 20})
            if r.status_code == 200:
                for msg in r.json().get("messages", []):
                    detail = self.c.get(f"{MAILPIT}/api/v1/message/{msg['ID']}").json()
                    headers_r = self.c.get(f"{MAILPIT}/api/v1/message/{msg['ID']}/headers")
                    headers = headers_r.json() if headers_r.status_code == 200 else {}
                    kinds = headers.get("X-Advar-Kind") or headers.get("X-ADVAR-Kind") or []
                    tokens = headers.get("X-Advar-Token") or headers.get("X-ADVAR-Token") or []
                    if tokens and (not kinds or kinds[0] == kind):
                        return tokens[0]
                    text = detail.get("Text", "") or ""
                    marker = "Verification token: " if kind == "verify" else "Reset token: "
                    if marker in text:
                        return text.split(marker, 1)[1].split()[0].strip()
            time.sleep(1)
        raise RuntimeError(f"no {kind} e-mail for {email} found in Mailpit at {MAILPIT}")

    def wait_for_status(
        self, test_id: str, wanted: tuple[str, ...], timeout: int = RUN_TIMEOUT
    ) -> dict[str, Any]:
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            t = self.req("GET", f"/tests/{test_id}")
            if t["status"] in wanted:
                return t
            if t["status"] == "failed":
                raise RuntimeError(f"test failed: {t.get('error')}")
            if t["status"] != last:
                print(
                    f"       status={t['status']} stage={t['progress'].get('stage')} pct={t['progress'].get('pct')}",
                    flush=True,
                )
                last = t["status"]
            time.sleep(2)
        raise RuntimeError(f"timeout waiting for {wanted}; last={last}")

    def stream_events(self, test_id: str, timeout: int = RUN_TIMEOUT) -> dict[str, list[dict[str, Any]]]:
        token = self.req("POST", f"/tests/{test_id}/progress/token")["stream_token"]
        seen: dict[str, list[dict[str, Any]]] = {}
        deadline = time.time() + timeout
        with self.c.stream(
            "GET",
            f"{API}/tests/{test_id}/progress",
            params={"st": token},
            timeout=httpx.Timeout(timeout, read=60),
        ) as r:
            self.expect(r.status_code == 200, f"SSE status {r.status_code}")
            event, data = None, ""
            for line in r.iter_lines():
                if time.time() > deadline:
                    break
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data += line.split(":", 1)[1].strip()
                elif line == "":
                    if event:
                        try:
                            payload = json.loads(data) if data else {}
                        except json.JSONDecodeError:
                            payload = {"raw": data}
                        seen.setdefault(event, []).append(payload)
                        if event == "stage":
                            print(
                                f"       stage {payload.get('stage')} {payload.get('pct')}% cancel_window={payload.get('cancel_window')}",
                                flush=True,
                            )
                        elif event == "run_batch":
                            print(
                                f"       run_batch {payload.get('runs_done')}/{payload.get('runs_target')} {payload.get('platform')}",
                                flush=True,
                            )
                        if event in ("completed", "failed", "cancelled"):
                            break
                    event, data = None, ""
        return seen

    # ------------------------------------------------------------------ flow
    def wait_for_api(self, timeout: int = 180) -> dict[str, Any]:
        """The api container installs requirements and runs migrations on start: wait for it."""
        deadline = time.time() + timeout
        last = "no response"
        while time.time() < deadline:
            try:
                r = self.c.get(API + "/health", timeout=10)
                if r.status_code == 200 and r.json().get("ok"):
                    return r.json()
                last = f"{r.status_code} {r.text[:120]}"
            except httpx.HTTPError as exc:
                last = exc.__class__.__name__
            time.sleep(3)
        raise RuntimeError(f"API not healthy after {timeout}s: {last}")

    def run(self) -> None:
        health = self.wait_for_api()
        self.expect(health["db"] and health["redis"], f"health {health}")
        self.expect(
            health["payment_mode"] == "mock" and health["llm_provider"] == "mock",
            "smoke needs PAYMENT_MODE=mock and LLM_PROVIDER=mock",
        )
        self.step(f"health ok (env={health['env']})")

        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        password = "smoke-pass-123"
        self.req(
            "POST",
            "/auth/register",
            json={"email": email, "password": password, "name": "Smoke", "country": "TH"},
        )
        token = self.mailpit_token(email)
        self.req("POST", "/auth/verify-email", json={"token": token})
        self.step("registered and verified via Mailpit")
        login = self.req("POST", "/auth/login", json={"email": email, "password": password})
        self.token = login["access_token"]
        me = self.req("GET", "/me")
        self.expect(me["email_verified"] is True, "email verified")
        self.step("logged in")

        profile = self.req(
            "POST",
            "/profiles",
            json={
                "name": "Smoke restaurant",
                "category_code": "restaurant",
                "data": {
                    "business_name": "Smoke Grill",
                    "cuisine": "thai",
                    "what_you_sell": "charcoal-grilled seafood",
                    "price_level": "mid",
                    "taste_profile": {"spice": 0.7, "sweet": 0.3, "sour": 0.6, "adventurousness": 0.5},
                    "customer_mix": "locals_mostly",
                    "customer_languages": ["th", "en"],
                    "followers": 1800,
                    "review_count": 140,
                    "rating": 4.4,
                    "months_in_business": 30,
                },
            },
        )
        self.step("profile created")

        test = self.req(
            "POST",
            "/tests",
            json={
                "title": "Smoke weekend promo",
                "country_code": "TH",
                "tier_code": TIER,
                "ad_copy": {
                    "caption": "สุดสัปดาห์นี้ ลด 20% ทักแชทจองโต๊ะได้เลย",
                    "headline": "20% off this weekend",
                    "cta": "send_message",
                },
                "audiences": [
                    {
                        "name": "Locals",
                        "targeting": {
                            "age_min": 18,
                            "age_max": 45,
                            "interests": ["food"],
                            "audience_size": 180000,
                        },
                    }
                ],
            },
        )
        tid = test["id"]
        self.req("PUT", f"/tests/{tid}/profile", json={"profile_id": profile["id"], "mode": "preset"})
        self.req(
            "PUT",
            f"/tests/{tid}/post",
            json={
                "post_type": "paid",
                "goal": "messages",
                "budget_minor": 6000,
                "currency": "USD",
                "schedule": {"days": 3},
            },
        )
        with SAMPLE_IMAGE.open("rb") as fh:
            asset = self.req("POST", f"/tests/{tid}/assets", files={"file": ("ad.jpg", fh, "image/jpeg")})
        self.expect(asset["kind"] == "image" and asset["width"] == 1080, "asset processed")
        self.req(
            "PUT",
            f"/tests/{tid}/platforms",
            json=[
                {"code": "facebook", "placements": ["feed"], "budget_share": 60},
                {"code": "tiktok", "placements": ["in_feed"], "budget_share": 40},
            ],
        )
        self.step("test created: paid, goal messages, image, facebook 60 / tiktok 40")

        confirm = self.req("POST", f"/tests/{tid}/confirm")
        self.expect(confirm["status"] == "awaiting_payment" and confirm["duplicate"] is None, "confirm")
        self.step(f"confirmed (price {confirm['price']['display']}, warnings={len(confirm['warnings'])})")
        checkout = self.req("GET", f"/tests/{tid}/checkout")
        self.expect(checkout["payment_mode"] == "mock" and "card" in checkout["methods"], "checkout")
        pay = self.req("POST", f"/tests/{tid}/pay/card")
        self.expect(
            pay["mode"] == "mock" and pay["status"] == "succeeded" and pay["test_status"] == "queued",
            "mock card payment",
        )
        self.step("paid by card (mock, no payment)")

        events = self.stream_events(tid)
        self.expect("stage" in events, "stage events received")
        self.expect("run_batch" in events, "run_batch events received")
        self.expect("completed" in events, f"completed event received (got {list(events)})")
        self.step(
            f"SSE: {len(events.get('stage', []))} stage, {len(events.get('run_batch', []))} run_batch, {len(events.get('comment', []))} comment, completed"
        )
        t = self.wait_for_status(tid, ("completed",), timeout=60)
        self.expect(t["score"] is not None, "score set")

        report = self.req("GET", f"/tests/{tid}/report")
        self.expect(
            len(report["reasons"]) > 0 and len(report["evidence"]) > 0, "report has reasons and evidence"
        )
        self.expect(report["headline_metric"]["metric"] == "messages", "headline metric is messages")
        self.expect(all(r["evidence_ids"] for r in report["reasons"]), "every reason cites evidence")
        pdf = self.req("GET", f"/tests/{tid}/report.pdf")
        self.expect(pdf["url"].startswith("http"), "pdf url")
        self.step(
            f"report: score {t['score']}, {len(report['reasons'])} reasons, {len(report['evidence'])} evidence, pdf url ok"
        )

        dup = self.req("POST", f"/tests/{tid}/duplicate")
        c2 = self.req("POST", f"/tests/{dup['id']}/confirm")
        self.expect(
            c2["duplicate"] is not None and c2["duplicate"]["is_duplicate"] is True, "duplicate detected"
        )
        self.step("duplicate reported as duplicate")

        dup2 = self.req("POST", f"/tests/{tid}/duplicate")
        self.req(
            "PUT",
            f"/tests/{dup2['id']}/post",
            json={
                "post_type": "organic",
                "goal": "engagement",
                "budget_minor": None,
                "currency": "USD",
                "schedule": {"observe_days": 3},
            },
        )
        c3 = self.req("POST", f"/tests/{dup2['id']}/confirm")
        self.expect(
            not (c3["duplicate"] and c3["duplicate"]["is_duplicate"]), "organic variant is not a duplicate"
        )
        self.req("POST", f"/tests/{dup2['id']}/pay/card")
        self.wait_for_status(dup2["id"], ("completed",))
        cmp = self.req("GET", "/tests/compare", params={"a": tid, "b": dup2["id"]})
        self.expect(cmp["a"]["post_type"] == "paid" and cmp["b"]["post_type"] == "organic", "compare")
        self.step("organic duplicate ran; compare works")

        # Myanmar: manual payment
        self.req("PATCH", "/me", json={"country": "MM"})
        mm = self.req(
            "POST",
            "/tests",
            json={
                "title": "Smoke Myanmar",
                "country_code": "MM",
                "tier_code": TIER,
                "ad_copy": {"caption": "ဒီအပတ် ၂၀% လျှော့", "cta": "send_message"},
            },
        )
        mid = mm["id"]
        self.req("PUT", f"/tests/{mid}/profile", json={"profile_id": profile["id"], "mode": "preset"})
        self.req(
            "PUT",
            f"/tests/{mid}/post",
            json={
                "post_type": "paid",
                "goal": "messages",
                "budget_minor": 2000,
                "currency": "USD",
                "schedule": {"days": 2},
            },
        )
        with SAMPLE_IMAGE.open("rb") as fh:
            self.req("POST", f"/tests/{mid}/assets", files={"file": ("ad.jpg", fh, "image/jpeg")})
        self.req(
            "PUT",
            f"/tests/{mid}/platforms",
            json=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
        )
        self.req("POST", f"/tests/{mid}/confirm")
        checkout = self.req("GET", f"/tests/{mid}/checkout")
        self.expect(
            "card" not in checkout["methods"] and "manual" in checkout["methods"],
            f"MM methods {checkout['methods']}",
        )
        r = self.c.post(f"{API}/tests/{mid}/pay/card", headers=self.h())
        self.expect(r.status_code == 403, "card refused for MM")
        order = self.req("POST", f"/tests/{mid}/pay/manual")
        self.expect(
            order["test_status"] == "payment_review"
            and order["local_currency"] == "MMK"
            and order["accounts"],
            "manual order",
        )
        self.step(f"Myanmar manual order {order['payment_code']} for {order['local_display']}")
        user_token = self.token
        admin_login = self.req("POST", "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        self.token = admin_login["access_token"]
        found = self.req("GET", "/admin/payments", params={"code": order["payment_code"]})["items"]
        self.expect(len(found) == 1, "admin finds the order by payment code")
        approved = self.req(
            "POST", f"/admin/payments/{found[0]['id']}/approve", json={"admin_reference": "smoke-tx"}
        )
        self.expect(approved["status"] == "succeeded", "approved")
        self.token = user_token
        events = self.stream_events(mid)
        self.expect("completed" in events, f"MM test completed (got {list(events)})")
        self.step("admin approved by payment code; Myanmar test completed")


def main() -> int:
    print(f"ADVAR smoke test against {API} (tier={TIER})")
    s = Smoke()
    try:
        s.run()
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL after {len(s.steps)} steps: {exc}")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
