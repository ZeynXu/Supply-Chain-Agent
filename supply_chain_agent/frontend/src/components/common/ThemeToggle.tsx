import { Switch, Tooltip } from 'antd';
import { BulbOutlined, MoonOutlined } from '@ant-design/icons';
import { useUIStore } from '@/store/uiStore';

export const ThemeToggle = () => {
  const { isDarkMode, toggleDarkMode } = useUIStore();

  return (
    <Tooltip title={isDarkMode ? '切换到亮色模式' : '切换到暗色模式'}>
      <Switch
        checked={isDarkMode}
        onChange={toggleDarkMode}
        checkedChildren={<MoonOutlined />}
        unCheckedChildren={<BulbOutlined />}
        style={{
          backgroundColor: isDarkMode ? '#177ddc' : undefined,
        }}
      />
    </Tooltip>
  );
};

export default ThemeToggle;
