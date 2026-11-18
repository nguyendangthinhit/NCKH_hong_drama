"""Client cho API mmodiary (`POST {base}/responses`, kiểu OpenAI Responses API).

- Key: dòng 4 của .env.local, nhiều key ngăn cách bằng dấu phẩy.
- Model: lấy tuần tự từ model_list.txt. Xoay kiểu (b): dùng model hiện tại cho tới khi lỗi
  mới chuyển model kế; key hết số dư thì sang key kế (bắt đầu lại từ model đầu).
- Tính tiền theo request: không retry mù. Lỗi tạm (timeout/5xx/429) chỉ thử lại 1 lần.
- Hết key/model thì raise LLMExhausted để luồng gọi dừng hẳn.

Streaming (config.STREAM): gửi "stream": true, đọc SSE rồi gộp lại thành body có `output_text`.
`extract_text` thử lần lượt
output_text → output[].content[].text → choices[0].message.content. Kiểm bằng:
    python -m analysis_new.mmo_client --probe
"""

import http.client
import json
import sys
import time
import urllib.error
import urllib.request

from analysis_new import config


class LLMExhausted(RuntimeError):
    """Đã thử hết key/model hoặc hết số dư: dừng, không gọi tiếp."""


def read_credentials(env_path=config.ENV_FILE, model_path=config.MODEL_FILE):
    """Trả (keys, base_url, models) từ .env.local và model_list.txt. Không in key ra log."""
    lines = env_path.read_text(encoding="utf-8").splitlines()

    def value(n):
        line = lines[n - 1] if len(lines) >= n else ""
        return line.split("=", 1)[1].strip() if "=" in line else ""

    keys = [k.strip() for k in value(config.ENV_KEY_LINE).split(",") if k.strip()]
    base_url = value(config.ENV_BASE_URL_LINE) or config.DEFAULT_BASE_URL
    models = [m.strip() for m in model_path.read_text(encoding="utf-8").splitlines() if m.strip()]
    if not keys or not models:
        raise ValueError("Thiếu key (dòng 4 .env.local) hoặc model (model_list.txt)")
    return keys, base_url.rstrip("/"), models


def extract_text(body):
    """Lấy text trả lời từ JSON response. TODO(response-format): chốt lại sau khi probe."""
    if not isinstance(body, dict):
        return ""
    if isinstance(body.get("output_text"), str) and body["output_text"].strip():
        return body["output_text"]
    parts = []
    for item in body.get("output") or []:
        if not isinstance(item, dict) or item.get("type") == "reasoning":
            continue
        for c in item.get("content") or []:
            if isinstance(c, dict) and isinstance(c.get("text"), str):
                parts.append(c["text"])
    if parts:
        return "".join(parts)
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _sse_to_body(raw):
    """Gộp luồng SSE (Responses API hoặc chat-completions) thành 1 JSON body có `output_text`.

    Ưu tiên response đầy đủ ở event `response.completed`; không có thì ghép các `delta`.
    """
    deltas, final = [], None
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            ev = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        etype = str(ev.get("type", ""))
        if etype.endswith("output_text.delta") and isinstance(ev.get("delta"), str):
            deltas.append(ev["delta"])
        elif etype in ("response.completed", "response.done") and isinstance(ev.get("response"), dict):
            final = ev["response"]
        elif isinstance(ev.get("choices"), list) and ev["choices"]:
            d = (ev["choices"][0].get("delta") or {}).get("content")
            if isinstance(d, str):
                deltas.append(d)
    text = "".join(deltas)
    if text.strip():
        return json.dumps({"output_text": text}, ensure_ascii=False)
    return json.dumps(final) if final else ""


