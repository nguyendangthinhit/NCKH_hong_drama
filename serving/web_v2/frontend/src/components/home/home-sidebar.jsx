import { Link, useLocation } from 'react-router-dom';
import { FacebookOutlined, FireOutlined, ArrowRightOutlined } from '@ant-design/icons';
import PostCard from '../PostCard/PostCard';
import EventImage from './event-image';
import FollowCommunity from './follow-community';
import styles from './home-sidebar.module.scss';

export default function HomeSidebar({ posts, news, loading }) {
  const location = useLocation();
  const first = posts[0];
  const state = { from: `${location.pathname}${location.search}` };
  return (
    <aside className={styles.sidebar} aria-label="Cộng đồng và tin Facebook">
      <FollowCommunity />
      <section className={styles.panel} aria-label="Tin hot Facebook">
        <div className={styles.titleRow}>
          <h2 className={styles.heading}><FacebookOutlined />Tin hot Facebook</h2>
          <Link to="/facebook" className={styles.more}>Xem tất cả <ArrowRightOutlined /></Link>
        </div>
        {loading ? <p className={styles.loading} role="status">Đang tải tin Facebook…</p> : first ? (
          <>
            <article className={styles.spotlight}>
              <Link to={`/events/${encodeURIComponent(first.id)}`} state={state} className={styles.spotlightImage} aria-label={first.title}>
                <EventImage src={first.imageUrl} alt="" className={styles.image} fallbackClassName={styles.fallback} />
                <span className={styles.imageLabel}><FacebookOutlined /> Thông tin sự kiện</span>
              </Link>
              <span className={styles.category}>{first.category}</span>
              <h3><Link to={`/events/${encodeURIComponent(first.id)}`} state={state}>{first.title}</Link></h3>
              {first.description && <p>{first.description}</p>}
              <PostCard post={first} variant="facebook" layout="reference" compact maxLinks={3} />
            </article>
            <div className={styles.storyList}>
              {posts.slice(1).map((post) => <PostCard key={post.id} post={post} variant="facebook" layout="row" showImage compact maxLinks={3} />)}
            </div>
          </>
        ) : <p className={styles.loading}>Chưa có sự kiện Facebook.</p>}
      </section>
      {news.length > 0 && (
        <section className={styles.darkPanel} aria-label="Điểm tin nổi bật">
          <h2 className={styles.heading}><FireOutlined />Điểm tin nổi bật</h2>
          <ol className={styles.ranking}>
            {news.slice(0, 3).map((post, index) => (
              <li key={post.id}>
                <span className={styles.rank}>{index + 1}</span>
                <Link to={`/events/${encodeURIComponent(post.id)}`} state={state}>{post.title}</Link>
                {post.totalComments > 0 && <span className={styles.count}>{post.totalComments.toLocaleString('vi-VN')}<small>bình luận</small></span>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </aside>
  );
}
