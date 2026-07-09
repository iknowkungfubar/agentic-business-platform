/* Zustand store for TurinTech Platform state management.
 *
 * Manages JWT tokens, conversation state, message history,
 * and global UI state. Single source of truth for all
 * frontend data flows.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ── Types ────────────────────────────────────────────────────

export type Page = 'login' | 'chat' | 'dashboard' | 'agents' | 'scan';

export interface Message {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model_tier: string;
  tokens_used?: number;
}

export interface Conversation {
  id: number;
  title: string;
  created_at?: string;
}

export interface ScanResult {
  scan_id: number;
  url: string;
  reachable: boolean;
  status_code: number | null;
  is_https: boolean;
  requires_auth: boolean;
  findings: Array<{
    severity: string;
    description: string;
    recommendation: string;
  }>;
}

export interface Agent {
  id: number;
  name: string;
  url: string;
  provider: string;
  status: string;
  tags?: string;
  last_seen?: string;
}

// ── Store Interface ───────────────────────────────────────────

export interface AppState {
  // Auth
  token: string;
  user: { email: string; role: string; org_id: number } | null;
  isAuthenticated: boolean;

  // Navigation
  currentPage: Page;

  // Chat
  messages: Message[];
  conversations: Conversation[];
  activeConversationId: number | null;
  isStreaming: boolean;

  // Admin
  agents: Agent[];
  scanResult: ScanResult | null;

  // UI
  sidebarOpen: boolean;
  error: string | null;
  globalLoading: boolean;

  // Actions
  setToken: (token: string, user?: { email: string; role: string; org_id: number }) => void;
  logout: () => void;
  setPage: (page: Page) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  appendToLastMessage: (content: string) => void;
  setConversations: (convs: Conversation[]) => void;
  setActiveConversation: (id: number | null) => void;
  setStreaming: (streaming: boolean) => void;
  setAgents: (agents: Agent[]) => void;
  setScanResult: (result: ScanResult | null) => void;
  setError: (error: string | null) => void;
  setGlobalLoading: (loading: boolean) => void;
  toggleSidebar: () => void;
}

// ── Store Implementation ──────────────────────────────────────

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Initial state
      token: '',
      user: null,
      isAuthenticated: false,
      currentPage: 'chat',
      messages: [],
      conversations: [],
      activeConversationId: null,
      isStreaming: false,
      agents: [],
      scanResult: null,
      sidebarOpen: true,
      error: null,
      globalLoading: false,

      // Auth actions
      setToken: (token, user) =>
        set({
          token,
          user: user ?? null,
          isAuthenticated: true,
          error: null,
        }),

      logout: () =>
        set({
          token: '',
          user: null,
          isAuthenticated: false,
          messages: [],
          conversations: [],
          activeConversationId: null,
          scanResult: null,
          error: null,
        }),

      // Navigation
      setPage: (page) => set({ currentPage: page }),

      // Chat actions
      setMessages: (messages) => set({ messages }),
      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),

      appendToLastMessage: (content) =>
        set((state) => {
          const msgs = [...state.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'assistant') {
            msgs[msgs.length - 1] = { ...last, content: last.content + content };
          }
          return { messages: msgs };
        }),

      setConversations: (conversations) => set({ conversations }),
      setActiveConversation: (id) => set({ activeConversationId: id }),
      setStreaming: (isStreaming) => set({ isStreaming }),

      // Admin actions
      setAgents: (agents) => set({ agents }),
      setScanResult: (scanResult) => set({ scanResult }),

      // UI actions
      setError: (error) => set({ error }),
      setGlobalLoading: (loading) => set({ globalLoading: loading }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    }),
    {
      name: 'turin-platform-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
