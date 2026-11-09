import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { MemoryRouter } = require('react-router-dom');
let server;
const components = {};
const render = (Component, props = {}, route = '/') => renderToStaticMarkup(
  React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(Component, props)),
);
const anchors = (html) => [...html.matchAll(/<a\b([^>]*)>[\s\S]*?<\/a>/g)].map((match) => match[0]);
const hrefs = (html) => [...html.matchAll(/href="([^"]*)"/g)].map((match) => match[1].replaceAll('&amp;', '&'));
const eventPath = (id) => `/events/${encodeURIComponent(id)}`;
const post = (id) => ({
  id, title: `Sự kiện ${id}`, category: 'Giải trí', description: 'Thông tin tóm tắt từ dữ liệu thử nghiệm.',
  imageUrl: 'https://images.example.com/event.jpg', totalComments: 12, isHot: true, status: 'done', timeEvent: '2026-03-23',
  links: [1, 2, 3, 4].map((index) => `https://source.example.com/${id}/${index}`),
});
const facebook = Array.from({ length: 5 }, (_, index) => post(`showbiz_fb${index + 1}`));
const news = Array.from({ length: 6 }, (_, index) => post(`education_news${index + 1}`));

before(async () => {
  server = await createServer({ root, logLevel: 'error', appType: 'custom',
    // Keep the test optimizer separate from the running development server.
    cacheDir: path.join(root, 'node_modules/.vite-redesign-tests'),
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] } });
  for (const [name, file] of Object.entries({
    Header: 'Header/Header', Footer: 'Footer/Footer', Card: 'PostCard/PostCard', Pagination: 'Pagination/Pagination',
    Featured: 'home/featured-events', Sidebar: 'home/home-sidebar', Rail: 'home/latest-events-rail',
  })) components[name] = (await server.ssrLoadModule(`/src/components/${file}.jsx`)).default;
});
after(async () => { await server?.close(); });

test('footer keeps the original information, platform, social and legal links', () => {
  const html = render(components.Footer);
  const links = hrefs(html);
  assert.ok(html.includes('<footer'));
  for (const heading of ['Thông tin', 'Nền tảng', 'NCKH']) assert.ok(html.includes(heading));
  for (const link of ['/', '/about', '/contact', '/privacy', '/terms', '/facebook', '/news', '/search', 'https://facebook.com', 'https://youtube.com']) {
    assert.ok(links.includes(link), link);
  }
  assert.equal(links.filter((link) => link === '/privacy').length, 2);
  assert.equal(links.filter((link) => link === '/terms').length, 2);
});

test('header preserves both category menus, route links and existing controls', () => {
  const html = render(components.Header, {}, '/news?cat=Giáo dục');
  const links = hrefs(html);
  for (const link of ['/', '/facebook', '/news', '/facebook?cat=Giải trí', '/facebook?cat=Giáo dục', '/news?cat=Giải trí', '/news?cat=Giáo dục']) {
    assert.ok(links.includes(link), link);
  }
  assert.ok(html.includes('aria-label="Tìm kiếm sự kiện"'));
  assert.ok(html.includes('type="submit"'));
  assert.ok(html.includes('aria-label="Thông báo"'));
  assert.ok(html.includes('Đăng nhập'));
  assert.ok(html.includes('aria-controls="header-dropdown-facebook"'));
  assert.ok(html.includes('aria-controls="header-dropdown-news"'));
});

for (const layout of ['card', 'row', 'rail', 'reference']) {
  test(`${layout} cards keep detail navigation and explicit source actions`, () => {
    const item = post('showbiz_demo / 1');
    const html = render(components.Card, { post: item, variant: 'facebook', layout, showImage: true, rank: 2, maxLinks: 3 }, '/facebook?cat=Giải trí');
    const links = hrefs(html);
    assert.equal(links.filter((link) => link === eventPath(item.id)).length, 3);
    assert.ok(html.includes('Xem chi tiết'));
    assert.ok(html.includes('#2'));
    assert.ok(html.includes('Facebook'));
    assert.ok(html.includes('+1 nguồn khác'));
    for (const source of item.links.slice(0, 3)) {
      const anchor = anchors(html).find((value) => value.includes(`href="${source}"`));
      assert.ok(anchor?.includes('target="_blank"'), source);
      assert.ok(anchor.includes('rel="noopener noreferrer"'), source);
    }
    assert.ok(!links.includes(item.links[3]));
  });
}

test('featured grid exposes four stories with one lead and supports loading/empty', () => {
  const html = render(components.Featured, { posts: news, loading: false });
  assert.equal((html.match(/<article\b/g) || []).length, 4);
  assert.equal((html.match(/Tiêu điểm/g) || []).length, 1);
  for (const item of news.slice(0, 4)) assert.ok(hrefs(html).includes(eventPath(item.id)));
  assert.ok(!hrefs(html).includes(eventPath(news[4].id)));
  const loading = render(components.Featured, { posts: [], loading: true });
  assert.ok(loading.includes('aria-busy="true"'));
  assert.equal(hrefs(loading).length, 0);
  const empty = render(components.Featured, { posts: [], loading: false });
  assert.ok(empty.includes('Chưa có sự kiện'));
});

