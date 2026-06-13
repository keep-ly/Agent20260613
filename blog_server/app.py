"""
博客服务器 - 基于 Flask
提供博客展示页面和 API 接口供 Agent 发布文章
"""
import sqlite3
import datetime
import hashlib
from functools import wraps
from pathlib import Path

import markdown as md_lib
from flask import Flask, request, jsonify, render_template, abort, g

# ==================== 配置 ====================
DATABASE = str(Path(__file__).parent.parent / "data.db")
API_KEY = "rl-agent-blog-api-key-2024"

app = Flask(__name__)


# ==================== 数据库 ====================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            tags TEXT,
            source TEXT DEFAULT 'agent',
            published_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS processed_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT,
            published_date TEXT,
            processed_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(source, item_id)
        )
    """)
    db.commit()
    db.close()


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ==================== 鉴权装饰器 ====================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== 页面路由 ====================
@app.route("/")
def index():
    db = get_db()
    articles = db.execute(
        "SELECT id, title, slug, summary, tags, published_at "
        "FROM articles ORDER BY published_at DESC"
    ).fetchall()
    return render_template("index.html", articles=articles)


@app.route("/article/<slug>")
def article_detail(slug):
    db = get_db()
    article = db.execute(
        "SELECT * FROM articles WHERE slug = ?", (slug,)
    ).fetchone()
    if article is None:
        abort(404)
    return render_template("article.html", article=article)


# ==================== API 路由 (供 Agent 调用) ====================
@app.route("/api/articles", methods=["GET"])
@require_api_key
def api_list_articles():
    """列出所有文章"""
    db = get_db()
    rows = db.execute(
        "SELECT id, title, slug, summary, tags, published_at "
        "FROM articles ORDER BY published_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/articles", methods=["POST"])
@require_api_key
def api_publish_article():
    """发布文章 (Agent 调用的核心接口)"""
    data = request.get_json(force=True)

    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not title or not content:
        return jsonify({"error": "title and content are required"}), 400

    # Markdown → HTML 转换
    content_html = md_lib.markdown(
        content,
        extensions=["extra", "codehilite", "tables", "toc"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
        },
    )

    # 生成 slug（含时间戳避免同日期重复运行冲突）
    slug_base = title.lower().replace(" ", "-")[:60]
    slug_input = f"{title}{datetime.datetime.now().timestamp()}"
    slug_hash = hashlib.md5(slug_input.encode()).hexdigest()[:8]
    slug = f"{slug_base}-{slug_hash}"

    summary_raw = data.get("summary", content[:200] + "...")
    # 摘要也做 Markdown → HTML 转换，并用 striptags 去除标签后存纯文本用于 meta
    summary_html = md_lib.markdown(summary_raw, extensions=["extra"])
    tags = data.get("tags", "")
    published_at = data.get("published_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    source = data.get("source", "agent")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO articles (title, slug, content, summary, tags, source, published_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, slug, content_html, summary_html, tags, source, published_at),
        )
        db.commit()
        article_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({
            "success": True,
            "id": article_id,
            "slug": slug,
            "url": f"{request.host_url}article/{slug}"
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Article with this slug already exists"}), 409


@app.route("/api/articles/<slug>", methods=["PUT"])
@require_api_key
def api_update_article(slug):
    """更新文章"""
    data = request.get_json(force=True)
    db = get_db()
    existing = db.execute("SELECT id FROM articles WHERE slug = ?", (slug,)).fetchone()
    if not existing:
        return jsonify({"error": "Article not found"}), 404

    fields = []
    values = []
    for key in ["title", "content", "summary", "tags"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No fields to update"}), 400

    values.append(slug)
    db.execute(f"UPDATE articles SET {', '.join(fields)} WHERE slug = ?", values)
    db.commit()
    return jsonify({"success": True, "slug": slug})


@app.route("/api/articles/<slug>", methods=["DELETE"])
@require_api_key
def api_delete_article(slug):
    """删除文章"""
    db = get_db()
    db.execute("DELETE FROM articles WHERE slug = ?", (slug,))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/processed", methods=["GET"])
@require_api_key
def api_check_processed():
    """检查某条记录是否已处理（去重查询接口）"""
    source = request.args.get("source")
    item_id = request.args.get("item_id")
    if not source or not item_id:
        return jsonify({"error": "source and item_id required"}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM processed_items WHERE source = ? AND item_id = ?",
        (source, item_id),
    ).fetchone()
    return jsonify({"processed": row is not None, "data": dict(row) if row else None})


@app.route("/api/processed", methods=["POST"])
@require_api_key
def api_mark_processed():
    """标记记录为已处理"""
    data = request.get_json(force=True)
    source = data.get("source")
    item_id = data.get("item_id")
    title = data.get("title", "")
    published_date = data.get("published_date", "")

    if not source or not item_id:
        return jsonify({"error": "source and item_id required"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO processed_items (source, item_id, title, published_date) "
            "VALUES (?, ?, ?, ?)",
            (source, item_id, title, published_date),
        )
        db.commit()
        return jsonify({"success": True}), 201
    except sqlite3.IntegrityError:
        return jsonify({"success": True, "message": "Already processed"})


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok", "timestamp": datetime.datetime.now().isoformat()})


# ==================== 错误处理 ====================
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ==================== 启动 ====================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
