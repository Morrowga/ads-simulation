"""Ad test endpoints: CRUD, profile/platform/post settings, cancel, restart, duplicate."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.deps import DB, Client, CurrentUser, Page
from app.schemas.common import OkOut
from app.schemas.common import Page as PageOut
from app.schemas.tests import (
    CancelOut,
    PlatformSelectionIn,
    PostSettingsIn,
    ProfileAttachIn,
    ProfileRefOut,
    TestCreateIn,
    TestListItem,
    TestOut,
    TestUpdateIn,
)
from app.services import cancel as cancel_service
from app.services import profiles as profile_service
from app.services import serializers, tests_service

router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("", response_model=TestOut, status_code=201)
async def create_test(body: TestCreateIn, db: DB, user: CurrentUser) -> TestOut:
    test = await tests_service.create(
        db,
        user,
        title=body.title,
        country_code=body.country_code,
        tier_code=body.tier_code,
        ad_copy=body.ad_copy.model_dump(),
        audiences=[a.model_dump() for a in body.audiences],
    )
    return TestOut(**await serializers.test_out(db, test))


@router.get("", response_model=PageOut[TestListItem])
async def list_tests(
    db: DB, user: CurrentUser, page: Page, status: str | None = Query(default=None)
) -> PageOut[TestListItem]:
    rows, next_cursor = await tests_service.list_tests(db, user, page.cursor, page.limit, status)
    return PageOut[TestListItem](
        items=[TestListItem(**serializers.test_list_item(t)) for t in rows], next_cursor=next_cursor
    )


@router.get("/{test_id}", response_model=TestOut)
async def get_test(test_id: uuid.UUID, db: DB, user: CurrentUser) -> TestOut:
    test = await tests_service.get_owned(db, user, test_id)
    return TestOut(**await serializers.test_out(db, test))


@router.patch("/{test_id}", response_model=TestOut)
async def patch_test(test_id: uuid.UUID, body: TestUpdateIn, db: DB, user: CurrentUser) -> TestOut:
    patch = body.model_dump(exclude_unset=True)

    if set(patch.keys()) == {"title"} and patch["title"]:
        test = await tests_service.get_owned(db, user, test_id, for_update=True)
        test.title = patch["title"]
        return TestOut(**await serializers.test_out(db, test))

    if "ad_copy" in patch and patch["ad_copy"] is not None:
        patch["ad_copy"] = body.ad_copy.model_dump()
    if "audiences" in patch and patch["audiences"] is not None:
        patch["audiences"] = [a.model_dump() for a in body.audiences]
    test = await tests_service.update(db, user, test_id, patch)
    return TestOut(**await serializers.test_out(db, test))


@router.delete("/{test_id}", response_model=OkOut)
async def delete_test(test_id: uuid.UUID, db: DB, user: CurrentUser) -> OkOut:
    await tests_service.delete(db, user, test_id)
    return OkOut(message="Draft deleted")


@router.put("/{test_id}/profile", response_model=ProfileRefOut)
async def put_profile(test_id: uuid.UUID, body: ProfileAttachIn, db: DB, user: CurrentUser) -> ProfileRefOut:
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    tests_service.ensure_editable(test)
    ref = await profile_service.apply_test_profile(
        db,
        user,
        test,
        profile_id=body.profile_id,
        mode=body.mode,
        changes=body.changes,
        new_preset_name=body.new_preset_name,
    )
    tests_service._back_to_draft(test)
    snap = ref["snapshot"] or {}
    return ProfileRefOut(
        profile_id=ref["profile_id"],
        preset_name=ref["preset_name"],
        version=ref["version"],
        mode=ref["mode"],
        snapshot={k: v for k, v in snap.items() if not k.startswith("_")},
    )


@router.put("/{test_id}/platforms", response_model=TestOut)
async def put_platforms(
    test_id: uuid.UUID, body: list[PlatformSelectionIn], db: DB, user: CurrentUser
) -> TestOut:
    test = await tests_service.set_platforms(db, user, test_id, [p.model_dump() for p in body])
    return TestOut(**await serializers.test_out(db, test))


@router.put("/{test_id}/post", response_model=TestOut)
async def put_post(test_id: uuid.UUID, body: PostSettingsIn, db: DB, user: CurrentUser) -> TestOut:
    sched = body.schedule.model_dump()
    test = await tests_service.set_post(
        db,
        user,
        test_id,
        post_type=body.post_type,
        goal=body.goal,
        budget_minor=body.budget_minor,
        currency=body.currency,
        schedule=sched,
    )
    return TestOut(**await serializers.test_out(db, test))


@router.post("/{test_id}/cancel", response_model=CancelOut)
async def cancel_test(test_id: uuid.UUID, db: DB, user: CurrentUser, client: Client) -> CancelOut:
    return CancelOut(**await cancel_service.cancel(db, user, test_id, client.ip))


@router.post("/{test_id}/restart", response_model=TestOut)
async def restart_test(test_id: uuid.UUID, db: DB, user: CurrentUser, client: Client) -> TestOut:
    test = await cancel_service.restart(db, user, test_id, client.ip)
    return TestOut(**await serializers.test_out(db, test))


@router.post("/{test_id}/duplicate", response_model=TestOut, status_code=201)
async def duplicate_test(test_id: uuid.UUID, db: DB, user: CurrentUser) -> TestOut:
    test = await tests_service.duplicate(db, user, test_id)
    return TestOut(**await serializers.test_out(db, test))
