from __future__ import annotations

import html
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .ai import answer_question, generate_daily_report
from .bazi import build_bazi_context
from .config import Settings, get_settings
from .scheduler import create_scheduler, generate_and_push
from .storage import load_last_fortune, profile_label, save_last_fortune

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    settings = get_settings()
    scheduler = create_scheduler(settings)
    scheduler.start()
    logger.info("Scheduler started with cron '%s' in timezone %s", settings.daily_push_cron, settings.app_timezone)
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
            scheduler = None


app = FastAPI(title="Fortune Reminder", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    date: str


def _settings() -> Settings:
    return get_settings()


def _verify_bearer_token(authorization: str | None, settings: Settings) -> None:
    settings.require_web_auth()
    expected = f"Bearer {settings.web_access_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")


def require_api_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: Settings = Depends(_settings),
) -> Settings:
    try:
        _verify_bearer_token(authorization, settings)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return settings


ELEMENT_CLASS = {"\u6728": "wood", "\u706b": "fire", "\u571f": "earth", "\u91d1": "metal", "\u6c34": "water"}
ELEMENT_ICON = {"\u6728": "\u6728", "\u706b": "\u706b", "\u571f": "\u571f", "\u91d1": "\u91d1", "\u6c34": "\u6c34"}
ELEMENT_LABEL = {"\u6728": "\u6728\u884c", "\u706b": "\u706b\u884c", "\u571f": "\u571f\u884c", "\u91d1": "\u91d1\u884c", "\u6c34": "\u6c34\u884c"}
PILLAR_SHORT = {"\u5e74\u67f1": "\u5e74", "\u6708\u67f1": "\u6708", "\u65e5\u67f1": "\u65e5", "\u65f6\u67f1": "\u65f6"}


def _profile_snapshot(settings: Settings) -> dict[str, object]:
    try:
        context = build_bazi_context(settings, datetime.now(ZoneInfo(settings.app_timezone)))
        natal = context["natal_bazi"]
        flow = context["flow"]
        day_master = context["day_master"]

        def element_class(element: str | None) -> str:
            return ELEMENT_CLASS.get(element or "", "neutral")

        def card(title: str, value: str, subtitle: str, element: str | None, detail: str = "") -> dict[str, str]:
            return {
                "title": title,
                "value": value,
                "subtitle": subtitle,
                "detail": detail,
                "element": element or "",
                "elementClass": element_class(element),
                "symbol": ELEMENT_ICON.get(element or "", "\u00b7"),
                "elementLabel": ELEMENT_LABEL.get(element or "", "\u5f85\u5b9a"),
            }

        pillars = [{
            "name": p["name"], "short": PILLAR_SHORT.get(p["name"], p["name"]),
            "ganzhi": p["ganzhi"], "stem": p["stem"], "branch": p["branch"],
            "stemElement": p["stem_element"], "branchElement": p["branch_element"],
            "stemClass": element_class(p["stem_element"]), "branchClass": element_class(p["branch_element"]),
        } for p in natal]
        relation_preview = " \u00b7 ".join(
            f"{item.get('scope', '\u6d41\u65e5')}\uff1a{item.get('flow_ganzhi', '')} {item.get('ten_god_to_day_master', '')}".strip()
            for item in context.get("relations", [])[:2]
            if item.get("flow_ganzhi") or item.get("ten_god_to_day_master")
        )
        bazi_value = "  ".join(p["ganzhi"] for p in natal)
        return {
            "birth": f"{chr(20844) + chr(21382) if settings.birth_calendar == 'solar' else chr(20892) + chr(21382)} {settings.birth_date} {settings.birth_time} {chr(183)} {settings.birth_place} {chr(183)} {chr(30007) if settings.birth_gender == 'male' else chr(22899) if settings.birth_gender == 'female' else chr(26410) + chr(35774) + chr(32622)}",
            "targetDate": context["target_date"], "targetSolar": flow.get("solar", ""), "targetLunar": flow.get("lunar", ""),
            "pillars": pillars, "relations": context.get("relations", []),
            "relationPreview": relation_preview or "\u4eca\u65e5\u6682\u65e0\u660e\u663e\u7684\u51b2\u5408\u5211\u5bb3\u63d0\u793a\uff0c\u5b9c\u6309\u81ea\u5df1\u7684\u8282\u594f\u7a33\u6b65\u63a8\u8fdb\u3002",
            "cards": [
                card("\u672c\u547d\u56db\u67f1", bazi_value, "\u5e74\u67f1 \u00b7 \u6708\u67f1 \u00b7 \u65e5\u67f1 \u00b7 \u65f6\u67f1", day_master["element"], "\u7528\u4e8e\u89c2\u5bdf\u547d\u76d8\u6574\u4f53\u7ed3\u6784\u4e0e\u4e94\u884c\u5e95\u8272\u3002"),
                card("\u65e5\u4e3b", f"{day_master['stem']} \u00b7 {day_master['element']}", f"{day_master['yin_yang']}\u6027 \u00b7 \u65e5\u4e3b\u6838\u5fc3", day_master["element"], "\u65e5\u4e3b\u662f\u89e3\u8bfb\u5f53\u5929\u4f53\u9a8c\u4e0e\u884c\u52a8\u8282\u594f\u7684\u6838\u5fc3\u3002"),
                card("\u6d41\u5e74", flow["year"]["ganzhi"], f"\u5929\u5e72{flow['year']['stem_element']} \u00b7 \u5730\u652f{flow['year']['branch_element']}", flow["year"]["stem_element"], "\u5e74\u5ea6\u4e3b\u9898\u4e0e\u957f\u671f\u65b9\u5411\u53c2\u8003\u3002"),
                card("\u6d41\u6708", flow["month"]["ganzhi"], f"\u5929\u5e72{flow['month']['stem_element']} \u00b7 \u5730\u652f{flow['month']['branch_element']}", flow["month"]["stem_element"], "\u672c\u6708\u4e3b\u7ebf\u4e0e\u9636\u6bb5\u6027\u8282\u594f\u53c2\u8003\u3002"),
                card("\u6d41\u65e5", flow["day"]["ganzhi"], f"\u5929\u5e72{flow['day']['stem_element']} \u00b7 \u5730\u652f{flow['day']['branch_element']}", flow["day"]["stem_element"], "\u4eca\u65e5\u6c14\u573a\u4e0e\u884c\u4e8b\u63d0\u9192\u53c2\u8003\u3002"),
            ],
        }
    except Exception:
        logger.exception("Failed to build profile snapshot")
        return {}


