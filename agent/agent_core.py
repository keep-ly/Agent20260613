"""
LangChain Agent 核心 - 集成工具、LLM 和任务编排
"""
import logging
import json
from datetime import datetime
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from agent.tools.browser_tool import BROWSER_TOOLS
from agent.tools.arxiv_tool import ARXIV_TOOLS
from agent.tools.huggingface_tool import HUGGINGFACE_TOOLS
from agent.tools.publish_tool import PUBLISH_TOOLS
from agent.dedup import DedupManager
from agent.content_processor import ContentProcessor

logger = logging.getLogger(__name__)

# ==================== Agent System Prompt ====================
SYSTEM_PROMPT = """
你是一名强化学习领域的科研助手 Agent，负责自动采集最新论文和前沿资讯，整理后发布到博客。

## 你的任务
按顺序执行以下步骤：
1. 使用 arxiv_search 工具搜索最近几天的强化学习论文
2. 使用 huggingface_fetch_rl_papers 工具获取 HuggingFace 上 RL 相关的最新论文和社区解读
3. 将收集到的原始数据交给 content_processor 工具整理成一篇 Markdown 博客文章
4. 使用 publish_blog_article 工具将整理好的文章发布到博客

## 重要规则
- 严格按步骤执行，不要跳过
- 如果某个数据源失败，继续执行剩余步骤
- 发布前确认内容非空
- 所有操作完成后输出摘要报告
"""

AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "请开始执行采集和发布任务，日期：{date}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


