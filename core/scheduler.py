"""
GEDOS Scheduler — APScheduler integration with SQLite persistence.
Handles recurring and one-time scheduled tasks.
"""

import logging
import re
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any, Tuple
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.job import Job

from core.memory import (
    add_scheduled_task, 
    get_scheduled_tasks, 
    get_scheduled_task_by_id, 
    update_scheduled_task, 
    delete_scheduled_task,
    ScheduledTask
)

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_system_timezone() -> str:
    """Detect system timezone. Returns IANA name e.g. America/Sao_Paulo."""
    try:
        import time
        tzname = time.tzname
        if tzname and tzname[0]:
            # Try common mappings for macOS
            offset = -time.timezone // 3600
            for name in ["America/Sao_Paulo", "America/New_York", "Europe/London", "Europe/Paris", "Asia/Tokyo", "UTC"]:
                try:
                    zi = ZoneInfo(name)
                    now = datetime.now(zi)
                    if abs((now.utcoffset() or timedelta(0)).total_seconds() / 3600 - offset) < 1:
                        return name
                except Exception:
                    pass
        return "UTC"
    except Exception:
        return "UTC"


def get_scheduler(timezone: Optional[str] = None) -> AsyncIOScheduler:
    """Get or create the global scheduler instance. Uses system timezone if not specified."""
    global _scheduler
    if _scheduler is None:
        tz = timezone or get_system_timezone()
        try:
            tz_obj = ZoneInfo(tz)
        except Exception:
            tz_obj = ZoneInfo("UTC")
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}
        job_defaults = {"coalesce": False, "max_instances": 3}
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=tz_obj,
        )
        logger.info("APScheduler created (timezone=%s)", tz)
    return _scheduler


