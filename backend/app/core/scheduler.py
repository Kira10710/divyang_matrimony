"""
APScheduler configuration — replaces Celery for v1.

Runs in-process inside the FastAPI app. Covers:
- 30-day account deletion purge (daily)
- Subscription expiry reminders (daily)

See Architecture Section 3.7 for rationale and limitations.
Trigger to move to Celery: Section 13.2.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def init_scheduler() -> None:
    """
    Register scheduled jobs and start the scheduler.

    Called during app lifespan startup.
    """
    # TODO: Add account purge job (runs daily, checks for accounts past 30-day cooling-off)
    # scheduler.add_job(purge_deleted_accounts, "cron", hour=2, minute=0)

    # TODO: Add subscription expiry reminder job (runs daily, sends notifications for 3-day-out expiry)
    # scheduler.add_job(send_expiry_reminders, "cron", hour=9, minute=0)

    scheduler.start()


def shutdown_scheduler() -> None:
    """Stop the scheduler. Called during app lifespan shutdown."""
    scheduler.shutdown(wait=False)
