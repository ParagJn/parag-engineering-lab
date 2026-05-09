import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { motion } from 'framer-motion'
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Sparkles,
  UploadCloud,
} from 'lucide-react'
import { analyzeDocument, askFollowUp, downloadMarkdown, uploadDocument } from './api'
import { createVisual, downloadFromUrl } from './api'

const modes = [
  { id: 'summarize', label: 'Summarize', detail: 'Executive narrative, key decisions, risks' },
  { id: 'identify_gaps', label: 'Identify Gaps', detail: 'Execution gaps, assumptions, missing controls' },
  { id: 'give_suggestions', label: 'Give Suggestions', detail: 'Practical improvements and stronger next steps' },
]

const samplePrompts = {
  summarize: `Analyze this document carefully and produce an executive-ready summary.

Focus on:
- The current state and the main business or technology pain points.
- The proposed target state and the intended business outcomes.
- The major recommendations, decisions requested, and dependencies.
- The cost, delivery timeline, risk, governance, and operating model implications.
- Any assumptions that leadership should understand before approving the approach.

Output format:
- Start with a concise executive summary.
- Then provide bullet points grouped by Current State, Target State, Key Decisions, Risks, Cost/Benefit, and Next Steps.
- If the document includes slide or page numbers, reference them where relevant.
- Do not critique the document unless a point is necessary to understand the summary.`,

  identify_gaps: `Review this document as a senior strategy, data architecture, and transformation advisor. Identify only meaningful gaps that could affect execution, approval, cost, risk, or the ability to reach the target state.

Focus on:
- Gaps between current state and target state.
- Missing interim steps, migration controls, ownership, decision gates, or governance.
- Weak assumptions around cost, implementation complexity, delivery timeline, cloud infrastructure, data quality, security, or change management.
- Areas where the proposal may create avoidable technical debt or rework.
- Missing success metrics, value-tracking measures, or operating model details.

Output format:
- Use bullet points grouped by slide/page number where possible.
- For each gap, include: Gap, Why it matters, Suggested fix, and Expected benefit.
- Be constructive and practical. The goal is not to find faults, but to improve confidence that the target state can actually be reached.
- If the material is already strong in an area, explicitly acknowledge that no change is needed.`,

  give_suggestions: `Analyze this document carefully. Understand the current state, the proposed target state, and the path required to reach it. Suggest practical improvements that make the strategy easier to approve, cheaper to execute, faster to deliver, and less likely to create interim technical debt.

Focus on:
- Subtle changes to the interim approach and next steps.
- How to sharpen the final objective so it is measurable and decision-oriented.
- How to reduce implementation cost without weakening the target architecture.
- How to shorten turnaround time through reusable patterns, governance gates, standard templates, and phased delivery.
- How to save cloud infrastructure cost through right-sizing, workload scheduling, storage lifecycle tiers, reserved capacity timing, observability budgets, and showback/chargeback.
- Where the existing recommendation is already good and should be preserved.

Output format:
- Use bullet points and reference slide/page numbers wherever the document supports it.
- For each suggestion, include: Suggested change, Why it is better than the current/default approach, Cost impact, Turnaround impact, and Risk reduction.
- Do not generate suggestions just to fill space. If the current material is strong, say so clearly.
- Think deeply before answering and prioritize recommendations that a steering committee would find credible.`,
}

const defaultPrompt = samplePrompts.give_suggestions