def start_scheduler():
    """Start the scheduler if not already running."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
        
        # Load existing schedules from database
        _load_schedules_from_db()


def stop_scheduler():
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def _load_schedules_from_db():
    """Load all active scheduled tasks from database and register them with APScheduler."""
    try:
        active_tasks = get_scheduled_tasks(active_only=True)
        scheduler = get_scheduler()
        
        for task in active_tasks:
            try:
                _register_task_with_scheduler(task)
                logger.info(f"Loaded scheduled task {task.id}: {task.task_description[:50]}...")
            except Exception as e:
                logger.error(f"Failed to load scheduled task {task.id}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to load schedules from database: {e}")


def _register_task_with_scheduler(task: ScheduledTask):
    """Register a ScheduledTask with APScheduler."""
    scheduler = get_scheduler()
    
    # Create trigger based on frequency
    if task.frequency == "once":
        time_parts = task.schedule_time.split(":")
        hour, minute = int(time_parts[0]), int(time_parts[1])
        tz = get_scheduler().timezone or ZoneInfo("UTC")
        now = datetime.now(tz)
        if getattr(task, "schedule_date", None):
            from datetime import date
            parts = task.schedule_date.split("-")
            if len(parts) == 3:
                target_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                target_time = datetime.combine(target_date, time(hour, minute), tzinfo=tz)
            else:
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time <= now:
                target_time = target_time + timedelta(days=1)
        trigger = DateTrigger(run_date=target_time)
        
    elif task.frequency == "daily":
        time_parts = task.schedule_time.split(":")
        hour, minute = int(time_parts[0]), int(time_parts[1])
        trigger = CronTrigger(hour=hour, minute=minute)
        
    elif task.frequency == "weekly":
        time_parts = task.schedule_time.split(":")
        hour, minute = int(time_parts[0]), int(time_parts[1])
        
        # Convert day name to CronTrigger day_of_week
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        day_of_week = day_map.get(task.day_of_week.lower()) if task.day_of_week else 0
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
        
    else:
        raise ValueError(f"Unsupported frequency: {task.frequency}")
    
    # Register job with scheduler
    job = scheduler.add_job(
        _execute_scheduled_task,
        trigger=trigger,
        args=[task.id],
        id=f"task_{task.id}",
        replace_existing=True
    )
    
    # Update task with job ID
    update_scheduled_task(task.id, job_id=job.id)


async def _execute_scheduled_task(task_id: int):
    """Execute a scheduled task in Pilot Mode."""
    try:
        task = get_scheduled_task_by_id(task_id)
        if not task or not task.is_active:
            logger.warning(f"Scheduled task {task_id} not found or inactive")
            return
        
        logger.info(f"Executing scheduled task {task_id}: {task.task_description}")
        
        # Import here to avoid circular imports
        from interfaces.telegram_bot import _execute_task_autonomously
        
        # Execute the task autonomously (Pilot Mode)
        result = await _execute_task_autonomously(
            task=task.task_description,
            user_id=int(task.user_id)
        )
        
        # Update last_run timestamp
        update_scheduled_task(task_id, last_run=datetime.utcnow())
        
        # For "once" tasks, deactivate after execution
        if task.frequency == "once":
            update_scheduled_task(task_id, is_active=False)
            # Remove from scheduler
            scheduler = get_scheduler()
            if scheduler.get_job(f"task_{task_id}"):
                scheduler.remove_job(f"task_{task_id}")
        
        logger.info(f"Scheduled task {task_id} completed: {result.get('success', False)}")
        
    except Exception as e:
        logger.exception(f"Failed to execute scheduled task {task_id}: {e}")


def _parse_natural_time(time_str: str) -> Optional[str]:
    """Parse natural language time to HH:MM. E.g. '9am' -> '09:00', '3:30pm' -> '15:30'."""
    time_str = time_str.strip().lower()
    # 9am, 9 am, 9:30am, 3pm, 12pm, 12am
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if minute > 59:
        return None
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm and hour > 12:  # 24h format
        pass
    elif not ampm and hour <= 12:
        pass  # assume AM if no suffix
    if hour > 23:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_schedule_command(command_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse /schedule command text into structured data.
    
    Supported formats (explicit):
    - /schedule daily 09:00 "check HN and summarize top 5 AI stories"
    - /schedule once 14:30 "remind me to review PR" 
    - /schedule weekly monday 09:00 "generate weekly report"
    
    Natural language:
    - /schedule "every day at 9am" "check HN"
    - /schedule "tomorrow at 3pm" "remind me to review PR"
    - /schedule "every monday at 9am" "generate weekly report"
    
    Returns:
        Dict with frequency, time, day_of_week, task keys or None if invalid
    """
    # Remove /schedule prefix and normalize whitespace
    text = command_text.replace("/schedule", "").strip()
    
    # Natural language: "every day at 9am" "task" or "tomorrow at 3pm" "task"
    nl_patterns = [
        # "every day at 9am" "task" or "daily at 9am" "task"
        (r'^(?:every\s+day|daily)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+"([^"]+)"$', 'daily', None),
        # "tomorrow at 3pm" "task" or "once tomorrow at 3pm" "task"
        (r'^(?:once\s+)?tomorrow\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+"([^"]+)"$', 'once_tomorrow', None),
        # "every monday at 9am" "task"
        (r'^every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+"([^"]+)"$', 'weekly', 1),  # day=grp1, time=grp2, task=grp3
    ]
    for pattern, freq, day_grp in nl_patterns:
        m = re.match(pattern, text, re.IGNORECASE)
        if m:
            if freq == 'daily':
                t = _parse_natural_time(m.group(1))
                if t:
                    return {'frequency': 'daily', 'time': t, 'day_of_week': None, 'task': m.group(2)}
            elif freq == 'once':
                t = _parse_natural_time(m.group(1))
                if t:
                    return {'frequency': 'once', 'time': t, 'day_of_week': None, 'task': m.group(2)}
            elif freq == 'once_tomorrow':
                t = _parse_natural_time(m.group(1))
                if t:
                    from datetime import date
                    tomorrow = (date.today() + timedelta(days=1)).isoformat()
                    return {'frequency': 'once', 'time': t, 'day_of_week': None, 'task': m.group(2), 'schedule_date': tomorrow}
            elif freq == 'weekly' and day_grp is not None:
                t = _parse_natural_time(m.group(2))
                if t:
                    return {'frequency': 'weekly', 'time': t, 'day_of_week': m.group(1).lower(), 'task': m.group(3)}
    
    # Explicit formats
    patterns = [
        r'^(daily|once)\s+(\d{1,2}:\d{2})\s+"([^"]+)"$',
        r'^weekly\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(\d{1,2}:\d{2})\s+"([^"]+)"$'
    ]
    match = re.match(patterns[0], text, re.IGNORECASE)
    if match:
        return {'frequency': match.group(1).lower(), 'time': match.group(2), 'day_of_week': None, 'task': match.group(3)}
    match = re.match(patterns[1], text, re.IGNORECASE)
    if match:
        return {'frequency': 'weekly', 'time': match.group(2), 'day_of_week': match.group(1).lower(), 'task': match.group(3)}
    
    return None


