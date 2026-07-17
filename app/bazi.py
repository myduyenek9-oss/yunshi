from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import Settings

try:
    from lunar_python import Lunar, Solar
except Exception:  # pragma: no cover - exercised only when dependency is missing
    Lunar = None  # type: ignore[assignment]
    Solar = None  # type: ignore[assignment]

HEAVENLY_STEMS = "甲乙丙丁戊己庚辛壬癸"
EARTHLY_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

STEM_ELEMENT = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
STEM_YINYANG = {
    "甲": "阳", "丙": "阳", "戊": "阳", "庚": "阳", "壬": "阳",
    "乙": "阴", "丁": "阴", "己": "阴", "辛": "阴", "癸": "阴",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
BRANCH_ELEMENT = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
BRANCH_CLASH = {"子": "午", "丑": "未", "寅": "申", "卯": "酉", "辰": "戌", "巳": "亥"}
BRANCH_COMBINE = {"子": "丑", "寅": "亥", "卯": "戌", "辰": "酉", "巳": "申", "午": "未"}
BRANCH_HARM = {"子": "未", "丑": "午", "寅": "巳", "卯": "辰", "申": "亥", "酉": "戌"}


@dataclass(frozen=True)
class Pillar:
    name: str
    ganzhi: str

    @property
    def stem(self) -> str:
        return self.ganzhi[0] if self.ganzhi else ""

    @property
    def branch(self) -> str:
        return self.ganzhi[1] if len(self.ganzhi) >= 2 else ""

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "ganzhi": self.ganzhi,
            "stem": self.stem,
            "branch": self.branch,
            "stem_element": STEM_ELEMENT.get(self.stem, "未知"),
            "branch_element": BRANCH_ELEMENT.get(self.branch, "未知"),
        }


def _call_first(obj: Any, method_names: list[str]) -> str:
    for method_name in method_names:
        method = getattr(obj, method_name, None)
        if callable(method):
            value = method()
            if value:
                return str(value)
    raise RuntimeError(f"lunar-python object does not expose any of: {method_names}")


def _parse_ymd(value: str) -> tuple[int, int, int]:
    year, month, day = value.split("-")
    return int(year), int(month), int(day)


def _parse_hms(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def _solar_from_settings(settings: Settings):
    if Solar is None or Lunar is None:
        raise RuntimeError("lunar-python dependency is not installed")
    year, month, day = _parse_ymd(settings.birth_date)
    hour, minute, second = _parse_hms(settings.birth_time)
    if settings.birth_calendar == "solar":
        return Solar.fromYmdHms(year, month, day, hour, minute, second)
    lunar = Lunar.fromYmdHms(year, month, day, hour, minute, second)
    return lunar.getSolar()


def _solar_from_datetime(dt: datetime):
    if Solar is None:
        raise RuntimeError("lunar-python dependency is not installed")
    return Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _pillars_from_lunar(lunar: Any) -> list[Pillar]:
    eight = lunar.getEightChar()
    return [
        Pillar("年柱", _call_first(eight, ["getYear"])),
        Pillar("月柱", _call_first(eight, ["getMonth"])),
        Pillar("日柱", _call_first(eight, ["getDay"])),
        Pillar("时柱", _call_first(eight, ["getTime"])),
    ]


def ten_god(day_stem: str, other_stem: str) -> str:
    self_element = STEM_ELEMENT.get(day_stem)
    other_element = STEM_ELEMENT.get(other_stem)
    if not self_element or not other_element:
        return "未知"
    same_yinyang = STEM_YINYANG.get(day_stem) == STEM_YINYANG.get(other_stem)
    if self_element == other_element:
        return "比肩" if same_yinyang else "劫财"
    if GENERATES[self_element] == other_element:
        return "食神" if same_yinyang else "伤官"
    if GENERATES[other_element] == self_element:
        return "偏印" if same_yinyang else "正印"
    if CONTROLS[self_element] == other_element:
        return "偏财" if same_yinyang else "正财"
    if CONTROLS[other_element] == self_element:
        return "七杀" if same_yinyang else "正官"
    return "未知"


def _branch_relation(one: str, other: str) -> str | None:
    if BRANCH_CLASH.get(one) == other or BRANCH_CLASH.get(other) == one:
        return "冲"
    if BRANCH_COMBINE.get(one) == other or BRANCH_COMBINE.get(other) == one:
        return "合"
    if BRANCH_HARM.get(one) == other or BRANCH_HARM.get(other) == one:
        return "害"
    return None


def _flow_relations(natal: list[Pillar], flow: list[Pillar]) -> list[dict[str, str]]:
    natal_day_stem = natal[2].stem
    relations: list[dict[str, str]] = []
    for flow_pillar in flow[:3]:
        relations.append({
            "scope": flow_pillar.name,
            "flow_ganzhi": flow_pillar.ganzhi,
            "flow_stem_element": STEM_ELEMENT.get(flow_pillar.stem, "未知"),
            "ten_god_to_day_master": ten_god(natal_day_stem, flow_pillar.stem),
        })
    branch_notes: list[str] = []
    for natal_pillar in natal:
        for flow_pillar in flow[:3]:
            relation = _branch_relation(natal_pillar.branch, flow_pillar.branch)
            if relation:
                branch_notes.append(
                    f"本命{natal_pillar.name}{natal_pillar.branch} 与 流{flow_pillar.name}{flow_pillar.branch} 形成{relation}"
                )
    if branch_notes:
        relations.append({"scope": "地支关系", "flow_ganzhi": "；".join(branch_notes), "flow_stem_element": "", "ten_god_to_day_master": ""})
    return relations


def build_bazi_context(settings: Settings, target_dt: datetime) -> dict[str, Any]:
    birth_solar = _solar_from_settings(settings)
    birth_lunar = birth_solar.getLunar()
    birth_pillars = _pillars_from_lunar(birth_lunar)

    target_solar = _solar_from_datetime(target_dt)
    target_lunar = target_solar.getLunar()
    target_pillars = _pillars_from_lunar(target_lunar)

    solar_birth_date = _call_first(birth_solar, ["toYmdHms", "toFullString", "toString"])
    lunar_birth_date = _call_first(birth_lunar, ["toYmdHms", "toFullString", "toString"])
    solar_target_date = _call_first(target_solar, ["toYmd", "toYmdHms", "toString"])
    lunar_target_date = _call_first(target_lunar, ["toYmd", "toYmdHms", "toString"])

    day_master = birth_pillars[2].stem
    day_master_element = STEM_ELEMENT.get(day_master, "未知")

    return {
        "target_date": target_dt.strftime("%Y-%m-%d"),
        "target_datetime": target_dt.isoformat(),
        "birth": {
            "configured_calendar": settings.birth_calendar,
            "solar": solar_birth_date,
            "lunar": lunar_birth_date,
            "place": settings.birth_place,
            "gender": settings.birth_gender,
        },
        "natal_bazi": [pillar.as_dict() for pillar in birth_pillars],
        "day_master": {
            "stem": day_master,
            "element": day_master_element,
            "yin_yang": STEM_YINYANG.get(day_master, "未知"),
        },
        "flow": {
            "solar": solar_target_date,
            "lunar": lunar_target_date,
            "year": target_pillars[0].as_dict(),
            "month": target_pillars[1].as_dict(),
            "day": target_pillars[2].as_dict(),
        },
        "relations": _flow_relations(birth_pillars, target_pillars),
        "disclaimer": "运势分析仅供个人参考，不作为医疗、投资、法律等专业决策依据。",
    }
