import assert from 'node:assert/strict';
import { after, afterEach, before, test } from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const originalFetch = globalThis.fetch;
let server;
let normalize;
let api;
let Content;

const education = {
  id_content: 'education_test',
  comment_counts: { total: 10, 'tích_cực': 3, 'tiêu_cực': 3, 'trung_lập': 1, 'ý_kiến_riêng': 1, 'rác': 2 },
  analysis: {
    'tích cực': { count: 3, summary: 'Diễn giải nhóm tích cực.', examples: ['Một bình luận minh họa.'] },
    'tiêu cực': { count: 3, summary: '', examples: ['Một ý kiến khác.'] },
  },
  conclusion: { focus: '', trend: '' },
};
const showbiz = {
  id_content: 'showbiz_test',
  total_comments: 469,
  emotion_stats: { 'Phẫn nộ': 400, 'Trung lập': 67 },
  top_comments: {
    by_emotion: { 'Phẫn nộ': { comment_id: 'c1', text: 'Bình luận được chọn.', score: 5 } },
    most_popular: [
      { comment_id: 'c1', text: 'Bình luận được chọn.', emotion: 'Phẫn nộ', likes: 4 },
      { comment_id: 'c2', text: 'Bình luận thứ hai.', emotion: 'Trung lập', likes: 0, reply_count: 0 },
    ],
  },
};

before(async () => {
  server = await createServer({ root, logLevel: 'error', appType: 'custom',
    // Keep the test optimizer separate from the running development server.
    cacheDir: path.join(root, 'node_modules/.vite-event-analysis-tests'),
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] } });
  ({ normalizeEventAnalysis: normalize } = await server.ssrLoadModule('/src/utils/normalize-event-analysis.js'));
  api = await server.ssrLoadModule('/src/services/event-analysis-api.js');
  ({ default: Content } = await server.ssrLoadModule('/src/components/Event_analysis/event-analysis-content.jsx'));
});
afterEach(() => { globalThis.fetch = originalFetch; });
after(async () => { await server?.close(); });

test('education excludes trash from percentages and keeps examples without narrative', () => {
  const data = normalize(education, education.id_content, 'education');
  assert.equal(data.validCount, 8);
  assert.equal(data.trashCount, 2);
  assert.equal(data.groups.find((group) => group.key === 'tích cực').percent, 37.5);
  assert.equal(data.comments.length, 2);
  assert.ok(data.comments.some((comment) => comment.key === 'tiêu cực'));
  assert.equal(data.conclusion.focus, '');
});

test('showbiz count gap becomes unclassified and selected comments are deduplicated', () => {
  const data = normalize(showbiz, showbiz.id_content, 'showbiz');
  assert.equal(data.classifiedCount, 467);
  assert.equal(data.unclassifiedCount, 2);
  assert.equal(data.trashCount, null);
  assert.equal(data.groups.reduce((sum, group) => sum + group.count, 0), 469);
  assert.equal(data.comments.length, 2);
  assert.equal(data.comments[1].likes, 0);
});

test('unknown labels and Unicode variants remain distinct from neutral', () => {
  const raw = structuredClone(education);
  raw.comment_counts.total = 12;
  raw.comment_counts['Góc nhìn mới'] = 2;
  raw.comment_counts['tích_cực'.normalize('NFD')] = raw.comment_counts['tích_cực'];
  delete raw.comment_counts['tích_cực'];
  const data = normalize(raw, raw.id_content, 'education');
  assert.equal(data.groups.find((group) => group.key === 'tích cực').count, 3);
  assert.equal(data.groups.find((group) => group.key === 'góc nhìn mới').count, 2);
});

test('wrong event, negative count and contradictory totals are rejected', () => {
  assert.throws(() => normalize(education, 'education_other', 'education'));
  assert.throws(() => normalize({ ...showbiz, emotion_stats: { bad: -1 } }, showbiz.id_content, 'showbiz'));
  assert.throws(() => normalize({ ...showbiz, total_comments: 10 }, showbiz.id_content, 'showbiz'));
  const zero = normalize({ ...showbiz, total_comments: 0, emotion_stats: {} }, showbiz.id_content, 'showbiz');
  assert.equal(zero.validCount, 0);
  assert.equal(zero.groups.length, 0);
});

