// conversationStore.ts - 对话状态管理
import { create } from 'zustand';
import type { Message, DataCard, SuggestedAction } from '@/types/conversation';
import type { AgentTrajectory, AgentStep, AgentEvent } from '@/types/agent';

interface ConversationState {
  messages: Message[];
  sessionId: string;
  sessionTitle: string;
  isLoading: boolean;
  streamingContent: string;
  agentTrajectory: AgentTrajectory | null;
  useMock: boolean;

  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastMessage: (content: string, dataCards?: DataCard[], suggestedActions?: SuggestedAction[]) => void;
  setStreamingContent: (content: string) => void;
  appendStreamingContent: (content: string) => void;
  clearStreamingContent: () => void;
  setLoading: (loading: boolean) => void;
  setSessionId: (id: string) => void;
  clearMessages: () => void;
  newSession: () => void;
  setUseMock: (useMock: boolean) => void;

  initAgentTrajectory: (sessionId: string) => void;
  addAgentStep: (step: AgentStep) => void;
  updateAgentStep: (stepId: string, updates: Partial<AgentStep>) => void;
  completeAgentTrajectory: () => void;
  clearAgentTrajectory: () => void;
  handleAgentEvent: (event: AgentEvent) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

const generateSessionTitle = (content: string) => {
  if (content.length <= 20) return content;
  return content.substring(0, 20) + '...';
};

export const useConversationStore = create<ConversationState>((set, get) => ({
  messages: [],
  sessionId: generateId(),
  sessionTitle: '新对话',
  isLoading: false,
  streamingContent: '',
  agentTrajectory: null,
  useMock: false,

  addMessage: (message) => {
    const newMessage: Message = {
      ...message,
      id: generateId(),
      timestamp: new Date().toISOString(),
    };
    set((state) => ({
      messages: [...state.messages, newMessage],
      sessionTitle: message.role === 'user' && state.messages.length === 0
        ? generateSessionTitle(message.content)
        : state.sessionTitle,
    }));
  },

  updateLastMessage: (content, dataCards, suggestedActions) => {
    set((state) => {
      const messages = [...state.messages];
      const lastIndex = messages.length - 1;
      if (lastIndex >= 0 && messages[lastIndex].role === 'assistant') {
        messages[lastIndex] = {
          ...messages[lastIndex],
          content,
          dataCards,
          suggestedActions,
          status: 'success',
          isStreaming: false,
        };
      }
      return { messages };
    });
  },

  setStreamingContent: (content) => set({ streamingContent: content }),
  appendStreamingContent: (content) => set((state) => ({ streamingContent: state.streamingContent + content })),
  clearStreamingContent: () => set({ streamingContent: '' }),
  setLoading: (loading) => set({ isLoading: loading }),
  setSessionId: (id) => set({ sessionId: id }),
  clearMessages: () => set({ messages: [], sessionTitle: '新对话' }),
  newSession: () => set({ messages: [], sessionId: generateId(), sessionTitle: '新对话', agentTrajectory: null }),
  setUseMock: (useMock) => set({ useMock }),

  initAgentTrajectory: (sessionId) => set({
    agentTrajectory: {
      sessionId,
      steps: [],
      overallStatus: 'pending',
      startTime: Date.now(),
    },
  }),

  addAgentStep: (step) => set((state) => {
    if (!state.agentTrajectory) return state;
    return {
      agentTrajectory: {
        ...state.agentTrajectory,
        steps: [...state.agentTrajectory.steps, step],
        currentStepId: step.id,
      },
    };
  }),

  updateAgentStep: (stepId, updates) => set((state) => {
    if (!state.agentTrajectory) return state;
    return {
      agentTrajectory: {
        ...state.agentTrajectory,
        steps: state.agentTrajectory.steps.map((step) =>
          step.id === stepId ? { ...step, ...updates } : step
        ),
      },
    };
  }),

  completeAgentTrajectory: () => set((state) => {
    if (!state.agentTrajectory) return state;
    return {
      agentTrajectory: {
        ...state.agentTrajectory,
        overallStatus: 'success',
        endTime: Date.now(),
      },
    };
  }),

  clearAgentTrajectory: () => set({ agentTrajectory: null }),

  handleAgentEvent: (event) => {
    const { type, data } = event;

    switch (type) {
      case 'step_start':
        get().addAgentStep({
          id: data.stepId || generateId(),
          agentType: data.agentType || 'orchestrator',
          title: data.title || '处理中',
          description: data.description || '',
          status: 'running',
          startTime: event.timestamp,
          tools: [],
          rawData: data.raw,
        });
        break;

      case 'step_end':
        // 更新步骤状态为成功
        const stepId = data.stepId || '';
        if (stepId) {
          get().updateAgentStep(stepId, {
            status: 'success',
            endTime: event.timestamp,
          });
        } else {
          // 如果没有指定stepId，更新当前正在运行的步骤
          const currentStepId = get().agentTrajectory?.currentStepId;
          if (currentStepId) {
            get().updateAgentStep(currentStepId, {
              status: 'success',
              endTime: event.timestamp,
            });
          }
        }
        break;

      case 'tool_call':
        if (data.toolCall) {
          const currentStepId = get().agentTrajectory?.currentStepId;
          if (currentStepId) {
            const step = get().agentTrajectory?.steps.find(s => s.id === currentStepId);
            if (step) {
              get().updateAgentStep(currentStepId, {
                tools: [...step.tools, data.toolCall],
              });
            }
          }
        }
        break;

      case 'complete':
        get().completeAgentTrajectory();
        if (data.raw?.response) {
          get().clearStreamingContent();
        }
        break;

      case 'error':
        get().completeAgentTrajectory();
        break;
    }
  },
}));

export default useConversationStore;
