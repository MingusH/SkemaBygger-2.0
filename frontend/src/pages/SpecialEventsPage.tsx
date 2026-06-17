import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { specialEventsApi, schoolsApi, classesApi, schedulesApi, type EventType, type EventScope } from '../api/client'

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  NO_SCHOOL: 'Fri dag / lukket',
  PROJECT_WEEK: 'Projektuge',
  EXCURSION: 'Klasseudflugt',
  EXAM_WEEK: 'Prøveuge',
  OTHER: 'Andet',
}

const EVENT_TYPE_COLORS: Record<EventType, string> = {
  NO_SCHOOL: 'bg-gray-100 text-gray-700',
  PROJECT_WEEK: 'bg-purple-100 text-purple-700',
  EXCURSION: 'bg-blue-100 text-blue-700',
  EXAM_WEEK: 'bg-orange-100 text-orange-700',
  OTHER: 'bg-gray-100 text-gray-600',
}

const INPUT = 'border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'

const EMPTY_FORM = {
  name: '',
  event_type: 'PROJECT_WEEK' as EventType,
  scope: 'SCHOOL_WIDE' as EventScope,
  start_date: '',
  end_date: '',
  hours_override: '',
  description: '',
  class_ids: [] as number[],
}

export default function SpecialEventsPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null)

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ['special-events', sid],
    queryFn: () => specialEventsApi.list(sid),
  })

  const { data: classes = [] } = useQuery({
    queryKey: ['classes', sid],
    queryFn: () => classesApi.list(sid),
  })

  const { data: schools = [] } = useQuery({ queryKey: ['schools'], queryFn: schoolsApi.list })
  const school = schools.find((s) => s.id === sid)

  const { data: schedules = [] } = useQuery({
    queryKey: ['schedules', sid],
    queryFn: () => schedulesApi.list(sid),
  })

  // Default the dropdown to the newest generated schedule once the list loads.
  const defaultScheduleId =
    [...schedules]
      .filter((s) => s.generated_at)
      .sort((a, b) => (b.generated_at ?? '').localeCompare(a.generated_at ?? ''))[0]?.id ?? null
  const effectiveScheduleId = selectedScheduleId ?? defaultScheduleId

  const { data: timeBank, refetch: refetchTimeBank, isFetching: tbFetching } = useQuery({
    queryKey: ['time-bank', sid, effectiveScheduleId],
    queryFn: () => schoolsApi.timeBank(sid, effectiveScheduleId ?? undefined),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      specialEventsApi.create(sid, {
        name: form.name,
        event_type: form.event_type,
        scope: form.scope,
        start_date: form.start_date,
        end_date: form.end_date,
        hours_override: form.hours_override ? parseFloat(form.hours_override) : null,
        description: form.description || null,
        class_ids: form.scope === 'PER_CLASS' ? form.class_ids : [],
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['special-events', sid] })
      qc.invalidateQueries({ queryKey: ['time-bank', sid] })
      setForm(EMPTY_FORM)
      setShowForm(false)
    },
    onError: (err: any) => alert(`Fejl: ${err.response?.data?.detail ?? err.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => specialEventsApi.delete(sid, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['special-events', sid] })
      qc.invalidateQueries({ queryKey: ['time-bank', sid] })
    },
  })

  const updateWeeksMutation = useMutation({
    mutationFn: (weeks: number) => schoolsApi.update(sid, { weeks_per_year: weeks }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schools'] })
      qc.invalidateQueries({ queryKey: ['time-bank', sid] })
    },
  })

  const toggleClass = (classId: number) => {
    setForm((f) => ({
      ...f,
      class_ids: f.class_ids.includes(classId)
        ? f.class_ids.filter((id) => id !== classId)
        : [...f.class_ids, classId],
    }))
  }

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline">← Tilbage til skole</Link>
        <h2 className="text-xl font-semibold text-gray-900 mt-2">Tidsbank & Særlige begivenheder</h2>
      </div>

      {/* ── Special Events ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">Særlige begivenheder ({events.length})</h3>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
          >
            {showForm ? 'Annuller' : '+ Opret begivenhed'}
          </button>
        </div>

        {showForm && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Navn</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="f.eks. Projektuge uge 6"
                  className={INPUT + ' w-full'}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Type</label>
                <select
                  value={form.event_type}
                  onChange={(e) => setForm({ ...form, event_type: e.target.value as EventType })}
                  className={INPUT + ' w-full'}
                >
                  {(Object.keys(EVENT_TYPE_LABELS) as EventType[]).map((t) => (
                    <option key={t} value={t}>{EVENT_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Fra dato</label>
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                  className={INPUT + ' w-full'}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Til dato</label>
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                  className={INPUT + ' w-full'}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Omfang</label>
                <select
                  value={form.scope}
                  onChange={(e) => setForm({ ...form, scope: e.target.value as EventScope, class_ids: [] })}
                  className={INPUT + ' w-full'}
                >
                  <option value="SCHOOL_WIDE">Hele skolen</option>
                  <option value="PER_CLASS">Bestemt klasse/klasser</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Timer med undervisning (valgfri)</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.hours_override}
                  onChange={(e) => setForm({ ...form, hours_override: e.target.value })}
                  placeholder="0 = ingen undervisning"
                  className={INPUT + ' w-full'}
                />
              </div>
            </div>

            {form.scope === 'PER_CLASS' && (
              <div>
                <label className="text-xs text-gray-500 mb-2 block">Berørte klasser</label>
                <div className="flex flex-wrap gap-2">
                  {classes.map((cls) => (
                    <button
                      key={cls.id}
                      type="button"
                      onClick={() => toggleClass(cls.id)}
                      className={`text-xs px-2.5 py-1 rounded-full border font-medium transition ${
                        form.class_ids.includes(cls.id)
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                      }`}
                    >
                      {cls.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label className="text-xs text-gray-500 mb-1 block">Beskrivelse (valgfri)</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Evt. yderligere info"
                className={INPUT + ' w-full'}
              />
            </div>

            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !form.name || !form.start_date || !form.end_date}
              className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Opretter...' : 'Gem begivenhed'}
            </button>
          </div>
        )}

        {eventsLoading ? (
          <p className="text-sm text-gray-400">Indlæser...</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-gray-400">Ingen begivenheder endnu.</p>
        ) : (
          <div className="space-y-2">
            {events.map((ev) => {
              const affectedClasses = ev.scope === 'PER_CLASS'
                ? classes.filter((c) => ev.class_ids.includes(c.id)).map((c) => c.name)
                : null
              return (
                <div key={ev.id} className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${EVENT_TYPE_COLORS[ev.event_type]}`}>
                      {EVENT_TYPE_LABELS[ev.event_type]}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{ev.name}</p>
                      <p className="text-xs text-gray-500">
                        {ev.start_date} → {ev.end_date}
                        {ev.scope === 'SCHOOL_WIDE' ? ' · Hele skolen' : affectedClasses?.length ? ` · ${affectedClasses.join(', ')}` : ''}
                        {ev.hours_override != null ? ` · ${ev.hours_override}t undervisning` : ' · Ingen undervisning'}
                        {ev.description ? ` · ${ev.description}` : ''}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      if (window.confirm(`Slet "${ev.name}"?`)) deleteMutation.mutate(ev.id)
                    }}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                  >
                    Slet
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ── Tidsbank ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="font-medium text-gray-900">Tidsbank</h3>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <label className="whitespace-nowrap">Skema</label>
              <select
                value={effectiveScheduleId ?? ''}
                onChange={(e) => setSelectedScheduleId(e.target.value ? Number(e.target.value) : null)}
                disabled={schedules.length === 0}
                className="border border-gray-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {schedules.length === 0 && <option value="">Ingen skemaer</option>}
                {schedules.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.status}
                    {s.generated_at ? ` · ${new Date(s.generated_at).toLocaleDateString('da-DK')}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <label className="whitespace-nowrap">Skoleuger/år</label>
              <input
                type="number"
                min="1"
                max="52"
                defaultValue={school?.weeks_per_year ?? 40}
                onBlur={(e) => {
                  const v = parseInt(e.target.value)
                  if (!isNaN(v) && v !== school?.weeks_per_year) updateWeeksMutation.mutate(v)
                }}
                className="w-16 border border-gray-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={() => refetchTimeBank()}
              disabled={tbFetching}
              className="text-sm bg-gray-100 text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              {tbFetching ? 'Beregner...' : 'Opdatér'}
            </button>
          </div>
        </div>

        {!timeBank || !timeBank.has_schedule ? (
          <p className="text-sm text-gray-400">
            {schedules.length === 0
              ? 'Generér et skema for at beregne tidsbanken.'
              : 'Det valgte skema har ingen lagte timer endnu. Generér skemaet for at beregne tidsbanken.'}
          </p>
        ) : timeBank.entries.length === 0 ? (
          <p className="text-sm text-gray-400">Ingen aktive klasser fundet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-gray-500 font-medium border-b border-gray-200">
                  <th className="text-left py-2 pr-4">Klasse</th>
                  <th className="text-right py-2 px-3">Skoletimer/år</th>
                  <th className="text-right py-2 px-3">Ministeriets min.</th>
                  <th className="text-right py-2 px-3">Tidsbank-pulje</th>
                  <th className="text-right py-2 px-3">Tidsbank brugt</th>
                  <th className="text-right py-2 pl-3">Timer tilbage til begivenheder</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {timeBank.entries.map((entry) => (
                  <tr key={entry.class_id} className={entry.is_sufficient ? '' : 'bg-red-50'}>
                    <td className="py-2 pr-4 font-medium text-gray-900">{entry.class_name}</td>
                    <td className="text-right py-2 px-3 font-medium text-gray-900">{entry.delivered.toFixed(0)}</td>
                    <td className="text-right py-2 px-3 text-gray-500">{entry.ministry_min_hours.toFixed(0)}</td>
                    <td className="text-right py-2 px-3 text-gray-500">{entry.timebank_pool.toFixed(0)}</td>
                    <td className="text-right py-2 px-3 text-gray-600">{entry.timebank_used > 0 ? `−${entry.timebank_used.toFixed(0)}` : '0'}</td>
                    <td className={`text-right py-2 pl-3 font-semibold ${entry.is_sufficient ? 'text-green-600' : 'text-red-600'}`}>
                      {entry.balance > 0 ? '+' : ''}{entry.balance.toFixed(0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 mt-3">
              Timer er i klokketimer (60 min) inkl. pauser, beregnet ud fra det valgte skema × skoleuger/år.
              <strong> Skoletimer/år</strong> = klassens reelle skoletid (start til slut hver dag) minus tidsbank brugt.
              <strong> Ministeriets min.</strong> = mindste årlige undervisningstid. <strong>Tidsbank-pulje</strong> = den fleksible
              pulje over minimum. <strong>Tidsbank brugt</strong> = timer som særlige begivenheder trækker fra puljen.
              <strong> Timer tilbage til begivenheder</strong> = Skoletimer/år − Ministeriets min., dvs. hvor mange timer
              der stadig kan bruges på begivenheder før minimum brydes. Rød = under minimum.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
