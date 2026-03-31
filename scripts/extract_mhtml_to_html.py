from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
from html import escape
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.common import MHTML_HTML_ROOT, SOURCE_ROOT, ensure_parent, posix_rel


TARGET_IDS = {
    "wenzhang-content",
    "trs_editor",
    "trseditor",
    "article-content",
    "zoom",
    "zoomcon",
    "main-content",
}
TARGET_CLASS_TOKENS = {
    "wenzhang-content",
    "trs_editor",
    "trseditor",
    "article-content",
    "article-body",
    "content-body",
    "detail-content",
}
FALLBACK_TAGS = {"article", "main", "body"}
SKIP_TAGS = {"script", "style", "noscript"}


@dataclass(slots=True)
class ExtractedArticle:
    title: str
    publish_date: str
    content_source: str
    source_url: str
    subject: str
    content_html: str


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_text = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            attr_map = _attr_map(attrs)
            name = (attr_map.get("name") or attr_map.get("property") or "").strip()
            content = (attr_map.get("content") or "").strip()
            if name and content:
                self.meta[name] = content
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data


class _SubtreeHTMLExtractor(HTMLParser):
    def __init__(self, matcher) -> None:
        super().__init__(convert_charrefs=False)
        self.matcher = matcher
        self.parts: list[str] = []
        self.capture_depth = 0
        self.skip_depth = 0
        self.found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = _attr_map(attrs)
        should_start = self.capture_depth == 0 and self.matcher(tag, attr_map)
        if should_start:
            self.found = True
            self.capture_depth = 1
            if tag in SKIP_TAGS:
                self.skip_depth = 1
                return
            self.parts.append(_format_start_tag(tag, attrs))
            return

        if self.capture_depth == 0:
            return

        self.capture_depth += 1
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth == 0:
            self.parts.append(_format_start_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = _attr_map(attrs)
        if self.capture_depth == 0 and not self.matcher(tag, attr_map):
            return
        if tag in SKIP_TAGS or self.skip_depth > 0:
            return
        self.parts.append(_format_startend_tag(tag, attrs))
        self.found = True

    def handle_endtag(self, tag: str) -> None:
        if self.capture_depth == 0:
            return
        if tag in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            self.capture_depth -= 1
            return
        if self.skip_depth == 0:
            self.parts.append(f"</{tag}>")
        self.capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.capture_depth > 0 and self.skip_depth == 0:
            self.parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        if self.capture_depth > 0 and self.skip_depth == 0:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self.capture_depth > 0 and self.skip_depth == 0:
            self.parts.append(f"&#{name};")


def parse_mhtml_article(path: Path) -> ExtractedArticle:
    with path.open("rb") as handle:
        message = BytesParser(policy=policy.default).parse(handle)

    html_payload = _extract_html_payload(message)
    html_text = _decode_html_part(html_payload)

    meta_parser = _MetaParser()
    meta_parser.feed(html_text)

    content_html = _extract_main_content_html(html_text).strip()
    title = (
        meta_parser.meta.get("ArticleTitle")
        or meta_parser.meta.get("title")
        or meta_parser.title_text.strip()
        or path.stem
    )

    return ExtractedArticle(
        title=title.strip(),
        publish_date=(meta_parser.meta.get("PubDate") or "").strip(),
        content_source=(meta_parser.meta.get("ContentSource") or "").strip(),
        source_url=(message.get("Snapshot-Content-Location") or "").strip(),
        subject=(message.get("Subject") or "").strip(),
        content_html=content_html,
    )


def write_article_outputs(
    article: ExtractedArticle,
    source_path: Path,
    source_root: Path,
    output_root: Path,
) -> tuple[Path, Path]:
    relative_path = source_path.relative_to(source_root)
    html_path = output_root / relative_path.with_suffix(".html")
    meta_path = output_root / relative_path.with_suffix(".meta.json")
    ensure_parent(html_path)
    ensure_parent(meta_path)

    html_document = _build_article_html(article)
    html_path.write_text(html_document, encoding="utf-8")

    metadata = {
        **asdict(article),
        "original_relative_path": posix_rel(relative_path),
        "original_filename": source_path.name,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return html_path, meta_path


def extract_all_mhtml(
    source_root: Path = SOURCE_ROOT,
    output_root: Path = MHTML_HTML_ROOT,
) -> list[tuple[Path, Path]]:
    outputs: list[tuple[Path, Path]] = []
    for path in sorted(source_root.rglob("*.mhtml")):
        article = parse_mhtml_article(path)
        outputs.append(write_article_outputs(article, path, source_root, output_root))
    return outputs


def _extract_html_payload(message) -> bytes:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload is not None:
                    return payload
    payload = message.get_payload(decode=True)
    if payload is None:
        raise RuntimeError("No HTML payload found in MHTML document.")
    return payload


def _decode_html_part(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def _extract_main_content_html(html_text: str) -> str:
    extractors = [
        _SubtreeHTMLExtractor(_is_primary_target),
        _SubtreeHTMLExtractor(_is_fallback_target),
    ]
    for extractor in extractors:
        extractor.feed(html_text)
        content = "".join(extractor.parts).strip()
        if extractor.found and content:
            return content
    return "<div><p>未能识别正文容器，请检查原始网页归档。</p></div>"


def _is_primary_target(tag: str, attrs: dict[str, str]) -> bool:
    if tag not in {"div", "article", "section", "main"}:
        return False
    element_id = attrs.get("id", "").strip().lower()
    class_tokens = {token.strip().lower() for token in attrs.get("class", "").split() if token.strip()}
    if element_id in TARGET_IDS:
        return True
    if any(token in TARGET_CLASS_TOKENS for token in class_tokens):
        return True
    return False


def _is_fallback_target(tag: str, attrs: dict[str, str]) -> bool:
    return tag in FALLBACK_TAGS


def _build_article_html(article: ExtractedArticle) -> str:
    meta_lines = []
    if article.publish_date:
        meta_lines.append(f"<p><strong>发布日期：</strong>{escape(article.publish_date)}</p>")
    if article.content_source:
        meta_lines.append(f"<p><strong>来源：</strong>{escape(article.content_source)}</p>")
    if article.source_url:
        meta_lines.append(
            f'<p><strong>原始链接：</strong><a href="{escape(article.source_url)}">{escape(article.source_url)}</a></p>'
        )

    meta_block = "\n".join(meta_lines)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{escape(article.title)}</title>\n"
        "</head>\n"
        "<body>\n"
        "  <article>\n"
        f"    <h1>{escape(article.title)}</h1>\n"
        f"{meta_block}\n"
        f"{article.content_html}\n"
        "  </article>\n"
        "</body>\n"
        "</html>\n"
    )


def _attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {key: (value or "") for key, value in attrs}


def _format_start_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    rendered_attrs = []
    for key, value in attrs:
        if value is None:
            rendered_attrs.append(key)
        else:
            rendered_attrs.append(f'{key}="{escape(value, quote=True)}"')
    suffix = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
    return f"<{tag}{suffix}>"


def _format_startend_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    rendered_attrs = []
    for key, value in attrs:
        if value is None:
            rendered_attrs.append(key)
        else:
            rendered_attrs.append(f'{key}="{escape(value, quote=True)}"')
    suffix = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
    return f"<{tag}{suffix} />"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract正文 HTML from MHTML files.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=MHTML_HTML_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = extract_all_mhtml(args.source_root, args.output_root)
    print(f"[ok] Extracted {len(outputs)} MHTML file(s) into {args.output_root}")


if __name__ == "__main__":
    main()
