"""User-facing configuration management for Orion."""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, Optional, Tuple

CURRENT_VERSION = 1
logger = logging.getLogger(__name__)


class SettingsError(RuntimeError):
    """Raised when configuration operations fail."""


def _encode_password(password: str) -> str:
    """Encode password for storage using base64."""
    if not password:
        return ""
    return base64.b64encode(password.encode('utf-8')).decode('utf-8')


def _decode_password(encoded: str) -> str:
    """Decode password from storage."""
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
    except Exception:
        # If decoding fails, return as-is (might be unencoded legacy password)
        return encoded


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password."""
    # Use alphanumeric characters (easier to type if needed)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class OrionSettings:
    """Persisted Orion configuration loaded from ``config.json``."""

    memgraph_host: str = "127.0.0.1"
    memgraph_port: int = 7687
    memgraph_user: str = "memgraph"  # Default Memgraph user
    memgraph_password_encoded: str = ""  # Base64 encoded password
    runtime_backend: str = "auto"
    qa_model: str = "gemma3:4b"
    embedding_backend: str = "auto"
    embedding_model: str = "openai/clip-vit-base-patch32"
    config_version: int = CURRENT_VERSION

    _KEY_ALIASES: ClassVar[Dict[str, str]] = {
        "memgraph.host": "memgraph_host",
        "memgraph.port": "memgraph_port",
        "memgraph.user": "memgraph_user",
        "memgraph.password": "memgraph_password_encoded",
        "runtime.backend": "runtime_backend",
        "runtime": "runtime_backend",
        "qa.model": "qa_model",
        "embedding.backend": "embedding_backend",
        "embedding.model": "embedding_model",
    }

    _SECRET_KEYS: ClassVar[Tuple[str, ...]] = ("memgraph.password",)
    _VALID_RUNTIMES: ClassVar[Tuple[str, ...]] = ("auto", "torch")
    _VALID_EMBEDDING_BACKENDS: ClassVar[Tuple[str, ...]] = (
        "auto",
        "ollama",
        "sentence-transformer",
    )
    
    def set_memgraph_password(self, password: str) -> None:
        """Set Memgraph password (will be encoded for storage)."""
        self.memgraph_password_encoded = _encode_password(password)
    
    def get_memgraph_password(self) -> str:
        """Get the actual Memgraph password (decoded)."""
        if not self.memgraph_password_encoded:
            return "" # Return empty if not set, Memgraph might not need it
        return _decode_password(self.memgraph_password_encoded)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    @classmethod
    def config_path(cls) -> Path:
        """Return the location of the user configuration file."""
        env_path = os.getenv("ORION_CONFIG_PATH")
        if env_path:
            path = Path(env_path).expanduser()
        else:
            base_dir = Path(
                os.getenv("ORION_CONFIG_DIR", Path.home() / ".orion")
            ).expanduser()
            path = base_dir / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def load(cls) -> "OrionSettings":
        """Load settings from disk, creating defaults if necessary."""
        path = cls.config_path()
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings

        try:
            raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (
            json.JSONDecodeError
        ) as exc:  # pragma: no cover - invalid config edge case
            raise SettingsError(
                f"Configuration file at {path} is not valid JSON: {exc}"
            ) from exc

        known_fields = {field.name for field in fields(cls)}
        data: Dict[str, Any] = {}
        for name in known_fields:
            if name in raw:
                data[name] = raw[name]

        settings = cls(**data)
        settings.config_version = CURRENT_VERSION
        try:
            settings.validate()
        except SettingsError:
            # If validation fails, do not persist; just surface the error.
            raise

        # Ensure new defaults are written back so the file stays current.
        settings.save(path)
        return settings

    def save(self, path: Path | None = None) -> None:
        """Persist the current settings to disk."""
        self.validate()
        target = path or self.config_path()
        payload = self.to_dict()
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def iter_display_items(self) -> Iterable[Tuple[str, str]]:
        """Yield human-friendly key/value pairs for CLI display."""
        ordering = (
            "memgraph.host",
            "memgraph.port",
            "memgraph.user",
            "memgraph.password",
            "runtime.backend",
            "qa.model",
            "embedding.backend",
            "embedding.model",
        )
        flat = self._flatten()
        for key in ordering:
            value = flat.get(key)
            if value is None:
                continue
            if key in self._SECRET_KEYS:
                yield key, self._mask_secret(value)
            else:
                yield key, str(value)

    def _flatten(self) -> Dict[str, Any]:
        # Show decoded password (masked) for display
        password_display = ""
        if self.memgraph_password_encoded:
            try:
                password_display = self.get_memgraph_password()
            except Exception:
                password_display = ""
        
        return {
            "memgraph.host": self.memgraph_host,
            "memgraph.port": self.memgraph_port,
            "memgraph.user": self.memgraph_user,
            "memgraph.password": password_display,
            "runtime.backend": self.runtime_backend,
            "qa.model": self.qa_model,
            "embedding.backend": self.embedding_backend,
            "embedding.model": self.embedding_model,
        }

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}…{value[-2:]}"

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def set_value(self, key: str, raw_value: str) -> None:
        """Update a configuration value using CLI-friendly keys."""
        field_name = self._resolve_field_name(key)
        value = raw_value.strip()

        if field_name == "runtime_backend":
            normalized = value.lower()
            if normalized == "mlx":
                normalized = "torch"
            if normalized not in self._VALID_RUNTIMES:
                raise SettingsError(
                    f"Runtime backend must be one of {self._VALID_RUNTIMES}."
                )
            value = normalized
        elif field_name == "embedding_backend":
            normalized = value.lower()
            if normalized not in self._VALID_EMBEDDING_BACKENDS:
                raise SettingsError(
                    f"Embedding backend must be one of {self._VALID_EMBEDDING_BACKENDS}."
                )
            value = normalized
        elif field_name == "memgraph_host":
            value = value or self.memgraph_host
        elif field_name == "memgraph_port":
            try:
                value = int(value)
            except ValueError:
                raise SettingsError("Memgraph port must be an integer.")
        elif field_name == "memgraph_password_encoded":
            # User provides plain password, we encode it
            self.set_memgraph_password(value)
            return
        elif field_name in {
            "memgraph_user",
            "qa_model",
            "embedding_model",
        }:
            if not value:
                raise SettingsError(f"Configuration '{key}' cannot be empty.")
        else:  # pragma: no cover - future-proof branch
            raise SettingsError(f"'{key}' cannot be modified via the CLI.")

        setattr(self, field_name, value)

    def _resolve_field_name(self, key: str) -> str:
        normalized = key.strip().lower().replace("_", ".")
        alias = self._KEY_ALIASES.get(normalized)
        if alias:
            return alias
        normalized = normalized.replace("-", ".")
        alias = self._KEY_ALIASES.get(normalized)
        if alias:
            return alias
        raise SettingsError(f"Unknown configuration key '{key}'.")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> None:
        if self.runtime_backend not in self._VALID_RUNTIMES:
            raise SettingsError(
                f"Runtime backend must be one of {self._VALID_RUNTIMES}."
            )
        if self.embedding_backend not in self._VALID_EMBEDDING_BACKENDS:
            raise SettingsError(
                f"Embedding backend must be one of {self._VALID_EMBEDDING_BACKENDS}."
            )
        # Memgraph is optional - only validate if configured
        # if not self.memgraph_host:
        #     raise SettingsError("Memgraph host cannot be empty.")
        # if not self.memgraph_user:
        #     raise SettingsError("Memgraph user cannot be empty.")

        # Password is optional for perception-only mode
        # if not self.memgraph_password_encoded:
        #     raise SettingsError(
        #         "Memgraph password not configured. Run 'orion init' to set up."
        #     )

        if not self.qa_model:
            raise SettingsError("QA model cannot be empty.")
        if not self.embedding_model:
            raise SettingsError("Embedding model cannot be empty.")


# ============================================================================
# Runtime Configuration Manager (OrionConfig)
# ============================================================================
# This section handles runtime OrionConfig objects (detection, clustering, etc.)
# as opposed to user settings above (credentials, preferences, etc.)


class ConfigManager:
    """
    Unified configuration manager for Orion runtime config.
    
    Manages OrionConfig objects (detection settings, clustering params, etc.)
    loaded from environment variables and config files.
    
    Note: This is separate from OrionSettings which handles user preferences
    like credentials and backend selection.
    """

    _instance: Optional["ConfigManager"] = None
    _config: Optional["OrionConfig"] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_config(cls) -> "OrionConfig":
        """Get the current Orion runtime configuration."""
        if cls._config is None:
            cls._config = cls._load_from_environment()
        return cls._config

    @classmethod
    def set_config(cls, config: "OrionConfig") -> None:
        """Set the Orion runtime configuration."""
        cls._config = config

    @classmethod
    def _load_from_environment(cls) -> "OrionConfig":
        """
        Load configuration from environment variables and config file.

        Environment variable precedence:
        - ORION_NEO4J_URI
        - ORION_NEO4J_USER
        - ORION_NEO4J_PASSWORD (via password_env_var)
        - ORION_OLLAMA_URL
        - ORION_OLLAMA_QA_MODEL
        - ORION_RUNTIME_BACKEND
        - ORION_CONFIG_PATH (for persisted config file)
        """
        from orion.managers.config import OrionConfig

        config = OrionConfig()

        # Load Neo4j config from environment
        if uri := os.getenv("ORION_NEO4J_URI"):
            config.neo4j.uri = uri
        if user := os.getenv("ORION_NEO4J_USER"):
            config.neo4j.user = user

        # Set password environment variable name (for secure access)
        if pwd_var := os.getenv("ORION_NEO4J_PASSWORD_VAR"):
            config.neo4j.password_env_var = pwd_var

        # Load Ollama config from environment
        if url := os.getenv("ORION_OLLAMA_URL"):
            config.ollama.base_url = url
        if qa_model := os.getenv("ORION_OLLAMA_QA_MODEL"):
            config.ollama.qa_model = qa_model

        # Load runtime config from environment
        if backend := os.getenv("ORION_RUNTIME_BACKEND"):
            config.runtime.backend = backend  # type: ignore
        if device := os.getenv("ORION_DEVICE"):
            config.runtime.device = device  # type: ignore

        return config

    @classmethod
    def save_config(cls, config: Optional["OrionConfig"] = None) -> Path:
        """
        Save runtime configuration to disk.

        Note: Passwords and secrets are NOT saved. They must be set
        via environment variables for security.
        """
        if config is None:
            config = cls.get_config()

        config_path = cls.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Build dict, excluding password fields
        config_dict = {
            "neo4j": {
                "uri": config.neo4j.uri,
                "user": config.neo4j.user,
                "password_env_var": config.neo4j.password_env_var,
            },
            "ollama": {
                "base_url": config.ollama.base_url,
                "qa_model": config.ollama.qa_model,
                "embedding_model": config.ollama.embedding_model,
            },
            "runtime": {
                "backend": config.runtime.backend,
                "device": config.runtime.device,
            },
        }

        with open(config_path, "w") as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Configuration saved to {config_path}")
        return config_path

    @classmethod
    def load_config_file(cls) -> Optional["OrionConfig"]:
        """
        Load configuration from persisted config file.

        Returns None if file doesn't exist. Raises ValueError if file is invalid.
        """
        from orion.managers.config import OrionConfig

        config_path = cls.get_config_path()

        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                data = json.load(f)

            config = OrionConfig()

            # Load Neo4j config
            if neo4j_data := data.get("neo4j"):
                if "uri" in neo4j_data:
                    config.neo4j.uri = neo4j_data["uri"]
                if "user" in neo4j_data:
                    config.neo4j.user = neo4j_data["user"]
                if "password_env_var" in neo4j_data:
                    config.neo4j.password_env_var = neo4j_data["password_env_var"]

            # Load Ollama config
            if ollama_data := data.get("ollama"):
                if "base_url" in ollama_data:
                    config.ollama.base_url = ollama_data["base_url"]
                if "qa_model" in ollama_data:
                    config.ollama.qa_model = ollama_data["qa_model"]
                if "embedding_model" in ollama_data:
                    config.ollama.embedding_model = ollama_data["embedding_model"]

            # Load runtime config
            if runtime_data := data.get("runtime"):
                if "backend" in runtime_data:
                    config.runtime.backend = runtime_data["backend"]  # type: ignore
                if "device" in runtime_data:
                    config.runtime.device = runtime_data["device"]  # type: ignore

            logger.info(f"Configuration loaded from {config_path}")
            return config

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid config file {config_path}: {e}")

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        env_path = os.getenv("ORION_CONFIG_PATH")
        if env_path:
            return Path(env_path).expanduser()

        config_dir = Path(
            os.getenv("ORION_CONFIG_DIR", Path.home() / ".orion")
        ).expanduser()
        return config_dir / "config.json"

    @classmethod
    def validate_neo4j_connection(cls, config: Optional["OrionConfig"] = None) -> bool:
        """
        Validate Neo4j connection without connecting.

        Returns True if credentials are set and parseable, False otherwise.
        """
        if config is None:
            config = cls.get_config()

        # Check URI format
        if not config.neo4j.uri:
            logger.warning("Neo4j URI not configured")
            return False

        # Check credentials exist
        if not config.neo4j.user:
            logger.warning("Neo4j user not configured")
            return False

        # Check password environment variable is set
        try:
            _ = config.neo4j.password
        except ValueError as e:
            logger.warning(f"Neo4j password not set: {e}")
            return False

        return True

    @classmethod
    def validate_ollama_connection(cls, config: Optional["OrionConfig"] = None) -> bool:
        """
        Validate Ollama connection settings are configured.

        Returns True if settings look valid, False otherwise.
        """
        if config is None:
            config = cls.get_config()

        if not config.ollama.base_url:
            logger.warning("Ollama base URL not configured")
            return False

        if not config.ollama.qa_model:
            logger.warning("Ollama Q&A model not configured")
            return False

        return True
