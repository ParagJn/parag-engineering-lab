import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, KeyRound, Radio, Save, Settings as SettingsIcon, ShieldCheck, XCircle } from 'lucide-react'
import Header from '../components/common/Header'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getSettings, updateSettings, verifySettings } from '../api/client'

const PROVIDERS = [
  {
    id: 'openai',
    label: 'OpenAI',
    help: 'Used for GPT interview analysis, question generation, and feedback synthesis.',
    placeholder: 'sk-...',
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    help: 'Used for Claude question refinement, answer review, and session summaries.',
    placeholder: 'sk-ant-...',
  },
  {
    id: 'gemini',
    label: 'Gemini',
    help: 'Used for Gemini final question review and answer evaluation.',
    placeholder: 'AIza...',
  },
]

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [providerMode, setProviderMode] = useState('built_in')
  const [hasKeys, setHasKeys] = useState({})
  const [maskedKeys, setMaskedKeys] = useState({})
  const [enabledProviders, setEnabledProviders] = useState([])
  const [keys, setKeys] = useState({ openai: '', anthropic: '', gemini: '' })
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [verificationResults, setVerificationResults] = useState([])

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await getSettings()
        setProviderMode(res.data.provider_mode)
        setHasKeys(res.data.has_keys || {})
        setMaskedKeys(res.data.masked_keys || {})
        setEnabledProviders(res.data.enabled_providers || [])
      } catch (err) {
        setError('Could not load settings. Make sure the backend is running.')
      } finally {
        setLoading(false)
      }
    }
    loadSettings()
  }, [])

  const activeCustomProviders = useMemo(() => {
    if (providerMode !== 'custom') return []
    return PROVIDERS
      .filter((provider) => enabledProviders.includes(provider.id))
      .filter((provider) => hasKeys[provider.id] || keys[provider.id]?.trim())
      .map((provider) => provider.label)
  }, [providerMode, enabledProviders, hasKeys, keys])

  const unavailableEnabledProviders = useMemo(() => {
    if (providerMode !== 'custom') return []
    return PROVIDERS
      .filter((provider) => enabledProviders.includes(provider.id))
      .filter((provider) => !hasKeys[provider.id] && !keys[provider.id]?.trim())
      .map((provider) => provider.label)
  }, [providerMode, enabledProviders, hasKeys, keys])

  const customModeInvalid =
    providerMode === 'custom' &&
    (activeCustomProviders.length === 0 || unavailableEnabledProviders.length > 0)

  const updateKey = (provider, value) => {
    setKeys((prev) => ({ ...prev, [provider]: value }))
    if (value.trim()) {
      setEnabledProviders((prev) => (prev.includes(provider) ? prev : [...prev, provider]))
    }
    setMessage(null)
    setError(null)
    setVerificationResults([])
  }

  const toggleProvider = (provider, checked) => {
    setEnabledProviders((prev) =>
      checked ? [...new Set([...prev, provider])] : prev.filter((item) => item !== provider)
    )
    setMessage(null)
    setError(null)
    setVerificationResults([])
  }

  const testKeys = async () => {
    setVerifying(true)
    setMessage(null)
    setError(null)
    setVerificationResults([])
    try {
      const res = await verifySettings({
        provider_mode: providerMode,
        api_keys: keys,
        enabled_providers: enabledProviders,
      })
      setVerificationResults(res.data.results || [])
      setMessage(
        res.data.ok
          ? 'All enabled provider keys verified.'
          : 'Some enabled provider keys could not be verified.'
      )
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not verify keys.')
    } finally {
      setVerifying(false)
    }
  }

  const saveSettings = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const res = await updateSettings({
        provider_mode: providerMode,
        api_keys: keys,
        enabled_providers: enabledProviders,
      })
      setProviderMode(res.data.provider_mode)
      setHasKeys(res.data.has_keys || {})
      setMaskedKeys(res.data.masked_keys || {})
      setEnabledProviders(res.data.enabled_providers || [])
      setKeys({ openai: '', anthropic: '', gemini: '' })
      setMessage(
        res.data.provider_mode === 'custom'
          ? 'Custom API keys are active for new AI calls.'
          : 'Built-in AI connectivity is active.'
      )
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save settings.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg bg-primary-50 text-primary-800 flex items-center justify-center">
            <SettingsIcon size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
            <p className="text-slate-500 text-sm mt-1">Choose how Interview Coach connects to the AI panel.</p>
          </div>
        </div>

        {loading && <LoadingSpinner fullPage text="Loading settings..." />}

        {!loading && (
          <form onSubmit={saveSettings} className="space-y-6">
            <section className="card p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-4">AI Connectivity</h2>
              <div className="grid gap-3">
                <label
                  className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                    providerMode === 'built_in'
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="flex gap-3">
                    <input
                      type="radio"
                      name="providerMode"
                      value="built_in"
                      checked={providerMode === 'built_in'}
                      onChange={() => setProviderMode('built_in')}
                      className="mt-1 h-4 w-4 text-primary-800 focus:ring-primary-500"
                    />
                    <div>
                      <div className="flex items-center gap-2 font-medium text-slate-800">
                        <Radio size={16} />
                        Built-in AI API keys
                      </div>
                      <p className="text-sm text-slate-500 mt-1">
                        Use the existing SAP AI Core connectivity configured with the application.
                      </p>
                    </div>
                  </div>
                </label>

                <label
                  className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                    providerMode === 'custom'
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="flex gap-3">
                    <input
                      type="radio"
                      name="providerMode"
                      value="custom"
                      checked={providerMode === 'custom'}
                      onChange={() => setProviderMode('custom')}
                      className="mt-1 h-4 w-4 text-primary-800 focus:ring-primary-500"
                    />
                    <div>
                      <div className="flex items-center gap-2 font-medium text-slate-800">
                        <KeyRound size={16} />
                        Use my API keys
                      </div>
                      <p className="text-sm text-slate-500 mt-1">
                        Use one, two, or three saved provider keys for the interview coach agents.
                      </p>
                    </div>
                  </div>
                </label>
              </div>
            </section>

            <section className={`card p-5 ${providerMode !== 'custom' ? 'opacity-70' : ''}`}>
              <div className="flex items-center justify-between gap-4 mb-4">
                <h2 className="text-sm font-semibold text-slate-700">Provider API Keys</h2>
                {providerMode === 'custom' && (
                  <span className="text-xs font-medium text-slate-500">
                    Active: {activeCustomProviders.length || 0}
                  </span>
                )}
              </div>

              <div className="space-y-4">
                {PROVIDERS.map((provider) => (
                  <div key={provider.id}>
                    <div className="flex items-center justify-between gap-3 mb-1.5">
                      <div className="flex items-center gap-2">
                        <input
                          id={`${provider.id}-enabled`}
                          type="checkbox"
                          checked={enabledProviders.includes(provider.id)}
                          onChange={(event) => toggleProvider(provider.id, event.target.checked)}
                          disabled={providerMode !== 'custom'}
                          className="h-4 w-4 rounded border-gray-300 text-primary-800 focus:ring-primary-500"
                        />
                        <label htmlFor={`${provider.id}-key`} className="label mb-0">
                          {provider.label} API Key
                        </label>
                      </div>
                      <div className="flex items-center gap-2">
                        {enabledProviders.includes(provider.id) && (
                          <span className="text-xs font-medium text-primary-800">Enabled</span>
                        )}
                        {hasKeys[provider.id] && (
                          <span className="inline-flex items-center gap-1 text-xs text-green-700 font-medium">
                            <CheckCircle2 size={13} />
                            Saved {maskedKeys[provider.id]}
                          </span>
                        )}
                      </div>
                    </div>
                    <input
                      id={`${provider.id}-key`}
                      type="password"
                      value={keys[provider.id]}
                      onChange={(event) => updateKey(provider.id, event.target.value)}
                      disabled={providerMode !== 'custom'}
                      placeholder={hasKeys[provider.id] ? 'Leave blank to keep existing key' : provider.placeholder}
                      className="input-field disabled:bg-gray-100 disabled:text-slate-400"
                      autoComplete="off"
                    />
                    <p className="text-xs text-slate-500 mt-1">{provider.help}</p>
                  </div>
                ))}
              </div>
            </section>

            {providerMode === 'custom' && activeCustomProviders.length === 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Enable at least one provider and enter its API key.
              </div>
            )}

            {providerMode === 'custom' && unavailableEnabledProviders.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Enabled providers need keys: {unavailableEnabledProviders.join(', ')}
              </div>
            )}

            {verificationResults.length > 0 && (
              <div className="card p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Key Check Results</h3>
                <div className="space-y-2">
                  {verificationResults.map((result) => {
                    const provider = PROVIDERS.find((item) => item.id === result.provider)
                    return (
                      <div
                        key={result.provider}
                        className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${
                          result.ok
                            ? 'border-green-200 bg-green-50 text-green-800'
                            : 'border-red-200 bg-red-50 text-red-700'
                        }`}
                      >
                        {result.ok ? <CheckCircle2 size={16} className="mt-0.5" /> : <XCircle size={16} className="mt-0.5" />}
                        <div>
                          <p className="font-medium">{provider?.label || result.provider}</p>
                          <p>{result.message}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {message && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                {message}
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={testKeys}
                disabled={verifying || customModeInvalid || providerMode !== 'custom'}
                className="btn-secondary flex items-center justify-center gap-2"
              >
                <ShieldCheck size={16} />
                {verifying ? 'Testing...' : 'Test enabled keys'}
              </button>
              <button
                type="submit"
                disabled={saving || customModeInvalid}
                className="btn-primary flex items-center gap-2"
              >
                <Save size={16} />
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  )
}
