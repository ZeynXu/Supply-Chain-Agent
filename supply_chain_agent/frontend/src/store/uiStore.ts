// uiStore.ts - UI状态管理
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  isDarkMode: boolean;
  sidebarCollapsed: boolean;
  wsConnected: boolean;
  wsUrl: string;
  apiUrl: string;
  modelName: string;

  toggleDarkMode: () => void;
  toggleSidebar: () => void;
  setWsConnected: (connected: boolean) => void;
  setWsUrl: (url: string) => void;
  setApiUrl: (url: string) => void;
  setModelName: (name: string) => void;
  reconnect: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

// 默认配置 - 使用空字符串表示通过Vite代理
const DEFAULT_API_URL = '';
const DEFAULT_WS_URL = 'ws://localhost:8000';

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      isDarkMode: false,
      sidebarCollapsed: false,
      wsConnected: false,
      wsUrl: import.meta.env.VITE_WS_URL || DEFAULT_WS_URL,
      apiUrl: import.meta.env.VITE_API_BASE_URL || DEFAULT_API_URL,
      modelName: 'claude-3-5-sonnet-20241022',

      toggleDarkMode: () => set((state) => ({ isDarkMode: !state.isDarkMode })),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setWsConnected: (connected) => set({ wsConnected: connected }),
      setWsUrl: (url) => set({ wsUrl: url }),
      setApiUrl: (url) => set({ apiUrl: url }),
      setModelName: (name) => set({ modelName: name }),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      reconnect: () => {
        console.log('触发 WebSocket 重连...');
        set({ wsConnected: false });
        // 实际重连逻辑由 useWebSocket hook 处理
      },
    }),
    {
      name: 'sca-ui-storage',
      partialize: (state) => ({
        isDarkMode: state.isDarkMode,
        sidebarCollapsed: state.sidebarCollapsed,
        wsUrl: state.wsUrl,
        apiUrl: state.apiUrl,
        modelName: state.modelName,
      }),
    }
  )
);

export default useUIStore;
