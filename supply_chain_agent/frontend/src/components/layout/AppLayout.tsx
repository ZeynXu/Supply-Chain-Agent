import { useState, useEffect } from 'react';
import { Layout, Button, Space, Badge, Tooltip, Popover } from 'antd';
import {
  BulbOutlined,
  MoonOutlined,
  ReloadOutlined,
  MenuOutlined,
  MessageOutlined,
  DashboardOutlined,
  ToolOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useUIStore } from '@/store/uiStore';
import { useNavigate, useLocation } from 'react-router-dom';

const { Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

// 菜单项配置
const menuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: '智能对话' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表板' },
  { key: '/tools', icon: <ToolOutlined />, label: '工具管理' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

export const AppLayout = ({ children }: AppLayoutProps) => {
  const {
    isDarkMode,
    wsConnected,
    toggleDarkMode,
    reconnect,
  } = useUIStore();

  const navigate = useNavigate();
  const location = useLocation();
  const [menuPopoverVisible, setMenuPopoverVisible] = useState(false);

  // 暗色模式切换时更新 CSS 变量
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  const handleReconnect = () => {
    reconnect();
  };

  const handleNavigate = (key: string) => {
    navigate(key);
    setMenuPopoverVisible(false);
  };

  // 菜单弹出内容
  const menuContent = (
    <div style={{ padding: '8px 0', minWidth: 160 }}>
      {menuItems.map((item) => (
        <div
          key={item.key}
          onClick={() => handleNavigate(item.key)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '12px 16px',
            cursor: 'pointer',
            background: location.pathname === item.key
              ? 'var(--color-primary)'
              : 'transparent',
            color: location.pathname === item.key
              ? '#fff'
              : 'var(--text-primary)',
            transition: 'all 0.2s',
            borderRadius: 6,
            margin: '0 8px',
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
          <span style={{ fontSize: 16 }}>{item.icon}</span>
          <span style={{ fontSize: 14, fontWeight: 500 }}>{item.label}</span>
        </div>
      ))}
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 右上角悬浮工具栏 */}
      <div
        style={{
          position: 'fixed',
          top: 16,
          right: 16,
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 16px',
          background: 'var(--bg-primary)',
          borderRadius: 12,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
          border: '1px solid var(--border-light)',
        }}
      >
        {/* 菜单按钮 */}
        <Popover
          content={menuContent}
          trigger="click"
          placement="bottomRight"
          open={menuPopoverVisible}
          onOpenChange={setMenuPopoverVisible}
          arrow={false}
          styles={{
            body: { padding: 0 },
          }}
        >
          <Button
            type="text"
            icon={<MenuOutlined style={{ fontSize: 16 }} />}
            style={{ fontWeight: 500 }}
          >
            菜单
          </Button>
        </Popover>

        {/* 分隔线 */}
        <div
          style={{
            width: 1,
            height: 20,
            background: 'var(--border-light)',
          }}
        />

        {/* 亮暗色模式切换 */}
        <Tooltip title={isDarkMode ? '切换到亮色模式' : '切换到暗色模式'}>
          <Button
            type="text"
            icon={isDarkMode ? <BulbOutlined /> : <MoonOutlined />}
            onClick={toggleDarkMode}
            style={{ fontSize: 16 }}
          />
        </Tooltip>

        {/* 分隔线 */}
        <div
          style={{
            width: 1,
            height: 20,
            background: 'var(--border-light)',
          }}
        />

        {/* 连接状态 */}
        <Space size={6}>
          <Badge status={wsConnected ? 'success' : 'error'} />
          <span
            style={{
              fontSize: 13,
              color: wsConnected ? '#52c41a' : '#ff4d4f',
            }}
          >
            {wsConnected ? '已连接' : '未连接'}
          </span>
          {!wsConnected && (
            <Tooltip title="重新连接">
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                onClick={handleReconnect}
                style={{ fontSize: 14 }}
              />
            </Tooltip>
          )}
        </Space>
      </div>

      {/* 主内容区 */}
      <Layout style={{ background: 'var(--bg-tertiary)' }}>
        <Content
          style={{
            flex: 1,
            padding: 0,
            overflow: 'auto',
            minHeight: '100vh',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
