from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import secrets
import sqlite3
import urllib.error
import urllib.request


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def _rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


class AuthRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def create_code(self, provider: str, provider_subject: str) -> dict:
        code = secrets.token_urlsafe(5).replace("-", "").replace("_", "")[:8].upper()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat()
        self.db.execute(
            """
            INSERT INTO auth_links (code, provider, provider_subject, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (code, provider, provider_subject, expires_at),
        )
        self.db.commit()
        return {"code": code, "expires_at": expires_at}

    def verify_minecraft_code(self, code: str, minecraft_uuid: str, minecraft_name: str) -> dict:
        link = self.db.execute(
            """
            SELECT * FROM auth_links
            WHERE code = ? AND status = 'pending' AND expires_at > ?
            """,
            (code.upper(), _utc_now()),
        ).fetchone()
        if not link:
            raise ValueError("Invalid or expired verification code.")

        now = _utc_now()
        provider = link["provider"]
        provider_subject = link["provider_subject"]

        existing = self.db.execute(
            "SELECT * FROM users WHERE minecraft_uuid = ?",
            (minecraft_uuid,),
        ).fetchone()

        if existing:
            if provider == "discord":
                self.db.execute(
                    """
                    UPDATE users
                    SET minecraft_name = ?, discord_id = ?, minecraft_verified_at = ?, updated_at = ?
                    WHERE minecraft_uuid = ?
                    """,
                    (minecraft_name, provider_subject, now, now, minecraft_uuid),
                )
            else:
                self.db.execute(
                    """
                    UPDATE users
                    SET minecraft_name = ?, google_id = ?, minecraft_verified_at = ?, updated_at = ?
                    WHERE minecraft_uuid = ?
                    """,
                    (minecraft_name, provider_subject, now, now, minecraft_uuid),
                )
        else:
            self.db.execute(
                """
                INSERT INTO users (
                  minecraft_uuid,
                  minecraft_name,
                  discord_id,
                  google_id,
                  display_name,
                  role,
                  minecraft_verified_at
                )
                VALUES (?, ?, ?, ?, ?, 'user', ?)
                """,
                (
                    minecraft_uuid,
                    minecraft_name,
                    provider_subject if provider == "discord" else None,
                    provider_subject if provider == "google" else None,
                    minecraft_name,
                    now,
                ),
            )

        self.db.execute(
            """
            UPDATE auth_links
            SET status = 'verified', minecraft_uuid = ?, minecraft_name = ?, verified_at = ?
            WHERE id = ?
            """,
            (minecraft_uuid, minecraft_name, now, link["id"]),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO points (minecraft_uuid, balance) VALUES (?, 0)",
            (minecraft_uuid,),
        )
        self.db.commit()
        return self.get_user_by_uuid(minecraft_uuid) or {}

    def get_user_by_uuid(self, minecraft_uuid: str) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM users WHERE minecraft_uuid = ?",
                (minecraft_uuid,),
            ).fetchone()
        )

    def is_minecraft_verified(self, minecraft_uuid: str) -> bool:
        row = self.db.execute(
            """
            SELECT 1 FROM users
            WHERE minecraft_uuid = ? AND minecraft_verified_at IS NOT NULL
            """,
            (minecraft_uuid,),
        ).fetchone()
        return row is not None


class RegistrationRepository:
    BAD_NAME_FRAGMENTS = {
        "ㅋㅋ",
        "ㅎㅎ",
        "ㅁㄴㅇ",
        "asdf",
        "test",
        "admin",
        "운영자",
        "관리자",
        "시발",
        "씨발",
        "병신",
        "ㅄ",
    }
    MINECRAFT_NAME = re.compile(r"^[A-Za-z0-9_]{3,16}$")
    KOREAN = re.compile(r"^[가-힣]+$")
    PASSWORD_ALG = "pbkdf2_sha256"
    PASSWORD_ITERATIONS = 210_000

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def _context(self, data: dict) -> dict:
        context = data.get("requestContext") or {}
        return {
            "ip_hash": context.get("ipHash"),
            "ip_prefix_hash": context.get("ipPrefixHash"),
            "user_agent_hash": context.get("userAgentHash"),
            "device_token_hash": context.get("deviceTokenHash"),
        }

    def _lookup_minecraft_uuid(self, minecraft_name: str) -> str | None:
        url = f"https://api.mojang.com/users/profiles/minecraft/{minecraft_name}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "BoriMC-API/1.0"})
            with urllib.request.urlopen(request, timeout=3) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
                raw_uuid = payload.get("id")
                if not raw_uuid:
                    return None
                return raw_uuid
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None

    def _invalid_reasons(self, data: dict, minecraft_uuid: str | None) -> list[str]:
        reasons: list[str] = []
        last_name = (data.get("lastName") or "").strip()
        first_name = (data.get("firstName") or "").strip()
        full_name = last_name + first_name
        minecraft_name = (data.get("minecraftName") or "").strip()
        password = data.get("password") or ""
        password_confirm = data.get("passwordConfirm") or ""
        agreements = data.get("agreements") or {}
        captcha = data.get("captcha") or {}
        normalized_name = full_name.lower()

        if not last_name or not first_name:
            reasons.append("NAME_EMPTY")
        if not self.KOREAN.match(last_name) or not (1 <= len(last_name) <= 2):
            reasons.append("LAST_NAME_INVALID")
        if not self.KOREAN.match(first_name) or not (1 <= len(first_name) <= 4):
            reasons.append("FIRST_NAME_INVALID")
        if not (2 <= len(full_name) <= 5):
            reasons.append("FULL_NAME_LENGTH_SUSPICIOUS")
        if any(fragment in normalized_name for fragment in self.BAD_NAME_FRAGMENTS):
            reasons.append("BAD_OR_JOKE_NAME")
        if not self.MINECRAFT_NAME.match(minecraft_name):
            reasons.append("MINECRAFT_NAME_INVALID")
        if minecraft_uuid is None:
            reasons.append("MINECRAFT_UUID_LOOKUP_FAILED")
        if len(password) < 8 or len(password) > 128:
            reasons.append("PASSWORD_LENGTH_INVALID")
        if password != password_confirm:
            reasons.append("PASSWORD_CONFIRM_MISMATCH")
        if agreements.get("rules") is not True or agreements.get("securityLogging") is not True:
            reasons.append("AGREEMENT_MISSING")
        if captcha.get("verified") is not True:
            reasons.append("CAPTCHA_NOT_VERIFIED")
        return reasons

    def _recent_attempt_count(self, data: dict) -> int:
        context = self._context(data)
        minecraft_name = (data.get("minecraftName") or "").strip()
        row = self.db.execute(
            """
            SELECT COUNT(*) AS count
            FROM registration_attempts
            WHERE created_at >= datetime('now', '-10 minutes')
              AND (
                (? IS NOT NULL AND ip_hash = ?)
                OR (? IS NOT NULL AND device_token_hash = ?)
                OR lower(minecraft_name) = lower(?)
              )
            """,
            (
                context["ip_hash"],
                context["ip_hash"],
                context["device_token_hash"],
                context["device_token_hash"],
                minecraft_name,
            ),
        ).fetchone()
        return int(row["count"] if row else 0)

    def _has_active_ban(
        self,
        context: dict,
        minecraft_uuid: str | None,
        google_sub: str | None,
        discord_id: str | None,
        minecraft_name: str | None,
        google_email: str | None,
    ) -> bool:
        row = self.db.execute(
            """
            SELECT 1
            FROM registration_bans
            WHERE is_active = 1
              AND (
                (? IS NOT NULL AND discord_id = ?)
                OR (? IS NOT NULL AND minecraft_uuid = ?)
                OR (? IS NOT NULL AND lower(minecraft_name) = lower(?))
                OR (? IS NOT NULL AND google_sub = ?)
                OR (? IS NOT NULL AND lower(google_email) = lower(?))
                OR (? IS NOT NULL AND ip_hash = ?)
                OR (? IS NOT NULL AND device_token_hash = ?)
              )
            LIMIT 1
            """,
            (
                discord_id,
                discord_id,
                minecraft_uuid,
                minecraft_uuid,
                minecraft_name,
                minecraft_name,
                google_sub,
                google_sub,
                google_email,
                google_email,
                context["ip_hash"],
                context["ip_hash"],
                context["device_token_hash"],
                context["device_token_hash"],
            ),
        ).fetchone()
        return row is not None

    def _hash_password(self, password: str) -> tuple[str, str]:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self.PASSWORD_ITERATIONS,
        )
        encoded = f"{self.PASSWORD_ALG}${self.PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"
        return encoded, self.PASSWORD_ALG

    def _safe_attempt_row(self, row: sqlite3.Row | None) -> dict | None:
        item = _row(row)
        if not item:
            return None
        item.pop("password_hash", None)
        item.pop("password_alg", None)
        return item

    def _auto_create_user(
        self,
        minecraft_uuid: str,
        minecraft_name: str,
        discord_id: str | None,
        google_sub: str | None,
        display_name: str,
    ) -> None:
        existing = self.db.execute(
            "SELECT * FROM users WHERE minecraft_uuid = ?",
            (minecraft_uuid,),
        ).fetchone()
        now = _utc_now()
        if existing:
            self.db.execute(
                """
                UPDATE users
                SET minecraft_name = ?,
                    discord_id = COALESCE(discord_id, ?),
                    google_id = COALESCE(google_id, ?),
                    display_name = COALESCE(display_name, ?),
                    updated_at = ?
                WHERE minecraft_uuid = ?
                """,
                (minecraft_name, discord_id, google_sub, display_name, now, minecraft_uuid),
            )
        else:
            self.db.execute(
                """
                INSERT INTO users (
                  minecraft_uuid, minecraft_name, discord_id, google_id, display_name, role
                )
                VALUES (?, ?, ?, ?, ?, 'user')
                """,
                (minecraft_uuid, minecraft_name, discord_id, google_sub, display_name),
            )

    def _previous_warning_count(self, data: dict, minecraft_uuid: str | None) -> int:
        context = self._context(data)
        minecraft_name = (data.get("minecraftName") or "").strip()
        row = self.db.execute(
            """
            SELECT COUNT(*) AS count
            FROM registration_attempts
            WHERE status IN ('WARNING', 'SUSPENDED_6H', 'BANNED')
              AND (
                (? IS NOT NULL AND ip_hash = ?)
                OR (? IS NOT NULL AND device_token_hash = ?)
                OR (? IS NOT NULL AND minecraft_uuid = ?)
                OR lower(minecraft_name) = lower(?)
              )
            """,
            (
                context["ip_hash"],
                context["ip_hash"],
                context["device_token_hash"],
                context["device_token_hash"],
                minecraft_uuid,
                minecraft_uuid,
                minecraft_name,
            ),
        ).fetchone()
        return int(row["count"] if row else 0)

    def record_security_event(self, data: dict) -> dict:
        evidence = json.dumps(data.get("evidence_json") or {}, ensure_ascii=False)
        self.db.execute(
            """
            INSERT INTO registration_security_events (
              event_type, severity, ip_hash, ip_prefix_hash, user_agent_hash, device_token_hash,
              discord_id, minecraft_uuid, google_sub, minecraft_name, discord_name, message, evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["event_type"],
                data.get("severity", "LOW"),
                data.get("ipHash"),
                data.get("ipPrefixHash"),
                data.get("userAgentHash"),
                data.get("deviceTokenHash"),
                data.get("discord_id"),
                data.get("minecraft_uuid"),
                data.get("google_sub"),
                data.get("minecraft_name"),
                data.get("discord_name"),
                data["message"],
                evidence,
            ),
        )
        self.db.commit()
        return {"ok": True}

    def submit(self, data: dict) -> dict:
        context = self._context(data)
        last_name = data["lastName"].strip()
        first_name = data["firstName"].strip()
        full_name = last_name + first_name
        minecraft_name = data["minecraftName"].strip()
        discord_name = data["discordName"].strip()
        discord_id = data.get("discordId")
        google_email = data.get("googleEmail")
        google_sub = data.get("googleSub")
        password = data.get("password") or ""

        if self._recent_attempt_count(data) >= 3:
            self.record_security_event({
                "event_type": "REGISTER_RATE_LIMITED",
                "severity": "MEDIUM",
                "ipHash": context["ip_hash"],
                "ipPrefixHash": context["ip_prefix_hash"],
                "userAgentHash": context["user_agent_hash"],
                "deviceTokenHash": context["device_token_hash"],
                "minecraft_name": minecraft_name,
                "discord_name": discord_name,
                "message": "Too many registration attempts in 10 minutes",
                "evidence_json": {"window": "10m", "limit": 3},
            })
            return {
                "ok": False,
                "status": "RATE_LIMITED",
                "message": "짧은 시간 안에 가입 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                "retryAfterSeconds": 600,
            }

        minecraft_uuid = self._lookup_minecraft_uuid(minecraft_name)
        reasons = self._invalid_reasons(data, minecraft_uuid)

        if self._has_active_ban(context, minecraft_uuid, google_sub, discord_id, minecraft_name, google_email):
            status = "BANNED"
            ban_reason = "Active registration ban exists"
            message = "이전 경고 이후에도 잘못된 가입 신청이 반복되어 가입이 차단되었습니다. 운영진에게 문의하세요."
        elif reasons and self._previous_warning_count(data, minecraft_uuid) > 0:
            status = "BANNED"
            ban_reason = "Repeated invalid registration after warning"
            message = "이전 경고 이후에도 잘못된 가입 신청이 반복되어 가입이 차단되었습니다. 운영진에게 문의하세요."
        elif reasons:
            status = "SUSPENDED_6H"
            ban_reason = None
            message = "가입 정보가 서버 규칙에 맞지 않아 6시간 동안 가입 신청이 제한되었습니다. 이름과 마크닉을 실제 정보에 맞게 입력해 주세요."
        else:
            status = "APPROVED"
            ban_reason = None
            message = "가입이 자동 승인되었습니다. Minecraft 서버에서는 /인증 코드로 계정 인증을 완료해 주세요."

        previous_warnings = self._previous_warning_count(data, minecraft_uuid)
        warning_count = previous_warnings + (1 if status in {"SUSPENDED_6H", "BANNED"} else 0)
        suspension_until = None
        if status == "SUSPENDED_6H":
            suspension_until = (datetime.now(timezone.utc) + timedelta(hours=6)).replace(microsecond=0).isoformat()

        validation_result = {
            "reasons": reasons,
            "minecraft_uuid_verified": minecraft_uuid is not None,
            "captcha_verified": (data.get("captcha") or {}).get("verified") is True,
            "auto_approved": status == "APPROVED",
        }
        password_hash, password_alg = self._hash_password(password) if status == "APPROVED" else (None, None)

        cursor = self.db.execute(
            """
            INSERT INTO registration_attempts (
              last_name, first_name, full_name, minecraft_name, minecraft_uuid, discord_name,
              discord_id, google_email, google_sub, password_hash, password_alg, ip_hash, ip_prefix_hash,
              user_agent_hash, device_token_hash, validation_result, warning_count, status, auto_approved,
              suspension_until, ban_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                last_name,
                first_name,
                full_name,
                minecraft_name,
                minecraft_uuid,
                discord_name,
                discord_id,
                google_email,
                google_sub,
                password_hash,
                password_alg,
                context["ip_hash"],
                context["ip_prefix_hash"],
                context["user_agent_hash"],
                context["device_token_hash"],
                json.dumps(validation_result, ensure_ascii=False),
                warning_count,
                status,
                1 if status == "APPROVED" else 0,
                suspension_until,
                ban_reason,
            ),
        )

        if status == "APPROVED" and minecraft_uuid:
            self._auto_create_user(minecraft_uuid, minecraft_name, discord_id, google_sub, full_name)

        if status == "BANNED":
            evidence = {
                "registration_attempt_id": cursor.lastrowid,
                "warning_count": warning_count,
                "reasons": reasons,
                "same_ip_hash": bool(context["ip_hash"]),
                "same_device_token": bool(context["device_token_hash"]),
            }
            self.db.execute(
                """
                INSERT INTO registration_bans (
                  discord_id, minecraft_uuid, minecraft_name, google_sub, google_email, ip_hash, device_token_hash,
                  reason, evidence_json, banned_by, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'system', 1)
                """,
                (
                    discord_id,
                    minecraft_uuid,
                    minecraft_name,
                    google_sub,
                    google_email,
                    context["ip_hash"],
                    context["device_token_hash"],
                    ban_reason or "Registration banned",
                    json.dumps(evidence, ensure_ascii=False),
                ),
            )

        if status not in {"PENDING", "APPROVED"}:
            self.db.execute(
                """
                INSERT INTO registration_security_events (
                  event_type, severity, ip_hash, ip_prefix_hash, user_agent_hash, device_token_hash,
                  discord_id, minecraft_uuid, google_sub, minecraft_name, discord_name, message, evidence_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "REGISTRATION_BLOCKED" if status == "BANNED" else "REGISTRATION_SUSPENDED",
                    "HIGH" if status == "BANNED" else "MEDIUM",
                    context["ip_hash"],
                    context["ip_prefix_hash"],
                    context["user_agent_hash"],
                    context["device_token_hash"],
                    discord_id,
                    minecraft_uuid,
                    google_sub,
                    minecraft_name,
                    discord_name,
                    message,
                    json.dumps(validation_result, ensure_ascii=False),
                ),
            )

        self.db.commit()
        response = {
            "ok": status in {"PENDING", "APPROVED"},
            "status": status,
            "message": message,
            "registrationAttemptId": cursor.lastrowid,
            "autoApproved": status == "APPROVED",
        }
        if suspension_until:
            response["retryAfterSeconds"] = 21600
            response["suspensionUntil"] = suspension_until
        return response

    def list_attempts(self, status_filter: str | None = None, limit: int = 100) -> list[dict]:
        if status_filter:
            rows = self.db.execute(
                """
                SELECT * FROM registration_attempts
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status_filter, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT * FROM registration_attempts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._safe_attempt_row(row) or {} for row in rows]

    def list_bans(self, active_only: bool = True, limit: int = 100) -> list[dict]:
        if active_only:
            rows = self.db.execute(
                """
                SELECT * FROM registration_bans
                WHERE is_active = 1
                ORDER BY banned_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM registration_bans ORDER BY banned_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return _rows(rows)

    def set_attempt_status(self, attempt_id: int, status: str, reason: str | None = None) -> dict:
        self.db.execute(
            """
            UPDATE registration_attempts
            SET status = ?, ban_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, reason, attempt_id),
        )
        if status == "APPROVED":
            attempt = self.db.execute(
                "SELECT * FROM registration_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if attempt and attempt["minecraft_uuid"]:
                self._auto_create_user(
                    attempt["minecraft_uuid"],
                    attempt["minecraft_name"],
                    attempt["discord_id"],
                    attempt["google_sub"],
                    attempt["full_name"],
                )
        self.db.commit()
        return self.get_attempt(attempt_id) or {}

    def clear_suspension(self, attempt_id: int) -> dict:
        self.db.execute(
            """
            UPDATE registration_attempts
            SET status = 'PENDING', suspension_until = NULL, ban_reason = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (attempt_id,),
        )
        self.db.commit()
        return self.get_attempt(attempt_id) or {}

    def create_ban(self, data: dict, banned_by: str) -> dict:
        minecraft_name = (data.get("minecraft_name") or "").strip() or None
        minecraft_uuid = (data.get("minecraft_uuid") or "").strip() or None
        if minecraft_name and not minecraft_uuid:
            minecraft_uuid = self._lookup_minecraft_uuid(minecraft_name)
        evidence = json.dumps(data.get("evidence_json") or {}, ensure_ascii=False)
        cursor = self.db.execute(
            """
            INSERT INTO registration_bans (
              discord_id, minecraft_uuid, minecraft_name, google_sub, google_email,
              ip_hash, device_token_hash, reason, evidence_json, banned_by, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                data.get("discord_id"),
                minecraft_uuid,
                minecraft_name,
                data.get("google_sub"),
                data.get("google_email"),
                data.get("ip_hash"),
                data.get("device_token_hash"),
                data["reason"],
                evidence,
                banned_by,
            ),
        )
        self.db.commit()
        row = self.db.execute("SELECT * FROM registration_bans WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row(row) or {}

    def unban(self, ban_id: int) -> dict:
        self.db.execute(
            "UPDATE registration_bans SET is_active = 0 WHERE id = ?",
            (ban_id,),
        )
        self.db.commit()
        row = self.db.execute("SELECT * FROM registration_bans WHERE id = ?", (ban_id,)).fetchone()
        return _row(row) or {}

    def get_attempt(self, attempt_id: int) -> dict | None:
        return self._safe_attempt_row(
            self.db.execute(
                "SELECT * FROM registration_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        )

    def register_admin(self, data: dict, added_by: str) -> dict:
        provider = data["provider"]
        provider_subject = data["provider_subject"]
        discord_id = data.get("discord_id") or (provider_subject if provider == "discord" else None)
        google_sub = data.get("google_sub") or (provider_subject if provider == "google" else None)
        minecraft_uuid = data.get("minecraft_uuid") or (provider_subject if provider == "minecraft" else None)
        minecraft_name = data.get("minecraft_name")
        display_name = data.get("display_name") or minecraft_name or data.get("google_email") or discord_id or provider_subject
        role = data.get("role", "admin")

        self.db.execute(
            """
            INSERT INTO admin_accounts (
              provider, provider_subject, discord_id, google_sub, google_email,
              minecraft_uuid, minecraft_name, display_name, role, added_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, provider_subject) DO UPDATE SET
              discord_id = excluded.discord_id,
              google_sub = excluded.google_sub,
              google_email = excluded.google_email,
              minecraft_uuid = excluded.minecraft_uuid,
              minecraft_name = excluded.minecraft_name,
              display_name = excluded.display_name,
              role = excluded.role,
              added_by = excluded.added_by
            """,
            (
                provider,
                provider_subject,
                discord_id,
                google_sub,
                data.get("google_email"),
                minecraft_uuid,
                minecraft_name,
                display_name,
                role,
                added_by,
            ),
        )
        if discord_id:
            self.db.execute(
                """
                INSERT INTO admins (discord_id, role, added_by_discord_id)
                VALUES (?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                  role = excluded.role,
                  added_by_discord_id = excluded.added_by_discord_id
                """,
                (discord_id, role, added_by),
            )
        if minecraft_uuid:
            self.db.execute(
                """
                UPDATE users
                SET role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE minecraft_uuid = ?
                """,
                (role, minecraft_uuid),
            )
        if google_sub:
            self.db.execute(
                """
                UPDATE users
                SET role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE google_id = ?
                """,
                (role, google_sub),
            )
        self.db.commit()
        row = self.db.execute(
            """
            SELECT * FROM admin_accounts
            WHERE provider = ? AND provider_subject = ?
            """,
            (provider, provider_subject),
        ).fetchone()
        return _row(row) or {}


class PointRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.auth = AuthRepository(db)

    def get_balance(self, minecraft_uuid: str) -> dict:
        row = self.db.execute(
            "SELECT * FROM points WHERE minecraft_uuid = ?",
            (minecraft_uuid,),
        ).fetchone()
        if row:
            return dict(row)
        return {"minecraft_uuid": minecraft_uuid, "balance": 0}

    def adjust(
        self,
        minecraft_uuid: str,
        amount: int,
        kind: str,
        source_id: str | None,
        reason: str | None,
        actor_discord_id: str | None,
    ) -> dict:
        if not self.auth.is_minecraft_verified(minecraft_uuid):
            raise ValueError("Minecraft verification is required before point changes.")

        current = self.get_balance(minecraft_uuid)["balance"]
        next_balance = current + amount
        if next_balance < 0:
            raise ValueError("Point balance cannot become negative.")

        self.db.execute(
            """
            INSERT INTO points (minecraft_uuid, balance)
            VALUES (?, ?)
            ON CONFLICT(minecraft_uuid) DO UPDATE SET
              balance = excluded.balance,
              updated_at = CURRENT_TIMESTAMP
            """,
            (minecraft_uuid, next_balance),
        )
        self.db.execute(
            """
            INSERT INTO point_transactions (
              minecraft_uuid, amount, kind, source_id, reason, actor_discord_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (minecraft_uuid, amount, kind, source_id, reason, actor_discord_id),
        )
        self.db.commit()
        return self.get_balance(minecraft_uuid)


class IncidentRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def _next_incident_id(self, incident_type: str) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"{incident_type}-{today}-"
        row = self.db.execute(
            "SELECT COUNT(*) AS count FROM incidents WHERE incident_id LIKE ?",
            (prefix + "%",),
        ).fetchone()
        return f"{prefix}{int(row['count']) + 1:03d}"

    def create(self, incident_type: str, summary: str, incident_id: str | None, visibility: str) -> dict:
        incident_id = incident_id or self._next_incident_id(incident_type)
        auto_allowed = 0
        self.db.execute(
            """
            INSERT INTO incidents (
              incident_id, type, summary, visibility, auto_punishment_allowed
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (incident_id, incident_type, summary, visibility, auto_allowed),
        )
        self.db.commit()
        return self.get(incident_id) or {}

    def list_recent(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT incident_id, type, status, summary, visibility, created_at
            FROM incidents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return _rows(rows)

    def get(self, incident_id: str) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        )

    def add_event(self, incident_id: str, data: dict) -> dict:
        payload = json.dumps(data.get("payload") or {}, ensure_ascii=False)
        self.db.execute(
            """
            INSERT INTO incident_events (
              incident_id, event_type, actor_uuid, target_uuid, world, x, y, z, yaw, pitch, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                data["event_type"],
                data.get("actor_uuid"),
                data.get("target_uuid"),
                data.get("world"),
                data.get("x"),
                data.get("y"),
                data.get("z"),
                data.get("yaw"),
                data.get("pitch"),
                payload,
            ),
        )
        self.db.commit()
        return {"incident_id": incident_id, "event_type": data["event_type"]}


class ItemRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def create_death_item(self, data: dict) -> dict:
        item_id = data.get("item_id") or secrets.token_hex(12)
        amount = int(data["original_amount"])
        self.db.execute(
            """
            INSERT INTO death_items (
              item_id, incident_id, death_id, owner_uuid, material, original_amount, remaining_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                data["incident_id"],
                data["death_id"],
                data["owner_uuid"],
                data["material"],
                amount,
                amount,
            ),
        )
        self.db.execute(
            """
            INSERT INTO item_movements (
              item_id, incident_id, movement_type, to_uuid, amount, payload_json
            )
            VALUES (?, ?, 'drop', ?, ?, ?)
            """,
            (
                item_id,
                data["incident_id"],
                data["owner_uuid"],
                amount,
                json.dumps({"tagged": True}, ensure_ascii=False),
            ),
        )
        self.db.commit()
        return self.get_death_item(item_id) or {}

    def get_death_item(self, item_id: str) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM death_items WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        )

    def add_movement(self, data: dict) -> dict:
        item = self.get_death_item(data["item_id"])
        if not item:
            raise ValueError("Tracked death item was not found.")

        amount = int(data["amount"])
        tag_removed = 0
        next_status = item["status"]
        next_remaining = item["remaining_amount"]
        next_returned = item["returned_amount"]
        next_tag_removed = item["tag_removed_amount"]

        if data["movement_type"] == "owner_return" and data.get("to_uuid") == item["owner_uuid"]:
            actual_return = min(amount, item["remaining_amount"])
            next_remaining = max(0, item["remaining_amount"] - actual_return)
            next_returned = item["returned_amount"] + actual_return
            next_tag_removed = item["tag_removed_amount"] + actual_return
            tag_removed = 1
            next_status = "fully_returned" if next_remaining == 0 else "partially_returned"
        elif data["movement_type"] == "pickup" and data.get("to_uuid") != item["owner_uuid"]:
            next_status = "picked_by_other"
        elif data["movement_type"] in {"chest_in", "chest_out"}:
            next_status = "stored"
        elif data["movement_type"] == "lost_suspected":
            next_status = "suspected_lost"

        self.db.execute(
            """
            INSERT INTO item_movements (
              item_id, incident_id, movement_type, from_uuid, to_uuid,
              container_location, amount, tag_removed, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["item_id"],
                data["incident_id"],
                data["movement_type"],
                data.get("from_uuid"),
                data.get("to_uuid"),
                data.get("container_location"),
                amount,
                tag_removed,
                json.dumps(data.get("payload") or {}, ensure_ascii=False),
            ),
        )
        self.db.execute(
            """
            UPDATE death_items
            SET remaining_amount = ?,
                returned_amount = ?,
                tag_removed_amount = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE item_id = ?
            """,
            (next_remaining, next_returned, next_tag_removed, next_status, data["item_id"]),
        )
        self.db.commit()
        return self.get_death_item(data["item_id"]) or {}

    def list_by_incident(self, incident_id: str) -> list[dict]:
        return _rows(
            self.db.execute(
                "SELECT * FROM death_items WHERE incident_id = ? ORDER BY created_at DESC",
                (incident_id,),
            ).fetchall()
        )


class SecretContainerRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def _container_id(self, world: str, x: int, y: int, z: int) -> str:
        safe_world = world.replace(":", "_").replace("/", "_").replace("\\", "_")
        return f"{safe_world}:{x}:{y}:{z}"

    def record_event(self, data: dict) -> dict:
        world = data["world"]
        x = int(data["x"])
        y = int(data["y"])
        z = int(data["z"])
        container_id = self._container_id(world, x, y, z)
        contents_json = json.dumps(data.get("contents") or [], ensure_ascii=False)
        payload_json = json.dumps(data.get("payload") or {}, ensure_ascii=False)

        self.db.execute(
            """
            INSERT INTO secret_containers (
              container_id, world, x, y, z, container_type,
              last_opened_at, last_opened_by_uuid, last_opened_by_name
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT(container_id) DO UPDATE SET
              container_type = excluded.container_type,
              last_opened_at = CURRENT_TIMESTAMP,
              last_opened_by_uuid = excluded.last_opened_by_uuid,
              last_opened_by_name = excluded.last_opened_by_name,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                container_id,
                world,
                x,
                y,
                z,
                data["container_type"],
                data["actor_uuid"],
                data["actor_name"],
            ),
        )
        cursor = self.db.execute(
            """
            INSERT INTO secret_container_events (
              container_id, event_type, actor_uuid, actor_name,
              world, x, y, z, container_type, contents_json, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                container_id,
                data["event_type"],
                data["actor_uuid"],
                data["actor_name"],
                world,
                x,
                y,
                z,
                data["container_type"],
                contents_json,
                payload_json,
            ),
        )
        self.db.commit()
        return self.get_event(int(cursor.lastrowid)) or {}

    def get_event(self, event_id: int) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM secret_container_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        )

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT *
            FROM secret_container_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return _rows(rows)

    def get_container_events(self, container_id: str, limit: int = 20) -> list[dict]:
        rows = self.db.execute(
            """
            SELECT *
            FROM secret_container_events
            WHERE container_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (container_id, limit),
        ).fetchall()
        return _rows(rows)

    def get_container(self, container_id: str) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM secret_containers WHERE container_id = ?",
                (container_id,),
            ).fetchone()
        )

    def search_related_events(
        self,
        target_name: str | None,
        world: str | None,
        x: int | None,
        y: int | None,
        z: int | None,
        radius: int = 15,
        limit: int = 10,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []

        if target_name:
            clauses.append("LOWER(actor_name) = LOWER(?)")
            params.append(target_name)

        if world and x is not None and y is not None and z is not None:
            radius = max(0, int(radius))
            clauses.append(
                """
                (
                  world = ?
                  AND x BETWEEN ? AND ?
                  AND y BETWEEN ? AND ?
                  AND z BETWEEN ? AND ?
                )
                """
            )
            params.extend([world, x - radius, x + radius, y - radius, y + radius, z - radius, z + radius])

        if not clauses:
            return []

        rows = self.db.execute(
            f"""
            SELECT *
            FROM secret_container_events
            WHERE {" OR ".join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return _rows(rows)


class LegalReportRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.secret_containers = SecretContainerRepository(db)

    def _next_report_id(self, report_type: str) -> str:
        prefix = "COMPLAINT" if report_type == "complaint" else "PROSECUTION"
        return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"

    def _decode_report(self, report: dict | None) -> dict | None:
        if not report:
            return None
        try:
            related = json.loads(report.get("related_secret_events_json") or "[]")
        except json.JSONDecodeError:
            related = []
        report["related_secret_events"] = related
        return report

    def create(self, data: dict) -> dict:
        related_events = self.secret_containers.search_related_events(
            data.get("target_name"),
            data.get("world"),
            data.get("x"),
            data.get("y"),
            data.get("z"),
            data.get("radius", 15),
            limit=10,
        )
        report_id = self._next_report_id(data["report_type"])
        related_json = json.dumps(related_events, ensure_ascii=False)

        self.db.execute(
            """
            INSERT INTO legal_reports (
              report_id, report_type, reporter_discord_id, reporter_name,
              target_name, summary, world, x, y, z, radius,
              related_secret_events_json, related_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                data["report_type"],
                data["reporter_discord_id"],
                data["reporter_name"],
                data["target_name"],
                data["summary"],
                data.get("world"),
                data.get("x"),
                data.get("y"),
                data.get("z"),
                data.get("radius", 15),
                related_json,
                len(related_events),
            ),
        )
        self.db.commit()
        return self.get(report_id) or {}

    def get(self, report_id: str) -> dict | None:
        report = _row(
            self.db.execute(
                "SELECT * FROM legal_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        )
        return self._decode_report(report)

    def list_recent(self, limit: int = 10) -> list[dict]:
        rows = _rows(
            self.db.execute(
                "SELECT * FROM legal_reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
        return [self._decode_report(row) or row for row in rows]


class ReplayRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def _decode_replay(self, replay: dict | None) -> dict | None:
        if not replay:
            return None
        try:
            payload = json.loads(replay.get("payload_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        replay["payload"] = payload
        return replay

    def create(self, data: dict) -> dict:
        replay_id = secrets.token_hex(10)
        self.db.execute(
            """
            INSERT INTO replays (
              replay_id, incident_id, subject_uuid, window_before_seconds,
              window_after_seconds, storage_path, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                replay_id,
                data["incident_id"],
                data.get("subject_uuid"),
                data.get("window_before_seconds", 30),
                data.get("window_after_seconds", 60),
                data.get("storage_path"),
                json.dumps(data.get("payload") or {}, ensure_ascii=False),
            ),
        )
        self.db.commit()
        return self.get(replay_id) or {}

    def get(self, replay_id: str) -> dict | None:
        replay = _row(
            self.db.execute(
                "SELECT * FROM replays WHERE replay_id = ?",
                (replay_id,),
            ).fetchone()
        )
        return self._decode_replay(replay)

    def list_recent(self, limit: int = 10) -> list[dict]:
        rows = _rows(
            self.db.execute(
                "SELECT * FROM replays ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
        return [self._decode_replay(row) or row for row in rows]


class TrialRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def start(self, data: dict) -> dict:
        trial_id = f"TRIAL-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"
        self.db.execute(
            """
            INSERT INTO trials (
              trial_id, incident_id, accused_name, victim_name, witnesses_json,
              discord_channel_id, discord_thread_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trial_id,
                data["incident_id"],
                data["accused_name"],
                data["victim_name"],
                json.dumps(data.get("witnesses") or [], ensure_ascii=False),
                data.get("discord_channel_id"),
                data.get("discord_thread_url"),
            ),
        )
        self.db.execute(
            "UPDATE incidents SET status = 'trial' WHERE incident_id = ?",
            (data["incident_id"],),
        )
        self.db.commit()
        return self.get(trial_id) or {}

    def close(self, trial_id: str, data: dict) -> dict:
        self.db.execute(
            """
            UPDATE trials
            SET status = 'closed',
                verdict = ?,
                punishment_type = ?,
                restitution = ?,
                memo = ?,
                decided_by_discord_id = ?,
                closed_at = ?
            WHERE trial_id = ?
            """,
            (
                data["verdict"],
                data["punishment_type"],
                data.get("restitution"),
                data.get("memo"),
                data.get("decided_by_discord_id"),
                _utc_now(),
                trial_id,
            ),
        )
        trial = self.get(trial_id)
        if trial:
            self.db.execute(
                "UPDATE incidents SET status = 'closed', closed_at = ? WHERE incident_id = ?",
                (_utc_now(), trial["incident_id"]),
            )
        self.db.commit()
        return self.get(trial_id) or {}

    def get(self, trial_id: str) -> dict | None:
        return _row(
            self.db.execute(
                "SELECT * FROM trials WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
        )

    def list_recent(self, limit: int = 10) -> list[dict]:
        return _rows(
            self.db.execute(
                "SELECT * FROM trials ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
