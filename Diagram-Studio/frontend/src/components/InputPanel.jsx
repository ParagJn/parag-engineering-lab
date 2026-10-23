import { useRef, useState } from 'react'
import { FileText, Upload, X } from 'lucide-react'

const MIN_CHARS = 40

export default function InputPanel({ accepted, maxMb, onSubmit, disabled }) {
  const [mode, setMode] = useState('upload')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const pick = (candidate) => {
    if (!candidate) return
    const suffix = '.' + candidate.name.split('.').pop().toLowerCase()
    if (accepted.length && !accepted.includes(suffix)) {
      setError(`Unsupported file type. Use ${accepted.join(', ')}.`)
      return
    }
    if (candidate.size > maxMb * 1024 * 1024) {
      setError(`That file is larger than ${maxMb} MB.`)
      return
    }
    setError('')
    setFile(candidate)
  }

  const ready = mode === 'upload' ? Boolean(file) : text.trim().length >= MIN_CHARS

  const submit = () => {
    if (!ready || disabled) return
    onSubmit(mode === 'upload' ? { file } : { text })
  }

  return (
    <div className="hairline rounded-xl" style={{ background: 'var(--panel)' }}>
      <div className="flex gap-1 p-2" style={{ borderBottom: '1px solid var(--rule)' }}>
        {[
          ['upload', 'Upload a file'],
          ['paste', 'Paste text'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setMode(key)}
            className="rounded-md px-3 py-1.5 text-[13px] font-medium"
            style={{
              background: mode === key ? 'var(--paper)' : 'transparent',
              border: `1px solid ${mode === key ? 'var(--rule)' : 'transparent'}`,
              color: mode === key ? 'var(--ink)' : 'var(--muted)',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {mode === 'upload' ? (
          file ? (
            <div className="flex items-center gap-3 rounded-lg p-4" style={{ background: 'var(--paper)', border: '1px solid var(--rule)' }}>
              <FileText size={20} style={{ color: 'var(--accent)' }} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{file.name}</div>
                <div className="kicker mt-0.5">{(file.size / 1024).toFixed(file.size > 102400 ? 0 : 1)} KB</div>
              </div>
              <button type="button" className="btn" onClick={() => setFile(null)} aria-label="Remove file">
                <X size={14} /> Remove
              </button>
            </div>
          ) : (
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                pick(e.dataTransfer.files?.[0])
              }}
              className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg px-6 py-12 text-center"
              style={{
                background: dragging ? 'var(--accent-soft)' : 'var(--paper)',
                border: `1px dashed ${dragging ? 'var(--accent)' : 'var(--line)'}`,
              }}
            >
              <Upload size={22} style={{ color: 'var(--muted)' }} />
              <div className="text-sm font-medium">Drop a document here, or click to choose</div>
              <div className="kicker">{accepted.join('  ')}  ·  up to {maxMb} MB</div>
              <input
                ref={inputRef}
                type="file"
                accept={accepted.join(',')}
                className="hidden"
                onChange={(e) => {
                  pick(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
            </div>
          )
        ) : (
          <textarea
            className="field font-mono"
            style={{ minHeight: 260, resize: 'vertical', fontSize: 13, lineHeight: 1.55 }}
            placeholder="Paste a design doc, README, spec or any text that describes a system, a process or a plan…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}

        {error && (
          <div className="mt-3 text-[13px]" style={{ color: 'var(--accent)' }}>
            {error}
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="kicker">{mode === 'paste' ? `${text.trim().length.toLocaleString()} characters` : 'Text is sent to the model to find the diagrams'}</div>
          <button type="button" className="btn btn-primary" disabled={!ready || disabled} onClick={submit}>
            Find diagrams
          </button>
        </div>
      </div>
    </div>
  )
}
