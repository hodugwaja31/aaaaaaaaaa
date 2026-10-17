import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(ValueError):
    pass


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} must be set.")
    return value


def _positive_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigError(f"{name} must be an integer.") from error
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero.")
    return parsed


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    guild_id: int
    anonymous_channel_id: int
    anonymous_log_channel_id: int
    cooldown_seconds: int = 30
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> "Settings":
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip() or os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise ConfigError("Set DISCORD_TOKEN or DISCORD_BOT_TOKEN.")
        anonymous_channel_id = _positive_int("ANONYMOUS_CHANNEL_ID", _required("ANONYMOUS_CHANNEL_ID"))
        anonymous_log_channel_id = _positive_int(
            "ANONYMOUS_LOG_CHANNEL_ID", _required("ANONYMOUS_LOG_CHANNEL_ID")
        )
        if anonymous_channel_id == anonymous_log_channel_id:
            raise ConfigError("ANONYMOUS_LOG_CHANNEL_ID must be different from ANONYMOUS_CHANNEL_ID.")
        return cls(
            token=token,
            guild_id=_positive_int("DISCORD_GUILD_ID", _required("DISCORD_GUILD_ID")),
            anonymous_channel_id=anonymous_channel_id,
            anonymous_log_channel_id=anonymous_log_channel_id,
            cooldown_seconds=_positive_int("ANONYMOUS_COOLDOWN_SECONDS", os.getenv("ANONYMOUS_COOLDOWN_SECONDS", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
