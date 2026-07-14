from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3

from ..db import get_db
from ..repositories import RegistrationRepository
from ..schemas import AdminAccountCreate, RegistrationBanCreate, RegistrationCreate, RegistrationSecurityEventCreate
from ..security import APIActor, require_admin_actor, require_registration_actor

router = APIRouter(prefix="/registrations", tags=["registrations"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-registrations"])


@router.post("")
def submit_registration(
    body: RegistrationCreate,
    actor: APIActor = Depends(require_registration_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    result = RegistrationRepository(db).submit(body.model_dump())
    return {**result, "actor": actor.kind}


@router.post("/security-events")
def record_security_event(
    body: RegistrationSecurityEventCreate,
    actor: APIActor = Depends(require_registration_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    result = RegistrationRepository(db).record_security_event(body.model_dump())
    return {**result, "actor": actor.kind}


@admin_router.get("/registrations")
def list_registrations(
    status: str | None = Query(default=None),
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    rows = RegistrationRepository(db).list_attempts(status_filter=status)
    return {"items": rows, "actor": actor.kind}


@admin_router.get("/registration-bans")
def list_registration_bans(
    active_only: bool = True,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    rows = RegistrationRepository(db).list_bans(active_only=active_only)
    return {"items": rows, "actor": actor.kind}


@admin_router.post("/registration-bans")
def create_registration_ban(
    body: RegistrationBanCreate,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    item = RegistrationRepository(db).create_ban(body.model_dump(), banned_by=actor.actor_id)
    return {"item": item, "actor": actor.kind}


@admin_router.post("/admins")
def register_admin_account(
    body: AdminAccountCreate,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    item = RegistrationRepository(db).register_admin(body.model_dump(), added_by=actor.actor_id)
    return {"item": item, "actor": actor.kind}


@admin_router.post("/registration/{registration_id}/approve")
def approve_registration(
    registration_id: int,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = RegistrationRepository(db).set_attempt_status(registration_id, "APPROVED")
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found.")
    return {"item": row, "actor": actor.kind}


@admin_router.post("/registration/{registration_id}/reject")
def reject_registration(
    registration_id: int,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = RegistrationRepository(db).set_attempt_status(registration_id, "REJECTED", "Rejected by admin")
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found.")
    return {"item": row, "actor": actor.kind}


@admin_router.post("/registration/{registration_id}/clear-suspension")
def clear_registration_suspension(
    registration_id: int,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = RegistrationRepository(db).clear_suspension(registration_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found.")
    return {"item": row, "actor": actor.kind}


@admin_router.post("/registration/{ban_id}/unban")
def unban_registration(
    ban_id: int,
    actor: APIActor = Depends(require_admin_actor),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = RegistrationRepository(db).unban(ban_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ban not found.")
    return {"item": row, "actor": actor.kind}
