import { useParams, Link, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import {
  electiveBandsApi, subjectsApi, teachersApi, roomsApi, classesApi,
  type ElectiveBandType,
} from '../api/client'

const INPUT = 'border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'

const TYPE_LABELS: Record<ElectiveBandType, string> = {
  PRACTICAL: 'Praktisk/musisk',
  LOCAL: 'Lokalt',
}
const TYPE_COLORS: Record<ElectiveBandType, string> = {
  PRACTICAL: 'bg-purple-100 text-purple-700',
  LOCAL: 'bg-blue-100 text-blue-700',
}

const EMPTY_BAND = {
  grade_level: 8,
  band_type: 'PRACTICAL' as ElectiveBandType,
  name: '',
  hours_per_week: 2,
  requires_consecutive: true,
  draws_timebank: false,
}

export default function ElectiveBandsPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()

  const { data: bands = [] } = useQuery({ queryKey: ['elective-bands', sid], queryFn: () => electiveBandsApi.list(sid) })

  // When linked from the schedule view (#band-<id>), scroll to that band once loaded.
  const location = useLocation()
  useEffect(() => {
    if (!location.hash || bands.length === 0) return
    const el = document.querySelector(location.hash)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      el.classList.add('ring-2', 'ring-purple-400')
      const t = setTimeout(() => el.classList.remove('ring-2', 'ring-purple-400'), 1600)
      return () => clearTimeout(t)
    }
  }, [location.hash, bands.length])
  const { data: subjects = [] } = useQuery({ queryKey: ['subjects', sid], queryFn: () => subjectsApi.list(sid) })
  const { data: teachers = [] } = useQuery({ queryKey: ['teachers', sid], queryFn: () => teachersApi.list(sid) })
  const { data: rooms = [] } = useQuery({ queryKey: ['rooms', sid], queryFn: () => roomsApi.list(sid) })
  const { data: classes = [] } = useQuery({ queryKey: ['classes', sid], queryFn: () => classesApi.list(sid) })

  const subjectName = (id: number) => subjects.find((s) => s.id === id)?.name ?? '?'
  const teacherName = (id: number) => { const t = teachers.find((x) => x.id === id); return t ? `${t.first_name} ${t.last_name}` : '?' }
  const roomName = (id: number) => rooms.find((r) => r.id === id)?.name ?? '?'

  const grades = Array.from(new Set(classes.map((c) => c.grade_level))).sort((a, b) => a - b)

  const [form, setForm] = useState(EMPTY_BAND)
  const [showForm, setShowForm] = useState(false)

  const invalidate = () => qc.invalidateQueries({ queryKey: ['elective-bands', sid] })

  const createBand = useMutation({
    mutationFn: () => electiveBandsApi.create(sid, { ...form, offerings: [] }),
    onSuccess: () => { invalidate(); setShowForm(false); setForm(EMPTY_BAND) },
    onError: (e: any) => alert(`Kunne ikke oprette: ${e.response?.data?.detail ?? e.message}`),
  })
  const deleteBand = useMutation({
    mutationFn: (id: number) => electiveBandsApi.delete(sid, id),
    onSuccess: invalidate,
  })
  const addOffering = useMutation({
    mutationFn: ({ bandId, body }: { bandId: number; body: { subject_id: number; teacher_id: number; room_id: number } }) =>
      electiveBandsApi.addOffering(sid, bandId, body),
    onSuccess: invalidate,
    onError: (e: any) => alert(`Kunne ikke tilføje hold: ${e.response?.data?.detail ?? e.message}`),
  })
  const deleteOffering = useMutation({
    mutationFn: ({ bandId, oid }: { bandId: number; oid: number }) => electiveBandsApi.deleteOffering(sid, bandId, oid),
    onSuccess: invalidate,
  })

  return (
    <div className="max-w-3xl">
      <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline inline-block mb-4">← Tilbage til skole</Link>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold text-gray-900">Valgfag (bånd)</h2>
        <button onClick={() => setShowForm((v) => !v)} className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
          {showForm ? 'Annuller' : '+ Nyt bånd'}
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Et bånd reserverer samme tid for alle klasser på en årgang; flere fag kører parallelt, hvert i sit lokale.
        Skemalæggeren placerer båndet. Et 2. praktisk valgfag markeres som “trækker fra tidsbank”.
      </p>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Navn</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="8. årgang – praktisk valgfag" className={INPUT + ' w-full'} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Årgang</label>
              <select value={form.grade_level} onChange={(e) => setForm({ ...form, grade_level: +e.target.value })} className={INPUT + ' w-full'}>
                {(grades.length ? grades : [1,2,3,4,5,6,7,8,9]).map((g) => <option key={g} value={g}>{g}. årgang</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Type</label>
              <select value={form.band_type} onChange={(e) => setForm({ ...form, band_type: e.target.value as ElectiveBandType })} className={INPUT + ' w-full'}>
                <option value="PRACTICAL">Praktisk/musisk</option>
                <option value="LOCAL">Lokalt valgfag</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Lektioner/uge</label>
              <input type="number" min={1} max={10} value={form.hours_per_week} onChange={(e) => setForm({ ...form, hours_per_week: +e.target.value })} className={INPUT + ' w-full'} />
            </div>
          </div>
          <div className="flex gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.requires_consecutive} onChange={(e) => setForm({ ...form, requires_consecutive: e.target.checked })} />
              Dobbeltlektion (sammenhængende)
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.draws_timebank} onChange={(e) => setForm({ ...form, draws_timebank: e.target.checked })} />
              Trækker fra tidsbank (2. praktiske)
            </label>
          </div>
          <button onClick={() => createBand.mutate()} disabled={!form.name || createBand.isPending} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40">
            Opret bånd
          </button>
        </div>
      )}

      <div className="space-y-4">
        {bands.map((b) => (
          <div key={b.id} id={`band-${b.id}`} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm scroll-mt-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900">{b.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[b.band_type]}`}>{TYPE_LABELS[b.band_type]}</span>
                  {b.draws_timebank && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">Tidsbank</span>}
                </div>
                <div className="text-sm text-gray-500 mt-0.5">
                  {b.grade_level}. årgang · {b.hours_per_week} lektioner/uge{b.requires_consecutive ? ' · dobbelt' : ''}
                </div>
              </div>
              <button onClick={() => { if (confirm(`Slet bånd "${b.name}"?`)) deleteBand.mutate(b.id) }} className="text-sm text-red-500 hover:text-red-700">Slet</button>
            </div>

            <div className="divide-y divide-gray-100 mb-3">
              {b.offerings.map((o) => (
                <div key={o.id} className="py-2 flex items-center justify-between text-sm">
                  <span className="text-gray-800">{subjectName(o.subject_id)} <span className="text-gray-400">·</span> {teacherName(o.teacher_id)} <span className="text-gray-400">·</span> {roomName(o.room_id)}</span>
                  <button onClick={() => deleteOffering.mutate({ bandId: b.id, oid: o.id })} className="text-xs text-red-400 hover:text-red-600">Fjern</button>
                </div>
              ))}
              {b.offerings.length === 0 && <p className="py-2 text-sm text-gray-400">Ingen hold endnu — tilføj fag nedenfor.</p>}
            </div>

            <OfferingAdder
              subjects={subjects.filter((s) => !s.is_elective_slot)}
              teachers={teachers}
              rooms={rooms}
              onAdd={(body) => addOffering.mutate({ bandId: b.id, body })}
            />
          </div>
        ))}
        {bands.length === 0 && <p className="text-sm text-gray-500">Ingen valgfagsbånd endnu.</p>}
      </div>
    </div>
  )
}

