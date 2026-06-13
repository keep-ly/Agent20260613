"""
调度器模块 - 定时触发 Agent 运行
"""
import logging
import threading
from datetime import datetime, time

from config import SCHEDULE_INTERVAL_HOURS, SCHEDULE_RUN_TIME

logger = logging.getLogger(__name__)


class AgentScheduler:
    """基于 APScheduler 的定时调度器"""

    def __init__(self, agent):
        self.agent = agent
        self.scheduler = None
        self._running = False

    def start(self):
        """启动调度器"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            self.scheduler = BackgroundScheduler()
            hour, minute = map(int, SCHEDULE_RUN_TIME.split(":"))
            self.scheduler.add_job(
                self._run_job,
                "cron",
                hour=hour,
                minute=minute,
                id="rl_agent_daily",
                name="RL Agent 每日采集任务",
            )
            self.scheduler.start()
            self._running = True
            logger.info(f"调度器已启动，每日 {SCHEDULE_RUN_TIME} 执行")
            logger.info(f"下次运行: {self.scheduler.get_job('rl_agent_daily').next_run_time}")

        except ImportError:
            logger.warning("APScheduler 未安装，使用简单间隔调度")
            self._start_simple()

    def _start_simple(self):
        """简单间隔调度（不依赖 APScheduler）"""
        self._running = True

        def _loop():
            import time as _time
            while self._running:
                logger.info("调度器触发...")
                try:
                    self.agent.run_once()
                except Exception as e:
                    logger.error(f"调度任务异常: {e}")
                _time.sleep(SCHEDULE_INTERVAL_HOURS * 3600)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        logger.info(f"简单调度器已启动，间隔 {SCHEDULE_INTERVAL_HOURS} 小时")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        logger.info("调度器已停止")

    def run_now(self):
        """立即执行一次"""
        return self.agent.run_once()