test('Unicode and case variants of total/trash metadata keep the correct denominator', () => {
  const raw = structuredClone(education);
  raw.comment_counts['rác'.normalize('NFD')] = raw.comment_counts['rác'];
  delete raw.comment_counts['rác'];
  raw.comment_counts[' TOTAL '] = raw.comment_counts.total;
  delete raw.comment_counts.total;
  const data = normalize(raw, raw.id_content, 'education');
  assert.equal(data.collectedCount, 10);
  assert.equal(data.trashCount, 2);
  assert.equal(data.validCount, 8);
  assert.equal(data.unclassifiedCount, 0);
});

test('all repository summaries match their event and have consistent rendered totals', () => {
  const base = path.resolve(root, '../../../data/processed');
  let checked = 0;
  for (const [domain, folder] of [['education', 'process_education/analyzed_dataa'], ['showbiz', 'process_showbiz/analyzed_data']]) {
    const dir = path.join(base, folder, 'summary');
    for (const file of fs.readdirSync(dir).filter((name) => name.endsWith('.json'))) {
      const id = file.slice(0, -5);
      const data = normalize(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')), id, domain);
      assert.equal(data.groups.reduce((sum, group) => sum + group.count, 0), data.validCount, id);
      if (data.validCount > 0) assert.ok(Math.abs(data.groups.reduce((sum, group) => sum + group.percent, 0) - 100) < 0.00001, id);
      assert.ok(data.comments.length <= 12, id);
      checked += 1;
    }
  }
  assert.ok(checked > 0);
});

test('service selects source, checks identity and treats 404 separately from other failures', async () => {
  let requested;
  globalThis.fetch = async (url) => { requested = url; return { ok: true, status: 200, json: async () => education }; };
  const data = await api.getEventAnalysis(education.id_content);
  assert.ok(requested.endsWith('/processed/process_education/analyzed_dataa/summary/education_test.json'));
  assert.equal(data.eventId, education.id_content);
  assert.ok(api.getEventAnalysisSource('showbiz_test').url.includes('/process_showbiz/analyzed_data/'));
  assert.equal(await api.getEventAnalysis('../unknown'), null);
  await assert.rejects(api.getEventAnalysis('education_other'));
  globalThis.fetch = async () => ({ ok: false, status: 404 });
  assert.equal(await api.getEventAnalysis('education_missing'), null);
  globalThis.fetch = async () => ({ ok: false, status: 503 });
  await assert.rejects(api.getEventAnalysis('education_test'));
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('invalid JSON'); } });
  await assert.rejects(api.getEventAnalysis('education_test'));
});

test('service aborts an outstanding fetch when its caller leaves the event', async () => {
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  });
  const controller = new AbortController();
  const pending = api.getEventAnalysis('education_test', { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, (error) => error.name === 'AbortError');
});

test('service ends a slow request with a timeout error', async (context) => {
  let expire;
  context.mock.method(globalThis, 'setTimeout', (callback) => { expire = callback; return 1; });
  context.mock.method(globalThis, 'clearTimeout', () => {});
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  });
  const pending = api.getEventAnalysis('education_test');
  expire();
  await assert.rejects(pending, /Quá thời gian/);
});

test('rendered analysis keeps table and narratives without illustrative comments', () => {
  const data = { ...normalize(education, education.id_content, 'education'), sourceUrl: 'https://example.com/summary.json' };
  data.groups[0].summary = '<script>bad</script>';
  const html = renderToStaticMarkup(React.createElement(Content, { data }));
  assert.ok(html.includes('<table'));
  assert.ok(html.includes('37,5%'));
  assert.ok(!html.includes('Bình luận minh họa'));
  assert.ok(!html.includes('Một ý kiến khác.'));
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'));
  assert.ok(!html.includes('Kết quả phân tích đã lưu'));
  assert.ok(!html.includes('Xem dữ liệu'));
  assert.ok(!html.includes(data.sourceUrl));
  assert.ok(!html.includes('Nhận định từ dữ liệu phân tích'));
  const zero = { ...normalize({ ...showbiz, total_comments: 0, emotion_stats: {}, top_comments: {} }, showbiz.id_content, 'showbiz'), sourceUrl: data.sourceUrl };
  const empty = renderToStaticMarkup(React.createElement(Content, { data: zero }));
  assert.ok(empty.includes('Chưa có bình luận hợp lệ'));
  assert.ok(!empty.includes('Bình luận minh họa'));
});
