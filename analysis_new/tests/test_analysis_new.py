"""Test offline cho analysis_new (không gọi API). Chạy: python -m pytest analysis_new/tests"""

import json
from pathlib import Path

import pytest

from analysis_new import event_pipeline as ep
from analysis_new import mmo_client
from analysis_new.request_planner import parse_label_response, plan_requests
from analysis_new.prompts import build_label_prompt
from analysis_new.tests.fake_llm import FakeLLM
from analysis_new.thread_loader import build_clusters, load_event

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data" / "sample" / "showbiz_068 (1).json"  # định dạng chính thức


def _c(cid, pid=None, text="bình luận đủ dài để không bị coi là rác"):
    return {"id": cid, "parent_id": pid if pid else "None", "text": text, "likes": "1"}


def test_orphan_and_cycle_become_roots():
    event = {"comments": [_c("a"), _c("b", "a"), _c("c", "missing"), _c("x", "y"), _c("y", "x")]}
    clusters = build_clusters(event)
    roots = {c["root_id"]: c for c in clusters}
    assert [n["id"] for n in roots["a"]["nodes"]] == ["a", "b"]
    assert roots["c"]["nodes"][0]["orphan"] is True
    assert sum(len(c["nodes"]) for c in clusters) == 5


def test_plan_requests_respects_limit_and_skips_all_trash():
    clusters = [{"root_id": str(i), "nodes": [{"rule_trash": False}] * 30} for i in range(3)]
    clusters.append({"root_id": "t", "nodes": [{"rule_trash": True}]})
    clusters.append({"root_id": "big", "nodes": [{"rule_trash": False}] * 100})
    batches = plan_requests(clusters, max_comments=60)
    assert [[c["root_id"] for c in b] for b in batches] == [["0", "1"], ["2"], ["big"]]


def test_parse_response_fallbacks():
    event = {"comments": [_c("a"), _c("b", "a"), _c("c", "a"), _c("t", "a", text="ok")]}
    batch = build_clusters(event)
    prompt, id_map, cmap = build_label_prompt("showbiz", {"name": "e"}, batch)
    assert "[rác - không gán nhãn]" in prompt
    text = '<think>x</think>```json\n{"clusters":[{"cluster":"K1","summary":"s","comments":[' \
           '{"id":"K1.0","is_trash":false,"emotion":"Phẫn nộ","toxic":true,"toxic_type":"chửi bới"},' \
           '{"id":"K1.1","is_trash":false,"emotion":"Vui"}]}]}\n```'
    labels, summ = parse_label_response("showbiz", text, batch, id_map, cmap)
    assert labels["a"]["emotion"] == "Phẫn nộ" and labels["a"]["toxic_type"] == "chửi bới"
    assert labels["b"]["label_source"] == "fallback_invalid_label"
    assert labels["c"]["label_source"] == "fallback_missing"
    assert labels["t"] == {"is_trash": True, "emotion": None, "label_source": "rule",
                           "toxic": None, "toxic_type": None}
    assert summ == {"a": "s"}


@pytest.mark.parametrize("body,expected", [
    ({"output_text": "A"}, "A"),
    ({"output": [{"type": "reasoning", "content": [{"text": "no"}]},
                 {"type": "message", "content": [{"type": "output_text", "text": "B"}]}]}, "B"),
    ({"choices": [{"message": {"content": "C"}}]}, "C"),
    ({}, ""),
])
def test_extract_text_variants(body, expected):
    assert mmo_client.extract_text(body) == expected


def test_client_rotation_model_then_key_then_exhausted(monkeypatch):
    monkeypatch.setattr(mmo_client.time, "sleep", lambda s: None)
    calls, answers = [], iter([
        (404, "model not found"),                      # key1/m1 -> m2
        (403, '{"error":"INSUFFICIENT_BALANCE"}'),     # key1 hết tiền -> key2/m1
        (200, json.dumps({"output_text": "ok"})),
        (500, "x"), (500, "x"),                        # lỗi tạm lặp lại -> m2
        (400, "bad"),                                  # m2 hết -> hết model
    ])

    def post(url, key, payload, timeout):
        calls.append((key, payload["model"]))
        return next(answers)

    c = mmo_client.MmoClient(["k1", "k2"], ["m1", "m2"], post=post)
    assert c.complete("p") == ("ok", "m1")
    with pytest.raises(mmo_client.LLMExhausted):
        c.complete("p")
    assert calls == [("k1", "m1"), ("k1", "m2"), ("k2", "m1"),
                     ("k2", "m1"), ("k2", "m1"), ("k2", "m2")]


def test_read_credentials_comma_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("a\nb\nc\nAPI_key= k1 , k2\nBase URL=https://x/v1/\n", encoding="utf-8")
    models = tmp_path / "m.txt"
    models.write_text("m1\n\nm2\n", encoding="utf-8")
    assert mmo_client.read_credentials(env, models) == (["k1", "k2"], "https://x/v1", ["m1", "m2"])


@pytest.mark.parametrize("domain", ["showbiz", "education"])
def test_end_to_end_with_fake_client(tmp_path, domain):
    event = load_event(OFFICIAL)
    clusters, batches = ep.prepare_event(event)
    client, labels, summaries = FakeLLM("Cà khịa" if domain == "showbiz" else "tiêu cực"), {}, {}
    for b in batches:
        lab, summ, _ = ep.label_batch(client, domain, event, b)
        labels.update(lab)
        summaries.update(summ)
    full, summary = ep.finalize_event(client, domain, event, clusters, labels, summaries)
    ep.write_outputs(tmp_path, full, summary)
    assert ep.is_done(tmp_path, event["event_id"])
    assert client.requests_sent == ep.count_requests(domain, batches)
    assert len(full["comments"]) == 787
    assert set(summary["label_sources"]) <= {"llm", "rule"}
    key = "emotion_stats" if domain == "showbiz" else "comment_counts"
    assert key in summary



