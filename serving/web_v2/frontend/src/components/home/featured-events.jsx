import { Link, useLocation } from 'react-router-dom';
import { ArrowRightOutlined, CommentOutlined } from '@ant-design/icons';
import EventImage from './event-image';
import styles from './featured-events.module.scss';

function FeaturedCard({ post, lead = false, index }) {
  const location = useLocation();
  return (
    <article className={`${styles.story} ${lead ? styles.lead : ''}`}>
      <Link className={styles.coverLink} to={`/events/${encodeURIComponent(post.id)}`} state={{ from: `${location.pathname}${location.search}` }} aria-label={`Đọc sự kiện: ${post.title}`} />
      <EventImage src={post.imageUrl} alt="" className={styles.image} fallbackClassName={styles.fallback} eager={lead} />
      <div className={styles.shade} />
      <span className={styles.badge}>{lead ? 'Tiêu điểm' : post.category || 'Sự kiện'}</span>
      <div className={styles.body}>
        <div className={styles.meta}>
          <span>{lead ? post.category || 'Sự kiện nổi bật' : `Điểm tin ${index + 1}`}</span>
          {post.totalComments > 0 && <span><CommentOutlined /> {post.totalComments.toLocaleString('vi-VN')} bình luận</span>}
        </div>
        <h2>{post.title}</h2>
        {post.description && <p className={styles.description}>{post.description}</p>}
        <div className={styles.bottom}><span>{post.category || 'Thông tin tổng hợp'}</span><span>Đọc tiếp <ArrowRightOutlined /></span></div>
      </div>
    </article>
  );
}

export default function FeaturedEvents({ posts, loading }) {
  if (loading) {
    return <div className={styles.grid} aria-label="Đang tải sự kiện nổi bật" aria-busy="true">
      {[0, 1, 2, 3].map((index) => <div key={index} className={`${styles.skeleton} ${index === 0 ? styles.lead : ''}`} />)}
    </div>;
  }
  if (!posts.length) return <div className={styles.empty}>Chưa có sự kiện để hiển thị.</div>;
  return <section className={styles.grid} aria-label="Sự kiện nổi bật">
    {posts.slice(0, 4).map((post, index) => <FeaturedCard key={post.id} post={post} lead={index === 0} index={index} />)}
  </section>;
}
