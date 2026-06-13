"""
LLM 内容整理模块 - 将原始抓取数据整理为结构化博客文章
"""
import logging
from datetime import datetime
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL

logger = logging.getLogger(__name__)

# ==================== Prompt 模板 ====================

SYSTEM_PROMPT = """
你是一名强化学习领域的资深科研助手，负责编写面向 RL 研究者的日报/周报。

请根据以下抓取的原始信息（包含论文标题、摘要、新闻链接、讨论热点等），生成一篇专业的博客文章。

格式要求：
1. 使用 Markdown 格式
2. 文章结构：
   - 开头：简要概述本期内容的整体趋势和亮点（2-3 句话）
   - ## 📄 最新论文：列出论文，每篇包含标题（加粗）、作者、arXiv 链接、1-2 句点评
   - ## 💬 社区解读：HuggingFace 社区对部分论文的解读和讨论
   - ## 🔗 值得关注：其他值得关注的链接和动态
   - 结尾：简短的总结

风格要求：
- 专业但不晦涩，面向有 ML 基础的研究者
- 对每篇论文给出简短的技术点评（创新点或局限）
- 必须附带原始链接（arXiv URL、Reddit permalink 等）
- 不要编造不存在的信息，原始数据中没有的信息就不要写

日期：{date}
"""

CONTENT_ORGANIZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "原始信息如下：\n\n{raw_data}"),
])

SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是内容编辑，请为以下文章生成一个简洁的摘要（不超过 200 字），用中文。"),
    ("human", "文章内容：\n\n{content}"),
])

FEW_SHOT_EXAMPLE = """
## 📄 最新论文

**Sample-Efficient Reinforcement Learning with Dual Policy Optimization**
- 作者：Zhang et al.
- arXiv: [https://arxiv.org/abs/2412.xxxxx](https://arxiv.org/abs/2412.xxxxx)
- 点评：提出双策略优化框架，在样本效率上有显著提升，但仅在 MuJoCo 环境上验证。

## 💬 社区解读

- [HuggingFace Papers] "RL with Diffusion Models" - 社区解读指出该文在离线 RL 场景下效果显著，但计算成本较高
"""


class ContentProcessor:
    """基于 LLM 的内容整理器"""

    def __init__(self):
        llm_kwargs = {
            "model": OPENAI_MODEL,
            "api_key": OPENAI_API_KEY,
            "temperature": 0.3,
            "max_tokens": 4000,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["base_url"] = OPENAI_BASE_URL

        self.llm = ChatOpenAI(**llm_kwargs)
        self.organizer_chain = CONTENT_ORGANIZER_PROMPT | self.llm | StrOutputParser()
        self.summary_chain = SUMMARY_PROMPT | self.llm | StrOutputParser()

    def organize(
        self,
        raw_data: str,
        date: Optional[str] = None,
    ) -> str:
        """
        将原始数据整理为结构化博客文章。
        
        Args:
            raw_data: 原始抓取数据（JSON 或文本）
            date: 文章日期
        
        Returns:
            Markdown 格式的博客文章
        """
        if date is None:
            date = datetime.now().strftime("%Y年%m月%d日")

        # 截断过长输入避免 token 超限
        if len(raw_data) > 24000:
            raw_data = raw_data[:24000] + "\n\n[内容过长已截断...]"

        logger.info(f"ContentProcessor: 正在整理原始数据 ({len(raw_data)} 字符)")

        try:
            result = self.organizer_chain.invoke({
                "date": date,
                "raw_data": raw_data,
            })
            logger.info(f"ContentProcessor: 整理完成 ({len(result)} 字符)")
            return result
        except Exception as e:
            logger.error(f"ContentProcessor 整理失败: {e}")
            # 降级：返回简化版本
            return self._fallback_organize(raw_data, date)

    def generate_summary(self, content: str) -> str:
        """生成文章摘要"""
        try:
            if len(content) > 2000:
                content = content[:2000]
            result = self.summary_chain.invoke({"content": content})
            return result.strip()[:200]
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return content[:200] + "..."

    def generate_tags(self, content: str) -> str:
        """根据内容生成标签"""
        # 简单的关键词匹配
        tags = ["强化学习", "RL"]
        keywords = {
            "RLHF": "RLHF",
            "PPO": "PPO",
            "DQN": "DQN",
            "Transformer": "Transformer",
            "LLM": "大语言模型",
            "Multi-Agent": "多智能体",
            "Offline RL": "离线强化学习",
            "Model-Based": "基于模型",
            "Meta-Learning": "元学习",
            "Robotics": "机器人",
        }
        for key, tag in keywords.items():
            if key.lower() in content.lower():
                tags.append(tag)
        return ", ".join(tags[:8])

    def _fallback_organize(self, raw_data: str, date: str) -> str:
        """LLM 失败时的降级处理"""
        return f"""# 强化学习研究日报 - {date}

        > 本期内容由 Agent 自动聚合，因 LLM 整理模块异常，以下为原始数据摘要。

        ## 原始数据

        ```
        {raw_data[:3000]}
        ```

        ---

        *（注：本文由 RL Research Agent 自动生成，LLM 整理模块暂时不可用）*
        """
