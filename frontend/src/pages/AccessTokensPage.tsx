import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tokensApi, type AccessTokenCreated } from '../api/client'

const INPUT = 'border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'

const EXPIRY_OPTIONS = [
  { label: 'Udløber aldrig', value: null },
  { label: '30 dage', value: 30 },
  { label: '90 dage', value: 90 },
  { label: '1 år', value: 365 },
]

function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('da-DK', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function AccessTokensPage() {
  const qc = useQueryClient()
  const { data: tokens = [], isLoading } = useQuery({ queryKey: ['access-tokens'], queryFn: tokensApi.list })

  const [name, setName] = useState('')
  const [expiresDays, setExpiresDays] = useState<number | null>(null)
  const [justCreated, setJustCreated] = useState<AccessTokenCreated | null>(null)
  const [copied, setCopied] = useState(false)

  const createMutation = useMutation({
    mutationFn: () => tokensApi.create({ name: name.trim(), expires_days: expiresDays }),
    onSuccess: (tok) => {
      setJustCreated(tok)
      setName('')
      setCopied(false)
      qc.invalidateQueries({ queryKey: ['access-tokens'] })
    },
    onError: (e: any) => alert(`Kunne ikke oprette token: ${e.response?.data?.detail ?? e.message}`),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => tokensApi.revoke(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['access-tokens'] }),
  })

  const copyToken = () => {
    if (!justCreated) return
    navigator.clipboard.writeText(justCreated.token)
    setCopied(true)
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Adgangstokens</h2>
        <p className="text-sm text-gray-500 mt-1">
          Langlivede tokens til at forbinde en AI-klient (f.eks. Claude Desktop) til SkemaBygger via MCP.
          En token giver samme adgang som din bruger — del den aldrig, og tilbagekald den hvis den lækkes.
        </p>
      </div>

      {/* Newly created token — shown once */}
      {justCreated && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 space-y-2">
          <p className="text-sm font-medium text-amber-800">
            Kopiér din token nu — den vises kun denne ene gang.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded-lg px-3 py-2 text-sm font-mono break-all">
              {justCreated.token}
            </code>
            <button
              onClick={copyToken}
              className="text-sm bg-amber-600 text-white px-3 py-2 rounded-lg hover:bg-amber-700 whitespace-nowrap"
            >
              {copied ? 'Kopieret ✓' : 'Kopiér'}
            </button>
          </div>
          <details className="text-xs text-amber-800">
            <summary className="cursor-pointer">Sådan bruger du den i Claude Desktop</summary>
            <pre className="mt-2 bg-white border border-amber-200 rounded-lg p-3 overflow-x-auto text-[11px] leading-relaxed">{`{
  "mcpServers": {
    "skemabygger": {
      "url": "https://<dit-domæne>/mcp/",
      "headers": { "Authorization": "Bearer ${justCreated.token}" }
    }
  }
}`}</pre>
          </details>
          <button onClick={() => setJustCreated(null)} className="text-xs text-amber-700 hover:text-amber-900 underline">
            Skjul
          </button>
        </div>
      )}

      {/* Create form */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-medium text-gray-900 mb-3">Ny token</h3>
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="text-xs text-gray-500 mb-1 block">Navn</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="f.eks. Min bærbar – Claude Desktop"
              className={INPUT + ' w-full'}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Udløb</label>
            <select
              value={expiresDays ?? ''}
              onChange={(e) => setExpiresDays(e.target.value === '' ? null : Number(e.target.value))}
              className={INPUT}
            >
              {EXPIRY_OPTIONS.map((o) => (
                <option key={o.label} value={o.value ?? ''}>{o.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40"
          >
            {createMutation.isPending ? 'Opretter...' : 'Opret token'}
          </button>
        </div>
      </section>

      {/* Existing tokens */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-medium text-gray-900 mb-3">Dine tokens ({tokens.length})</h3>
        {isLoading ? (
          <p className="text-sm text-gray-400">Indlæser...</p>
        ) : tokens.length === 0 ? (
          <p className="text-sm text-gray-400">Ingen tokens endnu.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {tokens.map((t) => {
              const expired = t.expires_at != null && new Date(t.expires_at) < new Date()
              return (
                <div key={t.id} className="py-3 flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium text-gray-900">{t.name}</span>
                    <span className="ml-2 font-mono text-xs text-gray-400">{t.prefix}…</span>
                    {expired && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">Udløbet</span>}
                    <div className="text-xs text-gray-500 mt-0.5">
                      Oprettet {fmtDate(t.created_at)} · Sidst brugt {fmtDate(t.last_used_at)} · Udløb {t.expires_at ? fmtDate(t.expires_at) : 'aldrig'}
                    </div>
                  </div>
                  <button
                    onClick={() => { if (window.confirm(`Tilbagekald "${t.name}"? Klienter der bruger den mister adgang straks.`)) revokeMutation.mutate(t.id) }}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                  >
                    Tilbagekald
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
