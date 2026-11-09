import assert from 'node:assert/strict';
import { after, afterEach, before, test } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const originalFetch = globalThis.fetch;
let server;
let api;
const rows = [
  { id_content: 'n1', platform: 'news' },
  { id_content: 'n2', platform: 'news' },
  { id_content: 'f1', platform: 'facebook' },
  { id_content: 'f2', platform: 'facebook' },
  { id_content: 'f3', platform: 'facebook' },
  { id_content: 't1', platform: 'tiktok' },
];

before(async () => {
  server = await createServer({ root, logLevel: 'error', appType: 'custom',
    cacheDir: path.join(root, 'node_modules/.vite-platform-filter-tests'),
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] } });
  api = await server.ssrLoadModule('/src/services/api.js');
});
afterEach(() => { globalThis.fetch = originalFetch; });
after(async () => { await server?.close(); });

function mockServer(checkOptions = () => {}) {
  globalThis.fetch = async (url, options) => {
    checkOptions(options);
    const params = new URL(url).searchParams;
    const filtered = rows.filter((row) => !params.get('platform') || row.platform === params.get('platform'));
    const page = Number(params.get('page') || 1);
    const perPage = Number(params.get('per_page') || 12);
    return { ok: true, json: async () => ({
      data: filtered.slice((page - 1) * perPage, page * perPage),
      total: filtered.length, page, total_pages: Math.ceil(filtered.length / perPage),
    }) };
  };
}

test('Facebook/news pagination requests the platform before page/count are calculated', async () => {
  mockServer();
  const first = await api.getPaginatedPosts('facebook', 1, 2);
  const second = await api.getPaginatedPosts('facebook', 2, 2);
  const news = await api.getPaginatedPosts('news', 1, 2);
  assert.deepEqual(first.data.map((post) => post.id), ['f1', 'f2']);
  assert.deepEqual(second.data.map((post) => post.id), ['f3']);
  assert.equal(first.total, 3);
  assert.equal(first.totalPages, 2);
  assert.deepEqual(news.data.map((post) => post.id), ['n1', 'n2']);
  assert.equal(news.total, 2);
});

test('null keeps all-source requests, including new platforms, and empty filters stay empty', async () => {
  mockServer();
  const all = await api.getPaginatedPosts(null, 1, 200);
  assert.equal(all.total, 6);
  assert.ok(all.data.some((post) => post.platform === 'tiktok'));
  const missing = await api.getPaginatedPosts('missing', 1, 12);
  assert.equal(missing.total, 0);
  assert.equal(missing.totalPages, 0);
  assert.deepEqual(missing.data, []);
});

test('homepage platform previews filter before limiting and normalize source input', async () => {
  mockServer();
  const facebook = await api.getLatestPostsByPlatform(' Facebook ', 1);
  const news = await api.getLatestPostsByPlatform('news', 1);
  assert.deepEqual(facebook.map((post) => post.id), ['f1']);
  assert.deepEqual(news.map((post) => post.id), ['n1']);
});

test('pagination continues forwarding cancellation options', async () => {
  const controller = new AbortController();
  mockServer((options) => assert.equal(options.signal, controller.signal));
  await api.getPaginatedPosts('facebook', 1, 2, { signal: controller.signal });
});
