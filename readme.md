# RL Research Agent

强化学习领域论文与前沿资讯自动采集、整理与博客发布 Agent。

每天自动从多个数据源抓取最新 RL 论文和社区解读，经由大语言模型整理为结构化日报，发布到自建博客网站。

## 系统架构

```
 ┌──────────────────┐
 │  run_agent.py    │  主入口（单次运行 / 定时调度）
 └────────┬─────────┘
          ▼
 ┌─────────────────────────────────────────┐
 │          RLAgent.run_pipeline()          │
 │                                         │
 │  ① arXiv API         → 最新 RL 论文     │
 │  ② HuggingFace Papers → RL 社区解读     │
 │  ③ ContentProcessor   → LLM 整理成 Markdown│
 │  ④ publish_tool       → 发布到博客      │
 └─────────────────────────────────────────┘
          │
          ▼
 ┌──────────────────┐
 │  Flask Blog 网站  │  文章展示 + REST API
 └──────────────────┘
```

**容错设计**：每个数据源独立 try/except，单个源失败不阻塞流水线。

## 项目结构

```
project/
├── run_agent.py                    # 主入口（--once / --test / --schedule）
├── config.py                       # 全局配置，读取环境变量
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板（复制为 .env 使用）
│
├── agent/                          # Agent 核心模块
│   ├── agent_core.py               # 流水线编排：采集→整理→发布
│   ├── content_processor.py        # LLM 内容整理（Prompt + DeepSeek/OpenAI）
│   ├── dedup.py                    # SQLite 去重管理器
│   ├── scheduler.py                # 定时调度器（APScheduler / 简单循环）
│   └── tools/
│       ├── arxiv_tool.py           # arXiv API 论文搜索
│       ├── huggingface_tool.py     # HuggingFace Papers（Playwright 渲染）
│       ├── browser_tool.py         # 通用 Playwright 浏览器工具
│       └── publish_tool.py         # 博客发布 API 客户端
│
├── blog_server/                    # Flask 博客网站
│   ├── app.py                      # Flask 应用（页面 + REST API）
│   ├── templates/
│   │   ├── index.html              # 文章列表页
│   │   └── article.html            # 文章详情页
│   └── static/css/style.css        # 样式（含代码高亮）
│
└── logs/                           # 运行日志
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入你的 API Key（DeepSeek 或 OpenAI 二选一）
```

**DeepSeek（推荐，国内直连）**：

```env
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_MODEL=deepseek-v4-flash
OPENAI_BASE_URL=https://api.deepseek.com
```

**OpenAI**：

```env
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 3. 启动博客服务器

```bash
python blog_server/app.py
```

访问 http://127.0.0.1:5000 查看博客首页。

### 4. 运行 Agent

```bash
# 快速测试（生成一篇测试文章）
python run_agent.py --test

# 单次采集并发布
python run_agent.py --once

# 启动定时调度（每天 09:00 自动运行）
python run_agent.py --schedule
```

## 数据源

| 数据源 | 获取方式 | 需要 API Key？ |
|--------|---------|:---:|
| arXiv（cs.LG, cs.AI, cs.CL, stat.ML） | arXiv 官方 API | 否 |
| HuggingFace Daily Papers（RL 标签） | Playwright 渲染 | 否 |
| Reddit（旧版，已废弃） | — | — |

## 博客 API

Agent 通过 REST API 将文章推送到博客服务器。鉴权方式：HTTP Header `X-API-Key`。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/articles` | 发布文章（含 Markdown→HTML 转换） |
| `GET` | `/api/articles` | 列出所有文章 |
| `PUT` | `/api/articles/<slug>` | 更新文章 |
| `DELETE` | `/api/articles/<slug>` | 删除文章 |
| `POST` | `/api/processed` | 标记内容已处理（去重） |
| `GET` | `/api/processed?source=&item_id=` | 检查是否已处理 |

## 配置参数

所有参数通过 `.env` 文件或系统环境变量配置，默认值在 [config.py](config.py)。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | — | LLM API Key（必填） |
| `OPENAI_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `BLOG_SERVER_HOST` | `127.0.0.1` | 博客服务器地址 |
| `BLOG_SERVER_PORT` | `5000` | 博客服务器端口 |
| `BLOG_API_KEY` | `rl-agent-blog-api-key-2024` | API 鉴权 Key |
| `ARXIV_MAX_RESULTS` | `20` | arXiv 最大返回数 |
| `SCHEDULE_RUN_TIME` | `09:00` | 每日运行时间 |
| `SCHEDULE_INTERVAL_HOURS` | `24` | 简单调度间隔 |

## 工作流详解

```
步骤1: arxiv_search
  → 关键词 "reinforcement learning"
  → 分类 cs.LG OR cs.AI OR cs.CL OR stat.ML
  → 最近 3 天，最多 15 篇
  → 去重过滤

步骤2: huggingface_fetch_rl_papers
  → https://huggingface.co/papers?tag=Reinforcement+Learning
  → Playwright 渲染 JS 页面
  → 提取论文卡片（标题 + URL + 社区摘要）
  → 去重过滤

步骤3: ContentProcessor.organize()
  → 拼接 arXiv + HuggingFace 原始数据
  → 通过 Prompt Template 调用 DeepSeek
  → 生成结构化 Markdown 文章

步骤4: publish_blog_article
  → POST /api/articles（Markdown→HTML）
  → 文章存入 SQLite
  → 博客页面可见
```

## 扩展指南

### 添加新数据源

1. 在 `agent/tools/` 下新建工具文件，用 `@tool` 装饰器定义函数
2. 在 `agent/tools/__init__.py` 导出
3. 在 `agent/agent_core.py` 添加流水线步骤

### 切换 LLM

兼容所有 OpenAI 兼容 API（DeepSeek、通义千问、ChatGLM 等），只需改 `.env` 中的 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`。

### 部署到云服务器

```bash
# 使用 gunicorn 或 waitress 替代 Flask 开发服务器
pip install waitress
waitress-serve --port=5000 blog_server.app:app

# Agent 定时调度
python run_agent.py --schedule
```

## License

MIT
