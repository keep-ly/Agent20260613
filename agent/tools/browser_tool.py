"""
Playwright 浏览器工具 - 封装浏览器自动化操作
用于抓取需要 JS 渲染的动态页面
"""
import logging
from typing import Optional

from langchain_core.tools import tool
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT

logger = logging.getLogger(__name__)


@tool
def browser_fetch(url: str, selector: Optional[str] = None, wait_selector: Optional[str] = None) -> str:
    """
    使用浏览器访问 URL 并提取页面文本内容。
    
    Args:
        url: 目标网页 URL
        selector: (可选) CSS 选择器，只提取匹配元素的文本
        wait_selector: (可选) 等待该 CSS 选择器出现后再提取内容（用于动态加载页面）
    
    Returns:
        提取到的页面文本内容
    """
    logger.info(f"BrowserTool: 正在访问 {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")

            # 等待特定元素出现
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except PlaywrightTimeout:
                    logger.warning(f"等待选择器 '{wait_selector}' 超时，继续提取")

            # 提取目标内容
            if selector:
                elements = page.query_selector_all(selector)
                text = "\n".join([el.inner_text() for el in elements if el])
            else:
                text = page.inner_text("body")

            if not text or len(text.strip()) < 50:
                logger.warning(f"提取内容过短: {len(text)} 字符")
                return f"[警告] 页面内容可能加载不完整，提取到 {len(text)} 字符"

            logger.info(f"BrowserTool: 成功提取 {len(text)} 字符")
            return text[:15000]  # 限制长度避免 token 超限

        except PlaywrightTimeout:
            return f"[错误] 页面加载超时: {url}"
        except Exception as e:
            logger.error(f"BrowserTool 错误: {e}")
            return f"[错误] 浏览器抓取失败: {str(e)}"
        finally:
            browser.close()


@tool
def browser_screenshot(url: str) -> str:
    """
    对目标网页截图（调试用）。
    
    Args:
        url: 目标网页 URL
    
    Returns:
        操作结果描述
    """
    import os
    screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        page = browser.new_page()
        try:
            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
            path = os.path.join(screenshot_dir, f"screenshot_{int(page.evaluate('Date.now()'))}.png")
            page.screenshot(path=path, full_page=True)
            browser.close()
            return f"截图已保存到: {path}"
        except Exception as e:
            browser.close()
            return f"[错误] 截图失败: {str(e)}"


# 导出 LangChain 工具列表
BROWSER_TOOLS = [browser_fetch, browser_screenshot]
