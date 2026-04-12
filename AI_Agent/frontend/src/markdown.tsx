import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { buildSourceHeading, prepareMarkdownForRendering } from "./lib/citations";
import type { SourceItem } from "./types";

interface MarkdownMessageProps {
  markdown: string;
  sources?: SourceItem[];
}

export function MarkdownMessage({ markdown, sources = [] }: MarkdownMessageProps) {
  const preparedMarkdown = prepareMarkdownForRendering(markdown, sources);

  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: "ignore", throwOnError: false }]]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noreferrer noopener" />
          ),
          table: ({ node: _node, ...props }) => (
            <div className="markdown-table-wrap">
              <table {...props} />
            </div>
          ),
        }}
      >
        {preparedMarkdown}
      </ReactMarkdown>

      {sources.length > 0 ? (
        <details className="source-panel">
          <summary>引用与检索片段</summary>
          <div className="source-list">
            {sources.map((source) => (
              <article className="source-card" key={`${source.index}-${source.path}`}>
                <div className="source-card__title">
                  <span className="source-card__index">[{source.index}]</span>
                  <a href={source.url} target="_blank" rel="noreferrer noopener">
                    {buildSourceHeading(source)}
                  </a>
                </div>
                <p className="source-card__snippet">{source.snippet}</p>
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
