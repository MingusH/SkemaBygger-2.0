import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { assignmentsApi, teachersApi, subjectsApi, classesApi, roomsApi, type Subject } from '../api/client'

const SELECT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

const ACADEMIC_YEAR = '2026/2027'

export default function AssignmentsPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()

  const { data: teachers = [] } = useQuery({ queryKey: ['teachers', sid], queryFn: () => teachersApi.list(sid) })
  const { data: subjects = [] } = useQuery({ queryKey: ['subjects', sid], queryFn: () => subjectsApi.list(sid) })
  const { data: classes = [] } = useQuery({ queryKey: ['classes', sid], queryFn: () => classesApi.list(sid) })
  const { data: rooms = [] } = useQuery({ queryKey: ['rooms', sid], queryFn: () => roomsApi.list(sid) })

  const [selectedClassId, setSelectedClassId] = useState<number | null>(null)
  const selectedClass = classes.find((c) => c.id === selectedClassId) ?? null

  const { data: assignments = [] } = useQuery({
    queryKey: ['assignments', sid, selectedClassId],
    queryFn: () => assignmentsApi.list(sid, selectedClassId ?? undefined),
    enabled: selectedClassId !== null,
  })

  // All school assignments — used to compute per-teacher load for auto-selection
  const { data: allAssignments = [] } = useQuery({
    queryKey: ['assignments', sid],
    queryFn: () => assignmentsApi.list(sid),
  })

  // ── Manual add form ───────────────────────────────────────────────────────
  const [form, setForm] = useState({ teacher_id: 0, subject_id: 0, hours_per_week: 2 })

  const createAssignment = useMutation({
    mutationFn: (body: { teacher_id: number; subject_id: number; hours_per_week: number }) =>
      assignmentsApi.create(sid, {
        ...body,
        student_class_id: selectedClassId!,
        academic_year: ACADEMIC_YEAR,
        requires_consecutive: false,
        parallel_group_id: null,
        preferred_room_id: null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments', sid, selectedClassId] }),
  })

  const deleteAssignment = useMutation({
    mutationFn: (id: number) => assignmentsApi.delete(sid, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments', sid, selectedClassId] }),
  })

  const updateAssignment = useMutation({
    mutationFn: ({ id, preferred_room_id }: { id: number; preferred_room_id: number | null }) =>
      assignmentsApi.update(sid, id, { preferred_room_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments', sid, selectedClassId] }),
  })

  // ── Auto-fill from UVM ────────────────────────────────────────────────────
  const [showAutoFill, setShowAutoFill] = useState(false)
  type AutoRow = { subject: Subject; hours: number; teacher_id: number }
  const [autoRows, setAutoRows] = useState<AutoRow[]>([])

  const buildAutoRows = () => {
    if (!selectedClass) return
    const assignedSubjectIds = new Set(assignments.map((a) => a.subject_id))
    const rows: AutoRow[] = subjects
      .filter((s) => !s.is_elective_slot)
      .flatMap((s) => {
        const mh = s.ministry_hours.find((h) => h.grade === selectedClass.grade_level)
        if (!mh || mh.hours_per_week <= 0) return []
        if (assignedSubjectIds.has(s.id)) return []
        return [{ subject: s, hours: Math.round(mh.hours_per_week), teacher_id: 0 }]
      })
    setAutoRows(rows)
    setShowAutoFill(true)
  }

  const autoSelectTeachers = (rows: AutoRow[]): AutoRow[] => {
    // Build running load map from all existing assignments
    const load = new Map<number, number>(teachers.map((t) => [t.id, 0]))
    allAssignments.forEach((a) => load.set(a.teacher_id, (load.get(a.teacher_id) ?? 0) + a.hours_per_week))

    return rows.map((row) => {
      const qualified = teachers.filter((t) => t.subject_ids.includes(row.subject.id))
      if (qualified.length === 0) return row
      // Pick the qualified teacher with the lowest running load
      const best = qualified.reduce((a, b) => (load.get(a.id) ?? 0) <= (load.get(b.id) ?? 0) ? a : b)
      // Account for this assignment in subsequent picks
      load.set(best.id, (load.get(best.id) ?? 0) + row.hours)
      return { ...row, teacher_id: best.id }
    })
  }

  const bulkCreate = useMutation({
    mutationFn: async () => {
      for (const row of autoRows) {
        if (!row.teacher_id) continue
        await assignmentsApi.create(sid, {
          teacher_id: row.teacher_id,
          subject_id: row.subject.id,
          hours_per_week: row.hours,
          student_class_id: selectedClassId!,
          academic_year: ACADEMIC_YEAR,
          requires_consecutive: false,
          parallel_group_id: null,
          preferred_room_id: null,
        })
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignments', sid, selectedClassId] })
      setShowAutoFill(false)
      setAutoRows([])
    },
  })

  // ── Bulk auto-assign all classes ─────────────────────────────────────────
  const [bulkResult, setBulkResult] = useState<Awaited<ReturnType<typeof assignmentsApi.bulkAutoAssign>> | null>(null)

  const bulkAutoAssignAll = useMutation({
    mutationFn: () => assignmentsApi.bulkAutoAssign(sid),
    onSuccess: (data) => {
      setBulkResult(data)
      qc.invalidateQueries({ queryKey: ['assignments', sid] })
    },
  })

  const subjectMap = Object.fromEntries(subjects.map((s) => [s.id, s]))
  const teacherMap = Object.fromEntries(teachers.map((t) => [t.id, t]))

  const unassignedCount = selectedClass
    ? subjects.filter((s) => {
        if (s.is_elective_slot) return false
        const mh = s.ministry_hours.find((h) => h.grade === selectedClass.grade_level)
        return mh && mh.hours_per_week > 0 && !assignments.some((a) => a.subject_id === s.id)
      }).length
    : 0

  return (
    <div className="max-w-5xl">
      <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline inline-block mb-4">← Tilbage til skole</Link>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Fag-tildeling</h2>
        <button
          onClick={() => {
            if (window.confirm('Dette sletter alle eksisterende tildelinger og gendanner dem fra bunden med opdateret lærerfordeling. Fortsæt?')) {
              setBulkResult(null)
              bulkAutoAssignAll.mutate()
            }
          }}
          disabled={bulkAutoAssignAll.isPending}
          className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-50"
        >
          {bulkAutoAssignAll.isPending ? 'Arbejder...' : 'Tilknyt alle fag til alle klasser'}
        </button>
      </div>

      {bulkResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-5 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-green-800">
              Oprettede <strong>{bulkResult.created}</strong> tildelinger.
              {bulkResult.skipped_no_teacher > 0 && (
                <span className="text-yellow-700 ml-2">
                  {bulkResult.skipped_no_teacher} fag sprunget over — ingen kvalificeret lærer.
                </span>
              )}
            </span>
            <button onClick={() => setBulkResult(null)} className="text-green-600 hover:text-green-800">×</button>
          </div>
          {bulkResult.grade_totals?.length > 0 && (
            <div className="mt-3 border-t border-green-200 pt-3">
              <div className="text-xs font-medium text-gray-600 mb-1">Årlig timeopfyldelse pr. årgang (inkl. pauser)</div>
              <div className="flex flex-wrap gap-2">
                {bulkResult.grade_totals.map((g) => (
                  <span
                    key={g.grade}
                    className={`px-2 py-1 rounded-md text-xs font-medium ${g.meets_total ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}
                    title={`Mål ${g.target_periods} lektioner/uge`}
                  >
                    {g.meets_total ? '✓' : '✗'} {g.grade}. årg: {g.delivered_clock_hours} / {g.target_clock_hours} t
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Class picker */}
      <div className="flex flex-wrap gap-2 mb-6">
        {classes
          .slice()
          .sort((a, b) => a.grade_level - b.grade_level || a.name.localeCompare(b.name))
          .map((c) => (
            <button
              key={c.id}
              onClick={() => { setSelectedClassId(c.id); setShowAutoFill(false) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition ${
                selectedClassId === c.id
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {c.name}
            </button>
          ))}
      </div>

      {selectedClassId !== null && (
        <>
          {/* Auto-fill banner */}
          {!showAutoFill && unassignedCount > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5 flex items-center justify-between text-sm">
              <span className="text-blue-800">
                {unassignedCount} fag fra UVM-planen er endnu ikke tildelt denne klasse.
              </span>
              <button
                onClick={buildAutoRows}
                className="bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 font-medium"
              >
                Tilknyt fag fra UVM
              </button>
            </div>
          )}

          {/* Auto-fill panel */}
          {showAutoFill && (
            <div className="bg-white border border-blue-200 rounded-xl p-5 shadow-sm mb-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Tilknyt fag fra UVM ({autoRows.length} fag)</h3>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setAutoRows(autoSelectTeachers(autoRows))}
                    className="text-sm bg-gray-800 text-white px-3 py-1.5 rounded-lg hover:bg-gray-900"
                  >
                    Vælg lærere automatisk
                  </button>
                  <button onClick={() => setShowAutoFill(false)} className="text-gray-400 hover:text-gray-600 text-sm">Annuller</button>
                </div>
              </div>
              <p className="text-xs text-gray-500 mb-3">Vælg lærer for hvert fag. Fag uden lærer springes over.</p>
              <div className="space-y-2">
                {autoRows.map((row, i) => (
                  <div key={row.subject.id} className="grid grid-cols-3 gap-3 items-center text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: row.subject.color_hex ?? '#6b7280' }}
                      />
                      <span className="font-medium text-gray-800">{row.subject.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">Timer/uge:</span>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={row.hours}
                        onChange={(e) => {
                          const next = [...autoRows]
                          next[i] = { ...row, hours: +e.target.value }
                          setAutoRows(next)
                        }}
                        className="w-16 border border-gray-300 rounded px-2 py-1 text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <select
                      value={row.teacher_id}
                      onChange={(e) => {
                        const next = [...autoRows]
                        next[i] = { ...row, teacher_id: +e.target.value }
                        setAutoRows(next)
                      }}
                      className={SELECT}
                    >
                      <option value={0}>Vælg lærer (spring over)</option>
                      {teachers
                        .filter((t) => t.subject_ids.includes(row.subject.id))
                        .map((t) => (
                          <option key={t.id} value={t.id}>{t.first_name} {t.last_name} ({t.short_code})</option>
                        ))}
                      {teachers.filter((t) => !t.subject_ids.includes(row.subject.id)).length > 0 && (
                        <optgroup label="Ikke kvalificerede">
                          {teachers
                            .filter((t) => !t.subject_ids.includes(row.subject.id))
                            .map((t) => (
                              <option key={t.id} value={t.id}>{t.first_name} {t.last_name} ({t.short_code})</option>
                            ))}
                        </optgroup>
                      )}
                    </select>
                  </div>
                ))}
              </div>
              <button
                onClick={() => bulkCreate.mutate()}
                disabled={bulkCreate.isPending || autoRows.every((r) => !r.teacher_id)}
                className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
              >
                {bulkCreate.isPending ? 'Opretter...' : `Opret ${autoRows.filter((r) => r.teacher_id).length} tildelinger`}
              </button>
            </div>
          )}

          {/* Manual add form */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm mb-6">
            <h3 className="font-medium text-gray-900 mb-3">Tilføj manuelt</h3>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Lærer</label>
                <select value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: +e.target.value })} className={SELECT}>
                  <option value={0}>Vælg lærer</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>{t.first_name} {t.last_name} ({t.short_code})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Fag</label>
                <select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: +e.target.value })} className={SELECT}>
                  <option value={0}>Vælg fag</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Timer/uge</label>
                <input
                  type="number" min={1} max={20}
                  value={form.hours_per_week}
                  onChange={(e) => setForm({ ...form, hours_per_week: +e.target.value })}
                  className={SELECT}
                />
              </div>
            </div>
            <button
              onClick={() => createAssignment.mutate(form)}
              disabled={!form.teacher_id || !form.subject_id}
              className="mt-3 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
            >
              + Tilføj
            </button>
          </div>

          {/* Assignments table */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Fag</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Lærer</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Timer/uge</th>
                  <th className="text-left px-4 py-3 text-gray-600 font-medium">Foretrukket lokale</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {assignments.map((a) => {
                  const subj = subjectMap[a.subject_id]
                  const teacher = teacherMap[a.teacher_id]
                  return (
                    <tr key={a.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span
                          className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                          style={{ backgroundColor: subj?.color_hex ?? '#6b7280' }}
                        />
                        {subj?.name ?? `Fag ${a.subject_id}`}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {teacher ? `${teacher.first_name} ${teacher.last_name}` : `Lærer ${a.teacher_id}`}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{a.hours_per_week}</td>
                      <td className="px-4 py-3">
                        <select
                          value={a.preferred_room_id ?? ''}
                          onChange={(e) =>
                            updateAssignment.mutate({
                              id: a.id,
                              preferred_room_id: e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          className="border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">— intet —</option>
                          {rooms.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name} ({r.short_code})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => deleteAssignment.mutate(a.id)}
                          className="text-xs text-red-500 hover:text-red-700"
                        >
                          Slet
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {assignments.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-gray-400">Ingen tildelinger endnu</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {selectedClassId === null && (
        <p className="text-gray-500 text-sm">Vælg en klasse ovenfor for at se og redigere tildelinger.</p>
      )}
    </div>
  )
}
