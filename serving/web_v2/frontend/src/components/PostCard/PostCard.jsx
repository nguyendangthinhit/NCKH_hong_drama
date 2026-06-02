import { useState } from 'react';
import {
  FacebookOutlined,
  GlobalOutlined,
  LinkOutlined,
  RightOutlined,
  FireOutlined,
} from '@ant-design/icons';
import { getMainLink, shortenUrl } from '../../utils/postHelpers';
import styles from './PostCard.module.scss';

const GRADIENTS = {
  'Giải trí': 'linear-gradient(135deg, #ff6b6b 0%, #ffa502 100%)',
  'Giáo dục': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  default: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
};

export default function PostCard({ post, variant = 'news', maxLinks, compact = false, rank, showImage = false }) {
  const [imgError, setImgError] = useState(false);
  const mainLink    = getMainLink(post);
  const allLinks    = post.links ?? [];
  const shownLinks  = maxLinks != null ? allLinks.slice(0, maxLinks) : allLinks;
  const hiddenCount = allLinks.length - shownLinks.length;

  const isFb = variant === 'facebook';
  const gradient = GRADIENTS[post.category] || GRADIENTS.default;

  return (
    <div className={`${styles.card} ${styles[`card--${variant}`]} ${compact ? styles['card--compact'] : ''}`}>
      {/* Rank badge */}
      {rank != null && (
        <div className={`${styles['card__rank']} ${rank <= 3 ? styles['card__rank--top'] : ''}`}>
          #{rank}
        </div>
      )}

      {/* Image / gradient media */}
      {showImage && (
        <div className={styles['card__media']} style={{ background: gradient }}>
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
              {isFb ? <FacebookOutlined /> : <GlobalOutlined />}
            </div>
          )}
          {post.isHot && (
            <span className={styles['card__hot-badge']}>
              <FireOutlined /> HOT
            </span>
          )}
        </div>
      )}

      {/* Accent stripe */}
      {!showImage && <div className={styles['card__accent']} />}

      <div className={styles['card__body']}>
        {/* Top badges */}
        <div className={styles['card__top']}>
          <span className={styles['card__badge']}>
            {isFb ? <FacebookOutlined /> : <GlobalOutlined />}
            {isFb ? ' Facebook' : ' Tin tức'}
          </span>
          {post.category && (
            <span className={styles['card__category']}>{post.category}</span>
          )}
        </div>

        {/* Title */}
        <div
          className={styles['card__title']}
          onClick={() => window.open(mainLink, '_blank')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && window.open(mainLink, '_blank')}
        >
          {post.title}
        </div>

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
          <a
            href={mainLink}
            target="_blank"
            rel="noopener noreferrer"
            className={styles['card__read-more']}
            onClick={(e) => e.stopPropagation()}
          >
            Xem nguồn <RightOutlined />
          </a>
        </div>
      </div>
    </div>
  );
}
