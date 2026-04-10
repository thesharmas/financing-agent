/** Result from analyzing a financing offer. */
export interface AnalysisResult {
  /** Full plain English analysis text. */
  analysis: string;
  /** MCP tools that were called during analysis. */
  toolCalls: string[];
}

/** Client usage statistics. */
export interface UsageInfo {
  name: string;
  company: string;
  createdAt: string;
  totalCalls: number;
  lastCalledAt: string | null;
}

/** Configuration options for the FinancingAgent client. */
export interface FinancingAgentOptions {
  /** Your API key (fin_...). Falls back to FINANCING_API_KEY env var. */
  apiKey?: string;
  /** Proxy URL. Override for self-hosted deployments. */
  baseUrl?: string;
  /** Request timeout in milliseconds. Default: 120000 (2 minutes). */
  timeoutMs?: number;
}

/** Event from the streaming analysis endpoint. */
export interface StreamEvent {
  type: "text" | "tool_use" | "done" | "error";
  content?: string;
  name?: string;
}
