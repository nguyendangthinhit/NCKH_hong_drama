import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import PostCard from '../PostCard/PostCard';
import styles from './latest-events-rail.module.scss';

export default function LatestEventsRail({ posts, loading, failed = false }) {
  const rail = useRef(null);
  const scroll = (direction) => {
    const element = rail.current;
    if (!element) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    element.scrollBy({ left: direction * Math.max(260, element.clientWidth * 0.8), behavior: reduceMotion ? 'auto' : 'smooth' });
  };
  return (
    <section className={styles.panel} aria-labelledby="latest-events-heading">
      <div className={styles.header}>
        <h2 id="latest-events-heading"><span className={styles.dot} />Sự kiện mới nhất</h2>
        <div className={styles.actions}>
          <Link to="/events">Xem tất cả <RightOutlined /></Link>
          <button onClick={() => scroll(-1)} disabled={loading || posts.length < 2} aria-label="Cuộn sự kiện về trước"><LeftOutlined /></button>
          <button onClick={() => scroll(1)} disabled={loading || posts.length < 2} aria-label="Cuộn sự kiện về sau"><RightOutlined /></button>
        </div>
      </div>
      {loading ? <p className={styles.notice} role="status">Đang tải sự kiện mới nhất…</p> : failed ? (
        <p className={styles.notice} role="alert">Chưa tải được sự kiện mới nhất. Vui lòng tải lại trang.</p>
      ) : posts.length ? (
        <div className={styles.rail} ref={rail} tabIndex={0} aria-label="Danh sách sự kiện cuộn ngang">
          {posts.map((post) => <PostCard key={post.id} post={post} sourceAware layout="rail" showImage showDate showHotBadge={false} compact maxLinks={3} />)}
        </div>
      ) : <p className={styles.notice}>Chưa có sự kiện.</p>}
    </section>
  );
}
