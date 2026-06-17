import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { timeslotsApi, teachersApi, constraintsApi } from '../api/client'

const DAYS = ['Man', 'Tir', 'Ons', 'Tor', 'Fre']
const INPUT = 'border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm'

export default function ConstraintsPage() {
  const { schoolId } = useParams<{ schoolId: string }>()
  const sid = Number(schoolId)
  const qc = useQueryClient()

  const { data: timeslots = [] } = useQuery({
    queryKey: ['timeslots', sid],
    queryFn: () => timeslotsApi.list(sid),
  })
  const { data: teachers = [] } = useQuery({
    queryKey: ['teachers', sid],
    queryFn: () => teachersApi.list(sid),
  })

  // ── Bell schedule ─────────────────────────────────────────────────────────

  // Group timeslots by period_number
  const periodMap = new Map<number, typeof timeslots[0][]>()
  for (const slot of timeslots) {
    const list = periodMap.get(slot.period_number) ?? []
    list.push(slot)
    periodMap.set(slot.period_number, list)
  }
  const periods = Array.from(periodMap.entries()).sort((a, b) => a[0] - b[0])

  const nextPeriod = periods.length > 0 ? Math.max(...periods.map(([n]) => n)) + 1 : 1
  const [slotForm, setSlotForm] = useState({ period_number: nextPeriod, start_time: '08:00', end_time: '08:45' })

  const addPeriod = useMutation({
    mutationFn: () =>
      timeslotsApi.createBulk(
        sid,
        [1, 2, 3, 4, 5].map((day) => ({
          day_of_week: day,
          period_number: slotForm.period_number,
          start_time: slotForm.start_time,
          end_time: slotForm.end_time,
          label: null,
        })),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['timeslots', sid] })
      setSlotForm((f) => ({ ...f, period_number: f.period_number + 1 }))
    },
  })

  const deletePeriod = useMutation({
    mutationFn: (slotIds: number[]) =>
      Promise.all(slotIds.map((id) => timeslotsApi.delete(sid, id))),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['timeslots', sid] }),
  })

  // ── Teacher unavailability ─────────────────────────────────────────────────

  const [selectedTeacherId, setSelectedTeacherId] = useState<number | null>(null)

  const { data: unavailabilities = [] } = useQuery({
    queryKey: ['teacher-unavail', sid, selectedTeacherId],
    queryFn: () => constraintsApi.listTeacherUnavailabilities(sid, selectedTeacherId!),
    enabled: selectedTeacherId !== null,
  })

  const unavailMap = new Map<number, number>() // time_slot_id → unavailability.id
  for (const u of unavailabilities) unavailMap.set(u.time_slot_id, u.id)

  const addUnavail = useMutation({
    mutationFn: (time_slot_id: number) =>
      constraintsApi.addTeacherUnavailability(sid, selectedTeacherId!, { time_slot_id, constraint_type: 'HARD' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teacher-unavail', sid, selectedTeacherId] }),
  })

  const removeUnavail = useMutation({
    mutationFn: (unavailId: number) =>
      constraintsApi.deleteTeacherUnavailability(sid, selectedTeacherId!, unavailId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teacher-unavail', sid, selectedTeacherId] }),
  })

  const handleCellClick = (slot: typeof timeslots[0]) => {
    if (!selectedTeacherId) return
    const existingId = unavailMap.get(slot.id)
    if (existingId !== undefined) {
      removeUnavail.mutate(existingId)
    } else {
      addUnavail.mutate(slot.id)
    }
  }

  // For the grid, build a lookup: period_number × day_of_week → slot
  const slotLookup = new Map<string, typeof timeslots[0]>()
  for (const slot of timeslots) slotLookup.set(`${slot.period_number}-${slot.day_of_week}`, slot)

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <Link to={`/schools/${sid}`} className="text-sm text-blue-600 hover:underline">← Tilbage til skole</Link>
        <h2 className="text-xl font-semibold text-gray-900 mt-2">Tidspunkter & Frihed</h2>
      </div>

      {/* ── Bell Schedule ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-medium text-gray-900 mb-4">Ugeskema — lektioner ({periods.length} lektioner)</h3>

        <div className="flex gap-2 items-end mb-4">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Lektion #</label>
            <input
              type="number"
              min={1}
              value={slotForm.period_number}
              onChange={(e) => setSlotForm({ ...slotForm, period_number: +e.target.value })}
              className={INPUT + ' w-24'}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Fra</label>
            <input
              type="time"
              value={slotForm.start_time}
              onChange={(e) => setSlotForm({ ...slotForm, start_time: e.target.value })}
              className={INPUT}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Til</label>
            <input
              type="time"
              value={slotForm.end_time}
              onChange={(e) => setSlotForm({ ...slotForm, end_time: e.target.value })}
              className={INPUT}
            />
          </div>
          <button
            onClick={() => addPeriod.mutate()}
            disabled={addPeriod.isPending}
            className="text-sm bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {addPeriod.isPending ? 'Opretter...' : '+ Tilføj lektion'}
          </button>
        </div>

        {periods.length === 0 ? (
          <p className="text-sm text-gray-400">Ingen lektioner endnu. Tilføj den første ovenfor.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {periods.map(([periodNum, slots]) => {
              const ref = slots.find((s) => s.day_of_week === 1) ?? slots[0]
              return (
                <div key={periodNum} className="py-2 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-4">
                    <span className="w-20 font-medium text-gray-800">Lektion {periodNum}</span>
                    <span className="text-gray-500">{ref.start_time.slice(0, 5)} – {ref.end_time.slice(0, 5)}</span>
                    <span className="text-xs text-gray-400">{slots.length} dage</span>
                  </div>
                  <button
                    onClick={() => deletePeriod.mutate(slots.map((s) => s.id))}
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

      {/* ── Teacher Unavailability ── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-medium text-gray-900 mb-4">Lærers utilgængelighed</h3>

        <div className="mb-4">
          <label className="text-xs text-gray-500 mb-1 block">Vælg lærer</label>
          <select
            value={selectedTeacherId ?? ''}
            onChange={(e) => setSelectedTeacherId(e.target.value === '' ? null : Number(e.target.value))}
            className={INPUT + ' w-64'}
          >
            <option value="">— vælg lærer —</option>
            {teachers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name} ({t.short_code})
              </option>
            ))}
          </select>
        </div>

        {selectedTeacherId !== null && periods.length === 0 && (
          <p className="text-sm text-gray-400">Opret lektioner i ugeskemaet ovenfor først.</p>
        )}

        {selectedTeacherId !== null && periods.length > 0 && (
          <>
            <div className="flex gap-3 mb-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded bg-red-200 border border-red-300" /> Utilgængelig
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded bg-white border border-gray-300" /> Tilgængelig
              </span>
              <span className="text-gray-400">(klik for at skifte)</span>
            </div>

            <div className="overflow-x-auto">
              <table className="text-sm border-collapse">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium w-28">Lektion</th>
                    {DAYS.map((d) => (
                      <th key={d} className="px-4 py-2 text-center text-gray-600 font-medium w-28">{d}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {periods.map(([periodNum, slots]) => {
                    const ref = slots.find((s) => s.day_of_week === 1) ?? slots[0]
                    return (
                      <tr key={periodNum} className="border-t border-gray-100">
                        <td className="px-3 py-2 text-gray-600 text-xs">
                          <div className="font-medium">Lektion {periodNum}</div>
                          <div className="text-gray-400">{ref.start_time.slice(0, 5)}–{ref.end_time.slice(0, 5)}</div>
                        </td>
                        {[1, 2, 3, 4, 5].map((day) => {
                          const slot = slotLookup.get(`${periodNum}-${day}`)
                          if (!slot) {
                            return <td key={day} className="px-4 py-2 text-center text-gray-300 text-xs">—</td>
                          }
                          const isUnavail = unavailMap.has(slot.id)
                          return (
                            <td key={day} className="px-2 py-1.5">
                              <button
                                onClick={() => handleCellClick(slot)}
                                className={`w-full rounded-md py-2 text-xs font-medium border transition ${
                                  isUnavail
                                    ? 'bg-red-100 border-red-300 text-red-700 hover:bg-red-200'
                                    : 'bg-white border-gray-200 text-gray-400 hover:bg-gray-50'
                                }`}
                              >
                                {isUnavail ? 'Fri' : '✓'}
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
