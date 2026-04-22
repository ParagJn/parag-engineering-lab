import { useRef, useState } from 'react'

const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.html', '.htm']
const MAX_FILES = 3

function getFileIcon(name = '') {
  const ext = name.split('.').pop().toLowerCase()
  if (ext === 'pdf') return { icon: 'fa-file-pdf', color: 'text-red-400' }
  if (['docx', 'doc'].includes(ext)) return { icon: 'fa-file-word', color: 'text-blue-400' }
  if (['html', 'htm'].includes(ext)) return { icon: 'fa-file-code', color: 'text-orange-400' }
  return { icon: 'fa-file', color: 'text-slate-400' }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export default function UploadZone({ files, setFiles }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const addFiles = (newFiles) => {
    const filtered = Array.from(newFiles).filter((f) => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      return ALLOWED_EXTS.includes(ext)
    })
    setFiles((prev) => {
      const combined = [...prev, ...filtered]
      return combined.slice(0, MAX_FILES)
    })
  }

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        <i className="fa-solid fa-upload mr-1.5"></i>Upload Documents
        <span className="ml-2 text-gray-400 normal-case font-normal">(up to {MAX_FILES})</span>
      </label>

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200
          ${dragging ? 'border-accent bg-blue-50' : 'border-gray-300 hover:border-accent hover:bg-blue-50/40'}
          ${files.length >= MAX_FILES ? 'opacity-50 cursor-not-allowed' : ''}`}
        onClick={() => files.length < MAX_FILES && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={files.length < MAX_FILES ? onDrop : (e) => e.preventDefault()}
      >
        <i className={`fa-solid fa-cloud-arrow-up text-3xl mb-2 ${dragging ? 'text-accent' : 'text-gray-400'}`}></i>
        <p className="text-gray-500 text-sm">
          {files.length >= MAX_FILES
            ? 'Maximum 3 files reached'
            : 'Drop files here or click to browse'}
        </p>
        <p className="text-gray-400 text-xs mt-1">PDF · DOCX · HTML</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.html,.htm"
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {files.map((file, idx) => {
            const { icon, color } = getFileIcon(file.name)
            return (
              <li
                key={idx}
                className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5"
              >
                <i className={`fa-solid ${icon} ${color} text-lg flex-shrink-0`}></i>
                <div className="flex-1 min-w-0">
                  <p className="text-gray-800 text-sm truncate font-medium">{file.name}</p>
                  <p className="text-gray-400 text-xs">{formatSize(file.size)}</p>
                </div>
                <button
                  onClick={() => removeFile(idx)}
                  className="text-gray-400 hover:text-red-500 transition-colors ml-1"
                  title="Remove"
                >
                  <i className="fa-solid fa-xmark"></i>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {files.length > 0 && files.length < MAX_FILES && (
        <p className="text-gray-400 text-xs mt-2 text-center">
          {MAX_FILES - files.length} more file{MAX_FILES - files.length > 1 ? 's' : ''} allowed
        </p>
      )}
    </div>
  )
}
