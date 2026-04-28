import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Server, Lock, User, ArrowRight, Loader2, CheckCircle2, AlertCircle, Sparkles, ChartNoAxesCombined, Braces, ShieldCheck } from 'lucide-react';
import { ApiError, apiRequest, getApiBaseUrl } from '../lib/api';

const FEATURES = [
  {
    icon: ChartNoAxesCombined,
    title: 'Analytics-first workspace',
    text: 'A clean command center for asking, exploring, and iterating on live data.',
  },
  {
    icon: Braces,
    title: 'Natural language to SQL',
    text: 'Ask questions conversationally and inspect structured results without context switching.',
  },
  {
    icon: ShieldCheck,
    title: 'Professional by default',
    text: 'A polished surface for demos, internal tooling, and operator workflows.',
  },
];

const engineOptions = [
  { value: 'postgres', label: 'PostgreSQL', accent: 'from-sky-500 to-blue-600' },
  { value: 'mysql', label: 'MySQL', accent: 'from-amber-400 to-orange-500' },
];

const inputClassName =
  'w-full rounded-2xl border border-[rgba(229,221,209,0.95)] bg-white px-4 py-3.5 text-sm text-ink-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] transition duration-200 placeholder:text-ink-500/80 focus:border-accent-300 focus:outline-none focus:ring-4 focus:ring-accent-100';

