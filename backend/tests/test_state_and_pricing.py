"""Unit tests: state machine, pricing, trial rules, e-mail normalisation, fx display, fingerprint."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.errors import ApiError, ErrorCode
from app.models import AdAsset, AdTest, Price
from app.services import fingerprint as fp
from app.services import fx, test_state
from app.services.auth_service import normalize_email
from app.services.pricing import compute_total


def _test(status: str = "draft") -> AdTest:
    return AdTest(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        status=status,
        tier_code="standard",
        country_code="TH",
        post_type="paid",
        goal="sales",
        platforms=[],
        schedule={},
        audiences=[],
        ad_copy={},
        settings_versions={},
        cancel_count=0,
    )


def test_state_machine_allowed_transitions() -> None:
    t = _test("draft")
    test_state.transition(t, "awaiting_payment")
    test_state.transition(t, "queued")
    assert t.queued_at is not None and t.cancel_window_open is True
    test_state.transition(t, "running")
    test_state.transition(t, "draft")  # user cancel inside the window
    test_state.transition(t, "queued")  # prepaid restart
    test_state.transition(t, "running")
    test_state.transition(t, "completed")
    assert t.finished_at is not None and t.cancel_window_open is False
    test_state.transition(t, "refunded")


def test_state_machine_rejects_invalid_transitions() -> None:
    t = _test("draft")
    with pytest.raises(ApiError) as exc:
        test_state.transition(t, "running")
    assert exc.value.code == ErrorCode.invalid_state
    t = _test("completed")
    with pytest.raises(ApiError):
        test_state.transition(t, "draft")
    t = _test("payment_review")
    test_state.transition(t, "awaiting_payment")  # cancel / expiry
    test_state.transition(t, "payment_review")
    test_state.transition(t, "queued")  # admin approve
    assert test_state.can_transition("failed", "queued") and not test_state.can_transition(
        "failed", "running"
    )


def test_pricing_with_extra_platforms() -> None:
    prices = {
        "standard": Price(tier_code="standard", currency="USD", amount_minor=1200, extra_platform_minor=600),
        "quick": Price(tier_code="quick", currency="USD", amount_minor=500, extra_platform_minor=600),
        "extra_platform": Price(
            tier_code="extra_platform", currency="USD", amount_minor=600, extra_platform_minor=0
        ),
    }
    assert compute_total(prices, "standard", 1)["total_usd_minor"] == 1200
    assert compute_total(prices, "standard", 2)["total_usd_minor"] == 1800
    assert compute_total(prices, "quick", 3)["total_usd_minor"] == 500 + 2 * 600
    with pytest.raises(ApiError):
        compute_total(prices, "unknown", 1)


def test_email_normalisation() -> None:
    assert normalize_email("Foo.Bar+trial@Gmail.com") == "foobar@gmail.com"
    assert normalize_email("foo.bar@googlemail.com") == "foobar@gmail.com"
    assert normalize_email("Someone+tag@Example.org") == "someone@example.org"
    assert normalize_email("keep.dots@example.org") == "keep.dots@example.org"


def test_fx_conversion_and_display() -> None:
    assert fx.format_money(1200, "USD") == "$12.00"
    assert fx.format_money(42000, "THB") == "฿420.00"
    assert fx.format_money(25200, "MMK") == "K25,200"
    thb = fx.convert_usd_minor(1200, Decimal("33.5"), "THB")
    assert thb == 40200  # 12 USD * 33.5 = 402.00 THB in satang
    mmk = fx.convert_usd_minor(1200, Decimal("2100"), "MMK")
    assert mmk == 25200 and mmk % 100 == 0  # friendly rounding to 100 kyat
    assert fx.minor_units("MMK") == 1 and fx.minor_units("THB") == 100


def _asset(sha: str) -> AdAsset:
    return AdAsset(
        id=uuid.uuid4(),
        ad_test_id=uuid.uuid4(),
        kind="image",
        storage_key="k",
        mime="image/jpeg",
        sha256=sha,
        size_bytes=1,
        meta={},
    )


def test_fingerprint_stability_and_sensitivity() -> None:
    t = _test()
    t.ad_copy = {"caption": "  Hello   world ", "headline": "H", "cta": "shop_now"}
    t.platforms = [
        {"code": "tiktok", "placements": ["in_feed"], "budget_share": 40, "settings_version": 1},
        {"code": "facebook", "placements": ["feed"], "budget_share": 60, "settings_version": 1},
    ]
    t.budget_minor = 6000
    t.currency = "USD"
    t.schedule = {"days": 3, "start_date": "2026-10-03"}
    t.profile_snapshot = {"followers": 10, "_preset_name": "x"}
    assets = [_asset("b" * 64), _asset("a" * 64)]
    f1, p1 = fp.fingerprint(t, assets, "1.2.0")
    # order of platforms / assets and whitespace in the caption do not matter
    t.platforms = list(reversed(t.platforms))
    t.ad_copy = {"caption": "hello world", "headline": "h", "cta": "SHOP_NOW"}
    f2, _ = fp.fingerprint(t, list(reversed(assets)), "1.2.0")
    assert f1 == f2
    # a changed field changes the fingerprint and is reported
    t.post_type = "organic"
    t.budget_minor = None
    f3, p3 = fp.fingerprint(t, assets, "1.2.0")
    assert f3 != f1
    assert fp.changed_fields(p1, p3) == ["post type or goal", "budget"]
    # engine version only
    t.post_type, t.budget_minor = "paid", 6000
    f4, p4 = fp.fingerprint(t, assets, "1.3.0")
    assert f4 != f1 and fp.changed_fields(p1, p4) == ["engine version"]
