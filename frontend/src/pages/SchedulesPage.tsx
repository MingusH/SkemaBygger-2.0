import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { schedulesApi, schoolsApi } from '../api/client'

const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Kladde', GENERATING: 'Genererer...', COMPLETE: 'Færdigt',
  FAILED: 'Fejlet', PUBLISHED: 'Publiceret',
}
const STATUS_COLORS: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-700',
  GENERATING: 'bg-yellow-100 text-yellow-700',
  COMPLETE: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  PUBLISHED: 'bg-blue-100 text-blue-700',
}

export default function SchedulesPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ['schedules', sid],
    queryFn: () => schedulesApi.list(sid),
    // While any schedule is still solving, re-check every 2s; stop once none are.
    refetchInterval: (query) =>
      (query.state.data ?? []).some((s) => s.status === 'GENERATING') ? 2000 : false,
  })

  const [form, setForm] = useState({ name: 'Skema 2026/2027', academic_year: '2026/2027' })
  const [validationResult, setValidationResult] = useState<any>(null)

  const createMutation = useMutation({
    mutationFn: () => schedulesApi.create(sid, form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules', sid] }),
  })

  const generateMutation = useMutation({
    mutationFn: (scheduleId: number) => schedulesApi.generate(sid, scheduleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules', sid] }),
    onError: (err: any) => alert(`Genereringsfejl: ${err.response?.data?.detail?.message ?? err.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (scheduleId: number) => schedulesApi.delete(sid, scheduleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules', sid] }),
    onError: (err: any) => alert(`Sletningsfejl: ${err.message}`),
  })

  const validateMutation = useMutation({
    mutationFn: () => schoolsApi.validate(sid),
    onSuccess: (data) => setValidationResult(data),
  })

  if (isLoading) return <div className="text-gray-500">Indlæser...</div>

  return (
    <div className="max-w-3xl">
      <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline inline-block mb-4">← Tilbage til skole</Link>
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Skemaer</h2>

      {/* Validation */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-gray-900">Validering</h3>
          <button
            onClick={() => validateMutation.mutate()}
            className="text-sm bg-gray-800 text-white px-3 py-1.5 rounded-lg hover:bg-gray-900"
          >
            Kør validering
          </button>
        </div>
        {validationResult && (
          <div className="text-sm space-y-1">
            <p className={validationResult.is_valid ? 'text-green-700 font-medium' : 'text-red-700 font-medium'}>
              {validationResult.is_valid ? '✓ Klar til generering' : `✗ ${validationResult.errors.length} fejl fundet`}
            </p>
            {validationResult.errors.map((e: any, i: number) => (
              <p key={i} className="text-red-600">[{e.rule}] {e.message}</p>
            ))}
            {validationResult.warnings.map((w: any, i: number) => (
              <p key={i} className="text-yellow-600">[{w.rule}] {w.message}</p>
            ))}
          </div>
        )}
      </div>

      {/* Create schedule */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6">
        <h3 className="font-medium text-gray-900 mb-3">Nyt skema</h3>
        <div className="flex gap-3 text-sm">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Navn"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => createMutation.mutate()}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Opret
          </button>
        </div>
      </div>

      {/* Schedule list */}
      <div className="space-y-3">
        {schedules.map((s) => (
          <div key={s.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900">{s.name}</p>
                <p className="text-sm text-gray-500">
                  {s.academic_year}
                  {s.generated_at && ` · Genereret ${new Date(s.generated_at).toLocaleDateString('da-DK')}`}
                  {s.score != null && ` · Score: ${s.score.toFixed(1)}`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[s.status]}`}>
                  {STATUS_LABELS[s.status]}
                </span>
                {(s.status === 'DRAFT' || s.status === 'FAILED') && (
                  <button
                    onClick={() => generateMutation.mutate(s.id)}
                    disabled={generateMutation.isPending}
                    className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    Generér skema
                  </button>
                )}
                {(s.status === 'COMPLETE' || s.status === 'PUBLISHED') && (
                  <button
                    onClick={() => navigate(`/schools/${sid}/schedules/${s.id}/view`)}
                    className="text-sm bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700"
                  >
                    Vis skema
                  </button>
                )}
                <button
                  onClick={() => {
                    if (window.confirm(`Slet skemaet "${s.name}"?`)) {
                      deleteMutation.mutate(s.id)
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="text-sm bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  Slet
                </button>
              </div>
            </div>
          </div>
        ))}
        {schedules.length === 0 && (
          <p className="text-sm text-gray-500">Ingen skemaer endnu. Opret dit første.</p>
        )}
      </div>
    </div>
  )
}