test('sidebar retains all five Facebook events and sources alongside upcoming community channels', () => {
  const html = render(components.Sidebar, { posts: facebook, news, loading: false });
  const links = hrefs(html);
  for (const item of facebook) {
    assert.ok(links.includes(eventPath(item.id)), item.id);
    for (const source of item.links.slice(0, 3)) assert.ok(links.includes(source), source);
  }
  assert.ok(links.includes('/facebook'));
  assert.ok(html.includes('Theo dõi hội hóng biến'));
  assert.ok(!html.includes('Khám phá cùng Hóng'));
  for (const label of ['Facebook', 'TikTok', 'Threads']) assert.ok(html.includes(label));
  assert.equal((html.match(/disabled=""/g) || []).length, 2);
  assert.equal((html.match(/Sắp ra mắt<\/span>/g) || []).length, 2);
  const fanpage = anchors(html).find((anchor) => anchor.includes('https://www.facebook.com/profile.php?id=61579650250828'));
  assert.ok(fanpage?.includes('target="_blank"'));
  assert.ok(fanpage.includes('rel="noopener noreferrer"'));
  assert.ok(!links.includes('#'));
  for (const fake of ['2.4M', '5.1M', '850K', 'REAL-TIME', 'người đang hóng', 'lượt xem']) assert.ok(!html.includes(fake), fake);
  assert.ok(render(components.Sidebar, { posts: [], news: [], loading: true }).includes('Đang tải tin Facebook'));
  assert.ok(render(components.Sidebar, { posts: [], news: [], loading: false }).includes('Chưa có sự kiện Facebook'));
});

test('latest events rail keeps detail/source links and opens the all-sources page', () => {
  const html = render(components.Rail, { posts: news, loading: false });
  const links = hrefs(html);
  assert.ok(links.includes('/events'));
  assert.ok(!links.includes('/news'));
  assert.ok(html.includes('Sự kiện mới nhất'));
  assert.ok(!html.includes('Tin tức nổi bật'));
  assert.ok(!html.includes('HOT'));
  assert.equal((html.match(/Ngày sự kiện:/g) || []).length, 6);
  for (const item of news) {
    assert.equal(links.filter((link) => link === eventPath(item.id)).length, 3, item.id);
    for (const source of item.links.slice(0, 3)) assert.ok(links.includes(source));
  }
  assert.ok(html.includes('aria-label="Cuộn sự kiện về trước"'));
  assert.ok(html.includes('aria-label="Cuộn sự kiện về sau"'));
  assert.ok(html.includes('tabindex="0"'));
  const loading = render(components.Rail, { posts: [], loading: true });
  assert.ok(loading.includes('Đang tải sự kiện'));
  assert.equal((loading.match(/disabled=""/g) || []).length, 2);
  assert.ok(render(components.Rail, { posts: [], loading: false }).includes('Chưa có sự kiện'));
  const failed = render(components.Rail, { posts: [], loading: false, failed: true });
  assert.ok(failed.includes('role="alert"'));
  assert.ok(failed.includes('Chưa tải được sự kiện mới nhất'));
});

for (const [platform, label] of [['facebook', 'Facebook'], ['tiktok', 'TikTok'], ['FutureSource', 'FutureSource'], ['constructor', 'constructor'], ['__proto__', '__proto__'], [undefined, 'Chưa rõ nguồn']]) {
  test(`source-aware cards display ${label} without labeling it as news`, () => {
    const html = render(components.Card, { post: { ...post('mixed'), platform }, sourceAware: true });
    assert.ok(html.includes(label));
    assert.ok(!html.includes('Tin tức'));
  });
}

function buttons(element) {
  if (!React.isValidElement(element)) return [];
  if (element.type === 'button') return [element];
  return React.Children.toArray(element.props.children).flatMap(buttons);
}

test('pagination callbacks and disabled boundaries remain unchanged', () => {
  assert.equal(components.Pagination({ page: 1, totalPages: 1, onPageChange() {} }), null);
  const chosen = [];
  const middle = buttons(components.Pagination({ page: 3, totalPages: 6, onPageChange: (page) => chosen.push(page) }));
  middle.find((button) => button.props['aria-label'] === 'Trang trước').props.onClick();
  middle.find((button) => button.props['aria-label'] === 'Trang sau').props.onClick();
  middle.find((button) => button.props['aria-label'] === 'Trang 6').props.onClick();
  assert.deepEqual(chosen, [2, 4, 6]);
  assert.equal(middle.find((button) => button.props['aria-label'] === 'Trang 3').props['aria-current'], 'page');
  for (const [page, label] of [[1, 'Trang trước'], [6, 'Trang sau']]) {
    const edge = buttons(components.Pagination({ page, totalPages: 6, onPageChange() {} }));
    assert.equal(edge.find((button) => button.props['aria-label'] === label).props.disabled, true);
  }
});
