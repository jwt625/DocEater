"""Configuration management for DocEater."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DOCEATER_",
        case_sensitive=False,
        extra="ignore",
    )

    # Database settings
    database_url: str = Field(
        default="postgresql://localhost:5432/doceater",
        description="PostgreSQL database URL"
    )

    # File watching settings
    watch_folder: str = Field(
        default_factory=lambda: str(Path.home() / "Downloads"),
        description="Folder to watch for new files"
    )
    watch_recursive: bool = Field(
        default=True,
        description="Watch folder recursively"
    )

    # File processing settings
    max_file_size_mb: int = Field(
        default=100,
        description="Maximum file size to process in MB"
    )
    supported_extensions: list[str] = Field(
        default_factory=lambda: [".pdf"],  # MVP: PDF only
        description="Supported file extensions"
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [".*", "~*", "*.tmp", "*.temp"],
        description="File patterns to exclude"
    )

    # Docling settings
    docling_enrich_formula: bool = Field(
        default=True,
        description="Enable formula enrichment in Docling"
    )

    # Processing settings
    max_concurrent_files: int = Field(
        default=3,
        description="Maximum number of files to process concurrently"
    )
    processing_delay_seconds: float = Field(
        default=1.0,
        description="Delay between processing files to avoid overwhelming system"
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_file: str | None = Field(
        default=None,
        description="Log file path (if None, logs to console)"
    )

    # Service settings
    service_name: str = Field(
        default="doceater",
        description="Service name for daemon mode"
    )
    pid_file: str | None = Field(
        default=None,
        description="PID file path for daemon mode"
    )

    @field_validator("watch_folder")
    @classmethod
    def validate_watch_folder(cls, v: str) -> str:
        """Ensure watch folder exists and is accessible."""
        path = Path(v).expanduser().resolve()
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception:
                # Fall back to Downloads folder
                fallback = Path.home() / "Downloads"
                fallback.mkdir(exist_ok=True)
                return str(fallback)

        if not path.is_dir():
            raise ValueError(f"Watch folder must be a directory: {path}")

        return str(path)

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Ensure max file size is reasonable."""
        if v <= 0:
            raise ValueError("max_file_size_mb must be positive")
        if v > 1000:  # 1GB limit
            raise ValueError("max_file_size_mb cannot exceed 1000MB")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {valid_levels}")
        return v.upper()

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def get_database_components(self) -> dict[str, Any]:
        """Parse database URL into components."""
        from urllib.parse import urlparse

        parsed = urlparse(self.database_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") or "doceater",
            "username": parsed.username,
            "password": parsed.password,
        }


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the current settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment and config files."""
    global _settings
    _settings = Settings()
    return _settings
