#!/usr/bin/env python3
"""Generate a self-contained novel reader HTML (no CDN, no API)."""
import html
import os
import re

NOVEL_PATH = "/workspace/武极之圣造乾坤.md"
OUT_PATH = "/workspace/reader.html"


def md_to_html(text: str):
    chapters = []
    body_parts = []
    chapter_idx = 0
    for raw in text.split("\n"):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = html.escape(stripped[2:].strip())
            body_parts.append(f"<h1>{title}</h1>")
            continue
        if stripped.startswith("## "):
            title = html.escape(stripped[3:].strip())
            cid = f"chapter-{chapter_idx}"
            chapters.append((cid, title))
            body_parts.append(f'<h2 id="{cid}">{title}</h2>')
            chapter_idx += 1
            continue
        if stripped == "---" or set(stripped) == {"-"}:
            body_parts.append("<hr>")
            continue
        body_parts.append(f"<p>{html.escape(stripped)}</p>")
    toc = "\n".join(
        f'<li class="toc-item"><a class="toc-link" href="#{cid}">{title}</a></li>'
        for cid, title in chapters
    )
    return toc, "\n".join(body_parts), len(chapters)


def build():
    with open(NOVEL_PATH, "r", encoding="utf-8") as f:
        novel = f.read()
    toc, body, n_chapters = md_to_html(novel)
    char_count = len(re.sub(r"\s+", "", novel))
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>《武极之圣造乾坤》在线阅读</title>
<style>
:root {{
  --bg: #0d1117; --card: #161b22; --side: #11151c; --text: #e6edf3;
  --muted: #8b949e; --gold: #e3b341; --purple: #bc8cff; --border: #30363d;
  --font: 18px; --lh: 1.95;
}}
body.sepia {{
  --bg: #f4ecd8; --card: #faf4e6; --side: #ebe1c9; --text: #433422;
  --muted: #7d6b53; --border: #d8cbb5;
}}
body.light {{
  --bg: #f6f8fa; --card: #fff; --side: #f0f2f5; --text: #1f2328;
  --muted: #656d76; --border: #d0d7de;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: var(--bg); color: var(--text); font-size: var(--font);
  line-height: var(--lh);
}}
.header {{
  position: sticky; top: 0; z-index: 20; background: var(--card);
  border-bottom: 1px solid var(--border); padding: 12px 20px;
  display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
}}
.header h1 {{ font-size: 1.15rem; color: var(--gold); }}
.meta {{ color: var(--muted); font-size: 0.85rem; }}
.tools {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.tools button {{
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
}}
.layout {{
  display: flex; max-width: 1280px; margin: 0 auto; padding: 24px 16px; gap: 20px;
}}
.sidebar {{
  width: 260px; flex-shrink: 0; background: var(--side);
  border: 1px solid var(--border); border-radius: 10px; padding: 16px;
  max-height: calc(100vh - 96px); position: sticky; top: 72px; overflow: auto;
}}
.sidebar h3 {{ color: var(--gold); font-size: 1rem; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}
.toc-list {{ list-style: none; }}
.toc-link {{
  display: block; color: var(--muted); text-decoration: none; font-size: 0.88rem;
  padding: 6px 10px; border-radius: 6px;
}}
.toc-link:hover {{ color: var(--text); background: rgba(227,179,65,.12); }}
.content {{
  flex: 1; background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 40px 48px; min-width: 0;
}}
.content h1 {{ text-align: center; color: var(--gold); font-size: 2rem; margin-bottom: 28px; padding-bottom: 16px; border-bottom: 2px solid var(--border); }}
.content h2 {{ color: var(--purple); font-size: 1.4rem; margin: 44px 0 18px; padding-bottom: 8px; border-bottom: 1px solid var(--border); scroll-margin-top: 80px; }}
.content p {{ margin-bottom: 18px; text-indent: 2em; letter-spacing: .4px; }}
.content hr {{ border: 0; height: 1px; background: var(--border); margin: 36px 0; }}
@media (max-width: 900px) {{
  .sidebar {{ display: none; }}
  .content {{ padding: 22px 16px; }}
}}
</style>
</head>
<body>
<header class="header">
  <div>
    <h1>《武极之圣造乾坤》</h1>
    <div class="meta">造化圣子 × 小魔仙 · {n_chapters}章 · 约{char_count}字 · 正文已内嵌，无需二次加载</div>
  </div>
  <div class="tools">
    <button type="button" onclick="cycleTheme()">切换主题</button>
    <button type="button" onclick="resize(1)">A+</button>
    <button type="button" onclick="resize(-1)">A-</button>
  </div>
</header>
<div class="layout">
  <aside class="sidebar">
    <h3>章节目录</h3>
    <ul class="toc-list">{toc}</ul>
  </aside>
  <main class="content">{body}</main>
</div>
<script>
let theme = 0, size = 18;
function cycleTheme() {{
  theme = (theme + 1) % 3;
  document.body.className = ["", "sepia", "light"][theme];
}}
function resize(d) {{
  size = Math.min(26, Math.max(14, size + d));
  document.documentElement.style.setProperty("--font", size + "px");
}}
</script>
</body>
</html>
"""
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {OUT_PATH} chars={len(page)} chapters={n_chapters} novel_chars={char_count}")


if __name__ == "__main__":
    build()