def _http_post(url, key, payload, timeout):
    """Trả (status, body_text). Lỗi mạng/timeout trả status 0.

    Payload có "stream": true thì đọc SSE; `timeout` áp cho từng lần đọc socket (không phải
    tổng thời gian) nên request dài vẫn sống nếu server liên tục gửi dữ liệu.
    """
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 **({"Accept": "text/event-stream"} if payload.get("stream") else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            if payload.get("stream") and "text/event-stream" in resp.headers.get("Content-Type", ""):
                raw = _sse_to_body(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        return 0, str(e)


def _is_balance_error(status, text):
    t = text.lower()
    return status in (401, 402) or (status == 403 and any(
        w in t for w in ("balance", "insufficient", "quota", "credit", "số dư")))


class MmoClient:
    def __init__(self, keys, models, base_url=config.DEFAULT_BASE_URL, post=_http_post):
        self.keys, self.models, self.post = list(keys), list(models), post
        self.url = base_url.rstrip("/") + config.RESPONSES_PATH
        self.key_idx = self.model_idx = 0
        self.requests_sent = 0

    @classmethod
    def from_files(cls):
        keys, base_url, models = read_credentials()
        return cls(keys, models, base_url)

    @property
    def current_model(self):
        return self.models[self.model_idx] if self.model_idx < len(self.models) else None

    def _next_model(self, why):
        print(f"  ⚠️  Bỏ model {self.current_model}: {why}", flush=True)
        self.model_idx += 1

    def _next_key(self, why):
        print(f"  ⚠️  Bỏ key #{self.key_idx + 1}: {why}", flush=True)
        self.key_idx += 1
        self.model_idx = 0

    def report_bad_output(self, why):
        """Model trả nội dung hỏng (HTTP 200 nhưng nhãn sai hàng loạt): lần gọi sau dùng model kế."""
        self._next_model(why)

    def complete(self, prompt):
        """Gửi 1 prompt, trả (text, model). Raise LLMExhausted khi hết key/model."""
        retried = False
        while self.key_idx < len(self.keys) and self.model_idx < len(self.models):
            model = self.current_model
            payload = {"model": model, "input": prompt, **config.EXTRA_BODY}
            if config.STREAM:
                payload["stream"] = True
            self.requests_sent += 1
            status, text = self.post(self.url, self.keys[self.key_idx], payload,
                                     config.REQUEST_TIMEOUT_S)
            if status == 200:
                try:
                    out = extract_text(json.loads(text))
                except json.JSONDecodeError:
                    out = ""
                if out.strip():
                    return out, model
                self._next_model("response 200 nhưng không đọc được text")
            elif _is_balance_error(status, text):
                self._next_key(f"HTTP {status} {text[:120]}")
            elif status in (0, 429) or status >= 500:
                if not retried:  # lỗi tạm: thử lại đúng 1 lần cùng key/model
                    retried = True
                    time.sleep(config.MAX_429_WAIT_S if status == 429 else 5)
                    continue
                self._next_model(f"HTTP {status} lặp lại")
            else:  # 400/403/404: model không hợp lệ hoặc không có quyền
                self._next_model(f"HTTP {status} {text[:120]}")
            retried = False
        raise LLMExhausted("Đã hết key/model khả dụng (hoặc hết số dư); dừng để không tốn request")


def _probe():
    """Gửi đúng 1 request ngắn và in nguyên response để chốt định dạng."""
    keys, base_url, models = read_credentials()
    payload = {"model": models[0], "input": "Trả lời đúng một từ: OK", **config.EXTRA_BODY}
    if config.STREAM:
        payload["stream"] = True
    status, text = _http_post(base_url + config.RESPONSES_PATH, keys[0], payload,
                              config.REQUEST_TIMEOUT_S)
    print(f"model={models[0]} HTTP {status}\n{text}")
    try:
        print("\nextract_text ->", repr(extract_text(json.loads(text))))
    except json.JSONDecodeError:
        print("\nResponse không phải JSON")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        _probe()
    else:
        print("Dùng: python -m analysis_new.mmo_client --probe  (tốn 1 request)")
