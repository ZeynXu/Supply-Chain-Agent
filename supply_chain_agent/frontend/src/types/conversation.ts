// conversation.ts - 对话消息相关类型定义

export type MessageRole = 'user' | 'assistant' | 'system';

export type MessageStatus = 'sending' | 'streaming' | 'success' | 'error';

export interface DataCard {
  type: 'status' | 'amount' | 'date' | 'location' | 'entity';
  label: string;
  value: string;
  icon?: string;
  color?: string;
}

export interface SuggestedAction {
  action: string;
  label: string;
  parameters?: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  status?: MessageStatus;
  dataCards?: DataCard[];
  suggestedActions?: SuggestedAction[];
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  sessionId: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface ChatRequest {
  query: string;
  session_id?: string;
  context?: Record<string, unknown>;
  preferences?: Record<string, unknown>;
}

export interface ChatResponse {
  success: boolean;
  query: string;
  response: string;
  intent?: {
    primary: string;
    secondary: string;
    confidence: number;
  };
  entities?: Record<string, string>;
  tools_used?: string[];
  processing_time?: number;
  session_id: string;
  timestamp: string;
  suggested_actions?: SuggestedAction[];
  error?: {
    code: string;
    message: string;
    details?: string;
  };
  requires_clarification?: boolean;
  clarification_questions?: string[];
}
