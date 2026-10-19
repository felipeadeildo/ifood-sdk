"""Runtime configuration, following pydantic-settings precedence.

Initialiser arguments win over environment variables, which win over the dotenv file,
which win over the defaults below.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def default_session_path() -> Path:
    """Where the session lives when nothing else says otherwise."""
    return Path.home() / ".config" / "ifood-sdk" / "session.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IFOOD_", env_file=".env", extra="ignore")

    base_url: str = "https://www.ifood.com.br/site-api"
    marketplace_url: str = "https://marketplace.ifood.com.br"
    timeout: float = 30.0
    session_path: Path = default_session_path()
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/155.0.0.0 Safari/537.36"
    )
