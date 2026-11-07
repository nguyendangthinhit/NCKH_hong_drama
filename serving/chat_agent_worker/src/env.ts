// Kiểu biến môi trường của Worker (vars trong wrangler.toml + secrets + Durable Object binding).
import type { SessionStore } from "./session-durable-object";

export interface Env {
  SESSIONS: DurableObjectNamespace<SessionStore>;
  ALLOWED_ORIGINS: string;
  LLM_ORDER: string;
  GROQ_MODEL: string;
  GEMINI_MODEL: string;
  LLM_TIMEOUT_MS: string;
  // Secrets
  GROQ_API_KEYS?: string;
  GEMINI_API_KEYS?: string;
  AGENT_API_KEY?: string;
}

export const csv = (value?: string): string[] =>
  (value ?? "").split(",").map((v) => v.trim()).filter(Boolean);
