import { FacebookFilled, TikTokOutlined } from '@ant-design/icons';
import { socialChannels } from '../../config/social-links';
import styles from './follow-community.module.scss';

const icons = {
  facebook: <FacebookFilled aria-hidden="true" />,
  tiktok: <TikTokOutlined aria-hidden="true" />,
  threads: <span className={styles.threadsMark} aria-hidden="true">@</span>,
};

export default function FollowCommunity() {
  return (
    <section className={styles.panel} aria-labelledby="follow-community-heading">
      <h2 className={styles.heading} id="follow-community-heading">
        <span className={styles.dot} aria-hidden="true" />Theo dõi hội hóng biến
      </h2>
      <div className={styles.channels}>
        {socialChannels.map((channel) => {
          const content = <>
            {icons[channel.id]}
            <strong>{channel.label}</strong>
            <span className={styles.status}>{channel.href ? 'Theo dõi' : 'Sắp ra mắt'}</span>
          </>;
          const className = `${styles.channel} ${styles[channel.id]}`;
          return channel.href ? (
            <a key={channel.id} className={className} href={channel.href} target="_blank" rel="noopener noreferrer" aria-label={`Theo dõi Hóng Biến trên ${channel.label} (mở tab mới)`}>
              {content}
            </a>
          ) : (
            <button key={channel.id} type="button" className={className} disabled title={`Kênh ${channel.label} sắp ra mắt`}>
              {content}
            </button>
          );
        })}
      </div>
    </section>
  );
}
