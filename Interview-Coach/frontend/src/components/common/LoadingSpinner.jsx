export default function LoadingSpinner({ size = 'md', text = null, fullPage = false }) {
  const sizes = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-[3px]',
    xl: 'w-14 h-14 border-4',
  }

  const spinner = (
    <div
      className={`${sizes[size]} rounded-full border-gray-200 border-t-primary-700 animate-spin`}
    />
  )

  if (fullPage) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        {spinner}
        {text && <p className="text-slate-500 text-sm">{text}</p>}
      </div>
    )
  }

  if (text) {
    return (
      <div className="flex items-center gap-3">
        {spinner}
        <span className="text-slate-500 text-sm">{text}</span>
      </div>
    )
  }

  return spinner
}
