from src.manager.async_task_manager import AsyncTask
from src.common.logger import get_logger
import asyncio

logger = get_logger("schedule")

class ScheduleAutoRefreshTask(AsyncTask):
    """日程表自动刷新任务，包装为AsyncTask"""
    def __init__(self, schedule_manager):
        super().__init__(task_name="ScheduleAutoRefreshTask")
        self.schedule_manager = schedule_manager

    async def run(self):
        logger.info("[Schedule] 自动刷新任务启动，等待到12点...")
        await self.schedule_manager.auto_refresh()
