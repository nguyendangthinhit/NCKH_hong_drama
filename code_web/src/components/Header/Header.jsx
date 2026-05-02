import { useState, useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  HomeOutlined,
  FacebookOutlined,
  GlobalOutlined,
  SearchOutlined,
  BellOutlined,
  UserOutlined,
  DownOutlined,
} from '@ant-design/icons';
import styles from './Header.module.scss';

const navItems = [
  { path: '/', label: 'Trang chủ', icon: <HomeOutlined />, exact: true },
  {
    label: 'Facebook',
    icon: <FacebookOutlined />,
    basePath: '/facebook',
    children: [
      { path: '/facebook',              label: 'Tất cả' },
      { path: '/facebook?cat=Giải trí', label: 'Giải trí' },
      { path: '/facebook?cat=Giáo dục', label: 'Giáo dục' },
    ],
  },
  {
    label: 'Tin Tức',
    icon: <GlobalOutlined />,
    basePath: '/news',
    children: [
      { path: '/news',              label: 'Tất cả' },
      { path: '/news?cat=Giải trí', label: 'Giải trí' },
      { path: '/news?cat=Giáo dục', label: 'Giáo dục' },
    ],
  },
];

export default function Header() {
  const [scrolled, setScrolled]         = useState(false);
  const [openDropdown, setOpenDropdown] = useState(null);
  const [searchQuery, setSearchQuery]   = useState('');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    // TODO: implement search
  };

  return (
    <>
      {/* ── Top bar ── */}
      <div className={`${styles.header} ${scrolled ? styles['header--scrolled'] : ''}`}>
        <div className={styles.header__top}>

          {/* Logo */}
          <Link to="/" className={styles.header__logo}>
            <img src="/images/logo1.png" alt="Hóng News" className={styles['header__logo-img']} />
          </Link>

          {/* Search */}
          <form className={styles.header__search} onSubmit={handleSearch}>
            <span className={styles['header__search-icon']}><SearchOutlined /></span>
            <input
              type="text"
              placeholder="Tìm kiếm drama..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>

          {/* Actions */}
          <div className={styles.header__actions}>
            <button className={styles['header__noti-btn']} aria-label="Thông báo">
              <BellOutlined />
            </button>

            <button className={styles['header__login-btn']}>
              <UserOutlined /> Đăng nhập
            </button>
          </div>
        </div>
      </div>

      {/* ── Navigation bar ── */}
      <nav className={`${styles.header__nav} ${scrolled ? styles['header__nav--scrolled'] : ''}`}>
        <div className={styles['header__nav-inner']}>
          {navItems.map((item) =>
            item.children ? (
              /* Dropdown item */
              <div
                key={item.label}
                className={styles['header__nav-dropdown']}
                onMouseEnter={() => setOpenDropdown(item.label)}
                onMouseLeave={() => setOpenDropdown(null)}
              >
                <button className={styles['header__nav-dropdown-trigger']}>
                  <span className={styles['header__nav-icon']}>{item.icon}</span>
                  {item.label}
                  <span className={`${styles['header__nav-arrow']} ${openDropdown === item.label ? styles['header__nav-arrow--open'] : ''}`}>
                    <DownOutlined />
                  </span>
                </button>

                <div className={`${styles['header__nav-dropdown-menu']} ${openDropdown === item.label ? styles['header__nav-dropdown-menu--open'] : ''}`}>
                  {item.children.map((child) => (
                    <Link
                      key={child.label}
                      to={child.path}
                      className={styles['header__nav-dropdown-item']}
                      onClick={() => setOpenDropdown(null)}
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              </div>
            ) : (
              /* Regular nav link */
              <NavLink
                key={item.path}
                to={item.path}
                end={item.exact}
                className={({ isActive }) =>
                  `${styles['header__nav-link']} ${isActive ? styles['header__nav-link--active'] : ''}`
                }
              >
                <span className={styles['header__nav-icon']}>{item.icon}</span>
                {item.label}
              </NavLink>
            )
          )}
        </div>
      </nav>
    </>
  );
}
