import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LinkOutlined,
  RightOutlined,
  FireOutlined,
} from '@ant-design/icons';
import { shortenUrl } from '../../utils/postHelpers';
import { getEventSource } from '../../utils/event-sources';
import PostSourceIcon from './post-source-icon';
import styles from './PostCard.module.scss';

const GRADIENTS = {
  'Giải trí': 'linear-gradient(135deg, #ff6b6b 0%, #ffa502 100%)',
  'Giáo dục': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  default: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
};

export default function PostCard({ post, variant = 'news', maxLinks, compact = false, rank, showImage = false, layout = 'card', showDate = false, showHotBadge = true, sourceAware = false }) {
  const [imgError, setImgError] = useState(false);
  const location = useLocation();
  const detailPath = `/events/${encodeURIComponent(post.id)}`;
  const navigationState = { from: `${location.pathname}${location.search}` };
  const allLinks    = post.links ?? [];
  const shownLinks  = maxLinks != null ? allLinks.slice(0, maxLinks) : allLinks;
  const hiddenCount = allLinks.length - shownLinks.length;

  const source = getEventSource(sourceAware ? post.platform : variant === 'facebook' ? 'facebook' : 'news');
  const cardVariant = sourceAware ? (['facebook', 'news'].includes(source.key) ? source.key : 'source') : variant;
  const gradient = GRADIENTS[post.category] || GRADIENTS.default;

  return (
    <div className={`${styles.card} ${styles[`card--${cardVariant}`]} ${styles[`card--${layout}`] || ''} ${compact ? styles['card--compact'] : ''}`}>
      {/* Rank badge */}
      {rank != null && (
        <div className={`${styles['card__rank']} ${rank <= 3 ? styles['card__rank--top'] : ''}`}>
          #{rank}
        </div>
      )}

      {/* Image / gradient media */}
      {showImage && (
        <Link
          to={detailPath}
          state={navigationState}
          className={styles['card__media']}
          style={{ background: gradient }}
          aria-label={`Đọc sự kiện: ${post.title}`}
        >
          {post.imageUrl && !imgError ? (
            <img
              src={post.imageUrl}
              alt={post.title}
              className={styles['card__media-img']}
              onError={() => setImgError(true)}
              loading="lazy"
            />
          ) : (
            <div className={styles['card__media-icon']}>
              <PostSourceIcon source={source.key} />
            </div>
          )}
          {showHotBadge && post.isHot && (
            <span className={styles['card__hot-badge']}>
              <FireOutlined /> HOT
            </span>
          )}
        </Link>
      )}

      {/* Accent stripe */}
      {!showImage && <div className={styles['card__accent']} />}

      <div className={styles['card__body']}>
        {/* Top badges */}
        <div className={styles['card__top']}>
          <span className={styles['card__badge']}>
            <PostSourceIcon source={source.key} />{' '}{source.label}
          </span>
          {post.category && (
            <span className={styles['card__category']}>{post.category}</span>
          )}
        </div>

        {/* Title */}
        <Link
          className={styles['card__title']}
          to={detailPath}
          state={navigationState}
        >
          {post.title}
        </Link>

        {showDate && post.timeEvent && <span className={styles['card__date']}>Ngày sự kiện: {post.timeEvent}</span>}
        {post.description && <p className={styles['card__excerpt']}>{post.description}</p>}

        {/* Comment stats */}
        {post.totalComments > 0 && (
          <div className={styles['card__stats']}>
            {post.totalComments.toLocaleString()} bình luận
          </div>
        )}

        {/* Links list */}
        {shownLinks.length > 0 && (
          <div className={styles['card__links']}>
            <span className={styles['card__links-label']}>
              <LinkOutlined /> {allLinks.length} nguồn liên quan
            </span>
            <div className={styles['card__links-list']}>
              {shownLinks.map((link, i) => (
                <a
                  key={i}
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles['card__link']}
                  title={link}
                >
                  {shortenUrl(link)}
                </a>
              ))}
              {hiddenCount > 0 && (
                <span className={styles['card__link-more']}>
                  +{hiddenCount} nguồn khác
                </span>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className={styles['card__footer']}>
          {post.status && (
            <span className={`${styles['card__status']} ${styles[`card__status--${post.status.toLowerCase()}`] ?? styles['card__status--default']}`}>
              {post.status}
            </span>
          )}
          <Link
            to={detailPath}
            state={navigationState}
            className={styles['card__read-more']}
          >
            Xem chi tiết <RightOutlined />
          </Link>
        </div>
      </div>
    </div>
  );
}
