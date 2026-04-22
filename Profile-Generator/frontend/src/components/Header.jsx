export default function Header() {
  return (
    <header className="w-full bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center">
          <i className="fa-solid fa-wand-magic-sparkles text-white text-sm"></i>
        </div>
        <div>
          <h1 className="text-gray-900 font-bold text-lg leading-none">Profile Generator</h1>
          <p className="text-gray-400 text-xs mt-0.5">AI-Powered CV · PDF · LinkedIn</p>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-100 border border-gray-200">
          <i className="fa-brands fa-google text-blue-500"></i> Gemini 2.5 Pro
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-100 border border-gray-200">
          <i className="fa-solid fa-robot text-amber-500"></i> Claude Opus
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-100 border border-gray-200">
          <i className="fa-brands fa-python text-green-500"></i> FastAPI
        </span>
      </div>
    </header>
  )
}
