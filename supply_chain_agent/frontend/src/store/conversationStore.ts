// conversationStore.ts - 对话状态管理
import { create } from 'zustand';
import type { Message, DataCard, SuggestedAction } from '@/types/conversation';
import type { AgentTrajectory, AgentStep, AgentEvent, SkillCall } from '@/types/agent';

interface ConversationState {
  messages: Message[];
  sessionId: string;
  sessionTitle: string;
  isLoading: boolean;
  streamingContent: string;
  agentTrajectory: AgentTrajectory | null;
  useMock: boolean;
  pendingSkills: Map<string, SkillCall[]>;  // 新增：待关联的 skill 调用

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
  pendingSkills: new Map(),

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
  newSession: () => set({ messages: [], sessionId: generateId(), sessionTitle: '新对话', agentTrajectory: null, pendingSkills: new Map() }),
  setUseMock: (useMock) => set({ useMock }),

  initAgentTrajectory: (sessionId) => set({
    agentTrajectory: {
      sessionId,
      steps: [],
      overallStatus: 'pending',
      startTime: Date.now(),
    },
    pendingSkills: new Map(),  // 每次初始化轨迹时清空待关联 skills
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
    console.log('[ConversationStore] 收到事件:', type, data);

    switch (type) {
      case 'step_start':
        const newStepId = data.stepId || generateId();
        // 检查是否有待关联的 skills（使用前缀匹配）
        const stepPrefix = newStepId.split('-')[0]; // 如 "plan_task"
        const pendingSkillsForStep = get().pendingSkills.get(stepPrefix) || get().pendingSkills.get(newStepId) || [];
        console.log('[ConversationStore] step_start:', newStepId, 'stepPrefix:', stepPrefix, 'pendingSkills:', pendingSkillsForStep.length, 'pendingSkills map:', Object.fromEntries(get().pendingSkills));
        get().addAgentStep({
          id: newStepId,
          agentType: data.agentType || 'orchestrator',
          title: data.title || '处理中',
          description: data.description || '',
          status: 'running',
          startTime: event.timestamp,
          tools: [],
          skills: pendingSkillsForStep,  // 使用待关联的 skills
          rawData: data.raw,
        });
        // 清除已使用的 pendingSkills
        if (pendingSkillsForStep.length > 0) {
          set((state) => {
            const newPending = new Map(state.pendingSkills);
            newPending.delete(stepPrefix);
            newPending.delete(newStepId);
            return { pendingSkills: newPending };
          });
        }
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

      case 'skill_load':
        console.log('[ConversationStore] 处理 skill_load 事件:', data);
        if (data.skillCall) {
          const skillStepId = data.stepId;
          const currentStepId = get().agentTrajectory?.currentStepId;
          const skillData = data.skillCall;  // 提取到变量，避免 undefined 问题
          console.log('[ConversationStore] skillStepId:', skillStepId, 'currentStepId:', currentStepId);

          // 首先尝试使用事件中的 stepId
          if (skillStepId) {
            // 尝试精确匹配，或者匹配以 skillStepId 前缀开头的 step
            // 例如：skillStepId="plan_task-skill" 可以匹配 "plan_task-1"
            const step = get().agentTrajectory?.steps.find(s => s.id === skillStepId);
            const prefixMatchStep = !step ? get().agentTrajectory?.steps.find(s => {
              const prefix = skillStepId.split('-')[0]; // 如 "plan_task"
              return s.id.startsWith(prefix + '-');
            }) : null;
            const targetStep = step || prefixMatchStep;
            console.log('[ConversationStore] 找到的 step:', step?.id, 'prefixMatchStep:', prefixMatchStep?.id, 'targetStep:', targetStep?.id);

            if (targetStep) {
              // step 已存在，直接更新
              const existingIndex = targetStep.skills?.findIndex(s => s.id === skillData.id) ?? -1;
              if (existingIndex >= 0 && targetStep.skills) {
                const updatedSkills = [...targetStep.skills];
                updatedSkills[existingIndex] = skillData;
                get().updateAgentStep(targetStep.id, { skills: updatedSkills });
              } else {
                get().updateAgentStep(targetStep.id, { skills: [...(targetStep.skills || []), skillData] });
              }
            } else {
              // step 还不存在，存储到 pendingSkills（使用前缀作为 key）
              const prefix = skillStepId.split('-')[0];
              set((state) => {
                const newPending = new Map(state.pendingSkills);
                const existing = newPending.get(prefix) || [];
                // 检查是否已存在相同 id 的 skill
                const existingIndex = existing.findIndex(s => s.id === skillData.id);
                if (existingIndex >= 0) {
                  const updated = [...existing];
                  updated[existingIndex] = skillData;
                  newPending.set(prefix, updated);
                } else {
                  newPending.set(prefix, [...existing, skillData]);
                }
                return { pendingSkills: newPending };
              });
            }
          } else if (currentStepId) {
            // 使用 currentStepId（兼容旧逻辑）
            const step = get().agentTrajectory?.steps.find(s => s.id === currentStepId);
            if (step) {
              const existingIndex = step.skills?.findIndex(s => s.id === skillData.id) ?? -1;
              if (existingIndex >= 0 && step.skills) {
                const updatedSkills = [...step.skills];
                updatedSkills[existingIndex] = skillData;
                get().updateAgentStep(currentStepId, { skills: updatedSkills });
              } else {
                get().updateAgentStep(currentStepId, { skills: [...(step.skills || []), skillData] });
              }
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
