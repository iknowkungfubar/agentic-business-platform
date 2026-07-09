import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ChatArea } from './ChatArea';

const mockState = {
  token: 'test-token',
  messages: [],
  conversations: [],
  isStreaming: false,
  activeConversationId: null,
  setMessages: vi.fn(),
  addMessage: vi.fn(),
  appendToLastMessage: vi.fn(),
  setConversations: vi.fn(),
  setActiveConversation: vi.fn(),
  setStreaming: vi.fn(),
};

vi.mock('../store/useChatStore', () => ({
  useAppStore: (selector: any) => {
    return selector ? selector(mockState) : mockState;
  },
}));

vi.mock('../api/client', () => ({
  chatApi: {
    getConversations: vi.fn().mockResolvedValue([]),
    getMessages: vi.fn().mockResolvedValue([]),
  },
  createChatStream: vi.fn(),
}));

describe('ChatArea', () => {
  it('renders the chat interface title', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<ChatArea />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('AI Chat')).toBeTruthy();
  });

  it('renders the input field', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<ChatArea />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText('chat.inputPlaceholder')).toBeTruthy();
  });

  it('shows empty state', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<ChatArea />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('chat.emptyTitle')).toBeTruthy();
  });
});