def test_official_nested_format_is_flattened_with_full_hierarchy():
    """Định dạng chính thức (cây replies lồng nhau) -> phẳng, đủ comment, đủ 7 cấp."""
    event = load_event(OFFICIAL)
    assert event["event_id"] == "showbiz_068" and event["name"] and event["post_title"]
    assert len(event["comments"]) == 787 and "replies" not in event["comments"][0]
    clusters = build_clusters(event)
    nodes = [n for c in clusters for n in c["nodes"]]
    assert len(clusters) == 590 and len(nodes) == 787
    assert max(n["level"] for n in nodes) == 7
    assert not any(n["orphan"] for n in nodes)
    # parent_id lấy từ cây phải khớp reply_to_id gốc
    assert all(c["parent_id"] == c.get("reply_to_id") for c in event["comments"] if c["parent_id"])


def test_official_format_end_to_end_keeps_original_fields(tmp_path):
    event = load_event(OFFICIAL)
    event["comments"] = event["comments"][:40]
    clusters, batches = ep.prepare_event(event)
    client, labels, summaries = FakeLLM("Ủng hộ"), {}, {}
    for b in batches:
        lab, summ, _ = ep.label_batch(client, "showbiz", event, b)
        labels.update(lab)
        summaries.update(summ)
    full, summary = ep.finalize_event(client, "showbiz", event, clusters, labels, summaries)
    assert summary["id_content"] == "showbiz_068"
    assert {"comment_id", "order", "likes", "level", "root_id", "emotion"} <= set(full["comments"][0])


def test_unknown_format_rejected(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"comments": [{"foo": 1}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_event(bad)


def test_label_codes_decoded_and_garbled_labels_fall_back():
    """Mã ASCII -> nhãn tiếng Việt; nhãn méo chữ (đã gặp thật: "Trung立") -> fallback."""
    from analysis_new.request_planner import _clean_item
    ok = _clean_item("showbiz", {"emotion": "ck", "toxic": True, "toxic_type": "NT"})
    assert ok["emotion"] == "Cà khịa" and ok["toxic_type"] == "công kích người thân"
    assert _clean_item("showbiz", {"emotion": "Ủng hộ"})["emotion"] == "Ủng hộ"
    assert _clean_item("education", {"stance": "YK"})["stance"] == "ý kiến riêng"
    assert _clean_item("showbiz", {"emotion": "Trung立"})["label_source"] == "fallback_invalid_label"


def test_sse_stream_is_merged_into_output_text():
    raw = ('event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"Xin "}\n\n'
           'data: {"type":"response.output_text.delta","delta":"chào"}\n\ndata: [DONE]\n')
    assert mmo_client.extract_text(json.loads(mmo_client._sse_to_body(raw))) == "Xin chào"
    done = 'data: {"type":"response.completed","response":{"output_text":"đủ"}}\n'
    assert mmo_client.extract_text(json.loads(mmo_client._sse_to_body(done))) == "đủ"
    assert mmo_client._sse_to_body("không phải sse") == ""


def test_client_requests_stream_and_skips_model_on_bad_output():
    payloads = []

    def post(url, key, payload, timeout):
        payloads.append(payload)
        return 200, json.dumps({"output_text": "ok"})

    c = mmo_client.MmoClient(["k"], ["m1", "m2"], post=post)
    c.complete("p")
    assert payloads[0]["stream"] is True
    c.report_bad_output("nhãn hỏng")
    assert c.current_model == "m2"


def test_mostly_bad_labels_raise_and_save_raw_response(tmp_path):
    """>50% nhãn hỏng: raise BadLabelResponse, lưu response, báo model hỏng cho client."""
    event = load_event(OFFICIAL)
    _, batches = ep.prepare_event(event)

    class GarbledLLM:
        requests_sent, reported = 0, None

        def complete(self, prompt):
            return "không phải JSON", "m1"

        def report_bad_output(self, why):
            self.reported = why

    client = GarbledLLM()
    with pytest.raises(ep.BadLabelResponse):
        ep.label_batch(client, "showbiz", event, batches[0], bad_dir=tmp_path)
    assert client.reported
    saved = list((tmp_path / "_bad_responses").glob("*.txt"))
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == "không phải JSON"


def test_broken_json_with_unescaped_quotes_is_salvaged():
    """Bản vớt từ response thật bị hỏng (summary chứa " chưa escape): nhãn và summary vẫn đọc được."""
    from analysis_new.request_planner import parse_label_response
    event = load_event(OFFICIAL)
    _, batches = ep.prepare_event(event)
    batch = batches[0]
    from analysis_new import prompts
    _, id_map, cluster_map = prompts.build_label_prompt("showbiz", event, batch)
    lid = next(k for k in id_map)
    cl = next(k for k in cluster_map)
    text = ('{"clusters":[{"cluster":"%s","summary":"Fan "gai con" cà khịa."},'
            '{"comments":[{"id":"%s","is_trash":false,"emotion":"CK","toxic":false,"toxic_type":null}],"cluster":"%s"}]}'
            % (cl, lid, cl))
    labels, summaries = parse_label_response("showbiz", text, batch, id_map, cluster_map)
    assert labels[id_map[lid]]["emotion"] == "Cà khịa" and labels[id_map[lid]]["label_source"] == "llm"
    assert "gai con" in summaries[cluster_map[cl]]
