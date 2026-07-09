import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '../store/useChatStore';
import { chatApi, createChatStream } from '../api/client';
import { Send, Plus } from 'lucide-react';

export function ChatArea() {
  const { t } = useTranslation();
  const { conversationId: paramId } = useParams();
  const token = useAppStore((s) => s.token);
  const messages = useAppStore((s) => s.messages);
  const conversations = useAppStore((s) => s.conversations);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const setMessages = useAppStore((s) => s.setMessages);
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const setConversations = useAppStore((s) => s.setConversations);
  const setActiveConversation = useAppStore((s) => s.setActiveConversation);
  const setStreaming = useAppStore((s) => s.setStreaming);
  const activeConversationId = useAppStore((s) => s.activeConversationId);

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load conversations on mount
  useEffect(() => {
    chatApi.getConversations().then(setConversations).catch(() => {});
  }, [setConversations]);

  // Load messages when conversation changes
  useEffect(() => {
    const convId = paramId ? Number(paramId) : null;
    setActiveConversation(convId);
    if (convId) {
      chatApi.getMessages(convId).then(setMessages).catch(() => setMessages([]));
    } else {
      setMessages([]);
    }
  }, [paramId, setActiveConversation, setMessages]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');

    // Add user message immediately
    addMessage({
      id: Date.now(),
      role: 'user',
      content: text,
      model_tier: '',
    });

    // Add placeholder assistant message
    addMessage({
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      model_tier: '',
    });

    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    createChatStream(
      text,
      activeConversationId,
      token,
      (tokenText) => appendToLastMessage(tokenText),
      (convId) => {
        setActiveConversation(convId);
        // Refresh conversations list
        chatApi.getConversations().then(setConversations).catch(() => {});
      },
      () => setStreaming(false),
      controller.signal,
    );
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleNewChat() {
    setActiveConversation(null);
    setMessages([]);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="h-16 border-b border-slate-700 flex items-center justify-between px-6">
        <h2 className="text-lg font-semibold">AI Chat</h2>
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2 text-sm bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={16} /> New Chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4" role="log" aria-live="polite" aria-label="Chat messages">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-slate-500 text-lg">{t('chat.emptyTitle')}</p>
              <p className="text-slate-600 text-sm mt-1">{t('chat.emptySubtitle')}</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            role="article"
            aria-label={`${msg.role === 'user' ? 'Your' : 'AI'} message`}
          >
            <div
              className={`max-w-[75%] rounded-xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-emerald-600/20 text-slate-100'
                  : 'bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.model_tier && (
                <p className="text-xs text-slate-500 mt-1">Tier: {msg.model_tier}</p>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-700 px-6 py-4">
        <div className="flex gap-3" role="form" aria-label="Message input">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? t('chat.streamingPlaceholder') : t('chat.inputPlaceholder')}
            disabled={isStreaming}
            aria-label={t('chat.inputPlaceholder')}
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            aria-label="Send message"
            className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white rounded-xl px-4 py-3 transition-colors disabled:cursor-not-allowed"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
