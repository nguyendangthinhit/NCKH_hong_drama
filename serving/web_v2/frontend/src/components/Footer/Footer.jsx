import { Link } from 'react-router-dom';
import {
  FacebookOutlined,
  YoutubeOutlined,
  GlobalOutlined,
  HomeOutlined,
  InfoCircleOutlined,
  PhoneOutlined,
  SafetyCertificateOutlined,
  FileTextOutlined,
  SearchOutlined,
  FireOutlined,
  CopyrightOutlined,
} from '@ant-design/icons';
import styles from './Footer.module.scss';

const footerLinks = {
  about: [
    { label: 'Về chúng tôi', href: '/about',   icon: <InfoCircleOutlined /> },
    { label: 'Liên hệ',      href: '/contact',  icon: <PhoneOutlined /> },
    { label: 'Bảo mật',      href: '/privacy',  icon: <SafetyCertificateOutlined /> },
    { label: 'Điều khoản',   href: '/terms',    icon: <FileTextOutlined /> },
  ],
  platforms: [
    { label: 'Trang chủ',      href: '/',         icon: <HomeOutlined /> },
    { label: 'Facebook Drama', href: '/facebook',  icon: <FacebookOutlined /> },
    { label: 'Tin Tức Nóng',   href: '/news',      icon: <GlobalOutlined /> },
    { label: 'Tìm kiếm',       href: '/search',    icon: <SearchOutlined /> },
  ],
};

const socials = [
  { icon: <FacebookOutlined />, href: 'https://facebook.com', label: 'Facebook' },
  { icon: <YoutubeOutlined />,  href: 'https://youtube.com',  label: 'YouTube' },
  { icon: <GlobalOutlined />,   href: '/',                    label: 'Website' },
];

export default function Footer() {
  return (
    <footer className={styles.footer}>
      {/* Wave top */}
      <div className={styles['footer__wave']}>
        <svg viewBox="0 0 1440 48" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,16 C360,48 1080,-16 1440,16 L1440,48 L0,48 Z" fill="#c8102e"/>
        </svg>
      </div>

      <div className={styles.footer__body}>
        <div className={styles.footer__inner}>

          {/* Brand */}
          <div className={styles.footer__brand}>
            <div className={styles.footer__logo}>
              <img src="/images/logo1.png" alt="Hóng News" className={styles['footer__logo-img']} />
            </div>
            <p className={styles.footer__tagline}>
              Nơi tổng hợp mọi drama hot nhất từ Facebook và các trang tin tức lớn.
              Cập nhật 24/7 — không bỏ lỡ bất kỳ drama nào.
            </p>
            {/* Socials */}
            <div className={styles.footer__socials}>
              {socials.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles['footer__social-btn']}
                  aria-label={s.label}
                >
                  {s.icon}
                </a>
              ))}
            </div>
          </div>

          {/* Links */}
          <div className={styles.footer__links}>
            <div className={styles['footer__link-col']}>
              <h4 className={styles['footer__link-heading']}>
                <InfoCircleOutlined /> Thông tin
              </h4>
              <nav>
                {footerLinks.about.map((link) => (
                  <Link key={link.label} to={link.href} className={styles['footer__link-item']}>
                    <span className={styles['footer__link-icon']}>{link.icon}</span>
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>

            <div className={styles['footer__link-col']}>
              <h4 className={styles['footer__link-heading']}>
                <FireOutlined /> Nền tảng
              </h4>
              <nav>
                {footerLinks.platforms.map((link) => (
                  <Link key={link.label} to={link.href} className={styles['footer__link-item']}>
                    <span className={styles['footer__link-icon']}>{link.icon}</span>
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className={styles.footer__bottom}>
        <div className={styles.footer__bottom_inner}>
          <p className={styles.footer__copyright}>
            <CopyrightOutlined /> {new Date().getFullYear()} - NCKH 
          </p>
          <div className={styles.footer__legal}>
            <Link to="/privacy"><SafetyCertificateOutlined /> Bảo mật</Link>
            <Link to="/terms"><FileTextOutlined /> Điều khoản</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
