/* Enterprise API client for TurinTech Platform.
 *
 * Axios-free fetch wrapper with:
 * - Automatic Bearer token injection
 * - 401 Unauthorized force-logout
 * - Global error handling with structured error extraction
 * - Request/response type safety
 */
import { useAppStore, type Agent, type Conversation, type Message, type ScanResult } from '../store/useChatStore';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Error Types ───────────────────────────────────────────────

export class ApiError extends Error {
  statusCode: number;
  code: string;
  requestId?: string;

  constructor(statusCode: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.code = code;
    this.requestId = requestId;
  }
}

// ── Core Request Function ─────────────────────────────────────

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, signal } = options;
  const token = useAppStore.getState().token;

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: requestHeaders,
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });

    // Handle 401 — force logout
    if (response.status === 401) {
      useAppStore.getState().logout();
      throw new ApiError(401, 'UNAUTHORIZED', 'Session expired. Please log in again.');
    }

    // Parse structured error responses
    if (!response.ok) {
      let errorData: { error?: { code?: string; message?: string; request_id?: string } } = {};
      try {
        errorData = await response.json();
      } catch {
        // Response body not JSON
      }

      const apiError = errorData?.error;
      throw new ApiError(
        response.status,
        apiError?.code || `HTTP_${response.status}`,
        apiError?.message || `Request failed with status ${response.status}`,
        apiError?.request_id,
      );
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, 'REQUEST_ABORTED', 'Request was cancelled');
    }
    throw new ApiError(0, 'NETWORK_ERROR', (error as Error).message || 'Network request failed');
  }
}

// ── Auth API ──────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: { email: string; role: string; org_id: number } }>(
      '/api/v1/auth/login',
      { method: 'POST', body: { email, password } },
    ),

  register: (email: string, password: string, org_name?: string) =>
    request<{ access_token: string; user: { email: string; role: string; org_id: number } }>(
      '/api/v1/auth/register',
      { method: 'POST', body: { email, password, org_name } },
    ),
};

// ── Chat API ──────────────────────────────────────────────────

export const chatApi = {
  getConversations: () =>
    request<Conversation[]>('/api/v1/conversations'),

  getMessages: (conversationId: number) =>
    request<Message[]>(`/api/v1/conversations/${conversationId}/messages`),

  classify: (text: string) =>
    request<{ intent: string; confidence: number }>('/api/v1/classify', {
      method: 'POST',
      body: { text },
    }),

  // SSE streaming chat — returns the EventSource URL
  getChatStreamUrl: (message: string, conversationId?: number) => {
    const params = new URLSearchParams({ message });
    if (conversationId) params.set('conversation_id', String(conversationId));
    return `${API_BASE}/api/v1/chat/stream?${params}`;
  },
};

// ── Admin API ─────────────────────────────────────────────────

export const adminApi = {
  listAgents: (page = 1, pageSize = 50) =>
    request<{ items: Agent[]; total: number; page: number; page_size: number }>(
      `/api/v1/agents?page=${page}&page_size=${pageSize}`,
    ),

  registerAgent: (name: string, url: string, provider?: string) =>
    request<Agent>('/api/v1/agents', {
      method: 'POST',
      body: { name, url, provider },
    }),

  checkAgentHealth: (agentId: number) =>
    request<{ id: number; status: string; last_seen: string }>(
      `/api/v1/agents/${agentId}/health`,
      { method: 'POST' },
    ),

  scanMcp: (url: string, timeout = 5) =>
    request<ScanResult>('/api/v1/scan-mcp', {
      method: 'POST',
      body: { url, timeout },
    }),

  listPolicies: () =>
    request<{ frameworks: string[]; policies: unknown[]; total: number }>('/api/v1/policies'),

  getDashboard: () => request<string>('/admin/dashboard'),
};

// ── SSE Streaming Consumer ────────────────────────────────────

export function createChatStream(
  message: string,
  conversationId: number | null,
  token: string,
  onToken: (token: string) => void,
  onDone: (conversationId: number) => void,
  onError: (error: Error) => void,
  signal?: AbortSignal,
): void {
  const params = new URLSearchParams({ message });
  if (conversationId) params.set('conversation_id', String(conversationId));

  fetch(`${API_BASE}/api/v1/chat/stream?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Stream failed' }));
        throw new Error(err.detail || err.error?.message || 'Stream failed');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.token) {
                onToken(parsed.token);
              }
              if (parsed.conversation_id) {
                onDone(parsed.conversation_id);
              }
            } catch {
              // Skip malformed SSE frames
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') return;
      onError(error);
    });
}
