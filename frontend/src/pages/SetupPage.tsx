import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { teachersApi, roomsApi, classesApi, schoolsApi, subjectsApi } from '../api/client'

const ROOM_TYPES = ['STANDARD', 'GYM', 'SCIENCE_LAB', 'COMPUTER', 'MUSIC', 'WORKSHOP', 'KITCHEN', 'ART', 'OTHER']
const ROOM_TYPE_LABELS: Record<string, string> = {
  STANDARD: 'Standardlokale', GYM: 'Gymnastiksal', SCIENCE_LAB: 'Naturfagslokale',
  COMPUTER: 'Computerlokale', MUSIC: 'Musiklokale', WORKSHOP: 'Værksted',
  KITCHEN: 'Køkken', ART: 'Billedkunst/krea', OTHER: 'Andet',
}
const INPUT = 'border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'

export default function SetupPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()

  const { data: subjects = [] } = useQuery({ queryKey: ['subjects', sid], queryFn: () => subjectsApi.list(sid) })
  const { data: teachers = [] } = useQuery({ queryKey: ['teachers', sid], queryFn: () => teachersApi.list(sid) })
  const { data: rooms = [] } = useQuery({ queryKey: ['rooms', sid], queryFn: () => roomsApi.list(sid) })
  const { data: classes = [] } = useQuery({ queryKey: ['classes', sid], queryFn: () => classesApi.list(sid) })

  // ── Subjects ──────────────────────────────────────────────────────────────
  const seedMutation = useMutation({
    mutationFn: () => schoolsApi.seedSubjects(sid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subjects', sid] }),
  })

  // Custom (non-UVM) subject, e.g. "Klassens tid". Assign it manually per class.
  const [subjectForm, setSubjectForm] = useState({ name: '', short_code: '' })
  const createSubject = useMutation({
    mutationFn: () => subjectsApi.create(sid, { name: subjectForm.name.trim(), short_code: subjectForm.short_code.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects', sid] })
      setSubjectForm({ name: '', short_code: '' })
    },
    onError: (e: any) => alert(`Kunne ikke oprette fag: ${e.response?.data?.detail ?? e.message}`),
  })

  const setSubjectRoomType = useMutation({
    mutationFn: ({ id, required_room_type }: { id: number; required_room_type: string | null }) =>
      subjectsApi.update(sid, id, {
        required_room_type,
        requires_special_room: required_room_type !== null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subjects', sid] }),
  })

  const setSubjectDoubleLessons = useMutation({
    mutationFn: ({ id, double_lessons }: { id: number; double_lessons: boolean }) =>
      subjectsApi.update(sid, id, { double_lessons }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subjects', sid] }),
  })

  // Swap the priority values of two adjacent subjects to reorder the ranking.
  const swapPriority = useMutation({
    mutationFn: async ({ a, b }: { a: { id: number; priority: number }; b: { id: number; priority: number } }) => {
      await subjectsApi.update(sid, a.id, { priority: b.priority })
      await subjectsApi.update(sid, b.id, { priority: a.priority })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subjects', sid] }),
  })

  // Whether a subject may receive surplus ("extra") lessons above the ministry minimum.
  const setSubjectAddExtra = useMutation({
    mutationFn: ({ id, add_extra }: { id: number; add_extra: boolean }) =>
      subjectsApi.update(sid, id, { add_extra }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subjects', sid] }),
  })

  // ── Teachers ──────────────────────────────────────────────────────────────
  const [teacherForm, setTeacherForm] = useState({ first_name: '', last_name: '', short_code: '', email: '' })
  const [teacherSubjectIds, setTeacherSubjectIds] = useState<number[]>([])
  const [editingTeacherId, setEditingTeacherId] = useState<number | null>(null)

  const resetTeacherForm = () => {
    setTeacherForm({ first_name: '', last_name: '', short_code: '', email: '' })
    setTeacherSubjectIds([])
    setEditingTeacherId(null)
  }

  const startEditTeacher = (t: typeof teachers[number]) => {
    setEditingTeacherId(t.id)
    setTeacherForm({ first_name: t.first_name, last_name: t.last_name, short_code: t.short_code, email: t.email ?? '' })
    setTeacherSubjectIds(t.subject_ids)
    document.getElementById('teacher-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const createTeacher = useMutation({
    mutationFn: () => teachersApi.create(sid, { ...teacherForm, max_hours_per_week: null, subject_ids: teacherSubjectIds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['teachers', sid] })
      resetTeacherForm()
    },
  })

  const updateTeacher = useMutation({
    mutationFn: () => teachersApi.update(sid, editingTeacherId!, { ...teacherForm, subject_ids: teacherSubjectIds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['teachers', sid] })
      resetTeacherForm()
    },
    onError: (e: any) => alert(`Kunne ikke gemme: ${e.response?.data?.detail ?? e.message}`),
  })

  const deleteTeacher = useMutation({
    mutationFn: (id: number) => teachersApi.delete(sid, id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ['teachers', sid] })
      if (editingTeacherId === id) resetTeacherForm()
    },
  })

  const toggleTeacherSubject = (id: number) =>
    setTeacherSubjectIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])

  // ── Rooms ─────────────────────────────────────────────────────────────────
  const [roomForm, setRoomForm] = useState({ name: '', short_code: '', capacity: 30, room_type: 'STANDARD' })

  const createRoom = useMutation({
    mutationFn: () => roomsApi.create(sid, roomForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rooms', sid] })
      setRoomForm({ name: '', short_code: '', capacity: 30, room_type: 'STANDARD' })
    },
  })

  const deleteRoom = useMutation({
    mutationFn: (id: number) => roomsApi.delete(sid, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rooms', sid] }),
  })

  // ── Classes ───────────────────────────────────────────────────────────────
  const [bulkForm, setBulkForm] = useState({ grade_start: 1, grade_end: 9, suffixes: 'A, B, C', student_count: 25 })

  const createBulkClasses = useMutation({
    mutationFn: () =>
      classesApi.createBulk(sid, {
        grade_start: bulkForm.grade_start,
        grade_end: bulkForm.grade_end,
        suffixes: bulkForm.suffixes.split(',').map((s) => s.trim()).filter(Boolean),
        student_count: bulkForm.student_count,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['classes', sid] }),
  })

  const deleteClass = useMutation({
    mutationFn: (id: number) => classesApi.delete(sid, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['classes', sid] }),
  })

  const setHomeRoom = useMutation({
    mutationFn: ({ id, home_room_id }: { id: number; home_room_id: number | null }) =>
      classesApi.update(sid, id, { home_room_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['classes', sid] }),
  })

  // Create one dedicated home room per class that lacks one, then assign it
  const autoAssignHomeRooms = useMutation({
    mutationFn: async () => {
      let created = 0
      for (const c of classes) {
        if (!c.is_active || c.home_room_id) continue
        const room = await roomsApi.create(sid, {
          name: `Lokale ${c.name}`,
          short_code: c.name.slice(0, 10),
          capacity: c.student_count || 30,
          room_type: 'STANDARD',
        })
        await classesApi.update(sid, c.id, { home_room_id: room.id })
        created++
      }
      return created
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', sid] })
      qc.invalidateQueries({ queryKey: ['rooms', sid] })
    },
  })

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline">← Tilbage til skole</Link>
        <h2 className="text-xl font-semibold text-gray-900 mt-2">Opsætning</h2>
      </div>

      {/* ── Subjects ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">Fag ({subjects.length})</h3>
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="text-sm bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {seedMutation.isPending ? 'Henter...' : 'Hent fra UVM'}
          </button>
        </div>

        {/* Custom subject (e.g. "Klassens tid") — no UVM timetal, tildeles manuelt pr. klasse */}
        <div className="flex gap-2 mb-4">
          <input
            placeholder="Eget fag (f.eks. Klassens tid)"
            value={subjectForm.name}
            onChange={(e) => setSubjectForm({ ...subjectForm, name: e.target.value })}
            className={INPUT + ' flex-1'}
          />
          <input
            placeholder="Kode"
            maxLength={10}
            value={subjectForm.short_code}
            onChange={(e) => setSubjectForm({ ...subjectForm, short_code: e.target.value })}
            className={INPUT + ' w-24'}
          />
          <button
            onClick={() => createSubject.mutate()}
            disabled={!subjectForm.name.trim() || !subjectForm.short_code.trim() || createSubject.isPending}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 whitespace-nowrap"
          >
            + Tilføj fag
          </button>
        </div>

        {subjects.length === 0 ? (
          <p className="text-sm text-gray-500">Ingen fag endnu. Klik "Hent fra UVM" for at importere alle folkeskolefag.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {subjects.map((s) => (
                <span
                  key={s.id}
                  className="text-xs px-2 py-1 rounded-full font-medium text-white"
                  style={{ backgroundColor: s.color_hex ?? '#6b7280' }}
                >
                  {s.short_code} · {s.name}
                  {s.required_room_type && ` · ${ROOM_TYPE_LABELS[s.required_room_type] ?? s.required_room_type}`}
                </span>
              ))}
            </div>

            {/* Special-room mapping */}
            <div className="mt-5 border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-600 mb-2">
                Lokaletype pr. fag (hård betingelse — fag placeres kun i den valgte lokaletype)
              </p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                {subjects
                  .filter((s) => !s.is_elective_slot)
                  .map((s) => (
                    <div key={s.id} className="flex items-center justify-between text-sm">
                      <span className="text-gray-700">{s.name}</span>
                      <select
                        value={s.required_room_type ?? ''}
                        onChange={(e) =>
                          setSubjectRoomType.mutate({ id: s.id, required_room_type: e.target.value === '' ? null : e.target.value })
                        }
                        className="border border-gray-300 rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Intet specifikt</option>
                        {ROOM_TYPES.map((t) => (
                          <option key={t} value={t}>{ROOM_TYPE_LABELS[t]}</option>
                        ))}
                      </select>
                    </div>
                  ))}
              </div>
            </div>

            {/* Double lessons */}
            <div className="mt-5 border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-600 mb-2">
                Dobbeltlektioner (faget placeres altid som to lektioner i træk uden pause imellem)
              </p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                {subjects
                  .filter((s) => !s.is_elective_slot)
                  .map((s) => (
                    <label key={s.id} className="flex items-center justify-between text-sm cursor-pointer">
                      <span className="text-gray-700">{s.name}</span>
                      <input
                        type="checkbox"
                        checked={s.double_lessons}
                        onChange={(e) =>
                          setSubjectDoubleLessons.mutate({ id: s.id, double_lessons: e.target.checked })
                        }
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </label>
                  ))}
              </div>
            </div>

            {/* Subject priority */}
            <div className="mt-5 border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-600 mb-1">Fag-prioritet</p>
              <p className="text-xs text-gray-400 mb-3">
                Når skemaet fyldes op ud over ministeriets minimum, får fag øverst de ekstra timer først (timebanken).
                Fjern et fag fra listen for kun at give det ministeriets minimum — fx Idræt, så det ikke får en løs enkelt-lektion.
              </p>
              <div className="max-w-md divide-y divide-gray-100">
                {(() => {
                  const ordered = subjects.filter((s) => !s.is_elective_slot && s.add_extra)
                  return ordered.map((s, i) => (
                    <div key={s.id} className="py-1.5 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span className="text-gray-400 w-5 text-right">{i + 1}.</span>
                        <span className="text-gray-700">{s.name}</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <button
                          onClick={() => i > 0 && swapPriority.mutate({ a: s, b: ordered[i - 1] })}
                          disabled={i === 0 || swapPriority.isPending}
                          className="px-1.5 py-0.5 rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30"
                          title="Op"
                        >
                          ▲
                        </button>
                        <button
                          onClick={() => i < ordered.length - 1 && swapPriority.mutate({ a: s, b: ordered[i + 1] })}
                          disabled={i === ordered.length - 1 || swapPriority.isPending}
                          className="px-1.5 py-0.5 rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30"
                          title="Ned"
                        >
                          ▼
                        </button>
                        <button
                          onClick={() => setSubjectAddExtra.mutate({ id: s.id, add_extra: false })}
                          disabled={setSubjectAddExtra.isPending}
                          className="ml-1 px-1.5 py-0.5 rounded text-red-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-30"
                          title="Fjern fra ekstra-timer (kun ministeriets minimum)"
                        >
                          ✕
                        </button>
                      </span>
                    </div>
                  ))
                })()}
              </div>

              {/* Excluded subjects (add_extra = false) */}
              {(() => {
                const excluded = subjects.filter((s) => !s.is_elective_slot && !s.add_extra)
                if (excluded.length === 0) return null
                return (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-gray-600 mb-1.5">Får kun ministeriets minimum (ingen ekstra timer)</p>
                    <div className="flex flex-wrap gap-2">
                      {excluded.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => setSubjectAddExtra.mutate({ id: s.id, add_extra: true })}
                          disabled={setSubjectAddExtra.isPending}
                          className="text-xs px-2 py-1 rounded-full border border-gray-300 text-gray-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-30"
                          title="Tilføj til ekstra-timer igen"
                        >
                          + {s.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </div>
          </>
        )}
      </section>

      {/* ── Teachers ── */}
      <section id="teacher-form" className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm scroll-mt-4">
        <h3 className="font-medium text-gray-900 mb-4">
          {editingTeacherId ? 'Rediger lærer' : `Lærere (${teachers.length})`}
        </h3>
        <div className="grid grid-cols-4 gap-2 mb-3">
          {(['first_name', 'last_name', 'short_code', 'email'] as const).map((f) => (
            <input
              key={f}
              placeholder={{ first_name: 'Fornavn', last_name: 'Efternavn', short_code: 'Kode', email: 'Email' }[f]}
              value={teacherForm[f]}
              onChange={(e) => setTeacherForm({ ...teacherForm, [f]: e.target.value })}
              className={INPUT}
            />
          ))}
        </div>
        {subjects.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-600 mb-1.5">Fag denne lærer underviser i:</p>
            <div className="flex flex-wrap gap-1.5">
              {subjects.filter((s) => !s.is_elective_slot).map((s) => {
                const checked = teacherSubjectIds.includes(s.id)
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggleTeacherSubject(s.id)}
                    className={`text-xs px-2 py-1 rounded-full border font-medium transition ${
                      checked ? 'text-white border-transparent' : 'text-gray-600 border-gray-300 hover:border-gray-400'
                    }`}
                    style={checked ? { backgroundColor: s.color_hex ?? '#6b7280', borderColor: s.color_hex ?? '#6b7280' } : {}}
                  >
                    {s.short_code}
                  </button>
                )
              })}
            </div>
          </div>
        )}
        <div className="flex items-center gap-2">
          <button
            onClick={() => (editingTeacherId ? updateTeacher.mutate() : createTeacher.mutate())}
            disabled={
              !teacherForm.first_name || !teacherForm.last_name || !teacherForm.short_code ||
              createTeacher.isPending || updateTeacher.isPending
            }
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40"
          >
            {editingTeacherId ? (updateTeacher.isPending ? 'Gemmer...' : 'Gem ændringer') : '+ Tilføj lærer'}
          </button>
          {editingTeacherId && (
            <button
              onClick={resetTeacherForm}
              className="text-sm text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-100"
            >
              Annuller
            </button>
          )}
        </div>
        <div className="mt-4 divide-y divide-gray-100 max-h-64 overflow-y-auto">
          {teachers.map((t) => (
            <div key={t.id} className="py-2 flex items-center justify-between text-sm">
              <div>
                <span className="font-medium text-gray-800">{t.first_name} {t.last_name}</span>
                <span className="text-gray-400 ml-1">({t.short_code})</span>
                {t.subject_ids.length > 0 && (
                  <span className="ml-2 flex-inline gap-1">
                    {t.subject_ids.map((sid2) => {
                      const subj = subjects.find((s) => s.id === sid2)
                      return subj ? (
                        <span
                          key={sid2}
                          className="text-xs px-1.5 py-0.5 rounded text-white ml-1"
                          style={{ backgroundColor: subj.color_hex ?? '#6b7280' }}
                        >
                          {subj.short_code}
                        </span>
                      ) : null
                    })}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => startEditTeacher(t)}
                  className={`text-xs px-2 py-1 ${editingTeacherId === t.id ? 'text-blue-700 font-medium' : 'text-blue-600 hover:text-blue-800'}`}
                >
                  Redigér
                </button>
                <button
                  onClick={() => deleteTeacher.mutate(t.id)}
                  className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                >
                  Slet
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Rooms ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-medium text-gray-900 mb-4">Lokaler ({rooms.length})</h3>
        <div className="grid grid-cols-4 gap-2 mb-3">
          <input placeholder="Navn" value={roomForm.name} onChange={(e) => setRoomForm({ ...roomForm, name: e.target.value })} className={INPUT} />
          <input placeholder="Kode" value={roomForm.short_code} onChange={(e) => setRoomForm({ ...roomForm, short_code: e.target.value })} className={INPUT} />
          <input type="number" placeholder="Kapacitet" value={roomForm.capacity} onChange={(e) => setRoomForm({ ...roomForm, capacity: +e.target.value })} className={INPUT} />
          <select value={roomForm.room_type} onChange={(e) => setRoomForm({ ...roomForm, room_type: e.target.value })} className={INPUT}>
            {ROOM_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <button
          onClick={() => createRoom.mutate()}
          disabled={!roomForm.name || !roomForm.short_code}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40"
        >
          + Tilføj lokale
        </button>
        <div className="mt-4 divide-y divide-gray-100">
          {rooms.map((r) => (
            <div key={r.id} className="py-2 flex items-center justify-between text-sm">
              <div>
                <span className="font-medium text-gray-800">{r.name}</span>
                <span className="text-gray-400 ml-1">({r.short_code})</span>
                <span className="text-gray-500 ml-2">{r.room_type} · {r.capacity} pladser</span>
              </div>
              <button
                onClick={() => deleteRoom.mutate(r.id)}
                className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
              >
                Slet
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ── Classes ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">Klasser ({classes.length})</h3>
          <button
            onClick={() => {
              const missing = classes.filter((c) => c.is_active && !c.home_room_id).length
              if (missing === 0) { alert('Alle klasser har allerede et hjemlokale.'); return }
              if (window.confirm(`Opret et hjemlokale (stamlokale) for ${missing} klasse(r) uden et og tildel det automatisk?`))
                autoAssignHomeRooms.mutate()
            }}
            disabled={autoAssignHomeRooms.isPending}
            className="text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {autoAssignHomeRooms.isPending ? 'Tildeler...' : 'Tildel hjemlokaler'}
          </button>
        </div>
        <div className="grid grid-cols-4 gap-2 mb-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Fra trin</label>
            <input type="number" min={1} max={9} value={bulkForm.grade_start} onChange={(e) => setBulkForm({ ...bulkForm, grade_start: +e.target.value })} className={INPUT + ' w-full'} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Til trin</label>
            <input type="number" min={1} max={9} value={bulkForm.grade_end} onChange={(e) => setBulkForm({ ...bulkForm, grade_end: +e.target.value })} className={INPUT + ' w-full'} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Bogstaver (kommasep.)</label>
            <input placeholder="A, B, C" value={bulkForm.suffixes} onChange={(e) => setBulkForm({ ...bulkForm, suffixes: e.target.value })} className={INPUT + ' w-full'} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Antal elever</label>
            <input type="number" value={bulkForm.student_count} onChange={(e) => setBulkForm({ ...bulkForm, student_count: +e.target.value })} className={INPUT + ' w-full'} />
          </div>
        </div>
        <p className="text-xs text-gray-400 mb-2">
          Opretter {(bulkForm.grade_end - bulkForm.grade_start + 1) * bulkForm.suffixes.split(',').filter((s) => s.trim()).length} klasser
          {' '}(f.eks. {bulkForm.grade_start}{bulkForm.suffixes.split(',')[0]?.trim() ?? 'A'} … {bulkForm.grade_end}{bulkForm.suffixes.split(',').slice(-1)[0]?.trim() ?? 'A'})
        </p>
        <button
          onClick={() => createBulkClasses.mutate()}
          disabled={createBulkClasses.isPending || bulkForm.grade_start > bulkForm.grade_end}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40"
        >
          {createBulkClasses.isPending ? 'Opretter...' : '+ Opret klasser'}
        </button>
        <div className="mt-4 divide-y divide-gray-100">
          {classes
            .slice()
            .sort((a, b) => a.grade_level - b.grade_level || a.name.localeCompare(b.name))
            .map((c) => (
              <div key={c.id} className="py-2 flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium text-gray-800">{c.name}</span>
                  <span className="text-gray-400 ml-1">(trin {c.grade_level})</span>
                  <span className="text-gray-500 ml-2">{c.student_count} elever</span>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={c.home_room_id ?? ''}
                    onChange={(e) => setHomeRoom.mutate({ id: c.id, home_room_id: e.target.value === '' ? null : +e.target.value })}
                    className="border border-gray-300 rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                    title="Hjemlokale (stamlokale)"
                  >
                    <option value="">— intet hjemlokale —</option>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => deleteClass.mutate(c.id)}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                  >
                    Slet
                  </button>
                </div>
              </div>
            ))}
        </div>
      </section>
    </div>
  )
}
