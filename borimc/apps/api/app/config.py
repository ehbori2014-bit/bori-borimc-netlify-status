from functools import lru_cache
from pathlib import Path
import os

API_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


for env_file in (Path.cwd() / ".env", API_DIR / ".env", PROJECT_ROOT / ".env"):
    _load_env_file(env_file)


class Settings:
    def __init__(self) -> None:
        self.env = os.getenv("BORIMC_ENV", "development")
        self.database_path = self._resolve_path(
            os.getenv("BORIMC_DATABASE_PATH"),
            PROJECT_ROOT / "database" / "borimc.sqlite3",
        )
        self.schema_path = self._resolve_path(
            os.getenv("BORIMC_SCHEMA_PATH"),
            PROJECT_ROOT / "database" / "schema.sql",
        )
        self.bot_api_token = os.getenv("BORIMC_BOT_API_TOKEN", "change-me-bot-token")
        self.plugin_api_token = os.getenv("BORIMC_PLUGIN_API_TOKEN", "change-me-plugin-token")
        self.registration_api_token = os.getenv(
            "BORIMC_REGISTRATION_SECRET",
            os.getenv("BORIMC_STATUS_SECRET", "change-me-registration-token"),
        )
        self.ip_hash_secret = os.getenv("BORIMC_IP_HASH_SECRET", "change-me-ip-hash-secret")
        self.admin_session_secret = os.getenv(
            "BORIMC_ADMIN_SESSION_SECRET",
            os.getenv("BORIMC_ADMIN_SECRET", "change-me-admin-session-secret"),
        )
        self.owner_discord_ids = [
            item.strip()
            for item in os.getenv("BORIMC_OWNER_DISCORD_IDS", "").split(",")
            if item.strip()
        ]
        self.public_url = os.getenv("BORIMC_PUBLIC_URL", "https://borimc.p-e.kr")
        self.admin_url = os.getenv("BORIMC_ADMIN_URL", "https://admin.borimc.p-e.kr")
        self.api_url = os.getenv("BORIMC_API_URL", "https://api.borimc.p-e.kr")
        self.minecraft_address = os.getenv("BORIMC_MINECRAFT_ADDRESS", "borimc.p-e.kr:10259")
        self._validate()

    @staticmethod
    def _resolve_path(raw_value: str | None, default: Path) -> Path:
        if not raw_value:
            return default
        path = Path(raw_value)
        if path.is_absolute():
            return path
        return (API_DIR / path).resolve()

    def _validate(self) -> None:
        if self.env != "production":
            return

        unsafe_values = {
            "BORIMC_BOT_API_TOKEN": self.bot_api_token,
            "BORIMC_PLUGIN_API_TOKEN": self.plugin_api_token,
            "BORIMC_REGISTRATION_SECRET": self.registration_api_token,
            "BORIMC_IP_HASH_SECRET": self.ip_hash_secret,
            "BORIMC_ADMIN_SESSION_SECRET": self.admin_session_secret,
        }
        for name, value in unsafe_values.items():
            if value.startswith("change-me") or len(value) < 24:
                raise RuntimeError(f"{name} must be replaced with a strong secret in production.")

        if not self.owner_discord_ids:
            raise RuntimeError("BORIMC_OWNER_DISCORD_IDS is required in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