function OfferingAdder({ subjects, teachers, rooms, onAdd }: {
  subjects: { id: number; name: string }[]
  teachers: { id: number; first_name: string; last_name: string }[]
  rooms: { id: number; name: string }[]
  onAdd: (body: { subject_id: number; teacher_id: number; room_id: number }) => void
}) {
  const [subjectId, setSubjectId] = useState<number | ''>('')
  const [teacherId, setTeacherId] = useState<number | ''>('')
  const [roomId, setRoomId] = useState<number | ''>('')
  const ready = subjectId !== '' && teacherId !== '' && roomId !== ''
  return (
    <div className="flex gap-2 flex-wrap items-center bg-gray-50 rounded-lg p-2">
      <select value={subjectId} onChange={(e) => setSubjectId(e.target.value === '' ? '' : +e.target.value)} className={INPUT}>
        <option value="">Fag…</option>
        {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <select value={teacherId} onChange={(e) => setTeacherId(e.target.value === '' ? '' : +e.target.value)} className={INPUT}>
        <option value="">Lærer…</option>
        {teachers.map((t) => <option key={t.id} value={t.id}>{t.first_name} {t.last_name}</option>)}
      </select>
      <select value={roomId} onChange={(e) => setRoomId(e.target.value === '' ? '' : +e.target.value)} className={INPUT}>
        <option value="">Lokale…</option>
        {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
      </select>
      <button
        onClick={() => { if (ready) { onAdd({ subject_id: subjectId, teacher_id: teacherId, room_id: roomId }); setSubjectId(''); setTeacherId(''); setRoomId('') } }}
        disabled={!ready}
        className="text-sm bg-gray-800 text-white px-3 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-40"
      >
        + Hold
      </button>
    </div>
  )
}
