import * as fs from "fs";
import * as path from "path";
import {
  AnalysisResult,
  FinancingAgentOptions,
  StreamEvent,
  UsageInfo,
} from "./types";

const DEFAULT_BASE_URL =
  "https://financing-proxy-259728300238.us-central1.run.app";
const DEFAULT_MESSAGE =
  "Analyze this financing offer. Extract all key terms, calculate the " +
  "effective APR, check for predatory terms, and compare to market " +
  "benchmarks. Explain everything in plain English.";

export class FinancingAgent {
  private apiKey: string;
  private baseUrl: string;
  private timeoutMs: number;

  constructor(options: FinancingAgentOptions = {}) {
    this.apiKey =
      options.apiKey || process.env.FINANCING_API_KEY || "";
    if (!this.apiKey) {
      throw new Error(
        "API key required. Pass apiKey or set FINANCING_API_KEY env var.\n" +
          "Get a key at: POST /v1/register"
      );
    }
    this.baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs || 120_000;
  }

  private headers(): Record<string, string> {
    return {
      "X-API-Key": this.apiKey,
      "Content-Type": "application/json",
    };
  }

  private readPdf(pdfPath: string): string {
    const buf = fs.readFileSync(pdfPath);
    return buf.toString("base64");
  }

  /** Analyze a PDF financing offer. Returns the full result. */
  async analyzePdf(
    pdfPath: string,
    message: string = DEFAULT_MESSAGE
  ): Promise<AnalysisResult> {
    const pdfData = this.readPdf(pdfPath);
    const title = path.basename(pdfPath);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(`${this.baseUrl}/v1/analyze/sync`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ pdf: pdfData, message, title }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`API error ${resp.status}: ${text}`);
      }

      const data = (await resp.json()) as Record<string, any>;
      return {
        analysis: data.analysis,
        toolCalls: (data.tool_calls || []).map((t: any) => t.name),
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Analyze a PDF and stream the response. Yields text chunks. */
  async *analyzePdfStream(
    pdfPath: string,
    message: string = DEFAULT_MESSAGE
  ): AsyncGenerator<string> {
    const pdfData = this.readPdf(pdfPath);
    const title = path.basename(pdfPath);

    const resp = await fetch(`${this.baseUrl}/v1/analyze`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ pdf: pdfData, message, title }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`API error ${resp.status}: ${text}`);
    }

    const reader = resp.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const event: StreamEvent = JSON.parse(line.slice(6));
        if (event.type === "text" && event.content) {
          yield event.content;
        } else if (event.type === "done") {
          return;
        } else if (event.type === "error") {
          throw new Error(`Analysis error: ${event.content}`);
        }
      }
    }
  }

  /** Analyze a financing offer described in text (no PDF). */
  async analyzeText(
    text: string,
    message?: string
  ): Promise<AnalysisResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(`${this.baseUrl}/v1/analyze/sync`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({
          pdf: "",
          message: message || text,
          title: "text-input",
        }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`API error ${resp.status}: ${text}`);
      }

      const data = (await resp.json()) as Record<string, any>;
      return {
        analysis: data.analysis,
        toolCalls: (data.tool_calls || []).map((t: any) => t.name),
      };
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Get your usage statistics. */
  async getUsage(): Promise<UsageInfo> {
    const resp = await fetch(`${this.baseUrl}/v1/usage`, {
      headers: this.headers(),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`API error ${resp.status}: ${text}`);
    }

    const data = (await resp.json()) as Record<string, any>;
    return {
      name: data.name,
      company: data.company,
      createdAt: data.created_at,
      totalCalls: data.total_calls,
      lastCalledAt: data.last_called_at,
    };
  }

  /** Register for an API key. Returns the key (shown once). */
  static async register(
    name: string,
    email: string,
    company: string,
    baseUrl?: string
  ): Promise<string> {
    const url = (baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
    const resp = await fetch(`${url}/v1/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, company }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Registration failed ${resp.status}: ${text}`);
    }

    const data = (await resp.json()) as Record<string, any>;
    return data.api_key;
  }
}