def validate_time_format(time_str: str) -> bool:
    """Validate HH:MM time format."""
    try:
        time_parts = time_str.split(":")
        if len(time_parts) != 2:
            return False
        hour, minute = int(time_parts[0]), int(time_parts[1])
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except (ValueError, IndexError):
        return False


def create_schedule(
    user_id: str,
    frequency: str,
    schedule_time: str,
    task_description: str,
    day_of_week: Optional[str] = None,
    schedule_date: Optional[str] = None,
) -> ScheduledTask:
    """
    Create a new scheduled task and register it with APScheduler.
    
    Args:
        user_id: Telegram user ID
        frequency: "once", "daily", or "weekly"
        schedule_time: HH:MM format
        task_description: Natural language task description
        day_of_week: Required for weekly tasks (monday, tuesday, etc)
        
    Returns:
        Created ScheduledTask object
        
    Raises:
        ValueError: If parameters are invalid
    """
    # Validate inputs
    if frequency not in ["once", "daily", "weekly"]:
        raise ValueError(f"Invalid frequency: {frequency}")
    
    if not validate_time_format(schedule_time):
        raise ValueError(f"Invalid time format: {schedule_time}")
    
    if frequency == "weekly" and not day_of_week:
        raise ValueError("day_of_week is required for weekly schedules")
    
    if frequency == "weekly" and day_of_week.lower() not in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        raise ValueError(f"Invalid day_of_week: {day_of_week}")
    
    # Create database record
    task = add_scheduled_task(
        user_id=user_id,
        task_description=task_description,
        frequency=frequency,
        schedule_time=schedule_time,
        day_of_week=day_of_week,
        schedule_date=schedule_date,
    )
    
    # Register with scheduler
    try:
        _register_task_with_scheduler(task)
        logger.info(f"Created scheduled task {task.id}: {frequency} at {schedule_time}")
        return task
    except Exception as e:
        # If scheduler registration fails, clean up database record
        delete_scheduled_task(task.id)
        raise e


def remove_schedule(task_id: int) -> bool:
    """
    Remove a scheduled task from both database and scheduler.
    
    Args:
        task_id: Database ID of the scheduled task
        
    Returns:
        True if removed successfully, False if not found
    """
    task = get_scheduled_task_by_id(task_id)
    if not task:
        return False
    
    # Remove from scheduler if active
    scheduler = get_scheduler()
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Removed job {job_id} from scheduler")
    
    # Remove from database
    return delete_scheduled_task(task_id)


def list_user_schedules(user_id: str) -> list[ScheduledTask]:
    """Get all active scheduled tasks for a user."""
    return get_scheduled_tasks(user_id=user_id, active_only=True)


def format_schedule_description(task: ScheduledTask) -> str:
    """Format a scheduled task for display to user."""
    if task.frequency == "once":
        return f"#{task.id}: Once at {task.schedule_time} — {task.task_description}"
    elif task.frequency == "daily":
        return f"#{task.id}: Daily at {task.schedule_time} — {task.task_description}"
    elif task.frequency == "weekly":
        return f"#{task.id}: Weekly {task.day_of_week.title()} at {task.schedule_time} — {task.task_description}"
    else:
        return f"#{task.id}: {task.frequency} — {task.task_description}"