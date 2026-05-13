// toolStore.ts - 工具状态管理
import { create } from 'zustand';
import type { Tool, ToolMetrics } from '@/types/tool';
import { toolService } from '@/api/toolService';

interface ToolState {
  tools: Tool[];
  toolMetrics: ToolMetrics[];
  loading: boolean;
  error: string | null;

  fetchTools: () => Promise<void>;
  fetchToolMetrics: (period?: string) => Promise<void>;
  setTools: (tools: Tool[]) => void;
  updateToolStatus: (name: string, status: Tool['status']) => void;
}

export const useToolStore = create<ToolState>((set) => ({
  tools: [],
  toolMetrics: [],
  loading: false,
  error: null,

  fetchTools: async () => {
    set({ loading: true, error: null });
    try {
      const tools = await toolService.getTools();
      set({ tools, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '获取工具列表失败', loading: false });
    }
  },

  fetchToolMetrics: async (period = '24h') => {
    try {
      const metrics = await toolService.getToolMetrics(period);
      set({ toolMetrics: metrics });
    } catch (err) {
      console.error('获取工具指标失败:', err);
    }
  },

  setTools: (tools) => set({ tools }),

  updateToolStatus: (name, status) => set((state) => ({
    tools: state.tools.map((t) =>
      t.name === name ? { ...t, status } : t
    ),
  })),
}));

export default useToolStore;
