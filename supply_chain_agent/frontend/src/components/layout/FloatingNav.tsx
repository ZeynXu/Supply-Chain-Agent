import { useState, useEffect } from 'react';
import { Drawer, Button } from 'antd';
import {
  MessageOutlined,
  DashboardOutlined,
  ToolOutlined,
  SettingOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

interface FloatingNavProps {
  collapsed?: boolean;
}

const menuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: '智能对话' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表板' },
  { key: '/tools', icon: <ToolOutlined />, label: '工具管理' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

export const FloatingNav = ({ collapsed }: FloatingNavProps) => {
  const [visible, setVisible] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 根据侧边栏折叠状态决定显示模式
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkWidth = () => {
      setIsMobile(window.innerWidth < 1280);
    };
    checkWidth();
    window.addEventListener('resize', checkWidth);
    return () => window.removeEventListener('resize', checkWidth);
  }, []);

  // 小屏幕或侧边栏折叠时显示悬浮按钮
  const showFloatingButton = isMobile || collapsed;

  const handleNavigate = (key: string) => {
    navigate(key);
    setVisible(false);
  };

  if (!showFloatingButton) {
    return null;
  }

  return (
    <>
      {/* 悬浮导航按钮 */}
      <Button
        type="primary"
        icon={<MenuOutlined />}
        onClick={() => setVisible(true)}
        style={{
          position: 'fixed',
          left: 16,
          top: 12,
          zIndex: 1000,
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
        }}
      />

      {/* 抽屉式导航菜单 */}
      <Drawer
        title="系统导航"
        placement="left"
        onClose={() => setVisible(false)}
        open={visible}
        width={280}
        styles={{
          body: { padding: 0 },
        }}
      >
        <div style={{ padding: '12px 0' }}>
          {menuItems.map((item) => (
            <div
              key={item.key}
              onClick={() => handleNavigate(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 24px',
                cursor: 'pointer',
                background: location.pathname === item.key
                  ? 'var(--color-primary)'
                  : 'transparent',
                color: location.pathname === item.key
                  ? '#fff'
                  : 'var(--text-primary)',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== item.key) {
                  e.currentTarget.style.background = 'var(--bg-secondary)';
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== item.key) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              <span style={{ fontSize: 18 }}>{item.icon}</span>
              <span style={{ fontSize: 15, fontWeight: 500 }}>{item.label}</span>
            </div>
          ))}
        </div>
      </Drawer>
    </>
  );
};

export default FloatingNav;
