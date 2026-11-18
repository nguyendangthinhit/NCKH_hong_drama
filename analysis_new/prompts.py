"""Prompt gán nhãn theo cụm. Mỗi request chứa nhiều cụm; mỗi cụm giữ nguyên cấp bậc reply.

Comment được đánh mã cục bộ "K<cụm>.<thứ tự>" để LLM trả lại đúng mã (ngắn, khó bịa).
Bộ nhãn và few-shot lấy từ prompt cũ ở analysis/single/.
"""

from analysis_new import config

_SHOWBIZ_RULES = """Nhãn emotion: "Phẫn nộ"=tức giận/bức xúc | "Cà khịa"=mỉa mai/châm biếm |
"Đồng cảm"=thương/chia sẻ | "Ủng hộ"=đồng ý/khen | "Trung lập"=thông tin/hỏi/không rõ cảm xúc.
toxic=true nếu chửi bới/công kích dù ngắn ("đm", "ngu", "con chó",...);
toxic_type: "chửi bới" / "công kích cá nhân" / "công kích người thân" (null nếu toxic=false).
Lưu ý: ":)))" hoặc 🌝 thường = mỉa mai → Cà khịa; chê ngoại hình/hành động → Cà khịa hoặc Phẫn nộ.
Ví dụ: "Sao nó xấu kinh dị vậy trời" → Cà khịa | "Ủng hộ chị 100%" → Ủng hộ |
"Đm thằng này láo" → Phẫn nộ, toxic=true, "chửi bới" | "Tội nghiệp quá" → Đồng cảm."""

_EDUCATION_RULES = """Nhãn stance: "tích cực"=đồng ý/ủng hộ/khen | "tiêu cực"=phản đối/chỉ trích/lo ngại |
"trung lập"=thờ ơ, "kệ", chỉ hỏi han, chờ xem, KHÔNG có ý kiến rõ ràng |
"ý kiến riêng"=ủng hộ một phần + phê phán phần khác, đề xuất giải pháp, phân tích 2 chiều.
Comment ngắn "Đúng rồi" / "Sai hoàn toàn" → tích cực/tiêu cực (xét theo điều nó trả lời).
Ví dụ: "Truy cứu trách nhiệm những người liên quan" → tiêu cực | "Hay quá, ủng hộ mạnh mẽ!" → tích cực."""

_TRASH_RULES = """is_trash=true nếu: chỉ là tên người; tag tên + emoji/reaction ngắn; chỉ emoji/ký tự lặp;
chứa link/quảng cáo; dưới 8 ký tự vô nghĩa. Comment rác không cần nhãn cảm xúc."""


def local_id(ci: int, ni: int) -> str:
    return f"K{ci}.{ni}"


def render_clusters(clusters) -> tuple:
    """Trả (văn bản các cụm, map mã cục bộ -> id thật, map "K<ci>" -> root_id)."""
    lines, id_map, cluster_map = [], {}, {}
    for ci, cl in enumerate(clusters, 1):
        cluster_map[f"K{ci}"] = cl["root_id"]
        local_of = {}
        lines.append(f"### Cụm K{ci}")
        for ni, n in enumerate(cl["nodes"]):
            lid = local_id(ci, ni)
            local_of[n["id"]], id_map[lid] = lid, n["id"]
            indent = "  " * (n["level"] - 1)
            where = f"cấp {n['level']}"
            if n["parent_id"] in local_of:
                where += f", trả lời {local_of[n['parent_id']]}"
            mark = " [rác - không gán nhãn]" if n["rule_trash"] else ""
            text = " ".join(n["text"].split())[:config.MAX_TEXT_CHARS]
            lines.append(f'{indent}[{lid}] ({where}){mark}: "{text}"')
    return "\n".join(lines), id_map, cluster_map


def _code_legend(cfg) -> str:
    """Dòng hướng dẫn trả nhãn bằng mã ASCII (tránh model làm méo chữ có dấu)."""
    legend = ", ".join(f"{k}={v}" for k, v in cfg["codes"].items())
    line = f'BẮT BUỘC ghi {cfg["label_field"]} bằng MÃ 2 chữ cái: {legend}.'
    if cfg["toxic"]:
        line += " toxic_type cũng ghi bằng mã: " + ", ".join(
            f"{k}={v}" for k, v in config.TOXIC_CODES.items()) + "."
    return line


def build_label_prompt(domain: str, event: dict, clusters) -> tuple:
    """Trả (prompt, id_map, cluster_map) cho một request gồm nhiều cụm."""
    cfg = config.domain_cfg(domain)
    body, id_map, cluster_map = render_clusters(clusters)
    field = cfg["label_field"]
    if cfg["toxic"]:
        rules = _SHOWBIZ_RULES
        item = f'{{"id":"K1.0","is_trash":false,"{field}":"CK","toxic":false,"toxic_type":null}}'
    else:
        rules = _EDUCATION_RULES
        item = f'{{"id":"K1.0","is_trash":false,"{field}":"TI"}}'
    codes = _code_legend(cfg)
    post = " ".join(str(event.get("post_title") or "").split())[:config.MAX_POST_CHARS]
    prompt = f"""Bạn là chuyên gia phân tích dư luận mạng xã hội Việt Nam ({domain}).
Sự kiện: {event.get("name") or event.get("event_id")}
Nội dung bài đăng: {post}

Dưới đây là {len(clusters)} cụm bình luận. Mỗi cụm gồm 1 comment cấp 1 và các reply con,
thụt lề theo cấp; "trả lời Kx.y" cho biết reply đó trả lời comment nào.
Đọc CẢ CỤM như một cuộc trò chuyện rồi gán nhãn TỪNG comment: nhãn nói về comment đó,
nhưng hiểu nghĩa của nó qua comment nó trả lời (ví dụ reply "chuẩn" đồng tình với comment
cha đang mỉa mai thì cũng là mỉa mai).

{body}

=== QUY TẮC ===
{_TRASH_RULES}
{rules}
{codes}
Với mỗi cụm viết "summary": 1-2 câu tóm tắt cuộc trao đổi (ai đồng tình/phản bác điều gì). Trong summary KHÔNG dùng dấu nháy kép ", nếu cần trích dẫn thì dùng nháy đơn '.

Chỉ trả về JSON, KHÔNG giải thích, bỏ qua comment đánh dấu [rác]:
{{"clusters":[{{"cluster":"K1","summary":"...","comments":[{item}]}}]}}"""
    return prompt, id_map, cluster_map


def build_event_summary_prompt(event: dict, counts: dict, examples: dict, cluster_summaries) -> str:
    """Một request/sự kiện (Giáo dục) thay cho 5 request tổng hợp của bản cũ."""
    lines = [f'- {s} ({counts.get(s, 0)}): ' + " | ".join(f'"{e}"' for e in ex)
             for s, ex in examples.items() if counts.get(s, 0)]
    threads = "\n".join(f"- {s}" for s in cluster_summaries[:30])
    labels = list(examples)
    return f"""Sự kiện giáo dục: {event.get("name") or event.get("event_id")}

Số comment và ví dụ theo lập trường:
{chr(10).join(lines)}

Tóm tắt một số cuộc trao đổi:
{threads}

Trả về JSON, không giải thích:
{{"summaries":{{{", ".join(f'"{s}":"2-3 câu xu thế chung"' for s in labels)}}},
"focus":"Dư luận quan tâm nhất về...","trend":"Xu hướng dư luận..."}}"""
