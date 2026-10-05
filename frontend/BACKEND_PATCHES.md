# Optional backend patch: change password while logged in

The Settings page calls `POST /api/v1/auth/change-password` with
`{"current_password": "...", "new_password": "..."}`. The current backend has no such endpoint;
the page detects the 404 and offers "Send me a reset link" instead (uses `POST /auth/forgot-password`),
so nothing breaks. Apply this patch in the backend when you want in-app password changes.

## `backend/app/schemas/auth.py`

```python
class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)
```

## `backend/app/services/auth_service.py`

```python
async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise ApiError(ErrorCode.invalid_credentials, "Current password is wrong")
    user.password_hash = hash_password(new_password)
    # revoke every other session: refresh tokens are rotated per session
    await revoke_all_refresh_tokens(db, user.id)
    await db.flush()
```

(`verify_password`, `hash_password` and the refresh-token revocation helper already exist in
`app/security.py` / `auth_service.py`; reuse the same functions the reset-password flow uses.)

## `backend/app/routers/auth.py`

```python
@router.post("/change-password", response_model=OkOut)
async def change_password(body: ChangePasswordIn, db: DB, user: CurrentUser, client: Client) -> OkOut:
    await auth_service.change_password(db, user, body.current_password, body.new_password)
    await audit.log(db, actor_id=user.id, action="auth.password_changed", ip=client.ip)
    return OkOut(ok=True, message="Password changed")
```

Errors follow the existing envelope: `invalid_credentials` (401) when the current password is wrong,
`validation_error` (422) for a short new password. The frontend maps both to translated messages.

## Test (`backend/tests/test_auth.py`)

```python
async def test_change_password(client, verified_user_headers):
    r = await client.post("/api/v1/auth/change-password", json={"current_password": "Passw0rd!", "new_password": "NewPassw0rd!"}, headers=verified_user_headers)
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", json={"email": "user@example.test", "password": "NewPassw0rd!"})
    assert r.status_code == 200
```

After adding the endpoint run `npm run gen:api` in `frontend/` so `src/lib/api-types.ts` includes it.
