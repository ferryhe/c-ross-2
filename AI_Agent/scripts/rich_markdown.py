from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


MARKED_JS_URL = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
KATEX_CSS_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
KATEX_JS_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
KATEX_AUTORENDER_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
REPO_ROOT = Path(__file__).resolve().parents[2]
GITHUB_DOC_PATH_RE = re.compile(
    r"(?P<citation>\[(?P<index>\d+)\]\s+(?P<path>(?:Knowledge_Base_MarkDown|AI_Agent|plans|scripts|tests|source_regulation|work)/[^\n\r]*?\.md))"
)


def estimate_component_height(markdown_text: str, *, min_height: int = 160, max_height: int = 900) -> int:
    line_count = markdown_text.count("\n") + 1
    table_bonus = markdown_text.count("|") * 3
    formula_bonus = markdown_text.count("$$") * 18
    code_bonus = markdown_text.count("```") * 24
    estimated = 80 + (line_count * 22) + table_bonus + formula_bonus + code_bonus
    return max(min_height, min(max_height, estimated))


def _run_git_command(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout.strip()


@lru_cache(maxsize=1)
def get_github_blob_base_url() -> str:
    remote = _run_git_command("config", "--get", "remote.origin.url")
    branch = _run_git_command("rev-parse", "--abbrev-ref", "HEAD") or "main"

    if remote.startswith("git@github.com:"):
        repo = remote.removeprefix("git@github.com:")
    elif remote.startswith("https://github.com/"):
        repo = remote.removeprefix("https://github.com/")
    else:
        repo = "ferryhe/c-ross-2"

    if repo.endswith(".git"):
        repo = repo[:-4]
    if branch == "HEAD":
        branch = "main"

    return f"https://github.com/{repo}/blob/{branch}"


def build_github_blob_url(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    encoded_path = quote(normalized, safe="/-_.~")
    return f"{get_github_blob_base_url()}/{encoded_path}"


def linkify_github_blob_references(markdown_text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        citation = match.group("citation")
        path = match.group("path")
        return f"[{citation}]({build_github_blob_url(path)})"

    return GITHUB_DOC_PATH_RE.sub(replace, markdown_text)


def build_rich_markdown_html(markdown_text: str) -> str:
    markdown_text = linkify_github_blob_references(markdown_text)
    payload = json.dumps(markdown_text, ensure_ascii=False).replace("</", "<\\/")
    return rf"""<!DOCTYPE html>
<html lang="zh">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{KATEX_CSS_URL}">
    <style>
      :root {{
        color-scheme: light;
      }}

      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
      }}

      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: rgb(49, 51, 63);
      }}

      #root {{
        line-height: 1.6;
        font-size: 1rem;
        overflow-wrap: anywhere;
      }}

      #root > :first-child {{
        margin-top: 0;
      }}

      #root > :last-child {{
        margin-bottom: 0;
      }}

      #root p, #root ul, #root ol, #root blockquote, #root pre, #root table {{
        margin: 0 0 0.9rem 0;
      }}

      #root table {{
        border-collapse: collapse;
        width: 100%;
        display: block;
        overflow-x: auto;
      }}

      #root th, #root td {{
        border: 1px solid rgba(49, 51, 63, 0.2);
        padding: 0.45rem 0.6rem;
        text-align: left;
        vertical-align: top;
      }}

      #root th {{
        background: rgba(49, 51, 63, 0.06);
      }}

      #root code {{
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        background: rgba(49, 51, 63, 0.08);
        border-radius: 0.3rem;
        padding: 0.1rem 0.25rem;
      }}

      #root pre {{
        background: rgba(49, 51, 63, 0.08);
        border-radius: 0.4rem;
        padding: 0.8rem 1rem;
        overflow-x: auto;
      }}

      #root pre code {{
        background: transparent;
        padding: 0;
      }}

      #root blockquote {{
        border-left: 0.25rem solid rgba(49, 51, 63, 0.25);
        padding-left: 0.8rem;
        color: rgba(49, 51, 63, 0.85);
      }}

      #root hr {{
        border: none;
        border-top: 1px solid rgba(49, 51, 63, 0.15);
        margin: 1rem 0;
      }}

      .katex-display {{
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0.2rem 0;
      }}

      #root a {{
        color: #0f62fe;
        text-decoration: underline;
        text-underline-offset: 0.12em;
      }}
    </style>
    <script src="{MARKED_JS_URL}"></script>
    <script defer src="{KATEX_JS_URL}"></script>
    <script defer src="{KATEX_AUTORENDER_URL}"></script>
  </head>
  <body>
    <div id="root"></div>
    <script>
      const markdownSource = {payload};

      function setFrameHeight() {{
        const height = Math.max(
          document.documentElement.scrollHeight || 0,
          document.body.scrollHeight || 0,
          document.getElementById("root").scrollHeight || 0
        );
        window.parent.postMessage(
          {{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }},
          "*"
        );
      }}

      function sanitizeHtmlTree(root) {{
        const disallowedTags = new Set([
          "script",
          "style",
          "iframe",
          "object",
          "embed",
          "link",
          "meta",
          "base",
          "form",
          "input",
          "button",
          "textarea",
          "select",
          "option"
        ]);
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        const nodesToRemove = [];

        while (walker.nextNode()) {{
          const element = walker.currentNode;
          const tagName = element.tagName.toLowerCase();
          if (disallowedTags.has(tagName)) {{
            nodesToRemove.push(element);
            continue;
          }}

          for (const attribute of Array.from(element.attributes)) {{
            const name = attribute.name.toLowerCase();
            const value = attribute.value.trim().toLowerCase();
            if (name.startsWith("on")) {{
              element.removeAttribute(attribute.name);
              continue;
            }}
            if ((name === "href" || name === "src" || name === "xlink:href") && value.startsWith("javascript:")) {{
              element.removeAttribute(attribute.name);
            }}
          }}
        }}

        for (const element of nodesToRemove) {{
          element.remove();
        }}
      }}

      function normalizeLikelyLatexArtifacts(mathText) {{
        return mathText.replace(
          /(\\\\(?:mathrm|mathbf|mathit|operatorname)\s*\\{{[^{{}}]+\\}})\s*\\{{\s*(\\\\text\s*\\{{[^{{}}]+\\}})\s*\\}}/g,
          "$1_{{$2}}"
        );
      }}

      function extractMathSegments(markdown) {{
        const codeFencePattern = /```[\s\S]*?```/g;
        const mathPattern = /\$\$[\s\S]+?\$\$|\\\\\[[\s\S]+?\\\\\]|(?<!\\)\$[^$\n]+?(?<!\\)\$|\\\\\([^\n]+?\\\\\)/g;
        const segments = [];
        let output = "";
        let cursor = 0;

        for (const codeFence of markdown.matchAll(codeFencePattern)) {{
          const codeStart = codeFence.index ?? 0;
          const codeText = codeFence[0];
          output += markdown
            .slice(cursor, codeStart)
            .replace(mathPattern, (match) => {{
              const token = `@@MATH_SEGMENT_${{segments.length}}@@`;
              segments.push(normalizeLikelyLatexArtifacts(match));
              return token;
            }});
          output += codeText;
          cursor = codeStart + codeText.length;
        }}

        output += markdown.slice(cursor).replace(mathPattern, (match) => {{
          const token = `@@MATH_SEGMENT_${{segments.length}}@@`;
          segments.push(normalizeLikelyLatexArtifacts(match));
          return token;
        }});

        return {{ markdown: output, segments }};
      }}

      function restoreMathSegments(root, segments) {{
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const replacements = [];

        while (walker.nextNode()) {{
          const node = walker.currentNode;
          const text = node.textContent || "";
          if (!text.includes("@@MATH_SEGMENT_")) {{
            continue;
          }}

          const fragment = document.createDocumentFragment();
          const parts = text.split(/(@@MATH_SEGMENT_\d+@@)/g).filter(Boolean);
          for (const part of parts) {{
            const match = part.match(/^@@MATH_SEGMENT_(\d+)@@$/);
            if (match) {{
              fragment.appendChild(document.createTextNode(segments[Number(match[1])] || part));
            }} else {{
              fragment.appendChild(document.createTextNode(part));
            }}
          }}
          replacements.push([node, fragment]);
        }}

        for (const [node, fragment] of replacements) {{
          node.parentNode.replaceChild(fragment, node);
        }}
      }}

      function configureLinks(root) {{
        for (const link of root.querySelectorAll("a[href]")) {{
          const href = link.getAttribute("href") || "";
          if (href.startsWith("http://") || href.startsWith("https://")) {{
            link.setAttribute("target", "_blank");
            link.setAttribute("rel", "noopener noreferrer");
          }}
        }}
      }}

      function render() {{
        if (!window.marked || !window.renderMathInElement) {{
          window.setTimeout(render, 50);
          return;
        }}

        marked.setOptions({{
          gfm: true,
          breaks: true
        }});

        const root = document.getElementById("root");
        const extracted = extractMathSegments(markdownSource);
        root.innerHTML = marked.parse(extracted.markdown);
        restoreMathSegments(root, extracted.segments);
        sanitizeHtmlTree(root);
        configureLinks(root);

        window.renderMathInElement(root, {{
          throwOnError: false,
          strict: "ignore",
          delimiters: [
            {{ left: "$$", right: "$$", display: true }},
            {{ left: "\\\\[", right: "\\\\]", display: true }},
            {{ left: "$", right: "$", display: false }},
            {{ left: "\\\\(", right: "\\\\)", display: false }}
          ]
        }});

        setFrameHeight();
        window.setTimeout(setFrameHeight, 120);
      }}

      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", render);
      }} else {{
        render();
      }}

      window.addEventListener("load", setFrameHeight);
      window.addEventListener("resize", setFrameHeight);
    </script>
  </body>
</html>
"""


def render_rich_markdown(markdown_text: str, *, height: int | None = None) -> None:
    import streamlit.components.v1 as components

    if not markdown_text.strip():
        return

    components.html(
        build_rich_markdown_html(markdown_text),
        height=height or estimate_component_height(markdown_text),
        scrolling=False,
    )
