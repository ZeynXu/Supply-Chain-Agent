import { Menu } from 'antd';
import {
  MessageOutlined,
  DashboardOutlined,
  ToolOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@/store/uiStore';

const menuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: '智能对话' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表板' },
  { key: '/tools', icon: <ToolOutlined />, label: '工具管理' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

export const SidebarMenu = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isDarkMode } = useUIStore();

  return (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={menuItems}
      onClick={({ key }) => navigate(key)}
      style={{
        border: 'none',
        background: 'transparent',
      }}
      theme={isDarkMode ? 'dark' : 'light'}
    />
  );
};

export default SidebarMenu;