def _fortune_page_html(*, token: str, settings: Settings, last_report: str, last_date: str, profile: str, snapshot: dict[str, object]) -> str:
    del settings
    template_path = __import__("pathlib").Path(__file__).with_name("fortune_page.html")
    template = template_path.read_text(encoding="utf-8-sig")
    replacements = {
        "__TOKEN__": json.dumps(token, ensure_ascii=False),
        "__LAST_REPORT__": json.dumps(last_report, ensure_ascii=False),
        "__LAST_DATE__": json.dumps(last_date, ensure_ascii=False),
        "__PROFILE__": json.dumps(profile, ensure_ascii=False),
        "__SNAPSHOT__": json.dumps(snapshot, ensure_ascii=False),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template.strip()



@app.get("/health")
def health(settings: Settings = Depends(_settings)) -> dict[str, object]:
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return {
        "status": "ok",
        "time": now.isoformat(),
        "timezone": settings.app_timezone,
        "scheduler_running": bool(scheduler and scheduler.running),
    }


@app.get("/fortune", response_class=HTMLResponse)
def fortune_page(
    token: str = Query(default=""),
    settings: Settings = Depends(_settings),
) -> HTMLResponse:
    try:
        settings.require_web_auth()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if token != settings.web_access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")

    snapshot = _profile_snapshot(settings)
    last = load_last_fortune(settings, current_profile_only=True)
    last_report = last.get("content") if last else "还没有为当前出生配置生成过运势。你可以先点击「生成今日日运」，或等待每天自动推送后再查看。"
    last_date = last.get("date") if last else "未生成"

    return HTMLResponse(
        content=_fortune_page_html(
            token=token,
            settings=settings,
            last_report=last_report,
            last_date=last_date,
            profile=profile_label(settings),
            snapshot=snapshot,
        ),
        media_type="text/html; charset=utf-8",
    )


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest, settings: Settings = Depends(require_api_token)) -> AskResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    now = datetime.now(ZoneInfo(settings.app_timezone))
    try:
        context = build_bazi_context(settings, now)
        last = load_last_fortune(settings, current_profile_only=True)
        last_summary = last.get("content") if last else None
        answer = answer_question(settings, context, question, last_summary=last_summary)
        return AskResponse(answer=answer, date=context["target_date"])
    except Exception as exc:
        logger.exception("Ask failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/push-now")
def push_now(settings: Settings = Depends(require_api_token)) -> dict[str, str]:
    try:
        return generate_and_push(settings)
    except Exception as exc:
        logger.exception("Manual push failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate-preview")
def generate_preview(settings: Settings = Depends(require_api_token)) -> dict[str, object]:
    """Generate current fortune and save it locally without sending DingTalk; useful for deployment smoke tests."""
    now = datetime.now(ZoneInfo(settings.app_timezone))
    try:
        context = build_bazi_context(settings, now)
        report = generate_daily_report(settings, context)
        save_last_fortune(settings, {"date": context["target_date"], "content": report, "context": context})
        return {"date": context["target_date"], "content": report}
    except Exception as exc:
        logger.exception("Preview generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
