"""
博客发布工具 - 通过 REST API 将文章发布到博客网站
"""
import logging
import json
import urllib.request
import urllib.error
from typing import Optional

from langchain_core.tools import tool

from config import BLOG_API_URL, BLOG_API_KEY

logger = logging.getLogger(__name__)


def _api_request(method: str, path: str, data: Optional[dict] = None) -> dict:
    """
    调用博客 API 的通用方法
    
    Args:
        method: HTTP 方法 (GET/POST/PUT/DELETE)
        path: API 路径（如 "/api/articles"）
        data: 请求体数据
    
    Returns:
        API 响应字典
    """
    url = f"{BLOG_API_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": BLOG_API_KEY,
    }

    body = json.dumps(data).encode("utf-8") if data else None

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error(f"API 请求失败 [{e.code}]: {error_body}")
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        logger.error(f"API 请求异常: {e}")
        return {"error": str(e)}


@tool
def publish_blog_article(
    title: str,
    content: str,
    summary: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """
    发布文章到博客网站。
    
    Args:
        title: 文章标题
        content: 文章内容（支持 Markdown/HTML）
        summary: 文章摘要（可选）
        tags: 标签，逗号分隔（可选，如 "RL,论文,前沿资讯"）
    
    Returns:
        发布结果，包含文章 URL
    """
    logger.info(f"PublishTool: 准备发布文章 '{title}'")

    data = {
        "title": title,
        "content": content,
        "summary": summary or content[:200] + "...",
        "tags": tags or "RL,强化学习",
        "source": "agent",
    }

    result = _api_request("POST", "/api/articles", data)

    if result.get("success"):
        article_url = result.get("url", "N/A")
        logger.info(f"PublishTool: 发布成功 - {article_url}")
        return f"[成功] 文章已发布！\n标题: {title}\nURL: {article_url}\nID: {result.get('id')}"
    else:
        error_msg = result.get("error", "未知错误")
        detail = result.get("detail", "")
        logger.error(f"PublishTool: 发布失败 - {error_msg} {detail}")
        return f"[失败] 文章发布失败: {error_msg} - {detail}"


@tool
def check_article_processed(source: str, item_id: str) -> str:
    """
    检查某条内容是否已经处理/发布过（去重）。
    
    Args:
        source: 数据来源（如 "arxiv", "reddit"）
        item_id: 内容唯一标识（如 arXiv ID）
    
    Returns:
        是否已处理的标记
    """
    import urllib.parse

    params = urllib.parse.urlencode({"source": source, "item_id": item_id})
    result = _api_request("GET", f"/api/processed?{params}")
    return json.dumps(result, ensure_ascii=False)


@tool
def mark_article_processed(source: str, item_id: str, title: str = "") -> str:
    """
    标记某条内容为已处理（发布后调用，避免重复）。
    
    Args:
        source: 数据来源
        item_id: 内容唯一标识
        title: 内容标题（可选，用于日志）
    
    Returns:
        操作结果
    """
    result = _api_request("POST", "/api/processed", {
        "source": source,
        "item_id": item_id,
        "title": title,
    })
    return json.dumps(result, ensure_ascii=False)


PUBLISH_TOOLS = [publish_blog_article, check_article_processed, mark_article_processed]
