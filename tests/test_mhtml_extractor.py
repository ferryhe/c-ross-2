from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract_mhtml_to_html import parse_mhtml_article, write_article_outputs


def _sample_mhtml() -> bytes:
    html = """<!DOCTYPE html>
<html>
  <head>
    <meta name="ArticleTitle" content="监管通知标题">
    <meta name="PubDate" content="2024-12-01 09:00">
    <meta name="ContentSource" content="监管机构">
  </head>
  <body>
    <div class="header">站点导航</div>
    <div id="wenzhang-content">
      <p>第一条 这是正文。</p>
      <p>第二条 继续正文。</p>
    </div>
    <div class="footer">页脚信息</div>
  </body>
</html>
"""
    message = f"""From: <Saved by Blink>
Snapshot-Content-Location: https://example.com/doc
Subject: 测试
MIME-Version: 1.0
Content-Type: multipart/related; type="text/html"; boundary="----boundary"

------boundary
Content-Type: text/html; charset="utf-8"
Content-Transfer-Encoding: quoted-printable
Content-Location: https://example.com/doc

{html}
------boundary--
"""
    return message.encode("utf-8")


def test_parse_mhtml_article_extracts_main_content(tmp_path):
    source = tmp_path / "sample.mhtml"
    source.write_bytes(_sample_mhtml())

    article = parse_mhtml_article(source)

    assert article.title == "监管通知标题"
    assert article.source_url == "https://example.com/doc"
    assert article.publish_date == "2024-12-01 09:00"
    assert "第一条 这是正文" in article.content_html
    assert "第二条 继续正文" in article.content_html
    assert "站点导航" not in article.content_html
    assert "页脚信息" not in article.content_html


def test_write_article_outputs_writes_html_and_metadata(tmp_path):
    source_root = tmp_path / "source_regulation"
    output_root = tmp_path / "work" / "mhtml_html"
    source_path = source_root / "通知.mhtml"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(_sample_mhtml())

    article = parse_mhtml_article(source_path)
    html_path, meta_path = write_article_outputs(article, source_path, source_root, output_root)

    assert html_path.exists()
    assert meta_path.exists()
    assert html_path.suffix == ".html"

    html_text = html_path.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert "<article>" in html_text
    assert "监管通知标题" in html_text
    assert meta["title"] == "监管通知标题"
    assert meta["original_relative_path"] == "通知.mhtml"
