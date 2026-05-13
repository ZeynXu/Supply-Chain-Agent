import { Routes, Route, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';

// 懒加载页面组件
const ChatPage = lazy(() => import('@/pages/chat/ChatPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const ToolsPage = lazy(() => import('@/pages/tools/ToolsPage'));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'));

// 加载占位组件
const PageLoading = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    minHeight: 400
  }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

export const AppRoutes = () => {
  return (
    <Suspense fallback={<PageLoading />}>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </Suspense>
  );
};

export default AppRoutes;
