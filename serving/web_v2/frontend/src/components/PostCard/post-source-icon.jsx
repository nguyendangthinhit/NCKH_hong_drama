import { FacebookOutlined, GlobalOutlined, YoutubeOutlined, TikTokOutlined, InstagramOutlined } from '@ant-design/icons';

const icons = {
  facebook: FacebookOutlined,
  news: GlobalOutlined,
  youtube: YoutubeOutlined,
  tiktok: TikTokOutlined,
  instagram: InstagramOutlined,
};

export default function PostSourceIcon({ source }) {
  const Icon = Object.hasOwn(icons, source) ? icons[source] : GlobalOutlined;
  return <Icon />;
}
