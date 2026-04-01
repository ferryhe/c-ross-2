import { fetchConfig, sendChatRequest } from "./api";

describe("api helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the selected model mode to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        text: "ok",
        sources: [],
        model: "gpt-5.4-mini",
        model_mode: "reasoning",
        language: "zh",
        rag_mode: "agentic",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await sendChatRequest({
      messages: [
        {
          id: "m1",
          role: "user",
          createdAt: new Date("2026-04-01T00:00:00Z"),
          content: [{ type: "text", text: "test" }],
          attachments: [],
          metadata: { custom: {} },
        },
      ],
      modelMode: "reasoning",
      signal: new AbortController().signal,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init?.body).toContain('"modelMode":"reasoning"');
  });

  it("loads chat config from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        knowledge_base_name: "中国偿二代问答系统",
        default_model_mode: "general",
        models: {
          general: "gpt-4.1",
          reasoning: "gpt-5.4-mini",
        },
        rag_mode: "agentic",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchConfig();

    expect(result.models.general).toBe("gpt-4.1");
    expect(result.models.reasoning).toBe("gpt-5.4-mini");
  });
});
