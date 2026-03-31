from __future__ import annotations

import json


MARKED_JS_URL = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
KATEX_CSS_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
KATEX_JS_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
KATEX_AUTORENDER_URL = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"


def estimate_component_height(markdown_text: str, *, min_height: int = 160, max_height: int = 900) -> int:
    line_count = markdown_text.count("\n") + 1
    table_bonus = markdown_text.count("|") * 3
    formula_bonus = markdown_text.count("$$") * 18
    code_bonus = markdown_text.count("```") * 24
    estimated = 80 + (line_count * 22) + table_bonus + formula_bonus + code_bonus
    return max(min_height, min(max_height, estimated))


def build_rich_markdown_html(markdown_text: str) -> str:
    payload = json.dumps(markdown_text, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
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
        root.innerHTML = marked.parse(markdownSource);
        sanitizeHtmlTree(root);

        window.renderMathInElement(root, {{
          throwOnError: false,
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
