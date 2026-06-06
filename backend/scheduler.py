import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select
from datetime import datetime, timedelta
from models import Package, PackageStatus
from database import engine
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, SERVER_BASE_URL

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def send_reminders():
    cutoff = datetime.now() - timedelta(hours=48)
    with Session(engine) as session:
        pkgs = session.exec(
            select(Package)
            .where(Package.status == PackageStatus.pending)
            .where(Package.arrived_at <= cutoff)
            .where(Package.employee_id.isnot(None))
        ).all()
        dt   = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
        sent = 0
        for pkg in pkgs:
            pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
            try:
                ok = await dt.send_reminder(pkg.employee_id, pkg.code, pickup_url)
                if ok:
                    sent += 1
            except Exception as e:
                logger.error("Reminder error pkg_id=%s: %s", pkg.id, e)
        logger.info("Reminders sent: %d / %d", sent, len(pkgs))


async def expire_old_packages():
    cutoff = datetime.now() - timedelta(days=7)
    with Session(engine) as session:
        pkgs = session.exec(
            select(Package)
            .where(Package.status.in_([PackageStatus.pending, PackageStatus.unclaimed]))
            .where(Package.arrived_at <= cutoff)
        ).all()
        for pkg in pkgs:
            pkg.status = PackageStatus.expired
            session.add(pkg)
        session.commit()
        logger.info("Expired %d packages", len(pkgs))



async def sync_employees():
    """每日凌晨从钉钉同步员工手机尾号缓存"""
    from routers.employees import sync_employees as _do_sync
    from database import get_session
    gen = get_session()
    session = next(gen)
    try:
        result = await _do_sync(session)
        logger.info("Employee sync: %s", result)
    finally:
        try: next(gen)
        except StopIteration: pass

def start_scheduler():
    scheduler.add_job(send_reminders,     "interval", hours=1,  id="reminders")
    scheduler.add_job(expire_old_packages, "cron",    hour=2, minute=0, id="expire")
    scheduler.add_job(sync_employees,     "cron",    hour=3, minute=0, id="emp_sync")
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
