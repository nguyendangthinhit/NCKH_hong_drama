import {
  FacebookOutlined,
  GlobalOutlined,
  LinkOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { getMainLink, shortenUrl } from '../../utils/postHelpers';
import styles from './PostCard.module.scss';

export default function PostCard({ post, variant = 'news', maxLinks, compact = false }) {
  const mainLink    = getMainLink(post);
  const allLinks    = post.links ?? [];
  const shownLinks  = maxLinks != null ? allLinks.slice(0, maxLinks) : allLinks;
  const hiddenCount = allLinks.length - shownLinks.length;

  const isFb = variant === 'facebook';

  return (
    <div className={`${styles.card} ${styles[`card--${variant}`]} ${compact ? styles['card--compact'] : ''}`}>
      {/* Accent stripe */}
      <div className={styles['card__accent']} />

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