function StatusPill({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700 ring-slate-200',
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  }
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${tones[tone]}`}>{children}</span>
}

function Header() {
  return (
    <header className="flex flex-col gap-4 border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur lg:flex-row lg:items-center lg:justify-between">
      <div>
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-slate-950 text-white">
            <BrainCircuit size={21} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-normal text-slate-950">Strategy Analyzer</h1>
            <p className="text-sm text-slate-500">Multi-agent review for strategy documents, decks, and business cases</p>
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone="green">FastAPI</StatusPill>
        <StatusPill>GPT validation</StatusPill>
        <StatusPill>Anthropic review</StatusPill>
      </div>
    </header>
  )
}

function UploadPanel({ document, onUpload, busy, error }) {
  const [dragging, setDragging] = useState(false)

  async function handleFiles(files) {
    const file = files?.[0]
    if (file) await onUpload(file)
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">Document</h2>
          <p className="text-sm text-slate-500">PDF, Word, or PowerPoint</p>
        </div>
        {document && <StatusPill tone="green">{document.kind.toUpperCase()}</StatusPill>}
      </div>
      <label
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          handleFiles(event.dataTransfer.files)
        }}
        className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed p-5 text-center transition ${
          dragging ? 'border-slate-900 bg-slate-50' : 'border-slate-300 bg-slate-50/70 hover:border-slate-500'
        }`}
      >
        {busy ? <Loader2 className="mb-3 animate-spin text-slate-700" /> : <UploadCloud className="mb-3 text-slate-600" />}
        <span className="text-sm font-semibold text-slate-900">{document ? document.filename : 'Drop a strategy document here'}</span>
        <span className="mt-1 text-xs text-slate-500">or browse from your computer</span>
        <input className="hidden" type="file" accept=".pdf,.docx,.pptx" onChange={(event) => handleFiles(event.target.files)} />
      </label>
      {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
    </section>
  )
}

function PreviewPanel({ document, onCollapse }) {
  const pages = document?.pages || []
  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-200 bg-white shadow-panel">
      <div className="flex items-center justify-between border-b border-slate-200 p-4">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-slate-600" />
          <h2 className="font-semibold text-slate-950">Preview</h2>
        </div>
        <div className="flex items-center gap-3">
          {document && <span className="hidden text-xs text-slate-500 sm:inline">{document.characters.toLocaleString()} extracted chars</span>}
          <button
            onClick={onCollapse}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500"
            title="Hide preview"
          >
            <PanelLeftClose size={15} />
            Hide
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">
        {!document ? (
          <div className="grid h-full min-h-80 place-items-center rounded-lg bg-slate-50 text-center text-sm text-slate-500">
            Upload a document to see extracted pages, slides, or sections.
          </div>
        ) : document.kind === 'pdf' ? (
          <div className="space-y-4">
            <iframe title="PDF preview" src={document.preview_url} className="h-[420px] w-full rounded-lg border border-slate-200" />
            <ExtractedPages pages={pages} />
          </div>
        ) : (
          <ExtractedPages pages={pages} />
        )}
      </div>
    </section>
  )
}

function ExtractedPages({ pages }) {
  return (
    <div className="space-y-3">
      {pages.map((page) => (
        <article key={page.number} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="text-sm font-bold text-slate-900">{page.title || `Page ${page.number}`}</h3>
            <span className="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
              {page.number}
            </span>
          </div>
          <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-slate-600">{page.text || 'No extractable text found.'}</p>
        </article>
      ))}
    </div>
  )
}