export default function ConfigScreen({ onConfigure }) {
  const [formData, setFormData] = useState({
    db_type: 'postgres',
    host: 'localhost',
    port: '5432',
    user: '',
    password: '',
    db_name: ''
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;

    // Auto-update default ports if type changes and port hasn't been heavily customized
    if (name === 'db_type') {
      const defaultPort = value === 'postgres' ? '5432' : '3306';
      setFormData(prev => ({ ...prev, [name]: value, port: prev.port === '5432' || prev.port === '3306' ? defaultPort : prev.port }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const [connected, setConnected] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiRequest('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...formData, port: parseInt(formData.port, 10) }),
      });
      setConnected(true);
      setTimeout(() => onConfigure(data.session_id), 700);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.payload);
      } else {
        setError({
          title: 'Connection failed',
          message: err.message || 'An unexpected error occurred while connecting.',
          suggestions: [],
          issues: [],
          technical_details: null,
        });
      }
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      key="config"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, y: 12 }}
      transition={{ duration: 0.3 }}
      className="relative min-h-screen overflow-hidden"
    >
      <div className="pointer-events-none absolute inset-0 mesh-bg opacity-90" />
      <div className="pointer-events-none absolute inset-0 paper-grid opacity-35" />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-7xl flex-col px-5 py-6 sm:px-8 lg:grid lg:grid-cols-[1.08fr_0.92fr] lg:gap-8 lg:px-10 lg:py-8">
        <motion.section
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.05 }}
          className="mb-8 flex flex-col justify-between rounded-[2rem] hero-gradient px-6 py-7 text-white shadow-[0_30px_80px_rgba(16,32,51,0.16)] sm:px-8 sm:py-8 lg:mb-0"
        >
          <div>
            <div className="mb-10 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/14 ring-1 ring-white/18 backdrop-blur-sm">
                <Database className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-white/70">DataChat AI</p>
                <p className="text-sm text-white/70">Conversational database analysis</p>
              </div>
            </div>

            <div className="max-w-xl">
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-white/60">New Interface</p>
              <h1 className="max-w-lg text-4xl font-semibold leading-[1.02] tracking-[-0.04em] sm:text-5xl lg:text-6xl">
                A fresh frontend with a lighter, sharper, more executive feel.
              </h1>
              <p className="mt-5 max-w-lg text-base leading-7 text-white/76 sm:text-lg">
                This is a from-scratch surface, not a reskin. The layout is intentionally editorial on the left and operational on the right so the app feels like a serious data product, not a demo form.
              </p>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <div key={title} className="rounded-[1.5rem] border border-white/12 bg-white/10 p-5 backdrop-blur-md">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/14">
                    <Icon className="h-5 w-5" />
                  </div>
                  <p className="text-sm font-semibold tracking-[-0.01em]">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-white/72">{text}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-3 text-sm text-white/70">
            <span className="rounded-full bg-white/10 px-3 py-1.5">Claude 3.5 Sonnet</span>
            <span className="rounded-full bg-white/10 px-3 py-1.5">FastAPI</span>
            <span className="rounded-full bg-white/10 px-3 py-1.5">PostgreSQL + MySQL</span>
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.12 }}
          className="soft-card flex min-h-[620px] flex-col rounded-[2rem] p-4 sm:p-5"
        >
          <div className="flex items-center justify-between rounded-[1.5rem] border border-line/70 bg-white/70 px-5 py-4">
            <div>
              <p className="section-label">Connection</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-ink-950">Open a database session</h2>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-50 text-accent-700 ring-1 ring-accent-100">
              <Sparkles className="h-5 w-5" />
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {engineOptions.map((engine) => {
              const active = formData.db_type === engine.value;
              return (
                <button
                  key={engine.value}
                  type="button"
                  onClick={() => handleChange({ target: { name: 'db_type', value: engine.value } })}
                  className={`rounded-[1.4rem] border px-4 py-4 text-left transition duration-200 ${active ? 'border-accent-300 bg-accent-50 shadow-[0_12px_26px_rgba(63,131,248,0.12)]' : 'border-line bg-white/68 hover:border-accent-100 hover:bg-white'}`}
                >
                  <div className={`h-1.5 rounded-full bg-gradient-to-r ${engine.accent}`} />
                  <p className="mt-4 text-sm font-semibold text-ink-950">{engine.label}</p>
                  <p className="mt-1 text-xs text-ink-700">Optimized connection defaults</p>
                </button>
              );
            })}
            <div className="hidden rounded-[1.4rem] border border-dashed border-line/90 bg-white/45 p-4 sm:block">
              <p className="section-label">Mode</p>
              <p className="mt-3 text-sm font-semibold text-ink-950">Interactive session</p>
              <p className="mt-1 text-xs leading-5 text-ink-700">Establish a session, then move into a full conversational workspace.</p>
            </div>
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -10, height: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-4 rounded-[1.4rem] border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="font-semibold text-red-800">{error.title}</p>
                      <p className="mt-1 leading-6">{error.message}</p>

                      {error.issues?.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {error.issues.map((issue, index) => (
                            <div key={`${issue.label}-${index}`} className="rounded-2xl border border-red-100 bg-white/70 px-3 py-2.5">
                              <p className="font-medium text-red-800">{issue.label}</p>
                              <p className="mt-1 text-red-700/90">{issue.detail}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {error.suggestions?.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-700/80">What to check</p>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-red-700/95">
                            {error.suggestions.map((suggestion, index) => (
                              <li key={`${suggestion}-${index}`}>{suggestion}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {error.technical_details && (
                        <details className="mt-3 rounded-2xl border border-red-100 bg-white/70 px-3 py-2.5">
                          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-red-700/80">
                            Technical details
                          </summary>
                          <p className="mt-2 break-words font-mono text-xs leading-5 text-red-800/85">
                            {error.technical_details}
                          </p>
                        </details>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit} className="mt-5 flex flex-1 flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-[1.6fr_0.7fr]">
              <label className="block">
                <span className="section-label">Host</span>
                <div className="relative mt-2">
                  <Server className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
                  <input type="text" name="host" value={formData.host} onChange={handleChange} required placeholder="localhost" className={`${inputClassName} pl-11`} />
                </div>
              </label>

              <label className="block">
                <span className="section-label">Port</span>
                <input type="number" name="port" value={formData.port} onChange={handleChange} required className={`${inputClassName} mt-2`} />
              </label>
            </div>

            <label className="block">
              <span className="section-label">Database Name</span>
              <div className="relative mt-2">
                <Database className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
                <input type="text" name="db_name" value={formData.db_name} onChange={handleChange} required placeholder="analytics" className={`${inputClassName} pl-11`} />
              </div>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="section-label">Username</span>
                <div className="relative mt-2">
                  <User className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
                  <input type="text" name="user" value={formData.user} onChange={handleChange} required placeholder="postgres" className={`${inputClassName} pl-11`} />
                </div>
              </label>

              <label className="block">
                <span className="section-label">Password</span>
                <div className="relative mt-2">
                  <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
                  <input type="password" name="password" value={formData.password} onChange={handleChange} placeholder="••••••••" className={`${inputClassName} pl-11`} />
                </div>
              </label>
            </div>

            <div className="mt-auto rounded-[1.6rem] border border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(248,244,236,0.9))] px-5 py-5">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <p className="section-label">Launch</p>
                  <p className="mt-2 text-sm leading-6 text-ink-700">
                    Start a connection session and move directly into the redesigned chat workspace.
                  </p>
                  <p className="mt-2 text-xs text-ink-500">
                    API target: {getApiBaseUrl()}/api/config
                  </p>
                </div>
                <div className="hidden rounded-full bg-gold-200/50 px-3 py-1 text-xs font-semibold text-ink-800 sm:block">Fresh light UI</div>
              </div>

              <motion.button
                type="submit"
                whileHover={{ scale: 1.01, y: -1 }}
                whileTap={{ scale: 0.99 }}
                disabled={isLoading || connected}
                className="flex w-full items-center justify-center gap-2 rounded-[1.2rem] bg-ink-950 px-5 py-4 text-sm font-semibold text-white shadow-[0_16px_30px_rgba(16,32,51,0.18)] transition hover:bg-[#18324c] disabled:opacity-65"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Connecting…
                  </>
                ) : connected ? (
                  <>
                    <CheckCircle2 className="h-4 w-4" />
                    Connected
                  </>
                ) : (
                  <>
                    Enter Workspace
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </motion.button>
            </div>
          </form>
        </motion.section>
      </div>
    </motion.div>
  );
}
