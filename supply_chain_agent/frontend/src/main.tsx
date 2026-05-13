import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { HashRouter } from 'react-router-dom';
import { useUIStore } from '@/store/uiStore';
import AppRoutes from './AppRoutes';
import { AppLayout } from '@/components/layout/AppLayout';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import '@/styles/global.css';

const AppContent = () => {
  const { isDarkMode } = useUIStore();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDarkMode ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          // 主色调 - 供应链科技蓝
          colorPrimary: '#2A5C82',
          borderRadius: 8,
          borderRadiusLG: 12,
          borderRadiusSM: 4,
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          // 暗色模式下的主色调调整
          colorPrimaryBg: isDarkMode ? 'rgba(74, 154, 212, 0.15)' : 'rgba(42, 92, 130, 0.1)',
        },
        components: {
          Layout: {
            siderBg: isDarkMode ? '#141414' : '#fff',
            headerBg: isDarkMode ? '#141414' : '#fff',
            triggerBg: isDarkMode ? '#1f1f1f' : '#f5f5f5',
            headerHeight: 56,
          },
          Menu: {
            darkItemBg: isDarkMode ? '#141414' : undefined,
            itemBorderRadius: 6,
          },
          Card: {
            borderRadiusLG: 12,
          },
          Button: {
            borderRadius: 6,
          },
          Input: {
            borderRadius: 8,
          },
          Modal: {
            borderRadiusLG: 12,
          },
          Drawer: {
            borderRadiusLG: 12,
          },
          Tag: {
            borderRadiusSM: 4,
          },
          Table: {
            borderRadiusLG: 8,
          },
        },
      }}
    >
      <App>
        <HashRouter>
          <AppLayout>
            <AppRoutes />
          </AppLayout>
        </HashRouter>
      </App>
    </ConfigProvider>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  </React.StrictMode>
);
