import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error instanceof Error && error.message
        ? error.message
        : 'Something went wrong while rendering the app.',
    }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled React error:', error, errorInfo)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
          <div className="w-full max-w-lg bg-white border border-red-200 rounded-2xl shadow-sm p-6 text-center">
            <div className="w-14 h-14 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-4">
              <i className="fa-solid fa-triangle-exclamation text-xl"></i>
            </div>
            <h1 className="text-xl font-bold text-gray-900">The app hit an unexpected error</h1>
            <p className="text-sm text-gray-600 mt-2">
              {this.state.message}
            </p>
            <button
              onClick={this.handleReload}
              className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 transition-colors"
            >
              <i className="fa-solid fa-rotate-right text-xs"></i>
              Reload app
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
