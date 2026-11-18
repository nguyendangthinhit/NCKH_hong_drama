import { lazy, Suspense, useState } from 'react';
import { CalendarOutlined, LinkOutlined, ExportOutlined } from '@ant-design/icons';
import { shortenUrl } from '../../utils/postHelpers';
import styles from './event-detail-page.module.scss';

const EventAnalysis = lazy(() => import('../../components/Event_analysis/event-analysis'));

function isSourceUrl(value) {
  try {
    return ['http:', 'https:'].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}

export default function EventDetailContent({ post }) {
  const [imageFailed, setImageFailed] = useState(false);
  const sources = [...new Set((post.links || []).filter((link) => typeof link === 'string' && isSourceUrl(link)))];
  const actors = (post.actors || []).filter((actor) => actor.name);
  const content = post.contentFull || post.description;
  const showExcerpt = post.description && post.contentFull && post.description.trim() !== post.contentFull.trim();

  return (
    <div className={styles.layout}>
      <article className={styles.article}>
        <header className={styles.header}>
          {post.category && <span className={styles.category}>{post.category}</span>}
          <h1>{post.title}</h1>
          <div className={styles.meta}>
            {post.timeEvent && <span><CalendarOutlined /> Thời gian sự kiện: {post.timeEvent}</span>}
            <span><LinkOutlined /> {sources.length} nguồn tham khảo</span>
            {post.totalComments > 0 && <span>{post.totalComments.toLocaleString('vi-VN')} bình luận</span>}
          </div>
          {showExcerpt && <p className={styles.excerpt}>{post.description}</p>}
        </header>

        {post.imageUrl && !imageFailed && (
          <img
            className={styles.image}
            src={post.imageUrl}
            alt={post.title}
            onError={() => setImageFailed(true)}
          />
        )}

        <section className={styles.section} aria-labelledby="event-content-heading">
          <h2 id="event-content-heading">Thông tin sự kiện</h2>
          <p className={styles.content}>
            {content || 'Chưa có nội dung chi tiết cho sự kiện này. Bạn có thể xem các nguồn tham khảo bên cạnh.'}
          </p>
        </section>

        {actors.length > 0 && (
          <section className={styles.section} aria-labelledby="event-actors-heading">
            <h2 id="event-actors-heading">Nhân vật liên quan</h2>
            <ul className={styles.actors}>
              {actors.map((actor, index) => (
                <li key={`${actor.name}-${index}`}>
                  <strong>{actor.name}</strong>{actor.role && <span> — {actor.role}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className={styles.section} aria-labelledby="event-analysis-heading">
          <h2 id="event-analysis-heading">Phân tích dư luận</h2>
          <Suspense fallback={<p role="status">Đang tải phần phân tích…</p>}>
            <EventAnalysis key={post.id} eventId={post.id} />
          </Suspense>
        </section>
      </article>

      <aside className={styles.sources} aria-labelledby="event-sources-heading">
        <h2 id="event-sources-heading">Nguồn tham khảo</h2>
        <p>Chọn nguồn bên dưới để đọc bài viết gốc trên trang bên ngoài.</p>
        {sources.length > 0 ? (
          <ol className={styles.sourceList}>
            {sources.map((url, index) => (
              <li key={url}>
                <span className={styles.sourceNumber}>Nguồn {index + 1}</span>
                <a href={url} target="_blank" rel="noopener noreferrer" className={styles.sourceLink}>
                  {shortenUrl(url, 80)}
                </a>
                <a href={url} target="_blank" rel="noopener noreferrer" className={styles.button}>
                  Xem nguồn <ExportOutlined />
                </a>
              </li>
            ))}
          </ol>
        ) : <p>Chưa có nguồn tham khảo cho sự kiện này.</p>}
      </aside>
    </div>
  );
}
