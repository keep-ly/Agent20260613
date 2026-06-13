"""
主入口脚本 - RL Research Agent
用法:
    python run_agent.py               # 启动定时调度
    python run_agent.py --once        # 运行一次
    python run_agent.py --test        # 快速测试（生成测试文章并发布）
"""
import sys
import os
import argparse
import logging
from datetime import datetime

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_LEVEL, LOG_FILE
from agent.agent_core import RLAgent
from agent.scheduler import AgentScheduler


def setup_logging():
    """配置日志系统"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def print_banner():
    print("""
╔══════════════════════════════════════════════╗
║        RL Research Agent v1.0                ║
║   强化学习论文与前沿资讯自动采集 & 发布            ║
╚══════════════════════════════════════════════╝
    """)


def main():
    parser = argparse.ArgumentParser(description="RL Research Agent")
    parser.add_argument("--once", action="store_true", help="运行一次后退出")
    parser.add_argument("--test", action="store_true", help="快速测试模式")
    parser.add_argument("--schedule", action="store_true", help="启动定时调度")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)
    print_banner()

    # 检查必要配置
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("⚠ 未设置 OPENAI_API_KEY 环境变量，LLM 功能可能不可用")
        logger.warning("  请运行: set OPENAI_API_KEY=your-key  (Windows)")
        logger.warning("  或创建 .env 文件配置")

    # 初始化 Agent
    logger.info("正在初始化 RL Agent...")
    agent = RLAgent()
    logger.info("Agent 初始化完成")
    logger.info(f"博客地址: http://127.0.0.1:5000")

    if args.test:
        # 快速测试模式
        logger.info("=== 快速测试模式 ===")
        result = agent.quick_test()
        if result["published"]:
            logger.info(f"✅ 测试文章发布成功！")
            logger.info(f"结果: {result['result']}")
            logger.info("请访问 http://127.0.0.1:5000 查看博客")
        else:
            logger.error(f"❌ 测试失败: {result['result']}")
            logger.error("请确保博客服务器已启动: python blog_server/app.py")

    elif args.once:
        # 单次运行
        logger.info("=== 单次运行模式 ===")
        results = agent.run_once()
        logger.info(f"结果摘要: {results}")

    elif args.schedule:
        # 定时调度模式
        logger.info("=== 定时调度模式 ===")
        scheduler = AgentScheduler(agent)
        try:
            scheduler.start()
            logger.info("按 Ctrl+C 停止...")
            while True:
                import time
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
            scheduler.stop()

    else:
        # 默认：如果带了 --schedule 就调度，否则单次运行
        logger.info("=== 默认单次运行模式 ===")
        logger.info("提示: 使用 --schedule 启动定时调度, --test 快速测试")
        results = agent.run_once()
        logger.info(f"结果摘要: {results}")


if __name__ == "__main__":
    main()
