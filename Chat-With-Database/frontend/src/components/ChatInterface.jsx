import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, User, Database, Loader2, Power, Copy, Check, Menu, Sparkles, Table2, Hash, ListTree, Search, ArrowUpRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ApiError, apiRequest } from '../lib/api';

// ─── Copy-button helper ─────────────────────────────────────────
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="flex items-center gap-1 rounded-full border border-line/90 bg-white px-2.5 py-1 text-[10px] font-mono text-ink-700 transition hover:border-accent-100 hover:text-accent-700"
    >
      {copied ? <><Check className="h-3 w-3 text-emerald-600" /> Copied</> : <><Copy className="h-3 w-3" /> Copy</>}
    </button>
  );
}

// ─── Code block for react-markdown ─────────────────────────────
function CodeBlock({ children, className }) {
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : 'sql';
  const code = String(children).replace(/\n$/, '');
  return (
    <div className="my-4 overflow-hidden rounded-[1.2rem] border border-line bg-white shadow-[0_10px_30px_rgba(111,89,57,0.07)]">
      <div className="flex items-center justify-between border-b border-line bg-[#fbf7ef] px-4 py-3">
        <span className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-ink-700">{lang}</span>
        <CopyButton text={code} />
      </div>
      <SyntaxHighlighter
        language={lang}
        style={oneLight}
        customStyle={{ margin: 0, borderRadius: 0, background: '#fffdf8', fontSize: '0.82rem', lineHeight: '1.7', padding: '1rem' }}
        showLineNumbers={code.split('\n').length > 3}
        lineNumberStyle={{ color: '#7c94ad', fontSize: '0.72rem', minWidth: '2.4em' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

const mdComponents = {
  code({ children, className, node, ...rest }) {
    const isBlock = /language-/.test(className || '');
    if (isBlock) return <CodeBlock className={className}>{children}</CodeBlock>;
    return <code {...rest} className={className}>{children}</code>;
  },
  pre({ children }) { return <>{children}</>; },
  table({ children }) {
    return (
      <div className="my-4 overflow-x-auto rounded-[1.2rem] border border-line bg-white shadow-[0_8px_20px_rgba(111,89,57,0.05)]">
        <table>{children}</table>
      </div>
    );
  },
};

// ─── Quick-prompt suggestions ───────────────────────────────────
const SUGGESTIONS = [
  { icon: Table2, label: 'List all tables', prompt: 'List all tables in the database' },
  { icon: ListTree, label: 'Schema overview', prompt: 'Give me an overview of the database schema' },
  { icon: Hash, label: 'Row counts', prompt: 'Show the row count for every table' },
  { icon: Search, label: 'Sample rows', prompt: 'Show 5 sample rows from each table' },
];

const insights = [
  { value: 'Live', label: 'Connection state' },
  { value: 'SQL', label: 'Structured answers' },
  { value: 'Fast', label: 'Low-friction iteration' },
];

export default function ChatInterface({ sessionId, onDisconnect }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: "Hey! I'm connected to your database and ready to help. Ask me anything — describe a table, run an analysis, or find patterns in your data."
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const formatApiErrorForChat = useCallback((payload) => {
    const sections = [];

    if (payload?.title) {
      sections.push(payload.title);
    }

    if (payload?.message) {
      sections.push(payload.message);
    }

    if (payload?.issues?.length) {
      sections.push(
        ['Issues found:', ...payload.issues.map((issue) => `- ${issue.label}: ${issue.detail}`)].join('\n')
      );
    }

    if (payload?.suggestions?.length) {
      sections.push(
        ['What to check:', ...payload.suggestions.map((suggestion) => `- ${suggestion}`)].join('\n')
      );
    }

    return sections.join('\n\n');
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = useCallback(async (text) => {
    const content = (text || input).trim();
    if (!content || isLoading) return;

    const userMsg = { id: Date.now(), role: 'user', content };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setIsLoading(true);

    try {
      const data = await apiRequest('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: content }),
      });
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: data.response }]);
    } catch (error) {
      const systemMessage = error instanceof ApiError
        ? {
            id: Date.now() + 1,
            role: 'system',
            content: formatApiErrorForChat(error.payload),
            errorDetails: error.payload,
          }
        : {
            id: Date.now() + 1,
            role: 'system',
            content: `Error: ${error.message}`,
          };
      setMessages(prev => [...prev, systemMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [formatApiErrorForChat, input, isLoading, sessionId]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <motion.div
      key="chat"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ duration: 0.3 }}
      className="relative min-h-screen overflow-hidden"
    >
      <div className="pointer-events-none absolute inset-0 mesh-bg opacity-90" />
      <div className="pointer-events-none absolute inset-0 paper-grid opacity-25" />

      <div className="relative z-10 flex min-h-screen gap-5 px-4 py-4 sm:px-6 lg:px-8">
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 300, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="hidden min-w-[300px] flex-col rounded-[2rem] soft-card md:flex"
              style={{ width: 300 }}
            >
              <div className="border-b border-line/80 px-6 py-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl hero-gradient text-white shadow-[0_12px_26px_rgba(16,32,51,0.14)]">
                    <Database className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="section-label">Workspace</p>
                    <p className="mt-1 text-lg font-semibold tracking-[-0.03em] text-ink-950">DataChat AI</p>
                  </div>
                </div>
              </div>

              <div className="px-6 pt-5">
                <div className="rounded-[1.5rem] border border-line bg-white/80 p-4">
                  <p className="section-label">Session</p>
                  <div className="mt-3 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span className="text-sm font-semibold text-ink-950">Connected</span>
                  </div>
                  <p className="mt-2 truncate text-xs font-mono text-ink-700">{sessionId}</p>
                </div>
              </div>

              <div className="px-6 pt-5">
                <p className="section-label">Highlights</p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {insights.map((item) => (
                    <div key={item.label} className="rounded-[1.2rem] border border-line bg-white px-3 py-3 text-center">
                      <p className="text-sm font-semibold text-ink-950">{item.value}</p>
                      <p className="mt-1 text-[11px] leading-4 text-ink-700">{item.label}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto custom-scrollbar px-4 pb-4 pt-5">
                <p className="section-label px-2">Quick prompts</p>
                <div className="mt-3 space-y-2">
                {SUGGESTIONS.map(({ icon: Icon, label, prompt }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => handleSubmit(prompt)}
                    disabled={isLoading}
                    className="group flex w-full items-center justify-between rounded-[1.3rem] border border-line bg-white px-4 py-4 text-left transition hover:-translate-y-0.5 hover:border-accent-100 hover:shadow-[0_12px_24px_rgba(63,131,248,0.08)] disabled:opacity-40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent-50 text-accent-700">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-ink-950">{label}</p>
                        <p className="mt-1 text-xs text-ink-700">Run this prompt instantly</p>
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-ink-500 transition group-hover:text-accent-700" />
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-line/80 p-5">
              <button
                type="button"
                onClick={onDisconnect}
                className="flex w-full items-center justify-center gap-2 rounded-[1.2rem] border border-line bg-white px-4 py-3 text-sm font-semibold text-ink-800 transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
              >
                <Power className="h-4 w-4" />
                Disconnect
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[2rem] soft-card">
        <header className="flex flex-shrink-0 items-center gap-3 border-b border-line/80 px-5 py-4 sm:px-6">
          <button
            type="button"
            onClick={() => setSidebarOpen(o => !o)}
            className="hidden h-11 w-11 items-center justify-center rounded-2xl border border-line bg-white text-ink-700 transition hover:border-accent-100 hover:text-accent-700 md:flex"
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>

          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="flex h-11 w-11 items-center justify-center rounded-2xl border border-line bg-white text-ink-700 transition hover:border-accent-100 hover:text-accent-700 md:hidden"
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="min-w-0 flex-1">
            <p className="section-label">Active Workspace</p>
            <div className="mt-1 flex items-center gap-3">
              <h1 className="truncate text-xl font-semibold tracking-[-0.03em] text-ink-950 sm:text-2xl">Chat with your database</h1>
              <span className="hidden rounded-full bg-accent-50 px-3 py-1 text-xs font-semibold text-accent-700 sm:inline-flex">Session live</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onDisconnect}
            className="flex items-center gap-2 rounded-2xl border border-line bg-white px-4 py-2.5 text-sm font-semibold text-ink-800 transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
          >
            <Power className="h-4 w-4" />
            Disconnect
          </button>
        </header>

        <main className="custom-scrollbar flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto flex max-w-4xl flex-col gap-6">
            <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-[1.6rem] border border-line bg-white px-5 py-5 shadow-[0_12px_26px_rgba(111,89,57,0.06)]">
                <p className="section-label">Welcome</p>
                <p className="mt-3 max-w-2xl text-base leading-7 text-ink-800">
                  Ask analytical questions in plain English and inspect the output in a refined, readable workspace built for demos and daily operations.
                </p>
              </div>
              <div className="soft-panel rounded-[1.6rem] px-5 py-5">
                <p className="section-label">Suggested starting point</p>
                <p className="mt-3 text-sm leading-6 text-ink-800">Start with schema exploration, then move into row counts, joins, and custom analysis prompts.</p>
              </div>
            </div>

            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-accent-50 text-accent-700 ring-1 ring-accent-100">
                    <Sparkles className="h-4 w-4" />
                  </div>
                )}

                <div className={`max-w-[92%] ${msg.role === 'user' ? 'sm:max-w-[72%]' : 'flex-1'}`}>
                  {msg.role === 'user' ? (
                    <div className="rounded-[1.7rem] rounded-tr-md border border-accent-100 bg-accent-50 px-5 py-4 text-sm leading-7 text-ink-950 shadow-[0_10px_24px_rgba(63,131,248,0.08)]">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ) : msg.role === 'system' ? (
                    <div className="rounded-[1.6rem] rounded-tl-md border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                      {msg.errorDetails ? (
                        <div>
                          <p className="font-semibold text-red-800">{msg.errorDetails.title}</p>
                          <p className="mt-2 leading-6">{msg.errorDetails.message}</p>

                          {msg.errorDetails.issues?.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {msg.errorDetails.issues.map((issue, index) => (
                                <div key={`${issue.label}-${index}`} className="rounded-2xl border border-red-100 bg-white/70 px-3 py-2.5">
                                  <p className="font-medium text-red-800">{issue.label}</p>
                                  <p className="mt-1 leading-6 text-red-700">{issue.detail}</p>
                                </div>
                              ))}
                            </div>
                          )}

                          {msg.errorDetails.suggestions?.length > 0 && (
                            <div className="mt-3">
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-700/80">What to check</p>
                              <ul className="mt-2 list-disc space-y-1 pl-5 text-red-700">
                                {msg.errorDetails.suggestions.map((suggestion, index) => (
                                  <li key={`${suggestion}-${index}`}>{suggestion}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      )}
                    </div>
                  ) : (
                    <div className="message-prose rounded-[1.7rem] rounded-tl-md border border-line bg-white px-5 py-5 text-sm shadow-[0_16px_32px_rgba(111,89,57,0.07)]">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl border border-line bg-white text-ink-700">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </motion.div>
            ))}

            <AnimatePresence>
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="flex gap-3 justify-start"
                >
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-accent-50 text-accent-700 ring-1 ring-accent-100">
                    <Sparkles className="h-4 w-4 animate-pulse" />
                  </div>
                  <div className="flex items-center gap-3 rounded-[1.6rem] rounded-tl-md border border-line bg-white px-5 py-4 shadow-[0_12px_24px_rgba(111,89,57,0.06)]">
                    <div className="flex items-center gap-1.5">
                      {[0, 150, 300].map(delay => (
                        <motion.div
                          key={delay}
                          className="h-2 w-2 rounded-full bg-accent-500"
                          animate={{ scale: [1, 1.6, 1], opacity: [0.4, 1, 0.4] }}
                          transition={{ duration: 1.2, delay: delay / 1000, repeat: Infinity }}
                        />
                      ))}
                    </div>
                    <span className="text-sm font-medium text-ink-700">Analyzing database…</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>
        </main>

        <footer className="border-t border-line/80 bg-white/70 px-4 py-5 backdrop-blur-xl sm:px-6">
          <div className="mx-auto max-w-4xl">
            {messages.length === 1 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 flex flex-wrap gap-2"
              >
                {SUGGESTIONS.map(({ icon: Icon, label, prompt }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => handleSubmit(prompt)}
                    disabled={isLoading}
                    className="flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-accent-100 hover:bg-accent-50 hover:text-accent-700 disabled:opacity-40"
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </button>
                ))}
              </motion.div>
            )}

            <div className="rounded-[1.8rem] border border-line bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(251,247,239,0.96))] p-3 shadow-[0_14px_28px_rgba(111,89,57,0.08)]">
              <div className="flex items-end gap-3 rounded-[1.2rem] bg-white px-4 py-3 ring-1 ring-line/70 transition focus-within:ring-accent-300">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about revenue, funnels, joins, missing records, or schema details…"
                rows={1}
                className="custom-scrollbar min-h-[48px] max-h-48 flex-1 resize-none bg-transparent py-2 text-sm leading-7 text-ink-950 placeholder:text-ink-500 focus:outline-none"
                onInput={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 192) + 'px';
                }}
              />

              <motion.button
                type="button"
                onClick={() => handleSubmit()}
                disabled={!input.trim() || isLoading}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="mb-1 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-ink-950 text-white shadow-[0_16px_28px_rgba(16,32,51,0.18)] transition hover:bg-[#18324c] disabled:bg-ink-500 disabled:shadow-none"
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </motion.button>
            </div>
            </div>

            <p className="mt-2 text-center text-[11px] text-ink-700">
              Enter to send · Shift+Enter for newline · Markdown tables and SQL blocks are rendered cleanly
            </p>
          </div>
        </footer>
      </div>
      </div>
    </motion.div>
  );
}
