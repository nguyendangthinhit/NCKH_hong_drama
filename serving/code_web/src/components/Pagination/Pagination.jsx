import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import styles from './Pagination.module.scss';

export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null;

  return (
    <div className={styles.pagination}>
      <button
        className={styles['page-btn']}
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        aria-label="Trang trước"
      >
        <LeftOutlined /> Trước
      </button>

      {[...Array(totalPages)].map((_, i) => {
        const p = i + 1;
        const show = p === 1 || p === totalPages || Math.abs(p - page) <= 1;
        const isEllipsis = p === 2 || p === totalPages - 1;

        if (show) {
          return (
            <button
              key={p}
              className={`${styles['page-btn']} ${p === page ? styles['page-btn--active'] : ''}`}
              onClick={() => onPageChange(p)}
              aria-label={`Trang ${p}`}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </button>
          );
        }
        if (isEllipsis) {
          return <span key={p} className={styles['page-ellipsis']}>…</span>;
        }
        return null;
      })}

      <button
        className={styles['page-btn']}
        onClick={() => onPageChange(page + 1)}
        disabled={page === totalPages}
        aria-label="Trang sau"
      >
        Sau <RightOutlined />
      </button>
    </div>
  );
}
