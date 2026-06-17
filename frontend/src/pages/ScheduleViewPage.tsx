import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import {
  schedulesApi, assignmentsApi, timeslotsApi, subjectsApi,
  teachersApi, roomsApi, classesApi, electiveBandsApi,
  type ScheduleEntry, type ElectiveBand, type ElectiveOffering,
} from '../api/client'

const DAYS = ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag']
type ViewMode = 'class' | 'teacher' | 'room'

const MODE_LABELS: Record<ViewMode, string> = {
  class: 'Klasse',
  teacher: 'Lærer',
  room: 'Lokale',
}

export default function ScheduleViewPage() {
  const { schoolId, scheduleId } = useParams<{ schoolId: string; scheduleId: string }>()
  const sid = Number(schoolId)
  const schedId = Number(scheduleId)
  const navigate = useNavigate()

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['schedule-entries', sid, schedId],
    queryFn: () => schedulesApi.entries(sid, schedId),
  })
  const { data: assignments = [] } = useQuery({ queryKey: ['assignments', sid], queryFn: () => assignmentsApi.list(sid) })
  const { data: timeslots = [] } = useQuery({ queryKey: ['timeslots', sid], queryFn: () => timeslotsApi.list(sid) })
  const { data: subjects = [] } = useQuery({ queryKey: ['subjects', sid], queryFn: () => subjectsApi.list(sid) })
  const { data: teachers = [] } = useQuery({ queryKey: ['teachers', sid], queryFn: () => teachersApi.list(sid) })
  const { data: rooms = [] } = useQuery({ queryKey: ['rooms', sid], queryFn: () => roomsApi.list(sid) })
  const { data: classes = [] } = useQuery({ queryKey: ['classes', sid], queryFn: () => classesApi.list(sid) })
  const { data: bands = [] } = useQuery({ queryKey: ['elective-bands', sid], queryFn: () => electiveBandsApi.list(sid) })

  const [mode, setMode] = useState<ViewMode>('class')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  // Lookup maps
  const assignmentMap = useMemo(() => new Map(assignments.map((a) => [a.id, a])), [assignments])
  const slotMap = useMemo(() => new Map(timeslots.map((t) => [t.id, t])), [timeslots])
  const subjectMap = useMemo(() => new Map(subjects.map((s) => [s.id, s])), [subjects])
  const teacherMap = useMemo(() => new Map(teachers.map((t) => [t.id, t])), [teachers])
  const roomMap = useMemo(() => new Map(rooms.map((r) => [r.id, r])), [rooms])
  const classMap = useMemo(() => new Map(classes.map((c) => [c.id, c])), [classes])
  // elective offering id → { offering, band }
  const offeringMap = useMemo(() => {
    const m = new Map<number, { offering: ElectiveOffering; band: ElectiveBand }>()
    for (const b of bands) for (const o of b.offerings) m.set(o.id, { offering: o, band: b })
    return m
  }, [bands])

  // Options for the entity picker based on mode
  const options = useMemo(() => {
    if (mode === 'class')
      return [...classes].sort((a, b) => a.grade_level - b.grade_level || a.name.localeCompare(b.name))
        .map((c) => ({ id: c.id, label: c.name }))
    if (mode === 'teacher')
      return [...teachers].sort((a, b) => a.last_name.localeCompare(b.last_name))
        .map((t) => ({ id: t.id, label: `${t.first_name} ${t.last_name} (${t.short_code})` }))
    return [...rooms].sort((a, b) => a.name.localeCompare(b.name))
      .map((r) => ({ id: r.id, label: `${r.name} (${r.short_code})` }))
  }, [mode, classes, teachers, rooms])

  // Distinct period numbers, sorted, with a representative time label
  const periods = useMemo(() => {
    const byPeriod = new Map<number, { start: string; end: string }>()
    for (const t of timeslots) {
      if (!byPeriod.has(t.period_number))
        byPeriod.set(t.period_number, { start: t.start_time.slice(0, 5), end: t.end_time.slice(0, 5) })
    }
    return [...byPeriod.entries()].sort((a, b) => a[0] - b[0]).map(([num, time]) => ({ num, ...time }))
  }, [timeslots])

  // Filter entries to the selected entity (handles regular and elective-band entries)
  const matches = (e: ScheduleEntry): boolean => {
    if (selectedId === null) return false
    if (mode === 'room') return e.room_id === selectedId
    if (e.assignment_id != null) {
      const a = assignmentMap.get(e.assignment_id)
      if (!a) return false
      return mode === 'class' ? a.student_class_id === selectedId : a.teacher_id === selectedId
    }
    if (e.elective_offering_id != null) {
      const ob = offeringMap.get(e.elective_offering_id)
      if (!ob) return false
      if (mode === 'class') {
        const cls = classMap.get(selectedId)
        return !!cls && cls.grade_level === ob.band.grade_level   // whole grade attends
      }
      return ob.offering.teacher_id === selectedId                 // teacher mode
    }
    return false
  }

  // Grid lookup: (period, day) → entries for the selected entity
  const cellEntries = (period: number, day: number) => {
    return entries.filter((e) => {
      const slot = slotMap.get(e.time_slot_id)
      if (!slot || slot.period_number !== period || slot.day_of_week !== day) return false
      return matches(e)
    })
  }

  if (isLoading) return <div className="text-gray-500">Indlæser skema...</div>

  return (
    <div className="max-w-6xl">
      <button onClick={() => navigate(`/schools/${sid}/schedules`)} className="text-sm text-gray-500 hover:text-gray-800 mb-4">
        ← Tilbage til skemaer
      </button>

      <div className="flex flex-wrap items-end gap-4 mb-6">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Vis efter</label>
          <div className="flex rounded-lg border border-gray-300 overflow-hidden">
            {(['class', 'teacher', 'room'] as ViewMode[]).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setSelectedId(null) }}
                className={`px-4 py-2 text-sm font-medium ${mode === m ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
              >
                {MODE_LABELS[m]}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{MODE_LABELS[mode]}</label>
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value === '' ? null : Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-64"
          >
            <option value="">— vælg {MODE_LABELS[mode].toLowerCase()} —</option>
            {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {selectedId === null ? (
        <p className="text-gray-500 text-sm">Vælg en {MODE_LABELS[mode].toLowerCase()} for at se skemaet.</p>
      ) : periods.length === 0 ? (
        <p className="text-gray-500 text-sm">Ingen lektioner defineret for denne skole.</p>
      ) : (
        <div className="overflow-x-auto bg-white border border-gray-200 rounded-xl shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-3 py-2 text-left text-gray-500 font-medium w-24">Lektion</th>
                {DAYS.map((d) => (
                  <th key={d} className="px-3 py-2 text-center text-gray-600 font-medium">{d}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periods.map((p) => (
                <tr key={p.num} className="border-b border-gray-100">
                  <td className="px-3 py-2 align-top text-xs text-gray-500">
                    <div className="font-medium text-gray-700">{p.num}.</div>
                    <div>{p.start}–{p.end}</div>
                  </td>
                  {[1, 2, 3, 4, 5].map((day) => {
                    const cells = cellEntries(p.num, day)
                    const regular = cells.filter((e) => e.assignment_id != null)
                    // Collapse all offerings of one band in this cell into a single block.
                    const bandGroups = new Map<number, { band: ElectiveBand; detail?: string }>()
                    for (const e of cells) {
                      if (e.elective_offering_id == null) continue
                      const ob = offeringMap.get(e.elective_offering_id)
                      if (!ob) continue
                      // In teacher/room view, show which subject this person/room has in the band.
                      const detail = mode === 'class' ? undefined
                        : subjectMap.get(ob.offering.subject_id)?.short_code
                      bandGroups.set(ob.band.id, { band: ob.band, detail })
                    }
                    return (
                      <td key={day} className="px-1.5 py-1.5 align-top">
                        <div className="space-y-1">
                          {regular.map((e) => {
                            const a = assignmentMap.get(e.assignment_id!)
                            const subj = a ? subjectMap.get(a.subject_id) : undefined
                            const teacher = a ? teacherMap.get(a.teacher_id) : undefined
                            const room = roomMap.get(e.room_id)
                            const cls = a ? classMap.get(a.student_class_id) : undefined
                            const lines: string[] = []
                            if (mode !== 'class' && cls) lines.push(cls.name)
                            if (mode !== 'teacher' && teacher) lines.push(teacher.short_code)
                            if (mode !== 'room' && room) lines.push(room.short_code)
                            return (
                              <div
                                key={e.id}
                                className="rounded-md px-2 py-1 text-white text-xs leading-tight"
                                style={{ backgroundColor: subj?.color_hex ?? '#6b7280' }}
                              >
                                <div className="font-semibold">{subj?.short_code ?? subj?.name ?? '—'}</div>
                                {lines.length > 0 && <div className="opacity-90">{lines.join(' · ')}</div>}
                              </div>
                            )
                          })}
                          {[...bandGroups.values()].map(({ band, detail }) => (
                            <button
                              key={`band-${band.id}`}
                              onClick={() => navigate(`/schools/${sid}/electives#band-${band.id}`)}
                              title="Gå til valgfagsbånd"
                              className="w-full text-left rounded-md px-2 py-1 text-white text-xs leading-tight bg-purple-600 hover:bg-purple-700"
                            >
                              <div className="font-semibold">{band.name}</div>
                              <div className="opacity-90">{detail ? detail : 'Valgfag'}</div>
                            </button>
                          ))}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
