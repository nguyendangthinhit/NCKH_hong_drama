// Cắt lát dữ liệu thống kê (insights.json, analyzed của sự kiện) làm ngữ cảnh cho LLM. Port của insight_context.py.
import { AgentEvent, INSIGHTS } from "./event-store";

const CATEGORY_LABEL: Record<string, string> = { education: "Giáo dục", showbiz: "Showbiz" };
type Category = "education" | "showbiz" | null;
const cats = (c: Category): string[] => (c ? [c] : ["education", "showbiz"]);

/** Danh sách sự kiện nhiều bình luận nhất của một hoặc cả hai lĩnh vực. */
export function topEventsText(category: Category, limit = 5): string {
  const lines: string[] = [];
  for (const cat of cats(category)) {
    const items: any[] = (INSIGHTS[cat]?.top_events_by_comments ?? []).slice(0, limit);
    lines.push(`Top sự kiện ${CATEGORY_LABEL[cat]} theo số bình luận:`);
    items.forEach((ev, i) =>
      lines.push(
        `${i + 1}. ${ev.ten_su_kien ?? ""} (tổng ${ev.total ?? 0} bình luận, ` +
          `${ev.clean ?? 0} hợp lệ, ${ev.trash ?? 0} rác)`,
      ),
    );
  }
  return lines.join("\n");
}

/** Số liệu tổng quan toàn hệ thống hoặc của một lĩnh vực. */
export function statsText(category: Category): string {
  const parts = [`Tổng quan hệ thống: ${JSON.stringify(INSIGHTS.overall ?? {})}`];
  for (const cat of cats(category)) {
    const block = Object.fromEntries(
      Object.entries(INSIGHTS[cat] ?? {}).filter(([k]) => k !== "top_events_by_comments" && k !== "category"),
    );
    parts.push(`${CATEGORY_LABEL[cat]}: ${JSON.stringify(block)}`);
  }
  return parts.join("\n");
}

/** Nội dung một sự kiện; kèm thống kê bình luận nếu câu hỏi về dư luận. */
export function eventText(event: AgentEvent, withStats: boolean): string {
  const actors = event.actors.map((a) => `${a.name ?? ""} (${a.role ?? ""})`).join(", ");
  const lines = [
    `[${CATEGORY_LABEL[event.category] ?? event.category}] ${event.title}`,
    `Thời điểm: ${event.time_event || "không rõ"}`,
  ];
  if (actors) lines.push(`Nhân vật: ${actors}`);
  lines.push(`Nội dung: ${event.content}`);
  if (withStats && Object.keys(event.analyzed).length) {
    lines.push("Thống kê bình luận dư luận: " + JSON.stringify(event.analyzed));
  }
  return lines.join("\n");
}
