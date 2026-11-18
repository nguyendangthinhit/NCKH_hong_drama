import assert from 'node:assert/strict';
import { after, afterEach, before, test } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const originalFetch = globalThis.fetch;
let server;
let api;

before(async () => {
  server = await createServer({ root, logLevel: 'error', appType: 'custom',
    cacheDir: path.join(root, 'node_modules/.vite-latest-events-tests'),
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] } });
  api = await server.ssrLoadModule('/src/services/latest-events-api.js');
});
afterEach(() => { globalThis.fetch = originalFetch; });
after(async () => { await server?.close(); });

const rows = [
  ['old-hot', '2024-03-23', 99999],
  ['unknown-date', '', 88888],
  ['invalid', '2026-02-30', 77777],
  ['fb-newer', '2027-01-01', 66666, 'facebook'],
  ['unpadded', '2025-07-6', 55555],
  ['full-day', '2025-07-19', 44444],
  ['partial-month', '2026-01', 33333],
  ['partial-day', '2025-07-xx', 22222],
  ['newest-news-low-engagement', '2026-03-23', 0],
  ['tied-b', '2026-03-21', 200],
  ['tied-a', '2026-03-21', 1],
  ['tiktok-newer', '2028-01-15', 0, 'tiktok'],
  ['future-platform', '2029-01-15', 0, 'new-platform'],
].map(([id, date, comments, platform = 'news']) => ({
  id_content: id, time_event: date, total_comments: comments, platform,
}));
const response = (data, page = 1, totalPages = 1) => ({
  ok: true, json: async () => ({ data, page, total_pages: totalPages }),
});

test('latest events include all platforms/pages, sorted before limiting and independent of comments', async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    const params = new URL(url).searchParams;
    calls.push(params);
    return response(params.get('page') === '1' ? rows.slice(0, 6) : rows.slice(6), Number(params.get('page')), 2);
  };
  const latest = await api.getLatestEvents(6);
  assert.deepEqual(latest.map((event) => event.id), [
    'future-platform', 'tiktok-newer', 'fb-newer', 'newest-news-low-engagement', 'tied-a', 'tied-b',
  ]);
  assert.equal(calls.length, 2);
  assert.ok(calls.every((params) => !params.has('platform')));
  const all = await api.getLatestEvents();
  assert.equal(all.length, rows.length);
  const position = (id) => all.findIndex((event) => event.id === id);
  assert.ok(position('partial-month') > position('newest-news-low-engagement'));
  assert.ok(position('partial-day') > position('unpadded'));
  assert.ok(position('full-day') < position('unpadded'));
  assert.ok(position('unknown-date') > position('old-hot'));
  assert.ok(position('invalid') > position('old-hot'));
});

test('a later-page failure rejects the entire newest list rather than returning incomplete results', async () => {
  globalThis.fetch = async (url) => new URL(url).searchParams.get('page') === '1'
    ? response(rows.slice(0, 6), 1, 2) : { ok: false, status: 503 };
  await assert.rejects(api.getLatestEvents(), /API 503/);
});

test('latest events forward cancellation to the active request', async () => {
  const controller = new AbortController();
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.signal, controller.signal);
    return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }));
  };
  const pending = api.getLatestEvents(6, { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
});

test('empty datasets stay empty and duplicate IDs across API pages render once', async () => {
  globalThis.fetch = async () => response([]);
  assert.deepEqual(await api.getLatestEvents(), []);
  globalThis.fetch = async () => response([rows[0], rows[0], rows[3]]);
  assert.deepEqual((await api.getLatestEvents()).map((event) => event.id), ['fb-newer', 'old-hot']);
});
