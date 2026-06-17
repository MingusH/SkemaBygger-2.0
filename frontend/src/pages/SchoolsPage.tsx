import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { schoolsApi } from '../api/client'

export default function SchoolsPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '', short_name: '', academic_year: '2026/2027',
    periods_per_day: 7, days_per_week: 5,
  })

  const { data: schools = [], isLoading } = useQuery({
    queryKey: ['schools'],
    queryFn: schoolsApi.list,
  })

  const create = useMutation({
    mutationFn: schoolsApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schools'] }); setShowForm(false) },
  })

  const deleteSchool = useMutation({
    mutationFn: (id: number) => schoolsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schools'] }),
  })

  if (isLoading) return <div className="text-gray-500">Indlæser...</div>

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Skoler</h2>
        <button
          onClick={() => setShowForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          + Ny skole
        </button>
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6 shadow-sm">
          <h3 className="font-medium text-gray-900 mb-4">Opret skole</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {(['name', 'short_name', 'academic_year'] as const).map((field) => (
              <div key={field}>
                <label className="block text-gray-600 mb-1 capitalize">{field.replace('_', ' ')}</label>
                <input
                  value={form[field]}
                  onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}
            <div>
              <label className="block text-gray-600 mb-1">Perioder pr. dag</label>
              <input
                type="number"
                value={form.periods_per_day}
                onChange={(e) => setForm({ ...form, periods_per_day: +e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => create.mutate(form)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              Opret
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="border border-gray-300 px-4 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
            >
              Annuller
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {schools.map((school) => (
          <div key={school.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900">{school.name}</p>
                <p className="text-sm text-gray-500">{school.academic_year} · {school.days_per_week} dage · {school.periods_per_day} perioder/dag</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate(`/schools/${school.id}`)}
                  className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700"
                >
                  Administrér
                </button>
                <button
                  onClick={() => {
                    if (window.confirm(`Slet "${school.name}"? Dette sletter al data tilknyttet skolen.`))
                      deleteSchool.mutate(school.id)
                  }}
                  className="text-sm text-red-500 hover:text-red-700 px-3 py-1.5 rounded-lg hover:bg-red-50"
                >
                  Slet
                </button>
              </div>
            </div>
          </div>
        ))}
        {schools.length === 0 && !showForm && (
          <p className="text-gray-500 text-sm">Ingen skoler endnu. Opret din første.</p>
        )}
      </div>
    </div>
  )
}
