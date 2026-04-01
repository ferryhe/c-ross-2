import { buildSourceHeading, linkifyNumericCitations } from "./citations";

describe("linkifyNumericCitations", () => {
  it("replaces numeric citations with clickable links", () => {
    const result = linkifyNumericCitations("答案见[1]和[2]。", [
      { index: 1, path: "a.md", url: "https://example.com/a", snippet: "A" },
      { index: 2, path: "b.md", url: "https://example.com/b", snippet: "B" },
    ]);

    expect(result).toContain("[1](https://example.com/a)");
    expect(result).toContain("[2](https://example.com/b)");
  });

  it("keeps unknown citations unchanged", () => {
    const result = linkifyNumericCitations("答案见[3]。", [
      { index: 1, path: "a.md", url: "https://example.com/a", snippet: "A" },
    ]);

    expect(result).toBe("答案见[3]。");
  });
});

describe("buildSourceHeading", () => {
  it("adds section heading for section sources", () => {
    expect(
      buildSourceHeading({
        index: 1,
        path: "Knowledge_Base_MarkDown/rules/foo.md",
        url: "https://example.com",
        snippet: "snippet",
        source_kind: "section",
        section_heading: "第二章",
      }),
    ).toBe("Knowledge_Base_MarkDown/rules/foo.md | 第二章");
  });
});
