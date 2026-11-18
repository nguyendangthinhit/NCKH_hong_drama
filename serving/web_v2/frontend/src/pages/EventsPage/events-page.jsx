import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { HomeOutlined, SearchOutlined } from '@ant-design/icons';
import useLatestEvents from '../../hooks/use-latest-events';
import useEventFilters from '../../hooks/use-event-filters';
import { getEventSource } from '../../utils/event-sources';
import PostCard from '../../components/PostCard/PostCard';
import Pagination from '../../components/Pagination/Pagination';
import styles from './events-page.module.scss';

const PER_PAGE = 12;
const searchText = (value) => String(value || '').normalize('NFC').toLocaleLowerCase('vi-VN');

export default function EventsPage() {
  const { events, loading, failed, reload } = useLatestEvents();
  const { query, filterQuery, pendingQuery, source, pageParam, updateQuery, startComposition,
    endComposition, commitQuery, changeSource, changePage, clearFilters } = useEventFilters();
  const requested = Number(pageParam || 1);
  const requestedPage = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;

  const sources = useMemo(() => {
    const options = new Map();
    events.forEach((event) => {
      const entry = getEventSource(event.platform);
      options.set(entry.key, entry);
    });
    return [...options.values()].sort((left, right) => left.label.localeCompare(right.label, 'vi'));
  }, [events]);

  const filtered = useMemo(() => {
    const keyword = searchText(filterQuery.trim());
    return events.filter((event) => {
      const eventSource = getEventSource(event.platform);
      if (source && eventSource.key !== source) return false;
      return !keyword || [event.title, event.category, eventSource.label]
        .some((value) => searchText(value).includes(keyword));
    });
  }, [events, filterQuery, source]);

  const totalPages = Math.ceil(filtered.length / PER_PAGE);
  const page = Math.min(requestedPage, Math.max(1, totalPages));
  const visibleEvents = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [page]);

  // Keep shared URLs accurate when a refresh removes events or a page is invalid.
  useEffect(() => {
    if (loading || failed || pendingQuery) return;
    const targetPage = page > 1 ? String(page) : null;
    if (pageParam !== targetPage) changePage(page, { replace: true });
  }, [page, loading, failed, pendingQuery, pageParam, changePage]);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <nav className={styles.breadcrumb} aria-label="Đường dẫn trang">
          <Link to="/"><HomeOutlined /> Trang chủ</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Tất cả sự kiện</span>
        </nav>

        <header className={styles.heading}>
          <span className={styles.eyebrow}>Khám phá thông tin</span>
          <h1>Tất cả sự kiện</h1>
          <p>Tổng hợp sự kiện từ các nguồn dữ liệu, sắp xếp theo thời gian mới nhất.</p>
        </header>

        <section className={styles.toolbar} aria-label="Tìm kiếm và lọc sự kiện">
          <div className={styles.search}>
            <label htmlFor="events-query">Tìm kiếm sự kiện</label>
            <div className={styles.searchInput}>
              <SearchOutlined aria-hidden="true" />
              <input
                id="events-query"
                type="search"
                placeholder="Tiêu đề, chủ đề hoặc nguồn..."
                value={query}
                onChange={(event) => updateQuery(event.target.value)}
                onCompositionStart={startComposition}
                onCompositionEnd={endComposition}
                onBlur={commitQuery}
              />
            </div>
          </div>
          <div className={styles.sourceFilter}>
            <label htmlFor="events-source">Nguồn dữ liệu</label>
            <select id="events-source" value={source} onChange={(event) => changeSource(event.target.value)}>
              <option value="">Tất cả nguồn</option>
              {source && !sources.some((entry) => entry.key === source) && (
                <option value={source}>Nguồn: {source}</option>
              )}
              {sources.map((entry) => <option key={entry.key} value={entry.key}>{entry.label}</option>)}
            </select>
          </div>
          <button className={`${styles.clear} ${!query && !source ? styles.clearHidden : ''}`} type="button" onClick={clearFilters} disabled={!query && !source}>Xóa bộ lọc</button>
        </section>

        <div className={styles.results} aria-live="polite" aria-atomic="true">
          {!loading && !failed && <p><strong>{filtered.length.toLocaleString('vi-VN')}</strong> sự kiện{query || source ? ` / ${events.length.toLocaleString('vi-VN')} sự kiện` : ''}</p>}
          {!loading && !failed && filtered.length > 0 && <span>Trang {page} / {totalPages} · Mới nhất trước</span>}
        </div>

        {loading ? (
          <div className={styles.notice} role="status">Đang tải danh sách sự kiện…</div>
        ) : failed ? (
          <section className={styles.notice} role="alert">
            <h2>Chưa tải được sự kiện</h2>
            <p>Không thể lấy danh sách từ máy chủ. Vui lòng thử lại.</p>
            <button className={styles.retry} type="button" onClick={reload}>Thử lại</button>
          </section>
        ) : filtered.length === 0 ? (
          <section className={styles.notice} role="status">
            <h2>{query || source ? 'Không tìm thấy sự kiện phù hợp' : 'Chưa có sự kiện'}</h2>
            <p>{query || source ? 'Thử từ khóa khác hoặc bỏ bộ lọc nguồn dữ liệu.' : 'Danh sách sẽ xuất hiện khi có dữ liệu sự kiện.'}</p>
            {(query || source) && <button className={styles.retry} type="button" onClick={clearFilters}>Xem tất cả sự kiện</button>}
          </section>
        ) : (
          <>
            <div className={styles.grid}>
              {visibleEvents.map((event) => (
                <PostCard key={event.id} post={event} sourceAware showImage showDate showHotBadge={false} maxLinks={3} />
              ))}
            </div>
            <Pagination page={page} totalPages={totalPages} onPageChange={changePage} />
          </>
        )}
      </div>
    </main>
  );
}
