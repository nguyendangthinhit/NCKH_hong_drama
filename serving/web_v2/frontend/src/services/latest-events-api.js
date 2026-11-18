import { getPaginatedPosts } from './api';

function eventDateKey(value) {
  const match = /^(\d{4})-(\d{1,2})(?:-(\d{1,2}|xx))?$/i.exec(String(value || '').trim());
  if (!match) return 0;
  const year = Number(match[1]);
  const month = Number(match[2]);
  // Month-only dates precede known days in that month, without inventing a day.
  const day = match[3] && match[3].toLowerCase() !== 'xx' ? Number(match[3]) : 0;
  if (year < 1 || month < 1 || month > 12) return 0;
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day > lastDay || (match[3] !== undefined && match[3].toLowerCase() !== 'xx' && day < 1)) return 0;
  return year * 10000 + month * 100 + day;
}

export async function getLatestEvents(limit, options) {
  // Load every source/page before sorting: the endpoint's default comment rank
  // must not hide recent low-engagement events or future platforms.
  const first = await getPaginatedPosts(null, 1, 200, options);
  const posts = [...first.data];
  for (let page = 2; page <= first.totalPages; page += 1) {
    const next = await getPaginatedPosts(null, page, 200, options);
    posts.push(...next.data);
  }
  const sorted = [...new Map(posts.map((post) => [post.id, post])).values()]
    .sort((a, b) => eventDateKey(b.timeEvent) - eventDateKey(a.timeEvent) || String(a.id).localeCompare(String(b.id)));
  return limit == null ? sorted : sorted.slice(0, limit);
}
