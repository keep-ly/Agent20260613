"""
HuggingFace Daily Papers 工具 - 使用 Playwright 抓取强化学习论文和社区讨论
替代原有 Reddit 数据源，无需 API Key，无需翻墙
"""
import json
import logging
from typing import Optional

from langchain_core.tools import tool
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT

logger = logging.getLogger(__name__)

HF_RL_URL = "https://huggingface.co/papers?tag=Reinforcement+Learning"


def _extract_papers_from_page(page) -> list:
    """
    从 HF Papers 页面提取论文卡片信息。
    尝试多种选择器策略，适配页面结构变化。
    """
    papers = []

    # 策略1：尝试 article 标签（最常见的论文卡片容器）
    try:
        articles = page.query_selector_all("article")
        if articles and len(articles) > 0:
            logger.info(f"HFTool: 找到 {len(articles)} 个 <article> 卡片")
            for article in articles:
                try:
                    # 标题
                    title_el = article.query_selector("h3")
                    title = title_el.inner_text().strip() if title_el else ""

                    # 链接
                    link_el = article.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""
                    if href and href.startswith("/"):
                        href = f"https://huggingface.co{href}"

                    # 摘要 — 取 article 里最大的文本块
                    text = article.inner_text().strip()
                    # 去掉标题部分取正文
                    if title:
                        text = text.replace(title, "", 1).strip()[:500]

                    if title:
                        papers.append({
                            "id": str(hash(title))[-12:],
                            "title": title,
                            "url": href or "",
                            "summary": text,
                            "source": "huggingface",
                        })
                except Exception:
                    continue

            if papers:
                return papers
    except Exception as e:
        logger.debug(f"HFTool: article 选择器失败: {e}")

    # 策略2：尝试 h3 + 相邻文本提取
    try:
        h3_elements = page.query_selector_all("h3")
        if h3_elements and len(h3_elements) > 0:
            logger.info(f"HFTool: 找到 {len(h3_elements)} 个 <h3> 标题")
            for h3 in h3_elements:
                try:
                    title = h3.inner_text().strip()
                    link_el = h3.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""
                    if href and href.startswith("/"):
                        href = f"https://huggingface.co{href}"

                    # 尝试取父元素的文本
                    parent = h3.evaluate("el => el.closest('article, section, div')")
                    if title:
                        papers.append({
                            "id": str(hash(title))[-12:],
                            "title": title,
                            "url": href or "",
                            "summary": "",
                            "source": "huggingface",
                        })
                except Exception:
                    continue

            if papers:
                return papers
    except Exception as e:
        logger.debug(f"HFTool: h3 选择器失败: {e}")

    return papers


@tool
def huggingface_fetch_rl_papers(limit: int = 10) -> str:
    """
    从 HuggingFace Daily Papers 抓取强化学习 (RL) 标签下的最新论文和社区解读。
    无需 API Key，使用浏览器渲染 JS 页面。
    
    Args:
        limit: 返回的论文数量上限
    
    Returns:
        JSON 格式的论文列表字符串
    """
    logger.info(f"HFTool: 访问 {HF_RL_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        try:
            # 访问页面
            page.goto(HF_RL_URL, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")

            # 等待页面渲染完成（论文卡片出现）
            try:
                page.wait_for_selector("article, h3, [data-target]", timeout=15000)
            except PlaywrightTimeout:
                logger.warning("HFTool: 论文卡片加载超时，尝试直接提取")
                # 额外等待让 JS 有时间渲染
                page.wait_for_timeout(5000)

            # 滚动页面触发懒加载
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(1000)

            # 提取论文
            papers = _extract_papers_from_page(page)

            # 如果上述策略都失败，用全页文本兜底
            if not papers:
                logger.warning("HFTool: 结构化提取失败，使用全页文本兜底")
                body_text = page.inner_text("body")
                if body_text and len(body_text.strip()) > 100:
                    return json.dumps({
                        "raw": True,
                        "text": body_text[:10000],
                        "source": "huggingface_raw",
                    }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "error": "HF Papers 页面内容加载不完整",
                        "text_length": len(body_text) if body_text else 0,
                    }, ensure_ascii=False)

            papers = papers[:limit]
            logger.info(f"HFTool: 成功提取 {len(papers)} 篇论文")
            return json.dumps(papers, ensure_ascii=False, indent=2)

        except PlaywrightTimeout:
            logger.error("HFTool: 页面加载超时")
            return json.dumps({"error": "HuggingFace Papers 页面加载超时"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"HFTool: 抓取失败 - {e}")
            return json.dumps({"error": f"抓取失败: {str(e)}"}, ensure_ascii=False)
        finally:
            browser.close()


HUGGINGFACE_TOOLS = [huggingface_fetch_rl_papers]
