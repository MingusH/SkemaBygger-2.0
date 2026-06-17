import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import {
  schoolsApi, teachersApi, classesApi, subjectsApi, roomsApi, assignmentsApi, schedulesApi,
  timeslotsApi, type TimeSlot,
} from '../api/client'

const toMin = (t: string) => { const [h, m] = t.split(':').map(Number); return h * 60 + m }
const fmt = (mins: number) => `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`
const LESSON_MIN = 45

export default function SchoolPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: schools = [] } = useQuery({ queryKey: ['schools'], queryFn: schoolsApi.list })
  const school = schools.find((s) => s.id === sid)

  const { data: teachers = [] } = useQuery({ queryKey: ['teachers', sid], queryFn: () => teachersApi.list(sid) })
  const { data: classes = [] } = useQuery({ queryKey: ['classes', sid], queryFn: () => classesApi.list(sid) })
  const { data: subjects = [] } = useQuery({ queryKey: ['subjects', sid], queryFn: () => subjectsApi.list(sid) })
  const { data: rooms = [] } = useQuery({ queryKey: ['rooms', sid], queryFn: () => roomsApi.list(sid) })
  const { data: assignments = [] } = useQuery({ queryKey: ['assignments', sid], queryFn: () => assignmentsApi.list(sid) })
  const { data: schedules = [] } = useQuery({ queryKey: ['schedules', sid], queryFn: () => schedulesApi.list(sid) })
  const { data: timeslots = [] } = useQuery({ queryKey: ['timeslots', sid], queryFn: () => timeslotsApi.list(sid) })

  // ── Periods-per-day editor (adds/removes bell-schedule periods to match) ──
  const [periods, setPeriods] = useState(7)
  useEffect(() => { if (school) setPeriods(school.periods_per_day) }, [school?.periods_per_day])

  const updatePeriods = useMutation({
    mutationFn: async (target: number) => {
      const days = school?.days_per_week ?? 5
      const maxP = timeslots.reduce((m, t) => Math.max(m, t.period_number), 0)

      if (target > maxP) {
        // Extend the day: new lessons run back-to-back from the latest end time (default 08:00).
        let cursor = timeslots.reduce((m, t) => Math.max(m, toMin(t.end_time)), 8 * 60)
        const newSlots: Omit<TimeSlot, 'id' | 'school_id'>[] = []
        for (let p = maxP + 1; p <= target; p++) {
          const start = fmt(cursor)
          cursor += LESSON_MIN
          const end = fmt(cursor)
          for (let day = 1; day <= days; day++) {
            newSlots.push({ day_of_week: day, period_number: p, start_time: start, end_time: end, label: null })
          }
        }
        if (newSlots.length) await timeslotsApi.createBulk(sid, newSlots)
      } else if (target < maxP) {
        const toDelete = timeslots.filter((t) => t.period_number > target)
        await Promise.all(toDelete.map((t) => timeslotsApi.delete(sid, t.id)))
      }
      await schoolsApi.update(sid, { periods_per_day: target })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schools'] })
      qc.invalidateQueries({ queryKey: ['timeslots', sid] })
    },
    onError: (err: any) => alert(`Kunne ikke opdatere lektioner: ${err.response?.data?.detail ?? err.message}`),
  })

  const stats = [
    { label: 'Lærere', value: teachers.length },
    { label: 'Klasser', value: classes.length },
    { label: 'Fag', value: subjects.length },
    { label: 'Lokaler', value: rooms.length },
    { label: 'Fag-tildelinger', value: assignments.length },
    { label: 'Skemaer', value: schedules.length },
  ]

  const sections = [
    { label: 'Opsætning', desc: 'Fag, lærere, klasser og lokaler', to: `/schools/${sid}/setup` },
    { label: 'Tidspunkter', desc: 'Lektioner og utilgængelighed', to: `/schools/${sid}/constraints` },
    { label: 'Fag-tildeling', desc: 'Hvem underviser hvad', to: `/schools/${sid}/assignments` },
    { label: 'Skema', desc: 'Generér og se skemaer', to: `/schools/${sid}/schedules` },
    { label: 'Tidsbank', desc: 'Særlige begivenheder og timeopgørelse', to: `/schools/${sid}/special-events` },
    { label: 'Valgfag', desc: 'Valgfagsbånd på tværs af klasser', to: `/schools/${sid}/electives` },
  ]

  return (
    <div className="max-w-4xl">
      <Link to="/" className="text-sm text-blue-600 hover:underline">← Tilbage til skoler</Link>
      <h2 className="text-2xl font-semibold text-gray-900 mt-2 mb-1">{school?.name ?? 'Skole'}</h2>
      <p className="text-sm text-gray-500 mb-6">
        {school && `${school.academic_year} · ${school.days_per_week} dage · ${school.periods_per_day} perioder/dag`}
      </p>

      {/* School day length */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm mb-8 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-sm font-medium text-gray-900">Lektioner pr. dag</div>
          <div className="text-xs text-gray-500 mt-0.5">
            Bestemmer hvor mange lektioner der er plads til. Tilføjer/fjerner lektioner i ugeskemaet — juster tider under Tidspunkter.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPeriods((p) => Math.max(1, p - 1))}
            className="w-8 h-8 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-lg leading-none"
          >
            −
          </button>
          <input
            type="number"
            min={1}
            max={14}
            value={periods}
            onChange={(e) => setPeriods(Math.max(1, +e.target.value))}
            className="w-16 text-center border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => setPeriods((p) => Math.min(14, p + 1))}
            className="w-8 h-8 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-lg leading-none"
          >
            +
          </button>
          <button
            onClick={() => updatePeriods.mutate(periods)}
            disabled={updatePeriods.isPending || periods === school?.periods_per_day}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 ml-1"
          >
            {updatePeriods.isPending ? 'Gemmer...' : 'Gem'}
          </button>
        </div>
      </div>

      {/* Overview */}
      <h3 className="text-sm font-medium text-gray-600 mb-2">Overblik</h3>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-8">
        {stats.map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4 text-center shadow-sm">
            <div className="text-2xl font-semibold text-gray-900">{s.value}</div>
            <div className="text-xs text-gray-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Navigation */}
      <h3 className="text-sm font-medium text-gray-600 mb-2">Administrér</h3>
      <div className="grid grid-cols-2 gap-4">
        {sections.map((sec) => (
          <button
            key={sec.label}
            onClick={() => navigate(sec.to)}
            className="text-left bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:border-blue-400 hover:shadow transition"
          >
            <div className="font-medium text-gray-900">{sec.label}</div>
            <div className="text-sm text-gray-500 mt-1">{sec.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
