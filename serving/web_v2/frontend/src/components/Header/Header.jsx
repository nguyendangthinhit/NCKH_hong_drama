import { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useLocation, useNavigate } from 'react-router-dom';
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
import HeaderBrand from './header-brand';

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
  const headerRef = useRef(null);
  const searchComposing = useRef(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const closeOutside = (event) => {
      if (!headerRef.current?.contains(event.target)) setOpenDropdown(null);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchComposing.current) return;
    const query = searchQuery.trim();
    navigate({ pathname: '/events', search: query ? `?${new URLSearchParams({ q: query })}` : '' });
    setSearchQuery('');
    setOpenDropdown(null);
  };

  return (
    <header ref={headerRef} className={`${styles.header} ${scrolled ? styles['header--scrolled'] : ''}`}>
      <div className={styles.header__strip}>
        <div className={styles['header__strip-inner']}>
          <span className={styles['header__strip-label']}>HOT 24/7</span>
          <span className={styles['header__strip-text']}>Thông tin · Thống kê · Phân tích</span>
          <span className={styles['header__strip-topics']}>Showbiz / Giáo dục</span>
        </div>
      </div>
        <div className={styles.header__top}>

          {/* Logo */}
          <HeaderBrand />

          {/* Search */}
          <form className={styles.header__search} onSubmit={handleSearch}>
            <input
              aria-label="Tìm kiếm sự kiện"
              type="text"
              placeholder="Tìm kiếm drama..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onCompositionStart={() => { searchComposing.current = true; }}
              onCompositionEnd={(event) => { searchComposing.current = false; setSearchQuery(event.currentTarget.value); }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault();
              }}
            />
            <button type="submit" className={styles['header__search-submit']} aria-label="Tìm kiếm">
              <SearchOutlined />
            </button>
          </form>

          {/* Actions */}
          <div className={styles.header__actions}>
            <button type="button" className={styles['header__noti-btn']} aria-label="Thông báo">
              <BellOutlined />
            </button>

            <button type="button" className={styles['header__login-btn']}>
              <UserOutlined /> Đăng nhập
            </button>
          </div>
        </div>

      {/* ── Navigation bar ── */}
      <nav className={styles.header__nav} aria-label="Điều hướng chính">
        <div className={styles['header__nav-inner']}>
          {navItems.map((item) =>
            item.children ? (
              /* Dropdown item */
              <div
                key={item.label}
                className={styles['header__nav-dropdown']}
                onMouseEnter={() => setOpenDropdown(item.label)}
                onMouseLeave={() => setOpenDropdown(null)}
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget)) setOpenDropdown(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    setOpenDropdown(null);
                    event.currentTarget.querySelector('button')?.focus();
                  }
                }}
              >
                <button
                  type="button"
                  className={`${styles['header__nav-dropdown-trigger']} ${location.pathname === item.basePath ? styles['header__nav-link--active'] : ''}`}
                  aria-expanded={openDropdown === item.label}
                  aria-controls={`header-dropdown-${item.basePath.slice(1)}`}
                  onClick={() => setOpenDropdown(item.label)}
                >
                  <span className={styles['header__nav-icon']}>{item.icon}</span>
                  {item.label}
                  <span className={`${styles['header__nav-arrow']} ${openDropdown === item.label ? styles['header__nav-arrow--open'] : ''}`}>
                    <DownOutlined />
                  </span>
                </button>

                <div
                  id={`header-dropdown-${item.basePath.slice(1)}`}
                  className={`${styles['header__nav-dropdown-menu']} ${openDropdown === item.label ? styles['header__nav-dropdown-menu--open'] : ''}`}
                >
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
    </header>
  );
}
