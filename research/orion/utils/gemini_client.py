from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Optional


class GeminiClientError(RuntimeError):

    pass


def load_dotenv(env_path: Optional[Path] = None) -> None:

    """Load environment variables from a .env file (without clobbering existing env)."""

    if env_path is None:
        # repo root / .env
        env_path = Path(__file__).resolve().parents[2] / ".env"

    if not env_path.exists():
        return

    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def get_api_key() -> Optional[str]:

    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def _import_google_genai():

    """Import google-genai and return (genai, types).

    We keep this import lazy so the rest of Orion can run without Gemini deps.
    """

    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise GeminiClientError(
            "google-genai is not installed. Install it via 'pip install google-genai'."
        ) from exc

    return genai, types


def _image_part_from_bytes(types_mod, data: bytes, mime_type: str):

    # Signature has changed across versions; support both.
    try:
        return types_mod.Part.from_bytes(data=data, mime_type=mime_type)
    except TypeError:
        return types_mod.Part.from_bytes(data, mime_type)


def _coerce_image_to_bytes(obj: Any, mime_type: str) -> bytes:

    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj)

    if isinstance(obj, str):
        # Treat as base64-encoded payload.
        return base64.b64decode(obj)

    # PIL.Image.Image support
    try:
        import PIL.Image  # type: ignore

        if isinstance(obj, PIL.Image.Image):
            buf = BytesIO()
            fmt = "JPEG" if mime_type == "image/jpeg" else None
            obj.save(buf, format=fmt)
            return buf.getvalue()
    except Exception:
        pass

    raise GeminiClientError(f"Unsupported image payload type: {type(obj)}")


def normalize_old_style_contents(contents: Any):

    """Convert legacy google.generativeai-style 'contents' into google.genai contents.

    Supported legacy items:
    - str
    - list[str | dict{"mime_type","data"} | PIL.Image.Image]
      where data is base64 str or raw bytes.
    """

    _, types_mod = _import_google_genai()

    if isinstance(contents, str):
        return contents

    if isinstance(contents, list):
        out: list[Any] = []
        for item in contents:
            if isinstance(item, str):
                out.append(item)
                continue

            if isinstance(item, dict) and "mime_type" in item and "data" in item:
                mime_type = str(item.get("mime_type") or "image/jpeg")
                data_bytes = _coerce_image_to_bytes(item["data"], mime_type)
                out.append(_image_part_from_bytes(types_mod, data_bytes, mime_type))
                continue

            # Allow direct PIL images
            try:
                import PIL.Image  # type: ignore

                if isinstance(item, PIL.Image.Image):
                    data_bytes = _coerce_image_to_bytes(item, "image/jpeg")
                    out.append(_image_part_from_bytes(types_mod, data_bytes, "image/jpeg"))
                    continue
            except Exception:
                pass

            out.append(item)

        return out

    return contents


@dataclass
class GeminiModel:

    """Adapter that mimics google.generativeai.GenerativeModel.generate_content()."""

    model_name: str
    api_key: str

    def __post_init__(self) -> None:
        genai, _ = _import_google_genai()
        self._client = genai.Client(api_key=self.api_key)

    def generate_content(self, contents: Any):
        contents_norm = normalize_old_style_contents(contents)
        return self._client.models.generate_content(model=self.model_name, contents=contents_norm)


def get_gemini_model(model_name: str, api_key: Optional[str] = None) -> GeminiModel:

    load_dotenv()
    api_key = api_key or get_api_key()
    if not api_key:
        raise GeminiClientError(
            "Missing GOOGLE_API_KEY or GEMINI_API_KEY. Add it to environment or .env (repo root)."
        )
    return GeminiModel(model_name=model_name, api_key=api_key)
