export type ModelMode = "general" | "reasoning";

export interface SourceItem {
  index: number;
  path: string;
  url: string;
  snippet: string;
  source_kind?: string | null;
  section_heading?: string | null;
}

export interface ChatResponse {
  text: string;
  sources: SourceItem[];
  model: string;
  model_mode: ModelMode;
  language: "zh" | "en";
  rag_mode: "agentic" | "standard";
}

export interface ChatConfigResponse {
  knowledge_base_name: string;
  default_model_mode: ModelMode;
  models: {
    general: string;
    reasoning: string;
  };
  rag_mode: "agentic" | "standard";
}
