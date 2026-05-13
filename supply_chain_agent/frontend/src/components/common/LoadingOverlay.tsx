import { Spin } from 'antd';

interface LoadingOverlayProps {
  loading?: boolean;
  tip?: string;
  children?: React.ReactNode;
}

export const LoadingOverlay = ({ loading, tip = '加载中...', children }: LoadingOverlayProps) => {
  if (!loading) {
    return <>{children}</>;
  }

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: 'rgba(255, 255, 255, 0.7)',
      zIndex: 100,
    }}>
      <Spin size="large" tip={tip} />
    </div>
  );
};

export default LoadingOverlay;
