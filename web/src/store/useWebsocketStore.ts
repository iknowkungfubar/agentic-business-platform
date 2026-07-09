/* WebSocket store — manages persistent WS connection with auto-reconnect.
 *
 * Connects to the platform's /ws endpoint, authenticates via stored JWT,
 * and dispatches incoming events to the Zustand store for reactive UI updates.
 */
import { create } from 'zustand';
import { useAppStore } from './useChatStore';

const WS_RECONNECT_DELAY = 3000;
const WS_MAX_RECONNECT_ATTEMPTS = 10;

interface WebSocketState {
  ws: WebSocket | null;
  connected: boolean;
  reconnectAttempts: number;
  connect: () => void;
  disconnect: () => void;
}

export const useWebsocketStore = create<WebSocketState>((set, get) => ({
  ws: null,
  connected: false,
  reconnectAttempts: 0,

  connect: () => {
    const state = get();
    if (state.ws?.readyState === WebSocket.OPEN) return;

    const token = useAppStore.getState().token;
    if (!token) return;

    const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = API_BASE.replace(/^http/, 'ws') + `/ws?token=${token}`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[WS] Connected');
        set({ connected: true, reconnectAttempts: 0 });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleEvent(data);
        } catch {
          // Ignore non-JSON messages (pongs, etc.)
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        set({ connected: false, ws: null });

        // Auto-reconnect
        const attempts = get().reconnectAttempts;
        if (attempts < WS_MAX_RECONNECT_ATTEMPTS) {
          setTimeout(() => {
            set({ reconnectAttempts: attempts + 1 });
            get().connect();
          }, WS_RECONNECT_DELAY * Math.min(attempts + 1, 5));
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      set({ ws });
    } catch (error) {
      console.error('[WS] Connection failed:', error);
    }
  },

  disconnect: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null, connected: false });
    }
  },
}));

function handleEvent(data: { type?: string }) {
  const type = data?.type;

  switch (type) {
    case 'document.ingested':
    case 'document.embedded':
      // Could trigger a document list refresh
      console.log('[WS] Document event:', data);
      break;

    case 'agent.status_changed':
      // Could trigger agent list refresh
      console.log('[WS] Agent status:', data);
      break;

    case 'billing.aggregated':
      // Could trigger billing refresh
      console.log('[WS] Billing event:', data);
      break;

    default:
      break;
  }
}
