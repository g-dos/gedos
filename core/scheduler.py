"""
GEDOS Scheduler — APScheduler integration with SQLite persistence.
Handles recurring and one-time scheduled tasks.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import parsedatetime
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from tzlocal import get_localzone

from core.memory import (
    ScheduledTask,
    add_scheduled_task,
    delete_scheduled_task,
    get_scheduled_task_by_id,
    get_scheduled_tasks,
    get_user_timezone,
    set_user_timezone,
    update_scheduled_task,
)

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_CALENDAR = parsedatetime.Calendar()
_DAY_ORDER = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
_DAY_TO_CRON = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}
_NAMED_TIMES = {"midnight": "00:00", "noon": "12:00"}


def _get_zoneinfo(name: Optional[str]) -> ZoneInfo:
    """Return a valid ZoneInfo, falling back to UTC."""
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def get_system_timezone() -> str:
    """Detect the system timezone using tzlocal."""
    try:
        zone = get_localzone()
        name = getattr(zone, "key", None) or str(zone)
        if name:
            return str(name)
    except Exception:
        logger.exception("Failed to detect local timezone")
    return "UTC"


def ensure_user_timezone(user_id: str) -> tuple[str, bool]:
    """Return the stored timezone for a user, storing the system timezone on first use."""
    stored = get_user_timezone(str(user_id))
    if stored:
        return stored, False
    detected = get_system_timezone()
    set_user_timezone(str(user_id), detected)
    return detected, True


def get_scheduler(timezone: Optional[str] = None) -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        tz = timezone or "UTC"
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}
        job_defaults = {"coalesce": False, "max_instances": 3}
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=_get_zoneinfo(tz),
        )
        logger.info("APScheduler created (timezone=%s)", tz)
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler if not already running."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
        _register_maintenance_jobs()
        _load_schedules_from_db()


def stop_scheduler() -> None:
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def _load_schedules_from_db() -> None:
    """Load all active scheduled tasks from database and register them with APScheduler."""
    try:
        for task in get_scheduled_tasks(active_only=True):
            try:
                _register_task_with_scheduler(task)
                logger.info("Loaded scheduled task %s: %s", task.id, task.task_description[:50])
            except Exception as exc:
                logger.error("Failed to load scheduled task %s: %s", task.id, exc)
    except Exception as exc:
        logger.error("Failed to load schedules from database: %s", exc)


def _run_retention_cleanup() -> None:
    """Run privacy retention cleanup for all known users."""
    try:
        from core.memory import cleanup_all_users

        deleted = cleanup_all_users()
        if deleted:
            logger.info("Retention cleanup removed %s expired row(s)", deleted)
    except Exception as exc:
        logger.error("Retention cleanup failed: %s", exc)


def _register_maintenance_jobs() -> None:
    """Register scheduler maintenance jobs once."""
    scheduler = get_scheduler("UTC")
    if scheduler.get_job("gedos_retention_cleanup") is None:
        scheduler.add_job(
            _run_retention_cleanup,
            trigger=CronTrigger(hour=3, minute=0, timezone=UTC),
            id="gedos_retention_cleanup",
            replace_existing=True,
        )


def _job_prefix(task_id: int) -> str:
    """Return the stable APScheduler job prefix for one scheduled task."""
    return f"task_{task_id}"


def _split_times(schedule_time: str) -> list[str]:
    """Split stored schedule times (comma-separated HH:MM values)."""
    return [part.strip() for part in str(schedule_time).split(",") if part.strip()]


def _split_days(day_of_week: Optional[str]) -> list[str]:
    """Split stored weekday lists."""
    if not day_of_week:
        return []
    return [part.strip().lower() for part in str(day_of_week).split(",") if part.strip()]


def _days_to_cron(days: list[str]) -> str:
    """Convert weekday names to a Cron day-of-week string."""
    cron_days = [_DAY_TO_CRON.get(day, day[:3].lower()) for day in days]
    return ",".join(cron_days) if cron_days else "mon"


def _register_task_with_scheduler(task: ScheduledTask) -> None:
    """Register a ScheduledTask with APScheduler."""
    scheduler = get_scheduler("UTC")
    prefix = _job_prefix(task.id)
    job_ids: list[str] = []

    if task.frequency == "once":
        hour, minute = map(int, str(task.schedule_time).split(":"))
        target_date = task.schedule_date or datetime.now(UTC).date().isoformat()
        year, month, day = map(int, target_date.split("-"))
        run_at = datetime(year, month, day, hour, minute, tzinfo=UTC)
        trigger = DateTrigger(run_date=run_at, timezone=UTC)
        job_id = prefix
        scheduler.add_job(_execute_scheduled_task, trigger=trigger, args=[task.id], id=job_id, replace_existing=True)
        job_ids.append(job_id)
    elif task.frequency == "daily":
        for index, hhmm in enumerate(_split_times(task.schedule_time), start=1):
            hour, minute = map(int, hhmm.split(":"))
            trigger = CronTrigger(hour=hour, minute=minute, timezone=UTC)
            job_id = f"{prefix}_{index}"
            scheduler.add_job(_execute_scheduled_task, trigger=trigger, args=[task.id], id=job_id, replace_existing=True)
            job_ids.append(job_id)
    elif task.frequency == "weekly":
        days = _split_days(task.day_of_week)
        cron_days = _days_to_cron(days)
        for index, hhmm in enumerate(_split_times(task.schedule_time), start=1):
            hour, minute = map(int, hhmm.split(":"))
            trigger = CronTrigger(day_of_week=cron_days, hour=hour, minute=minute, timezone=UTC)
            job_id = f"{prefix}_{index}"
            scheduler.add_job(_execute_scheduled_task, trigger=trigger, args=[task.id], id=job_id, replace_existing=True)
            job_ids.append(job_id)
    elif task.frequency == "interval":
        minutes = int(str(task.schedule_time))
        trigger = IntervalTrigger(minutes=minutes, timezone=UTC)
        job_id = prefix
        scheduler.add_job(_execute_scheduled_task, trigger=trigger, args=[task.id], id=job_id, replace_existing=True)
        job_ids.append(job_id)
    else:
        raise ValueError(f"Unsupported frequency: {task.frequency}")

    update_scheduled_task(task.id, job_id=",".join(job_ids))


async def _execute_scheduled_task(task_id: int) -> None:
    """Execute a scheduled task in Pilot Mode."""
    try:
        task = get_scheduled_task_by_id(task_id)
        if not task or not task.is_active:
            logger.warning("Scheduled task %s not found or inactive", task_id)
            return

        logger.info("Executing scheduled task %s: %s", task_id, task.task_description)
        from interfaces.telegram_bot import _execute_task_autonomously

        result = await _execute_task_autonomously(task=task.task_description, user_id=int(task.user_id))
        update_scheduled_task(task_id, last_run=datetime.utcnow())

        if task.frequency == "once":
            update_scheduled_task(task_id, is_active=False)
            scheduler = get_scheduler()
            prefix = _job_prefix(task_id)
            for job in list(scheduler.get_jobs()):
                if job.id == prefix or job.id.startswith(f"{prefix}_"):
                    scheduler.remove_job(job.id)

        logger.info("Scheduled task %s completed: %s", task_id, result.get("success", False))
    except Exception as exc:
        logger.exception("Failed to execute scheduled task %s: %s", task_id, exc)


def _parse_natural_time(time_str: str) -> Optional[str]:
    """Parse natural language time to HH:MM."""
    candidate = time_str.strip().lower()
    if candidate in _NAMED_TIMES:
        return _NAMED_TIMES[candidate]
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", candidate)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = (match.group(3) or "").lower()
    if minute > 59:
        return None
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if not ampm and hour > 23:
        return None
    if hour > 23:
        return None
    return f"{hour:02d}:{minute:02d}"


def _format_12h(hhmm: str) -> str:
    """Format HH:MM to 12-hour display."""
    parsed = datetime.strptime(hhmm, "%H:%M")
    display = parsed.strftime("%I:%M %p")
    if display.startswith("0"):
        display = display[1:]
    return display


def _format_days(days: list[str]) -> str:
    """Return a human-readable weekday label."""
    if days == _DAY_ORDER[:5]:
        return "weekday"
    if len(days) == 1:
        return days[0].title()
    if len(days) == 2:
        return f"{days[0].title()} and {days[1].title()}"
    return ", ".join(day.title() for day in days[:-1]) + f", and {days[-1].title()}"


def _extract_times(text: str) -> list[str]:
    """Extract one or more times from a natural-language schedule expression."""
    lowered = text.lower()
    found: list[str] = []
    for word, hhmm in _NAMED_TIMES.items():
        if re.search(rf"\b{word}\b", lowered):
            found.append(hhmm)
    for match in re.finditer(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", lowered):
        parsed = _parse_natural_time(match.group(0))
        if parsed:
            found.append(parsed)
    if not found and "morning" in lowered:
        found.append("09:00")
    if not found and "night" in lowered:
        found.append("00:00")
    ordered: list[str] = []
    for hhmm in found:
        if hhmm not in ordered:
            ordered.append(hhmm)
    return ordered


def _weekday_list_from_text(text: str) -> list[str]:
    """Extract weekday names from an expression."""
    lowered = text.lower()
    if "weekday" in lowered or "weekdays" in lowered:
        return _DAY_ORDER[:5]
    found = [day for day in _DAY_ORDER if day in lowered]
    return found


def _humanize_schedule(
    schedule_type: str,
    times: list[str],
    days: Optional[list[str]],
    interval_minutes: Optional[int],
    run_at: Optional[datetime],
) -> str:
    """Build a user-facing confirmation string."""
    if schedule_type == "interval" and interval_minutes is not None:
        if interval_minutes == 60:
            return "Every hour"
        if interval_minutes % 60 == 0:
            hours = interval_minutes // 60
            unit = "hour" if hours == 1 else "hours"
            return f"Every {hours} {unit}"
        return f"Every {interval_minutes} minutes"
    if schedule_type == "once" and run_at is not None:
        return f"Once at {run_at.strftime('%a, %b %d %I:%M %p').replace(' 0', ' ')}"
    if schedule_type == "daily":
        if len(times) > 1:
            rendered = " and ".join(_format_12h(item) for item in times)
            return f"Every day at {rendered}"
        return f"Every day at {_format_12h(times[0])}"
    if schedule_type == "weekly" and days:
        rendered_times = " and ".join(_format_12h(item) for item in times)
        return f"Every {_format_days(days)} at {rendered_times}"
    return "Custom schedule"


def parse_schedule_expression(text: str, user_tz: str) -> Optional[dict[str, Any]]:
    """
    Parse a natural-language schedule expression into a structured representation.
    """
    raw = text.strip()
    lowered = re.sub(r"\s+", " ", raw.lower())
    if not lowered:
        return None

    tz = _get_zoneinfo(user_tz)
    now_local = datetime.now(tz)
    times = _extract_times(lowered)

    if re.fullmatch(r"every hour", lowered):
        return {
            "type": "interval",
            "days": None,
            "times": [],
            "interval_minutes": 60,
            "run_at": None,
            "raw": raw,
            "human_readable": "Every hour",
        }

    interval_match = re.fullmatch(r"every (\d+) (minute|minutes|hour|hours)", lowered)
    if interval_match:
        amount = int(interval_match.group(1))
        if amount <= 0:
            return None
        unit = interval_match.group(2)
        minutes = amount * 60 if unit.startswith("hour") else amount
        return {
            "type": "interval",
            "days": None,
            "times": [],
            "interval_minutes": minutes,
            "run_at": None,
            "raw": raw,
            "human_readable": _humanize_schedule("interval", [], None, minutes, None),
        }

    if lowered.startswith("in "):
        relative_match = re.fullmatch(r"in\s+(-?\d+)\s+(minute|minutes|hour|hours)", lowered)
        if relative_match and int(relative_match.group(1)) <= 0:
            return None
        run_at, status = _CALENDAR.parseDT(lowered, sourceTime=now_local, tzinfo=tz)
        if status > 0:
            if run_at <= now_local:
                return None
            return {
                "type": "once",
                "days": None,
                "times": [run_at.strftime("%H:%M")],
                "interval_minutes": None,
                "run_at": run_at.astimezone(tz),
                "raw": raw,
                "human_readable": _humanize_schedule("once", [run_at.strftime("%H:%M")], None, None, run_at.astimezone(tz)),
            }

    if lowered.startswith("once ") or lowered.startswith("next "):
        candidate = lowered[5:] if lowered.startswith("once ") else lowered
        run_at, status = _CALENDAR.parseDT(candidate, sourceTime=now_local, tzinfo=tz)
        if status > 0:
            localized = run_at.astimezone(tz)
            return {
                "type": "once",
                "days": None,
                "times": [localized.strftime("%H:%M")],
                "interval_minutes": None,
                "run_at": localized,
                "raw": raw,
                "human_readable": _humanize_schedule("once", [localized.strftime("%H:%M")], None, None, localized),
            }

    if lowered.startswith("daily ") or lowered.startswith("every day") or lowered.startswith("every morning") or lowered.startswith("every night"):
        if not times:
            return None
        return {
            "type": "daily",
            "days": None,
            "times": times,
            "interval_minutes": None,
            "run_at": None,
            "raw": raw,
            "human_readable": _humanize_schedule("daily", times, None, None, None),
        }

    if lowered.startswith("twice a day"):
        if len(times) < 2:
            return None
        return {
            "type": "daily",
            "days": None,
            "times": times[:2],
            "interval_minutes": None,
            "run_at": None,
            "raw": raw,
            "human_readable": _humanize_schedule("daily", times[:2], None, None, None),
        }

    if lowered.startswith("every weekday") or lowered.startswith("weekdays"):
        chosen_times = times or ["09:00"]
        days = _DAY_ORDER[:5]
        return {
            "type": "weekly",
            "days": days,
            "times": chosen_times,
            "interval_minutes": None,
            "run_at": None,
            "raw": raw,
            "human_readable": _humanize_schedule("weekly", chosen_times, days, None, None),
        }

    if lowered.startswith("every "):
        days = _weekday_list_from_text(lowered)
        if days:
            chosen_times = times or ["09:00"]
            return {
                "type": "weekly",
                "days": days,
                "times": chosen_times,
                "interval_minutes": None,
                "run_at": None,
                "raw": raw,
                "human_readable": _humanize_schedule("weekly", chosen_times, days, None, None),
            }

    explicit_once = re.fullmatch(r"once at (\d{1,2}:\d{2})", lowered)
    if explicit_once:
        hhmm = explicit_once.group(1)
        if validate_time_format(hhmm):
            run_at = now_local.replace(
                hour=int(hhmm.split(":")[0]),
                minute=int(hhmm.split(":")[1]),
                second=0,
                microsecond=0,
            )
            return {
                "type": "once",
                "days": None,
                "times": [hhmm],
                "interval_minutes": None,
                "run_at": run_at,
                "raw": raw,
                "human_readable": _humanize_schedule("once", [hhmm], None, None, run_at),
            }

    return None


def parse_schedule_command(command_text: str, user_tz: Optional[str] = None) -> Optional[dict[str, Any]]:
    """
    Parse /schedule command text into structured data.
    """
    text = command_text.replace("/schedule", "", 1).strip()
    tz_name = user_tz or get_system_timezone()

    explicit_daily = re.match(r'^(daily|once)\s+(\d{1,2}:\d{2})\s+"([^"]+)"$', text, re.IGNORECASE)
    if explicit_daily:
        frequency = explicit_daily.group(1).lower()
        hhmm = explicit_daily.group(2)
        task = explicit_daily.group(3)
        local_dt = None
        if frequency == "once":
            tz = _get_zoneinfo(tz_name)
            local_dt = datetime.now(tz).replace(
                hour=int(hhmm.split(":")[0]),
                minute=int(hhmm.split(":")[1]),
                second=0,
                microsecond=0,
            )
        return {
            "frequency": frequency,
            "time": hhmm,
            "times": [hhmm],
            "day_of_week": None,
            "days": None,
            "interval_minutes": None,
            "task": task,
            "schedule_date": local_dt.date().isoformat() if local_dt else None,
            "human_readable": _humanize_schedule(frequency, [hhmm], None, None, local_dt),
        }

    explicit_weekly = re.match(
        r'^weekly\s+([a-z,\s]+)\s+(\d{1,2}:\d{2})\s+"([^"]+)"$',
        text,
        re.IGNORECASE,
    )
    if explicit_weekly:
        days = [day.strip().lower() for day in re.split(r",|\sand\s", explicit_weekly.group(1)) if day.strip()]
        hhmm = explicit_weekly.group(2)
        task = explicit_weekly.group(3)
        return {
            "frequency": "weekly",
            "time": hhmm,
            "times": [hhmm],
            "day_of_week": ",".join(days),
            "days": days,
            "interval_minutes": None,
            "task": task,
            "schedule_date": None,
            "human_readable": _humanize_schedule("weekly", [hhmm], days, None, None),
        }

    nl_match = re.match(r'^(.*?)\s+"([^"]+)"$', text)
    if not nl_match:
        return None
    schedule_expr = nl_match.group(1).strip()
    task = nl_match.group(2)
    parsed = parse_schedule_expression(schedule_expr, tz_name)
    if not parsed:
        return None

    run_at = parsed.get("run_at")
    times = list(parsed.get("times") or [])
    days = list(parsed.get("days") or []) or None

    return {
        "frequency": parsed["type"],
        "time": times[0] if times else None,
        "times": times,
        "day_of_week": ",".join(days) if days else None,
        "days": days,
        "interval_minutes": parsed.get("interval_minutes"),
        "task": task,
        "schedule_date": run_at.date().isoformat() if run_at else None,
        "human_readable": parsed["human_readable"],
    }


def validate_time_format(time_str: str) -> bool:
    """Validate HH:MM time format."""
    try:
        hour, minute = map(int, str(time_str).split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except Exception:
        return False


def _convert_local_times_to_utc(times: list[str], timezone_name: str) -> list[str]:
    """Convert local HH:MM recurring times to stored UTC HH:MM values."""
    tz = _get_zoneinfo(timezone_name)
    base = datetime.now(tz)
    converted: list[str] = []
    for hhmm in times:
        local_dt = base.replace(
            hour=int(hhmm.split(":")[0]),
            minute=int(hhmm.split(":")[1]),
            second=0,
            microsecond=0,
        )
        utc_dt = local_dt.astimezone(UTC)
        converted.append(utc_dt.strftime("%H:%M"))
    return converted


def _convert_utc_times_to_local(times: list[str], timezone_name: str) -> list[str]:
    """Convert stored UTC HH:MM values back to local HH:MM for display."""
    tz = _get_zoneinfo(timezone_name)
    base = datetime.now(UTC)
    converted: list[str] = []
    for hhmm in times:
        utc_dt = base.replace(
            hour=int(hhmm.split(":")[0]),
            minute=int(hhmm.split(":")[1]),
            second=0,
            microsecond=0,
        )
        converted.append(utc_dt.astimezone(tz).strftime("%H:%M"))
    return converted


def create_schedule(
    user_id: str,
    frequency: str,
    schedule_time: Optional[str],
    task_description: str,
    day_of_week: Optional[str] = None,
    schedule_date: Optional[str] = None,
    schedule_times: Optional[list[str]] = None,
    interval_minutes: Optional[int] = None,
    timezone: Optional[str] = None,
) -> ScheduledTask:
    """
    Create a new scheduled task and register it with APScheduler.
    """
    tz_name = timezone or ensure_user_timezone(str(user_id))[0]
    frequency = str(frequency).strip().lower()

    if frequency not in {"once", "daily", "weekly", "interval"}:
        raise ValueError(f"Invalid frequency: {frequency}")

    local_times = list(schedule_times or ([] if schedule_time is None else [schedule_time]))
    if frequency == "interval":
        if not interval_minutes or interval_minutes <= 0:
            raise ValueError("interval_minutes is required for interval schedules")
        stored_time = str(interval_minutes)
        stored_date = None
    else:
        if not local_times or not all(validate_time_format(item) for item in local_times):
            raise ValueError(f"Invalid time format: {schedule_time}")
        if frequency == "once":
            if not schedule_date:
                schedule_date = datetime.now(_get_zoneinfo(tz_name)).date().isoformat()
            year, month, day = map(int, schedule_date.split("-"))
            local_run_at = datetime(
                year,
                month,
                day,
                int(local_times[0].split(":")[0]),
                int(local_times[0].split(":")[1]),
                tzinfo=_get_zoneinfo(tz_name),
            )
            utc_run_at = local_run_at.astimezone(UTC)
            stored_time = utc_run_at.strftime("%H:%M")
            stored_date = utc_run_at.date().isoformat()
            local_times = [local_times[0]]
        else:
            stored_time = ",".join(_convert_local_times_to_utc(local_times, tz_name))
            stored_date = schedule_date

    if frequency == "weekly":
        days = _split_days(day_of_week)
        if not days:
            raise ValueError("day_of_week is required for weekly schedules")
        invalid = [day for day in days if day not in _DAY_ORDER]
        if invalid:
            raise ValueError(f"Invalid day_of_week: {','.join(invalid)}")

    task = add_scheduled_task(
        user_id=user_id,
        task_description=task_description,
        frequency=frequency,
        schedule_time=stored_time,
        day_of_week=day_of_week,
        schedule_date=stored_date,
    )

    try:
        _register_task_with_scheduler(task)
        logger.info("Created scheduled task %s: %s", task.id, task_description[:60])
        return task
    except Exception:
        delete_scheduled_task(task.id)
        raise


def remove_schedule(task_id: int) -> bool:
    """Remove a scheduled task from both database and scheduler."""
    task = get_scheduled_task_by_id(task_id)
    if not task:
        return False

    scheduler = get_scheduler()
    prefix = _job_prefix(task_id)
    for job in list(scheduler.get_jobs()):
        if job.id == prefix or job.id.startswith(f"{prefix}_"):
            scheduler.remove_job(job.id)
            logger.info("Removed job %s from scheduler", job.id)
    return delete_scheduled_task(task_id)


def list_user_schedules(user_id: str) -> list[ScheduledTask]:
    """Get all active scheduled tasks for a user."""
    return get_scheduled_tasks(user_id=user_id, active_only=True)


def format_schedule_description(task: ScheduledTask, user_tz: Optional[str] = None) -> str:
    """Format a scheduled task for display to a user in local time."""
    tz_name = user_tz or ensure_user_timezone(task.user_id)[0]

    if task.frequency == "interval":
        minutes = int(str(task.schedule_time))
        return f"#{task.id}: {_humanize_schedule('interval', [], None, minutes, None)} — {task.task_description}"

    local_times = _convert_utc_times_to_local(_split_times(task.schedule_time), tz_name)
    rendered_times = " and ".join(_format_12h(item) for item in local_times)

    if task.frequency == "once":
        run_date = task.schedule_date or datetime.now(UTC).date().isoformat()
        year, month, day = map(int, run_date.split("-"))
        utc_dt = datetime(year, month, day, int(_split_times(task.schedule_time)[0].split(":")[0]), int(_split_times(task.schedule_time)[0].split(":")[1]), tzinfo=UTC)
        local_dt = utc_dt.astimezone(_get_zoneinfo(tz_name))
        when = local_dt.strftime("%a, %b %d %I:%M %p").replace(" 0", " ")
        return f"#{task.id}: Once at {when} — {task.task_description}"

    if task.frequency == "daily":
        return f"#{task.id}: Every day at {rendered_times} — {task.task_description}"

    if task.frequency == "weekly":
        days = _split_days(task.day_of_week)
        return f"#{task.id}: Every {_format_days(days)} at {rendered_times} — {task.task_description}"

    return f"#{task.id}: {task.frequency} — {task.task_description}"


def format_schedule_rule(task: ScheduledTask, user_tz: Optional[str] = None) -> str:
    """Return only the human-friendly recurrence rule for a task."""
    description = format_schedule_description(task, user_tz=user_tz)
    if ": " in description and " — " in description:
        return description.split(": ", 1)[1].rsplit(" — ", 1)[0]
    return description


def get_next_run_datetime(task: ScheduledTask, user_tz: Optional[str] = None) -> Optional[datetime]:
    """Return the next scheduled run in the user's local timezone."""
    scheduler = get_scheduler()
    prefix = _job_prefix(task.id)
    candidates: list[datetime] = []
    for job in scheduler.get_jobs():
        if job.id == prefix or job.id.startswith(f"{prefix}_"):
            next_run = getattr(job, "next_run_time", None)
            if next_run:
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=UTC)
                candidates.append(next_run)
    if not candidates:
        return None
    next_utc = min(candidates)
    tz_name = user_tz or ensure_user_timezone(task.user_id)[0]
    return next_utc.astimezone(_get_zoneinfo(tz_name))


def format_next_run(task: ScheduledTask, user_tz: Optional[str] = None, detailed: bool = False) -> str:
    """Return a friendly 'next run' string in local timezone."""
    next_run = get_next_run_datetime(task, user_tz=user_tz)
    if next_run is None:
        return "Not scheduled"
    now_local = datetime.now(next_run.tzinfo or UTC)
    run_date = next_run.date()
    if run_date == now_local.date():
        return f"Today at {_format_12h(next_run.strftime('%H:%M'))}"
    if run_date == (now_local.date() + timedelta(days=1)):
        if detailed:
            return f"Tomorrow, {next_run.strftime('%a %b')} {next_run.day} at {_format_12h(next_run.strftime('%H:%M'))}"
        return f"Tomorrow at {_format_12h(next_run.strftime('%H:%M'))}"
    day_label = next_run.strftime("%A" if detailed else "%A")
    month_day = next_run.strftime("%b")
    return f"{day_label} {month_day} {next_run.day} at {_format_12h(next_run.strftime('%H:%M'))}"
