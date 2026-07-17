from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.bazi import build_bazi_context, ten_god
from app.config import Settings


def test_ten_god_basic_mapping() -> None:
    assert ten_god("甲", "甲") == "比肩"
    assert ten_god("甲", "乙") == "劫财"
    assert ten_god("甲", "丙") == "食神"
    assert ten_god("甲", "辛") == "正官"


def test_build_bazi_context_contains_natal_and_flow() -> None:
    settings = Settings(
        WEB_ACCESS_TOKEN="test-token",
        MOCK_AI=True,
        BIRTH_CALENDAR="solar",
        BIRTH_DATE="1990-01-01",
        BIRTH_TIME="08:00",
        BIRTH_PLACE="北京",
        BIRTH_GENDER="male",
    )
    context = build_bazi_context(settings, datetime(2026, 7, 17, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")))
    assert context["target_date"] == "2026-07-17"
    assert len(context["natal_bazi"]) == 4
    assert context["flow"]["day"]["ganzhi"]
    assert context["day_master"]["stem"]
