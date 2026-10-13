import { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare, Send, Shield, ThumbsUp, ThumbsDown,
  Sparkles, AlertCircle, Plus, RefreshCw, FileText, X,
} from 'lucide-react';
import { Card, Button, Drawer, Spinner, EmptyState, ErrorState } from '@/components/ui';
import { api } from '@/lib/api';
import { formatTime } from '@/lib/format';
import type { ChatMessage, ChatSource, Conversation } from '@/lib/types';

const SUGGESTED_QUESTIONS = [
  'Quel est mon plafond de remboursement dentaire ?',
  'Où en est mon dossier du 12 septembre ?',
  'Qu\'est-ce qui est exclu de mon contrat ?',
];

function renderMarkdown(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .split('\n')
    .map((line, i) => `<p key="${i}">${line || '&nbsp;'}</p>`)
    .join('');
}

export function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState(false);
  const [sources, setSources] = useState<ChatSource[]>([]);
  const [drawerSource, setDrawerSource] = useState<ChatSource | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.getConversations().then((data) => {
      setConversations(data.conversations);
      if (data.conversations.length > 0) {
        setActiveConvId(data.conversations[0].id);
        setMessages(data.conversations[0].messages);
      }
      setLoadingHistory(false);
    }).catch(() => setLoadingHistory(false));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, typing]);

  const adjustTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, []);

  const handleSend = async (text?: string) => {
    const content = (text || input).trim();
    if (!content || sending) return;

    setError(false);
    setInput('');

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);

    setSending(true);
    setTyping(true);

    try {
      const resp = await api.sendMessage(activeConvId, content);
      setTyping(false);

      // Streaming effect
      const words = resp.answer.split(' ');
      let current = '';
      for (let i = 0; i < words.length; i++) {
        current += (i > 0 ? ' ' : '') + words[i];
        setStreamingText(current);
        await new Promise((r) => setTimeout(r, 20));
      }

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: resp.answer,
        timestamp: new Date().toISOString(),
        sources: resp.sources,
        feedback: null,
      };
      setMessages((m) => [...m, assistantMsg]);
      setStreamingText('');
      setSources(resp.sources);

      if (!activeConvId) {
        setActiveConvId(resp.conversation_id);
      }
    } catch {
      setError(true);
      setTyping(false);
    } finally {
      setSending(false);
      setTimeout(adjustTextarea, 0);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFeedback = (msgId: string, feedback: 'up' | 'down') => {
    setMessages((m) =>
      m.map((msg) =>
        msg.id === msgId ? { ...msg, feedback: msg.feedback === feedback ? null : feedback } : msg
      )
    );
  };

  const newConversation = () => {
    setMessages([]);
    setActiveConvId(null);
    setStreamingText('');
    setSources([]);
    setError(false);
  };

  const charCount = input.length;
  const maxChars = 1000;

  return (
    <div className="flex gap-4 h-[calc(100vh-13.5rem)]">
      {/* Conversation list */}
      <div className="hidden lg:flex w-64 flex-shrink-0 flex-col">
        <Card className="p-3 flex-1 flex flex-col">
          <Button variant="outline" size="sm" className="w-full mb-3" onClick={newConversation}>
            <Plus className="w-4 h-4" /> Nouvelle conversation
          </Button>
          <div className="flex-1 overflow-y-auto scrollbar-thin space-y-1">
            {loadingHistory ? (
              <div className="space-y-2 p-2">
                {[1, 2].map((i) => <div key={i} className="skeleton h-16 rounded-2xl" />)}
              </div>
            ) : conversations.length === 0 ? (
              <p className="text-xs text-surface-400 p-3 text-center">Aucune conversation</p>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => {
                    setActiveConvId(conv.id);
                    setMessages(conv.messages);
                    setStreamingText('');
                  }}
                  className={`w-full text-left px-4 py-3 rounded-2xl transition-all ${
                    activeConvId === conv.id
                      ? 'bg-surface-200 dark:bg-surface-700'
                      : 'hover:bg-surface-200/60 dark:hover:bg-surface-700'
                  }`}
                >
                  <p className="text-sm font-medium text-surface-700 dark:text-surface-200 truncate">{conv.title}</p>
                  <p className="text-xs text-surface-400 truncate mt-0.5">{conv.last_message}</p>
                </button>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* AI disclaimer banner */}
        <div className="mb-3 flex items-center gap-2.5 px-4 py-2.5 rounded-2xl bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 text-sm text-primary-700 dark:text-primary-300">
          <Shield className="w-4 h-4 flex-shrink-0 text-primary-500" />
          <span>Vous échangez avec un assistant IA. Il peut se tromper : vérifiez les informations importantes.</span>
        </div>

        <Card className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto scrollbar-thin p-4 md:p-6">
            {messages.length === 0 && !streamingText && !typing ? (
              <EmptyState
                icon={<Sparkles className="w-8 h-8" />}
                title="Comment puis-je vous aider ?"
                description="Posez une question sur votre contrat, vos remboursements ou l'état de vos dossiers."
                action={
                  <div className="flex flex-wrap gap-2 justify-center mt-2">
                    {SUGGESTED_QUESTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={() => handleSend(q)}
                        className="px-3 py-2 rounded-xl text-sm bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 text-primary-700 dark:text-primary-300 hover:bg-primary-100 dark:hover:bg-primary-800/40 transition-all"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                }
              />
            ) : (
              <div className="space-y-4">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}>
                    {msg.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                        <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-300" />
                      </div>
                    )}
                    <div className={`max-w-[75%] ${msg.role === 'user' ? 'order-2' : ''}`}>
                      <div className={`rounded-2xl px-5 py-3 ${
                        msg.role === 'user'
                          ? 'bg-surface-200 dark:bg-surface-700 text-surface-900 dark:text-surface-50 rounded-br-md'
                          : 'bg-transparent text-surface-800 dark:text-surface-100 px-0'
                      }`}>
                        <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className="text-xs text-surface-400">{formatTime(msg.timestamp)}</span>
                        {msg.role === 'assistant' && (
                          <>
                            {msg.sources && msg.sources.length > 0 && (
                              <div className="flex gap-1.5">
                                {msg.sources.map((src, i) => (
                                  <button
                                    key={i}
                                    onClick={() => setDrawerSource(src)}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-white dark:bg-surface-600 text-primary-600 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-800/40 transition-all"
                                  >
                                    <FileText className="w-3 h-3" />
                                    {src.document} - p. {src.page}
                                  </button>
                                ))}
                              </div>
                            )}
                            <div className="flex gap-1 ml-auto">
                              <button
                                onClick={() => handleFeedback(msg.id, 'up')}
                                className={`p-1 rounded ${msg.feedback === 'up' ? 'text-success-600 bg-success-50 dark:bg-success-900/30' : 'text-surface-400 hover:text-surface-600'}`}
                              >
                                <ThumbsUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleFeedback(msg.id, 'down')}
                                className={`p-1 rounded ${msg.feedback === 'down' ? 'text-danger-600 bg-danger-50 dark:bg-danger-900/30' : 'text-surface-400 hover:text-surface-600'}`}
                              >
                                <ThumbsDown className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                    {msg.role === 'user' && (
                      <div className="w-8 h-8 rounded-lg bg-kraft-100 dark:bg-kraft-800 flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-semibold text-kraft-700 dark:text-kraft-300">Moi</span>
                      </div>
                    )}
                  </div>
                ))}

                {/* Typing indicator */}
                {typing && (
                  <div className="flex gap-3 animate-slide-up">
                    <div className="w-8 h-8 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-300" />
                    </div>
                    <div className="bg-white dark:bg-surface-700 rounded-2xl rounded-bl-lg shadow-soft px-5 py-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-surface-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 rounded-full bg-surface-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 rounded-full bg-surface-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}

                {/* Streaming message */}
                {streamingText && !typing && (
                  <div className="flex gap-3 animate-slide-up">
                    <div className="w-8 h-8 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-300" />
                    </div>
                    <div className="max-w-[75%]">
                      <div className="rounded-2xl rounded-bl-lg px-5 py-3 bg-white dark:bg-surface-700 shadow-soft">
                        <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }} />
                      </div>
                    </div>
                  </div>
                )}

                {error && (
                  <ErrorState
                    message="Une erreur est survenue. Vérifiez votre connexion et réessayez."
                    onRetry={() => { setError(false); handleSend(messages[messages.length - 1]?.content); }}
                  />
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Composer */}
          <div className=" p-3 md:p-4">
            <div className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => { setInput(e.target.value); adjustTextarea(); }}
                  onKeyDown={handleKeyDown}
                  placeholder="Écrivez votre message..."
                  maxLength={maxChars}
                  className="chat-textarea w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 text-surface-900 dark:text-surface-100 placeholder-surface-400 px-4 py-3 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:focus:ring-primary-900/40 scrollbar-thin"
                  rows={1}
                />
                <span className="absolute right-3 bottom-2 text-xs text-surface-400 tabular-nums">
                  {charCount}/{maxChars}
                </span>
              </div>
              <Button
                onClick={() => handleSend()}
                disabled={!input.trim() || sending}
                className="!rounded-2xl"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-xs text-surface-400 mt-2">Entrée pour envoyer · Maj+Entrée pour un saut de ligne</p>
          </div>
        </Card>
      </div>

      {/* Source drawer */}
      <Drawer open={!!drawerSource} onClose={() => setDrawerSource(null)} title="Source citée" width="md">
        {drawerSource && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-primary-600" />
              <div>
                <p className="font-semibold text-surface-800 dark:text-surface-100">{drawerSource.document}</p>
                <p className="text-sm text-surface-400">Page {drawerSource.page}</p>
              </div>
            </div>
            <div className="rounded-xl border border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50 p-4">
              <p className="text-sm text-surface-700 dark:text-surface-200 italic leading-relaxed">
                « {drawerSource.excerpt} »
              </p>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
