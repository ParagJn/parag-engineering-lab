import { useState } from 'react'

function getLinkIcon(url = '') {
  if (url.includes('github.com')) return { icon: 'fa-brands fa-github', color: 'text-slate-300' }
  if (url.includes('linkedin.com')) return { icon: 'fa-brands fa-linkedin', color: 'text-blue-400' }
  if (url.includes('medium.com')) return { icon: 'fa-brands fa-medium', color: 'text-green-400' }
  if (url.includes('twitter.com') || url.includes('x.com')) return { icon: 'fa-brands fa-x-twitter', color: 'text-slate-300' }
  return { icon: 'fa-solid fa-link', color: 'text-slate-400' }
}

export default function LinksInput({ links, setLinks }) {
  const [draft, setDraft] = useState('')

  const addLink = () => {
    const trimmed = draft.trim()
    if (!trimmed) return
    // Basic URL sanity check — only allow http/https
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      alert('Please enter a valid URL starting with http:// or https://')
      return
    }
    if (links.includes(trimmed)) return
    setLinks((prev) => [...prev, trimmed])
    setDraft('')
  }

  const removeLink = (idx) => setLinks((prev) => prev.filter((_, i) => i !== idx))

  const onKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); addLink() }
  }

  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        <i className="fa-solid fa-globe mr-1.5"></i>Public Links
        <span className="ml-2 text-gray-400 normal-case font-normal">GitHub · LinkedIn · Portfolio</span>
      </label>

      <div className="flex gap-2">
        <input
          type="url"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="https://github.com/yourusername"
          className="flex-1 bg-white border border-gray-300 text-gray-800 text-sm rounded-lg px-3 py-2.5
            placeholder-gray-400 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition"
        />
        <button
          onClick={addLink}
          className="px-4 py-2.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-blue-500
            transition-colors flex items-center gap-1.5"
        >
          <i className="fa-solid fa-plus text-xs"></i> Add
        </button>
      </div>

      {links.length > 0 && (
        <ul className="mt-3 space-y-2">
          {links.map((url, idx) => {
            const { icon, color } = getLinkIcon(url)
            return (
              <li
                key={idx}
                className="flex items-center gap-2.5 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2"
              >
                <i className={`${icon} ${color} text-base flex-shrink-0`}></i>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 text-gray-700 text-xs truncate hover:text-accent transition-colors"
                >
                  {url}
                </a>
                <button
                  onClick={() => removeLink(idx)}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                >
                  <i className="fa-solid fa-xmark text-xs"></i>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