function PromptPanel({ mode, setMode, prompt, setPrompt, thinkingMode, setThinkingMode, onAnalyze, disabled, busy }) {
  function selectMode(nextMode) {
    setMode(nextMode)
    setPrompt(samplePrompts[nextMode])
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-slate-700" />
        <h2 className="font-semibold text-slate-950">Prompt</h2>
      </div>
      <div className="grid gap-2">
        {modes.map((item) => (
          <label
            key={item.id}
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
              mode === item.id ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:border-slate-400'
            }`}
          >
            <input className="mt-1 accent-slate-950" type="radio" name="mode" checked={mode === item.id} onChange={() => selectMode(item.id)} />
            <span>
              <span className="block text-sm font-bold">{item.label}</span>
              <span className={`block text-xs ${mode === item.id ? 'text-slate-300' : 'text-slate-500'}`}>{item.detail}</span>
            </span>
          </label>
        ))}
      </div>
      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        rows={12}
        className="mt-4 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 outline-none transition focus:border-slate-900 focus:bg-white"
      />
      <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <input
          type="checkbox"
          checked={thinkingMode}
          onChange={(event) => setThinkingMode(event.target.checked)}
          className="mt-1 accent-slate-950"
        />
        <span>
          <span className="block text-sm font-bold text-slate-900">Thinking mode</span>
          <span className="block text-xs leading-5 text-slate-500">Uses Anthropic extended reasoning through SAP AI Core before synthesis.</span>
        </span>
      </label>
      <button
        onClick={onAnalyze}
        disabled={disabled || busy}
        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {busy ? <Loader2 size={17} className="animate-spin" /> : <Bot size={17} />}
        {busy ? 'Agents reviewing...' : 'Run multi-agent review'}
      </button>
    </section>
  )
}

function AnalysisPanel({ analysis, warning, agents, busy, previewCollapsed, onShowPreview, onDownloadMarkdown }) {
  const [visualBusy, setVisualBusy] = useState(false)

  async function downloadVisual() {
    if (!analysis || visualBusy) return
    setVisualBusy(true)
    try {
      const visual = await createVisual({ analysis })
      await downloadFromUrl(visual.url, visual.filename || 'strategy-visual.png')
    } finally {
      setVisualBusy(false)
    }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-200 bg-white shadow-panel">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 p-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={18} className="text-emerald-600" />
          <h2 className="font-semibold text-slate-950">Output</h2>
        </div>
        <div className="flex items-center gap-2">
          {previewCollapsed && (
            <button
              onClick={onShowPreview}
              className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500"
              title="Show preview"
            >
              <PanelLeftOpen size={15} />
              Preview
            </button>
          )}
          <button
            onClick={downloadVisual}
            disabled={!analysis || visualBusy}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {visualBusy ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            PNG
          </button>
          <button
            onClick={onDownloadMarkdown}
            disabled={!analysis}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Download size={15} />
            MD
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-5">
        {busy ? (
          <div className="grid h-full min-h-80 place-items-center text-center">
            <div>
              <Loader2 className="mx-auto mb-4 animate-spin text-slate-700" size={32} />
              <p className="font-semibold text-slate-900">Anthropic and GPT agents are comparing notes.</p>
              <p className="mt-1 text-sm text-slate-500">This can take a few minutes, please wait for the process to complete.</p>
            </div>
          </div>
        ) : analysis ? (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="markdown max-w-none text-sm leading-7 text-slate-700">
            {warning && <p className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-amber-800">{warning}</p>}
            <ReactMarkdown>{analysis}</ReactMarkdown>
            {agents?.length > 0 && (
              <div className="mt-6 border-t border-slate-200 pt-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Agent trace</p>
                <div className="flex flex-wrap gap-2">
                  {agents.map((agent, index) => (
                    <StatusPill key={`${agent.agent}-${index}`} tone={agent.ok ? 'green' : 'amber'}>
                      {agent.agent}
                    </StatusPill>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        ) : (
          <div className="grid h-full min-h-80 place-items-center rounded-lg bg-slate-50 text-center text-sm text-slate-500">
            Generated analysis will appear here with download support.
          </div>
        )}
      </div>
    </section>
  )
}

function ChatPanel({ documentId, analysis, messages, setMessages }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!question.trim() || !analysis || busy) return
    const current = question.trim()
    setQuestion('')
    setMessages((items) => [...items, { role: 'user', content: current }])
    setBusy(true)
    try {
      const response = await askFollowUp({ document_id: documentId, analysis, question: current })
      setMessages((items) => [...items, { role: 'assistant', content: response.content }])
    } catch (error) {
      setMessages((items) => [...items, { role: 'assistant', content: error.message }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center gap-2">
        <MessageSquareText size={18} className="text-slate-700" />
        <h2 className="font-semibold text-slate-950">Ask follow-up</h2>
      </div>
      <div className="mb-3 max-h-[420px] space-y-3 overflow-auto rounded-lg bg-slate-50 p-3">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">Ask about assumptions, cost levers, next steps, or slide-level wording.</p>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={`rounded-lg px-4 py-3 text-sm leading-6 ${
                message.role === 'user'
                  ? 'ml-auto max-w-[86%] whitespace-pre-wrap bg-slate-950 text-white'
                  : 'chat-markdown markdown w-full overflow-x-auto border border-slate-200 bg-white text-slate-700'
              }`}
            >
              {message.role === 'assistant' ? <ReactMarkdown>{message.content}</ReactMarkdown> : message.content}
            </div>
          ))
        )}
      </div>
      <div className="flex gap-2">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit()
          }}
          disabled={!analysis}
          placeholder="Ask a question about the generated content..."
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-slate-900 focus:bg-white disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={!analysis || busy}
          className="grid h-10 w-10 place-items-center rounded-lg bg-slate-950 text-white transition hover:bg-slate-800 disabled:bg-slate-300"
          title="Send"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>
    </section>
  )
}

export default function App() {
  const [document, setDocument] = useState(null)
  const [mode, setMode] = useState('give_suggestions')
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [analysis, setAnalysis] = useState('')
  const [agents, setAgents] = useState([])
  const [warning, setWarning] = useState('')
  const [chatMessages, setChatMessages] = useState([])
  const [thinkingMode, setThinkingMode] = useState(true)
  const [previewCollapsed, setPreviewCollapsed] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  const canAnalyze = useMemo(() => Boolean(document?.document_id), [document])

  async function handleUpload(file) {
    setUploading(true)
    setError('')
    setAnalysis('')
    setChatMessages([])
    try {
      const response = await uploadDocument(file)
      setDocument(response)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleAnalyze() {
    if (!document) return
    setAnalyzing(true)
    setError('')
    setWarning('')
    setChatMessages([])
    try {
      const response = await analyzeDocument({ document_id: document.document_id, mode, prompt, thinking_mode: thinkingMode })
      setAnalysis(response.content)
      setAgents(response.agents || [])
      setWarning(response.warning || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  function handleDownloadMarkdown() {
    const sections = [analysis]
    if (chatMessages.length > 0) {
      sections.push(
        [
          '# Follow-up Q&A',
          ...chatMessages.map((message) => {
            const heading = message.role === 'user' ? '## User Question' : '## Assistant Response'
            return `${heading}\n\n${message.content}`
          }),
        ].join('\n\n'),
      )
    }
    downloadMarkdown(sections.filter(Boolean).join('\n\n---\n\n'))
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)]">
      <Header />
      <main
        className={`grid h-[calc(100vh-81px)] gap-4 p-4 ${
          previewCollapsed
            ? 'lg:grid-cols-[360px_minmax(0,1fr)]'
            : 'lg:grid-cols-[360px_minmax(360px,1fr)_minmax(520px,0.95fr)]'
        }`}
      >
        <div className="flex min-h-0 flex-col gap-4">
          <UploadPanel document={document} onUpload={handleUpload} busy={uploading} error={error} />
          <PromptPanel
            mode={mode}
            setMode={setMode}
            prompt={prompt}
            setPrompt={setPrompt}
            thinkingMode={thinkingMode}
            setThinkingMode={setThinkingMode}
            onAnalyze={handleAnalyze}
            disabled={!canAnalyze}
            busy={analyzing}
          />
        </div>
        {!previewCollapsed && <PreviewPanel document={document} onCollapse={() => setPreviewCollapsed(true)} />}
        <div className="flex min-h-0 flex-col gap-4">
          <AnalysisPanel
            analysis={analysis}
            warning={warning}
            agents={agents}
            busy={analyzing}
            previewCollapsed={previewCollapsed}
            onShowPreview={() => setPreviewCollapsed(false)}
            onDownloadMarkdown={handleDownloadMarkdown}
          />
          <ChatPanel documentId={document?.document_id} analysis={analysis} messages={chatMessages} setMessages={setChatMessages} />
        </div>
      </main>
    </div>
  )
}
