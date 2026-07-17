from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import Settings

LAST_FORTUNE_FILENAME = "last_fortune.json"


def _path(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / LAST_FORTUNE_FILENAME


def profile_signature(settings: Settings) -> str:
    payload = {
        "birth_calendar": settings.birth_calendar,
        "birth_date": settings.birth_date,
        "birth_time": settings.birth_time,
        "birth_place": settings.birth_place,
        "birth_gender": settings.birth_gender,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def profile_label(settings: Settings) -> str:
    calendar = chr(20844) + chr(21382) if settings.birth_calendar == "solar" else chr(20892) + chr(21382)
    gender = chr(30007) if settings.birth_gender == "male" else chr(22899) if settings.birth_gender == "female" else chr(26410) + chr(35774) + chr(32622)
    return f"{calendar} {chr(183)} {settings.birth_date} {settings.birth_time} {chr(183)} {settings.birth_place} {chr(183)} {gender}"


def save_last_fortune(settings: Settings, payload: dict[str, Any]) -> None:
    enriched = dict(payload)
    enriched.setdefault("profile_signature", profile_signature(settings))
    enriched.setdefault("profile_label", profile_label(settings))
    path = _path(settings)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_last_fortune(settings: Settings, current_profile_only: bool = True) -> dict[str, Any] | None:
    path = _path(settings)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if current_profile_only and data.get("profile_signature") != profile_signature(settings):
        return None
    return data
