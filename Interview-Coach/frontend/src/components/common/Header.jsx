import { Link, useLocation } from 'react-router-dom'
import { BrainCircuit, LayoutDashboard, PlusCircle } from 'lucide-react'

export default function Header() {
  const { pathname } = useLocation()

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-primary-800 rounded-lg flex items-center justify-center">
              <BrainCircuit className="w-4.5 h-4.5 text-white" size={18} />
            </div>
            <span className="font-semibold text-slate-800 text-lg tracking-tight">
              Interview Coach
            </span>
          </Link>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            <Link
              to="/"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                pathname === '/'
                  ? 'bg-primary-50 text-primary-800'
                  : 'text-slate-600 hover:bg-gray-100 hover:text-slate-800'
              }`}
            >
              <LayoutDashboard size={15} />
              <span className="hidden sm:inline">Dashboard</span>
            </Link>
            <Link
              to="/setup"
              className="flex items-center gap-1.5 ml-1 btn-primary text-sm py-2 px-4"
            >
              <PlusCircle size={15} />
              <span>New Interview</span>
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
