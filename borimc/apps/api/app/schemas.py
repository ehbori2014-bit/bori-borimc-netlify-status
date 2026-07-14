from typing import Any, Literal

from pydantic import BaseModel, Field

IncidentType = Literal["PVP", "ITEM", "ENV", "REPLAY", "CHEST", "ADMIN", "TRIAL"]
PointKind = Literal[
    "minecraft_activity",
    "minesweeper",
    "discord_first_verify",
    "admin_adjustment",
    "trial_penalty",
]


class AuthCodeCreate(BaseModel):
    provider: Literal["discord", "google"]
    provider_subject: str = Field(min_length=1)


class MinecraftVerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)
    minecraft_uuid: str = Field(min_length=8)
    minecraft_name: str = Field(min_length=1, max_length=32)


class PointAdjustRequest(BaseModel):
    minecraft_uuid: str
    amount: int
    kind: PointKind
    source_id: str | None = None
    reason: str | None = None


class IncidentCreate(BaseModel):
    type: IncidentType
    summary: str = Field(min_length=1)
    incident_id: str | None = None
    visibility: Literal["public_summary", "admin_only"] = "admin_only"


class IncidentEventCreate(BaseModel):
    event_type: str
    actor_uuid: str | None = None
    target_uuid: str | None = None
    world: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    yaw: float | None = None
    pitch: float | None = None
    payload: dict[str, Any] | None = None


class DeathItemCreate(BaseModel):
    incident_id: str
    death_id: str
    owner_uuid: str
    material: str
    original_amount: int = Field(gt=0)
    item_id: str | None = None


class ItemMovementCreate(BaseModel):
    item_id: str
    incident_id: str
    movement_type: Literal[
        "drop",
        "pickup",
        "chest_in",
        "chest_out",
        "player_transfer",
        "owner_return",
        "lost_suspected",
    ]
    amount: int = Field(gt=0)
    from_uuid: str | None = None
    to_uuid: str | None = None
    container_location: str | None = None
    payload: dict[str, Any] | None = None


class SecretContainerEventCreate(BaseModel):
    event_type: Literal["open", "close"]
    actor_uuid: str
    actor_name: str = Field(min_length=1, max_length=32)
    world: str = Field(min_length=1)
    x: int
    y: int
    z: int
    container_type: str = Field(min_length=1)
    contents: list[dict[str, Any]] = []
    payload: dict[str, Any] | None = None


class LegalReportCreate(BaseModel):
    report_type: Literal["complaint", "prosecution"]
    reporter_discord_id: str = Field(min_length=1)
    reporter_name: str = Field(min_length=1, max_length=100)
    target_name: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=1, max_length=1200)
    world: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    radius: int = Field(default=15, ge=0, le=100)


class ReplayCreate(BaseModel):
    incident_id: str
    subject_uuid: str | None = None
    window_before_seconds: int = 30
    window_after_seconds: int = 60
    storage_path: str | None = None
    payload: dict[str, Any] | None = None


class TrialCreate(BaseModel):
    incident_id: str
    accused_name: str
    victim_name: str
    witnesses: list[str] = []
    discord_channel_id: str | None = None
    discord_thread_url: str | None = None


class TrialClose(BaseModel):
    verdict: str
    punishment_type: Literal[
        "warning",
        "point_deduction",
        "item_return_order",
        "temporary_access_restriction",
        "ip_ban_candidate",
        "permanent_ban_candidate",
        "combined",
        "manual_judgement",
    ]
    restitution: str | None = None
    memo: str | None = None
    decided_by_discord_id: str | None = None


class RegistrationAgreements(BaseModel):
    rules: bool = False
    securityLogging: bool = False


class RegistrationCaptcha(BaseModel):
    provider: str = "recaptcha"
    version: str = "v2"
    verified: bool = False


class RegistrationRequestContext(BaseModel):
    ipHash: str | None = None
    ipPrefixHash: str | None = None
    userAgentHash: str | None = None
    deviceTokenHash: str | None = None
    siteUrl: str | None = None


class RegistrationCreate(BaseModel):
    lastName: str = Field(min_length=1, max_length=2)
    firstName: str = Field(min_length=1, max_length=4)
    minecraftName: str = Field(min_length=3, max_length=16)
    discordName: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    passwordConfirm: str = Field(min_length=8, max_length=128)
    googleEmail: str | None = None
    discordId: str | None = None
    googleSub: str | None = None
    agreements: RegistrationAgreements
    captcha: RegistrationCaptcha
    requestContext: RegistrationRequestContext


class RegistrationSecurityEventCreate(BaseModel):
    event_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    ipHash: str | None = None
    ipPrefixHash: str | None = None
    userAgentHash: str | None = None
    deviceTokenHash: str | None = None
    discord_id: str | None = None
    minecraft_uuid: str | None = None
    google_sub: str | None = None
    minecraft_name: str | None = None
    discord_name: str | None = None
    message: str = Field(min_length=1, max_length=1200)
    evidence_json: dict[str, Any] | None = None


class VerificationMinecraftCodeCreate(BaseModel):
    provider: Literal["discord", "google"]
    providerUserId: str = Field(min_length=1)
    minecraftName: str | None = Field(default=None, max_length=32)


class VerificationAdminRequestCreate(BaseModel):
    provider: Literal["discord", "google"]
    providerUserId: str = Field(min_length=1)


class RegistrationBanCreate(BaseModel):
    discord_id: str | None = None
    minecraft_uuid: str | None = None
    minecraft_name: str | None = Field(default=None, max_length=32)
    google_sub: str | None = None
    google_email: str | None = None
    ip_hash: str | None = None
    device_token_hash: str | None = None
    reason: str = Field(min_length=1, max_length=500)
    evidence_json: dict[str, Any] | None = None


class AdminAccountCreate(BaseModel):
    provider: Literal["discord", "google", "minecraft"]
    provider_subject: str = Field(min_length=1, max_length=128)
    discord_id: str | None = None
    google_sub: str | None = None
    google_email: str | None = None
    minecraft_uuid: str | None = None
    minecraft_name: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=100)
    role: Literal["owner", "admin"] = "admin"
