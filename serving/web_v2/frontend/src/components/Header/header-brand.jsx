import { Link } from 'react-router-dom';
import styles from './header-brand.module.scss';

export default function HeaderBrand() {
  return (
    <div className={styles.identity}>
      <Link to="/" className={styles.logo} aria-label="Hóng Biến.VN - Trang chủ">
        <span className={styles.badge}>HÓNG</span>
        <span className={styles.wordmark}>
          <span className={styles.name}>BIẾN<span>.VN</span></span>
          <span className={styles.subtitle}>Showbiz • Drama • Mạng Xã Hội</span>
        </span>
      </Link>
      <p className={styles.slogan}>
        &quot;Ăn dưa hóng phốt 24/7 - Không bỏ lỡ bất kỳ drama nào!&quot;
      </p>
    </div>
  );
}
