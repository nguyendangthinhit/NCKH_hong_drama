"""
Nạp đồ thị thảo luận vào Neo4j (idempotent: chạy lại không nhân đôi nút).

Nguồn: data/gnn/graphs_{domain}.pkl (+ tuỳ chọn predictions_{domain}.json của GNN).
Kết nối qua biến môi trường: NEO4J_URI (mặc định bolt://localhost:7687),
NEO4J_USER (mặc định neo4j), NEO4J_PASSWORD (bắt buộc).

Usage:
    python load_graph_to_neo4j.py --init-schema --domain education
    python load_graph_to_neo4j.py --domain education --predictions data/gnn/predictions_education.json
    python load_graph_to_neo4j.py --domain education --wipe-domain   # xoá phần domain này trước khi nạp
"""

import argparse
import json
import os
import pickle
from pathlib import Path

from neo4j import GraphDatabase

SCHEMA_FILE = Path(__file__).with_name("schema.cypher")
BATCH = 1000

UPSERT_EVENTS = """
UNWIND $rows AS r
MERGE (e:Event {id: r.id}) SET e.domain = r.domain
"""
UPSERT_COMMENTS = """
UNWIND $rows AS r
MERGE (c:Comment {uid: r.uid})
SET c += r.props
WITH c, r
MATCH (e:Event {id: r.event_id})
MERGE (c)-[:IN_EVENT]->(e)
MERGE (l:Label {key: r.label_key})
  ON CREATE SET l.name = r.props.label, l.domain = r.domain
MERGE (c)-[:HAS_LABEL]->(l)
"""
UPSERT_REPLIES = """
UNWIND $rows AS r
MATCH (c:Comment {uid: r.child}), (p:Comment {uid: r.parent})
MERGE (c)-[:REPLY_TO]->(p)
"""


def connect():
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise SystemExit("Thiếu biến môi trường NEO4J_PASSWORD")
    return GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.environ.get("NEO4J_USER", "neo4j"), pw),
    )


def init_schema(session):
    text = "\n".join(l for l in SCHEMA_FILE.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("//"))
    for stmt in filter(None, (s.strip() for s in text.split(";"))):
        session.run(stmt)


def build_rows(graphs, domain, predictions=None):
    """Chuyển graphs.pkl thành các dòng nạp. predictions: list theo thứ tự nút toàn cục."""
    events, comments, replies = [], [], []
    k = 0  # chỉ số nút toàn cục (khớp thứ tự predictions)
    for g in graphs:
        ev = g["event_id"]
        events.append({"id": ev, "domain": domain})
        uids = [f"{ev}::{n}" for n in g["node_ids"]]
        for i, uid in enumerate(uids):
            props = {
                "uid": uid, "comment_id": g["node_ids"][i], "event_id": ev,
                "text": g["texts"][i], "label": g["labels"][i],
                "depth": g["structural"]["depth"][i],
                "in_degree": g["structural"]["in_degree"][i],
                "sibling_count": g["structural"]["sibling_count"][i],
            }
            if predictions is not None:
                p = predictions[k]
                props.update(pred_label=p["pred_label_name"],
                             pred_conf=round(p["confidence"], 4), split=p["split"])
            comments.append({"uid": uid, "event_id": ev, "domain": domain,
                             "label_key": f"{domain}::{g['labels'][i]}", "props": props})
            k += 1
        for src, dst in g["edges"]:
            replies.append({"child": uids[src], "parent": uids[dst]})
    n_dup = len(comments) - len({c["uid"] for c in comments})
    if n_dup:
        print(f"[{domain}] CẢNH BÁO: {n_dup} bình luận trùng (event_id, comment_id), "
              "bản sau ghi đè bản trước trong Neo4j")
    return events, comments, replies


def run_batches(session, query, rows):
    for i in range(0, len(rows), BATCH):
        session.run(query, rows=rows[i:i + BATCH]).consume()


def load_domain(driver, domain, predictions_path=None, wipe=False, data_dir="data/gnn"):
    with open(Path(data_dir) / f"graphs_{domain}.pkl", "rb") as fh:
        graphs = pickle.load(fh)
    preds = None
    if predictions_path:
        with open(predictions_path, encoding="utf-8") as fh:
            preds = json.load(fh)
        n_nodes = sum(g["n_nodes"] for g in graphs)
        if len(preds) != n_nodes:
            raise SystemExit(f"predictions có {len(preds)} dòng, graph có {n_nodes} nút")
    events, comments, replies = build_rows(graphs, domain, preds)
    with driver.session() as s:
        if wipe:
            s.run("MATCH (e:Event {domain: $d}) OPTIONAL MATCH (c:Comment)-[:IN_EVENT]->(e) "
                  "DETACH DELETE c, e", d=domain).consume()
            s.run("MATCH (l:Label {domain: $d}) DETACH DELETE l", d=domain).consume()
        run_batches(s, UPSERT_EVENTS, events)
        run_batches(s, UPSERT_COMMENTS, comments)
        run_batches(s, UPSERT_REPLIES, replies)
    print(f"[{domain}] nạp {len(events)} sự kiện, {len(comments)} bình luận, {len(replies)} cạnh REPLY_TO")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    ap.add_argument("--predictions", help="predictions_{domain}.json (chỉ dùng khi nạp 1 domain)")
    ap.add_argument("--init-schema", action="store_true")
    ap.add_argument("--wipe-domain", action="store_true")
    ap.add_argument("--data-dir", default="data/gnn", help="thư mục chứa graphs_{domain}.pkl")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    if args.predictions and len(domains) != 1:
        raise SystemExit("--predictions chỉ dùng với một --domain")
    driver = connect()
    try:
        if args.init_schema:
            with driver.session() as s:
                init_schema(s)
            print("schema OK")
        for d in domains:
            load_domain(driver, d, args.predictions, args.wipe_domain, args.data_dir)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
