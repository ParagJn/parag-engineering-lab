import { useState } from 'react'

const TABS = [
  { key: 'cv',       label: 'CV Preview',       icon: 'fa-id-card' },
  { key: 'linkedin', label: 'LinkedIn Preview',  icon: 'fa-brands fa-linkedin' },
  { key: 'download', label: 'Downloads',         icon: 'fa-download' },
]

export default function OutputPanel({ result }) {
  const [activeTab, setActiveTab] = useState('cv')

  if (!result) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-white rounded-xl border border-gray-200 shadow-sm">
        <i className="fa-regular fa-rectangle-list text-5xl text-gray-300 mb-4"></i>
        <p className="text-gray-500 font-medium">Your generated CV will appear here</p>
        <p className="text-gray-400 text-sm mt-1">Upload documents or add links, then click Generate</p>
      </div>
    )
  }

  const { cv_html, linkedin_html, pdf_ready, job_id, profile_name } = result

  return (
    <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-gray-200 px-4 pt-3 gap-1 bg-gray-50">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-all
              ${activeTab === tab.key
                ? 'bg-white text-accent border border-gray-200 border-b-white -mb-px shadow-sm'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'}`}
          >
            <i className={`fa-solid ${tab.icon} text-xs`}></i>
            {tab.label}
          </button>
        ))}
        {profile_name && (
          <div className="ml-auto flex items-center gap-2 pb-2">
            <span className="text-xs text-gray-400">Generated for</span>
            <span className="text-xs font-semibold text-accent bg-blue-50 px-2 py-0.5 rounded-full border border-blue-100">
              {profile_name}
            </span>
          </div>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 relative overflow-hidden">
        {activeTab === 'cv' && (
          <iframe
            srcDoc={cv_html}
            sandbox="allow-same-origin allow-scripts"
            className="w-full h-full border-none bg-white"
            title="CV Preview"
          />
        )}

        {activeTab === 'linkedin' && (
          <iframe
            srcDoc={linkedin_html}
            sandbox="allow-same-origin allow-scripts"
            className="w-full h-full border-none bg-white"
            title="LinkedIn Preview"
          />
        )}

        {activeTab === 'download' && (
          <div className="flex flex-col items-center justify-center h-full gap-4 p-10">
            <div className="text-center mb-4">
              <i className="fa-solid fa-circle-check text-5xl text-green-500 mb-3"></i>
              <h3 className="text-gray-800 text-xl font-bold">Your Profile is Ready!</h3>
              <p className="text-gray-500 text-sm mt-1">Download all three formats below</p>
            </div>

            <div className="grid grid-cols-1 gap-4 w-full max-w-md">
              {/* HTML CV */}
              <a
                href={`/api/download/${job_id}/cv-html`}
                download="profile-cv.html"
                className="flex items-center gap-4 bg-white hover:bg-orange-50 border border-gray-200
                  hover:border-orange-300 rounded-xl p-4 transition-all group shadow-sm"
              >
                <div className="w-12 h-12 rounded-xl bg-orange-100 flex items-center justify-center flex-shrink-0">
                  <i className="fa-solid fa-file-code text-orange-500 text-xl"></i>
                </div>
                <div className="flex-1">
                  <p className="text-gray-800 font-semibold">HTML Resume</p>
                  <p className="text-gray-500 text-xs">Beautiful animated web-ready CV</p>
                </div>
                <i className="fa-solid fa-download text-gray-400 group-hover:text-orange-500 transition-colors"></i>
              </a>

              {/* PDF CV */}
              <a
                href={pdf_ready ? `/api/download/${job_id}/pdf` : undefined}
                download={pdf_ready ? 'profile-cv.pdf' : undefined}
                className={`flex items-center gap-4 border rounded-xl p-4 transition-all group shadow-sm
                  ${pdf_ready
                    ? 'bg-white hover:bg-red-50 border-gray-200 hover:border-red-300 cursor-pointer'
                    : 'bg-gray-50 border-gray-100 cursor-not-allowed opacity-60'}`}
              >
                <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                  <i className="fa-solid fa-file-pdf text-red-500 text-xl"></i>
                </div>
                <div className="flex-1">
                  <p className="text-gray-800 font-semibold">PDF Resume</p>
                  <p className="text-gray-500 text-xs">
                    {pdf_ready ? 'Print-perfect PDF with full styling' : 'PDF generation failed — download HTML instead'}
                  </p>
                </div>
                <i className={`fa-solid ${pdf_ready ? 'fa-download' : 'fa-triangle-exclamation'} text-gray-400 group-hover:text-red-500 transition-colors`}></i>
              </a>

              {/* LinkedIn HTML */}
              <a
                href={`/api/download/${job_id}/linkedin-html`}
                download="profile-linkedin.html"
                className="flex items-center gap-4 bg-white hover:bg-blue-50 border border-gray-200
                  hover:border-blue-300 rounded-xl p-4 transition-all group shadow-sm"
              >
                <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <i className="fa-brands fa-linkedin text-blue-600 text-xl"></i>
                </div>
                <div className="flex-1">
                  <p className="text-gray-800 font-semibold">LinkedIn Helper</p>
                  <p className="text-gray-500 text-xs">Copy-paste tool with character counters</p>
                </div>
                <i className="fa-solid fa-download text-gray-400 group-hover:text-blue-500 transition-colors"></i>
              </a>
            </div>

            <button
              onClick={() => window.location.reload()}
              className="mt-4 text-gray-400 hover:text-gray-600 text-sm flex items-center gap-2 transition-colors"
            >
              <i className="fa-solid fa-rotate-left text-xs"></i> Generate another profile
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
