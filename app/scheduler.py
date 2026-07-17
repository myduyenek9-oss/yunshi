from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .ai import generate_daily_report
from .bazi import build_bazi_context
from .config import Settings
from .dingtalk import send_markdown
from .storage import save_last_fortune

logger = logging.getLogger(__name__)


def generate_and_push(settings: Settings, target_dt: datetime | None = None) -> dict[str, str]:
    tz = ZoneInfo(settings.app_timezone)
    now = target_dt.astimezone(tz) if target_dt else datetime.now(tz)
    context = build_bazi_context(settings, now)
    report = generate_daily_report(settings, context)
    title = f"今日运势提醒 {context['target_date']}"
    result = send_markdown(settings, title=title, markdown_text=report)
    save_last_fortune(settings, {"date": context["target_date"], "content": report, "context": context, "dingtalk": result})
    logger.info("Daily fortune pushed for %s", context["target_date"])
    return {"date": context["target_date"], "status": "sent"}


def create_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.app_timezone))
    trigger = CronTrigger.from_crontab(settings.daily_push_cron, timezone=ZoneInfo(settings.app_timezone))
    scheduler.add_job(
        generate_and_push,
        trigger=trigger,
        args=[settings],
        id="daily_fortune_push",
        name="Daily fortune DingTalk push",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    return scheduler
