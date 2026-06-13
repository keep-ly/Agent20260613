"""
arXiv API 工具 - 获取强化学习领域最新论文
"""
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime, timedelta

from langchain_core.tools import tool

from config import ARXIV_CATEGORIES, ARXIV_MAX_RESULTS, REQUEST_DELAY

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"


def _parse_arxiv_entry(entry: ET.Element) -> dict:
    """解析单个 arXiv 条目"""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def _text(tag: str) -> str:
        el = entry.find(f"atom:{tag}", ns)
        return el.text.strip() if el is not None and el.text else ""

    authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]

    # 提取 arXiv ID
    arxiv_id = ""
    id_url = _text("id")
    if "/abs/" in id_url:
        arxiv_id = id_url.split("/abs/")[-1]
        # 去除版本号
        if "v" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("v", 1)[0]

    return {
        "arxiv_id": arxiv_id,
        "title": _text("title").replace("\n", " ").strip(),
        "authors": ", ".join(authors[:5]) + ("..." if len(authors) > 5 else ""),
        "summary": _text("summary").replace("\n", " ").strip()[:500],
        "published": _text("published"),
        "url": id_url,
        "pdf_url": _text("id").replace("/abs/", "/pdf/") if "/abs/" in _text("id") else "",
        "categories": [c.get("term") for c in entry.findall("atom:category", ns)],
    }


@tool
def arxiv_search(
    query: str = "reinforcement learning",
    max_results: int = ARXIV_MAX_RESULTS,
    days_back: int = 1,
) -> str:
    """
    搜索 arXiv 上的强化学习最新论文。
    
    Args:
        query: 搜索关键词，默认为 "reinforcement learning"
        max_results: 最大返回数量
        days_back: 搜索最近 N 天的论文
    
    Returns:
        JSON 格式的论文列表字符串
    """
    import json
    import time

    logger.info(f"ArxivTool: 搜索 '{query}', 最近 {days_back} 天, 最多 {max_results} 篇")

    # 构建日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # 构建查询（按类别过滤 + 按日期排序）
    cat_filter = " OR ".join([f"cat:{cat}" for cat in ARXIV_CATEGORIES])
    search_query = f"({query}) AND ({cat_filter})"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    logger.info(f"ArxivTool: 请求 {url}")

    try:
        time.sleep(REQUEST_DELAY)  # arXiv API 限速
        req = urllib.request.Request(url, headers={"User-Agent": "RL-Agent-Blog/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)

        papers = []
        logger.info(f"ArxivTool: API 返回 {len(entries)} 条记录，正在过滤...")
        for entry in entries:
            paper = _parse_arxiv_entry(entry)
            # 日期过滤
            if paper["published"]:
                try:
                    pub_date = datetime.strptime(paper["published"][:10], "%Y-%m-%d")
                    if pub_date < start_date:
                        continue
                except ValueError:
                    pass
            papers.append(paper)

        logger.info(f"ArxivTool: 找到 {len(papers)} 篇论文")
        return json.dumps(papers, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"ArxivTool 错误: {e}")
        return f"[错误] arXiv API 请求失败: {str(e)}"


@tool
def arxiv_get_by_id(arxiv_id: str) -> str:
    """
    根据 arXiv ID 获取单篇论文的详细信息。
    
    Args:
        arxiv_id: arXiv 论文 ID（如 "2301.12345"）
    
    Returns:
        论文详细信息的字符串
    """
    import json

    params = {"id_list": arxiv_id, "max_results": 1}
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RL-Agent-Blog/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            return f"[错误] 未找到论文: {arxiv_id}"

        paper = _parse_arxiv_entry(entry)
        return json.dumps(paper, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"[错误] arXiv 查询失败: {str(e)}"


ARXIV_TOOLS = [arxiv_search, arxiv_get_by_id]
