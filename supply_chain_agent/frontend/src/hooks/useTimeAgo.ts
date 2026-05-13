import { useEffect, useState } from 'react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

// 配置dayjs
dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

export const useTimeAgo = (timestamp: string | Date) => {
  const [timeAgo, setTimeAgo] = useState(() => dayjs(timestamp).fromNow());

  useEffect(() => {
    const updateTime = () => {
      setTimeAgo(dayjs(timestamp).fromNow());
    };

    updateTime();

    // 每分钟更新一次
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, [timestamp]);

  return timeAgo;
};

export const formatDate = (timestamp: string | Date, format = 'YYYY-MM-DD HH:mm:ss') => {
  return dayjs(timestamp).format(format);
};

export const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = ((ms % 60000) / 1000).toFixed(0);
  return `${minutes}m ${seconds}s`;
};
