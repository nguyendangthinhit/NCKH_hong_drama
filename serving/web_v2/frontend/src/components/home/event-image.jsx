import { useState } from 'react';
import { PictureOutlined } from '@ant-design/icons';

export default function EventImage({ src, alt, className, fallbackClassName, eager = false }) {
  const [failedSrc, setFailedSrc] = useState(null);
  if (!src || failedSrc === src) {
    return <span className={fallbackClassName} aria-hidden="true"><PictureOutlined /></span>;
  }
  return <img src={src} alt={alt} className={className} loading={eager ? 'eager' : 'lazy'} onError={() => setFailedSrc(src)} />;
}