class RLAgent:
    """强化学习研究 Agent 主类"""

    def __init__(self):
        # 初始化 LLM
        llm_kwargs = {
            "model": OPENAI_MODEL,
            "api_key": OPENAI_API_KEY,
            "temperature": 0.2,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["base_url"] = OPENAI_BASE_URL

        self.llm = ChatOpenAI(**llm_kwargs)

        # 初始化组件
        self.dedup = DedupManager()
        self.processor = ContentProcessor()

        # 汇总所有工具
        self.tools = BROWSER_TOOLS + ARXIV_TOOLS + HUGGINGFACE_TOOLS + PUBLISH_TOOLS

    def run_pipeline(self, date: Optional[str] = None) -> dict:
        """
        运行完整的数据采集→整理→发布流水线（不使用 Agent 自动决策，用确定性流水线更稳定）
        
        Args:
            date: 日期字符串
        
        Returns:
            执行结果摘要
        """
        if date is None:
            date = datetime.now().strftime("%Y年%m月%d日")

        logger.info(f"=== RL Agent 流水线启动 - {date} ===")
        results = {
            "date": date,
            "arxiv_papers": 0,
            "huggingface_papers": 0,
            "published": False,
            "article_url": None,
            "errors": [],
        }

        raw_data_parts = []

        # ===== 步骤1: 抓取 arXiv 论文 =====
        logger.info("步骤 1/4: 抓取 arXiv 论文...")
        try:
            arxiv_raw = ""
            for tool in ARXIV_TOOLS:
                if tool.name == "arxiv_search":
                    arxiv_raw = tool.invoke({
                        "query": "reinforcement learning",
                        "max_results": 15,
                        "days_back": 3,
                    })
                    break

            if arxiv_raw and not arxiv_raw.startswith("[错误]"):
                try:
                    papers = json.loads(arxiv_raw)
                    # 去重过滤
                    papers = self.dedup.filter_unprocessed(papers, "arxiv", "arxiv_id")
                    results["arxiv_papers"] = len(papers)
                    raw_data_parts.append(f"## arXiv 最新论文\n\n```json\n{json.dumps(papers, ensure_ascii=False, indent=2)}\n```")
                except json.JSONDecodeError:
                    raw_data_parts.append(arxiv_raw)
            else:
                results["errors"].append(f"arXiv 抓取失败: {arxiv_raw}")
                raw_data_parts.append(f"arXiv 抓取失败: {arxiv_raw}")
        except Exception as e:
            msg = f"arXiv 步骤异常: {e}"
            logger.error(msg)
            results["errors"].append(msg)

        # ===== 步骤2: 抓取 HuggingFace Papers =====
        logger.info("步骤 2/4: 抓取 HuggingFace Papers...")
        try:
            hf_raw = ""
            for tool in HUGGINGFACE_TOOLS:
                if tool.name == "huggingface_fetch_rl_papers":
                    hf_raw = tool.invoke({"limit": 10})
                    break

            if hf_raw and not hf_raw.startswith("[错误]"):
                try:
                    data = json.loads(hf_raw)
                    if isinstance(data, list):
                        papers = self.dedup.filter_unprocessed(data, "huggingface", "id")
                        results["huggingface_papers"] = len(papers)
                        raw_data_parts.append(f"## HuggingFace RL 论文\n\n```json\n{json.dumps(papers, ensure_ascii=False, indent=2)}\n```")
                    elif isinstance(data, dict) and data.get("raw"):
                        results["huggingface_papers"] = -1  # -1 表示原始文本
                        raw_data_parts.append(f"## HuggingFace RL 论文 (原始文本)\n\n{data.get('text', '')[:3000]}")
                    else:
                        raw_data_parts.append(hf_raw)
                except json.JSONDecodeError:
                    raw_data_parts.append(hf_raw)
            else:
                results["errors"].append(f"HuggingFace 抓取失败: {hf_raw}")
        except Exception as e:
            msg = f"HuggingFace 步骤异常: {e}"
            logger.error(msg)
            results["errors"].append(msg)

        # ===== 步骤3: LLM 整理内容 =====
        logger.info("步骤 3/4: LLM 整理内容...")
        raw_data = "\n\n".join(raw_data_parts)

        if not raw_data.strip() or raw_data == "\n\n":
            logger.warning("没有获取到任何原始数据，生成占位文章")
            article_content = f"""# 强化学习研究日报 - {date}

        > 本期暂无新数据，请检查数据源配置。

        ## 状态
        - arXiv: {"成功" if results["arxiv_papers"] > 0 else "无新数据"}
        - HuggingFace: {"成功" if results["huggingface_papers"] > 0 else "无新数据"}
        """
        
        else:
            article_content = self.processor.organize(raw_data, date)

        # 生成摘要和标签
        summary = self.processor.generate_summary(article_content)
        tags = self.processor.generate_tags(article_content)
        title = f"强化学习研究日报 - {date}"

        # ===== 步骤4: 发布到博客 =====
        logger.info("步骤 4/4: 发布到博客...")
        try:
            for tool in PUBLISH_TOOLS:
                if tool.name == "publish_blog_article":
                    publish_result = tool.invoke({
                        "title": title,
                        "content": article_content,
                        "summary": summary,
                        "tags": tags,
                    })
                    logger.info(f"发布结果: {publish_result}")

                    if "[成功]" in publish_result:
                        results["published"] = True
                        # 提取 URL
                        if "URL:" in publish_result:
                            results["article_url"] = publish_result.split("URL:")[-1].strip()

                        # 标记已处理
                        self._mark_all_processed(results)
                    else:
                        results["errors"].append(f"发布失败: {publish_result}")
                    break
        except Exception as e:
            msg = f"发布步骤异常: {e}"
            logger.error(msg)
            results["errors"].append(msg)

        # ===== 完成后输出报告 =====
        logger.info(f"=== 流水线完成 ===")
        logger.info(f"论文(arXiv): {results['arxiv_papers']} 篇 | 论文(HF): {results['huggingface_papers']} 篇")
        logger.info(f"发布: {'成功' if results['published'] else '失败'}")
        if results["errors"]:
            logger.warning(f"错误: {results['errors']}")

        return results

    def _mark_all_processed(self, results: dict):
        """流水线成功后标记所有数据为已处理"""
        # 这一步依赖实际的工具调用返回数据，简化处理
        pass

    def run_once(self) -> dict:
        """手动运行一次"""
        return self.run_pipeline()

    def quick_test(self) -> dict:
        """快速测试：生成测试文章并发布"""
        logger.info("=== 快速测试模式 ===")
        date = datetime.now().strftime("%Y年%m月%d日")
        test_content = f"""# 强化学习研究日报 - {date}（测试）

        > 这是一篇由 RL Research Agent 自动生成的测试文章。

        ## 📄 最新论文

        **暂无数据** - 这是测试模式，未实际抓取论文。

        ## 💬 社区热点

        **Reddit** - 请在配置 API Key 后重新运行获取真实数据。

        ## 🔗 配置提示

        1. 设置环境变量 `OPENAI_API_KEY` 启用 LLM 整理
        2. 设置 `REDDIT_CLIENT_ID` 和 `REDDIT_CLIENT_SECRET` 启用 Reddit
        3. 启动博客服务器：`python blog_server/app.py`

        ---

        *本文由 RL Research Agent 自动生成*
        """

        title = f"强化学习研究日报 - {date}（测试）"
        summary = "RL Research Agent 测试文章，验证流水线是否正常运作。"
        tags = "RL,测试,强化学习"

        for tool in PUBLISH_TOOLS:
            if tool.name == "publish_blog_article":
                result = tool.invoke({
                    "title": title,
                    "content": test_content,
                    "summary": summary,
                    "tags": tags,
                })
                logger.info(f"测试发布结果: {result}")
                return {
                    "published": "[成功]" in result,
                    "result": result,
                }

        return {"published": False, "result": "未找到 publish 工具"}
