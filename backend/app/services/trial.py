"""Free trial rules: one Standard trial per verified account, IP/device soft limits, feature switch."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import TrialGrant, User
from app.security import now_utc
from app.services import settings_service


async def trial_used(db: AsyncSession, user_id) -> bool:  # noqa: ANN001
    res = await db.execute(select(func.count()).select_from(TrialGrant).where(TrialGrant.user_id == user_id))
    return int(res.scalar_one() or 0) > 0


async def eligibility(db: AsyncSession, user: User, tier_code: str | None = None) -> tuple[bool, str | None]:
    """(eligible, reason_when_not)."""
    if not bool(await settings_service.get(db, "trial_enabled", True)):
        return False, "trial_disabled"
    if user.email_verified_at is None:
        return False, "email_not_verified"
    if await trial_used(db, user.id):
        return False, "trial_used"
    trial_tier = str(await settings_service.get(db, "trial_tier", "standard"))
    if tier_code and tier_code != trial_tier:
        return False, f"trial_only_{trial_tier}"
    return True, None


async def limits_exceeded(db: AsyncSession, ip: str | None, device_hash: str | None) -> bool:
    """Soft limits: too many trials from one IP or device in 24 h -> review required."""
    since = now_utc() - timedelta(days=1)
    ip_limit = int(await settings_service.get(db, "trial_ip_limit_per_day", 3))
    dev_limit = int(await settings_service.get(db, "trial_device_limit_per_day", 2))
    if ip:
        res = await db.execute(
            select(func.count())
            .select_from(TrialGrant)
            .where(TrialGrant.ip == ip, TrialGrant.granted_at >= since)
        )
        if int(res.scalar_one() or 0) >= ip_limit:
            return True
    if device_hash:
        res = await db.execute(
            select(func.count())
            .select_from(TrialGrant)
            .where(TrialGrant.device_hash == device_hash, TrialGrant.granted_at >= since)
        )
        if int(res.scalar_one() or 0) >= dev_limit:
            return True
    return False


async def grant(
    db: AsyncSession, user: User, ad_test_id, ip: str | None, device_hash: str | None
) -> TrialGrant:  # noqa: ANN001
    ok, reason = await eligibility(db, user)
    if not ok:
        if reason == "email_not_verified":
            raise ApiError(ErrorCode.email_not_verified, "Verify your e-mail to use the free trial")
        raise ApiError(
            ErrorCode.trial_not_available, f"Free trial not available ({reason})", details={"reason": reason}
        )
    if await limits_exceeded(db, ip, device_hash):
        raise ApiError(
            ErrorCode.trial_review_required,
            "Too many trials from this network or device; contact support",
            details={"reason": "limits"},
        )
    row = TrialGrant(
        user_id=user.id, ad_test_id=ad_test_id, ip=ip, device_hash=device_hash, granted_at=now_utc()
    )
    db.add(row)
    await db.flush()
    return row


async def reset_for_user(db: AsyncSession, user_id) -> int:  # noqa: ANN001
    res = await db.execute(select(TrialGrant).where(TrialGrant.user_id == user_id))
    rows = list(res.scalars().all())
    for r in rows:
        await db.delete(r)
    await db.flush()
    return len(rows)
