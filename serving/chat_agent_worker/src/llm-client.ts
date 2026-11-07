// Gọi LLM (Groq / Gemini qua REST). Lỗi một key/provider thì tự chuyển sang cái kế tiếp. Port của llm_client.py.
import { csv, Env } from "./env";

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const geminiUrl = (model: string) =>
  `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
const MAX_OUTPUT_TOKENS = 700;
const TEMPERATURE = 0.3;

export class LLMUnavailable extends Error {}

type Call = (key: string, system: string, user: string) => Promise<string>;

/** Chọn điểm bắt đầu ngẫu nhiên để chia tải giữa các key miễn phí (Worker không giữ trạng thái xoay vòng). */
function pickKeys(keys: string[], count: number): string[] {
  if (!keys.length) return [];
  const start = Math.floor(Math.random() * keys.length);
  return Array.from({ length: Math.min(count, keys.length) }, (_, i) => keys[(start + i) % keys.length]);
}

export async function generate(env: Env, system: string, user: string): Promise<{ text: string; provider: string }> {
  const timeout = Number(env.LLM_TIMEOUT_MS) || 6000;
  const post = async (url: string, headers: Record<string, string>, body: unknown): Promise<any> => {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeout),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  };

  const groq: Call = async (key, sys, usr) => {
    const model = env.GROQ_MODEL;
    const body: Record<string, unknown> = {
      model,
      messages: [{ role: "system", content: sys }, { role: "user", content: usr }],
      temperature: TEMPERATURE,
      max_tokens: MAX_OUTPUT_TOKENS,
    };
    // Model có chế độ suy luận: giảm/tắt để trả lời nhanh, không lẫn phần suy luận.
    if (model.includes("gpt-oss")) Object.assign(body, { reasoning_effort: "low", include_reasoning: false });
    else if (model.includes("qwen")) body.reasoning_effort = "none";
    const json = await post(GROQ_URL, { Authorization: `Bearer ${key}` }, body);
    return json.choices[0].message.content;
  };

  const gemini: Call = async (key, sys, usr) => {
    const json = await post(geminiUrl(env.GEMINI_MODEL), { "x-goog-api-key": key }, {
      systemInstruction: { parts: [{ text: sys }] },
      contents: [{ role: "user", parts: [{ text: usr }] }],
      generationConfig: { temperature: TEMPERATURE, maxOutputTokens: MAX_OUTPUT_TOKENS },
    });
    return json.candidates[0].content.parts.map((p: { text?: string }) => p.text ?? "").join("");
  };

  const providers: Record<string, { call: Call; keys: string[] }> = {
    groq: { call: groq, keys: csv(env.GROQ_API_KEYS) },
    gemini: { call: gemini, keys: csv(env.GEMINI_API_KEYS) },
  };
  const errors: string[] = [];
  for (const name of csv(env.LLM_ORDER)) {
    const p = providers[name];
    if (!p) continue;
    // Tối đa 2 key mỗi provider rồi chuyển provider để giữ độ trễ thấp.
    for (const key of pickKeys(p.keys, 2)) {
      try {
        const text = (await p.call(key, system, user)).trim();
        if (text) return { text, provider: name };
        errors.push(`${name}: rỗng`);
      } catch (e) {
        errors.push(`${name} ${(e as Error).message}`);
        console.warn(`LLM ${name} lỗi (${(e as Error).message}), thử tiếp`);
      }
    }
  }
  throw new LLMUnavailable(errors.join("; ") || "chưa cấu hình khoá LLM nào");
}
