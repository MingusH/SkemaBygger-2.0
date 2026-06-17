import axios from 'axios'

// In dev, '/api' is proxied to the backend by Vite. In production (separate static
// site), set VITE_API_BASE_URL to the backend URL, e.g. https://skemabygger-api.onrender.com/api
export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api' })

// Attach JWT from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Types matching backend schemas
export interface School {
  id: number
  name: string
  short_name: string
  academic_year: string
  periods_per_day: number
  days_per_week: number
  weeks_per_year: number
}

export type EventType = 'NO_SCHOOL' | 'PROJECT_WEEK' | 'EXCURSION' | 'EXAM_WEEK' | 'OTHER'
export type EventScope = 'SCHOOL_WIDE' | 'PER_CLASS'

export interface SpecialEvent {
  id: number
  school_id: number
  name: string
  event_type: EventType
  scope: EventScope
  start_date: string   // ISO date "YYYY-MM-DD"
  end_date: string
  hours_override: number | null
  description: string | null
  class_ids: number[]
}

export interface ClassTimeBankEntry {
  class_id: number
  class_name: string
  grade_level: number
  weekly_hours: number
  delivered: number
  ministry_min_hours: number
  timebank_pool: number
  timebank_used: number
  balance: number
  is_sufficient: boolean
}

export interface SchoolTimeBankRead {
  school_id: number
  weeks_per_year: number
  schedule_id: number | null
  has_schedule: boolean
  entries: ClassTimeBankEntry[]
}

export interface Teacher {
  id: number
  school_id: number
  first_name: string
  last_name: string
  short_code: string
  email: string | null
  max_hours_per_week: number | null
  is_active: boolean
  subject_ids: number[]
}

export interface Room {
  id: number
  school_id: number
  name: string
  short_code: string
  capacity: number
  room_type: string
  is_active: boolean
}

export interface Subject {
  id: number
  school_id: number
  name: string
  short_code: string
  category: string
  color_hex: string | null
  requires_special_room: boolean
  required_room_type: string | null
  double_lessons: boolean
  is_elective_slot: boolean
  priority: number
  ministry_hours: { grade: number; hours_per_week: number }[]
}

export interface StudentClass {
  id: number
  school_id: number
  name: string
  grade_level: number
  student_count: number
  home_room_id: number | null
  is_active: boolean
}

export interface Assignment {
  id: number
  school_id: number
  teacher_id: number
  subject_id: number
  student_class_id: number
  hours_per_week: number
  preferred_room_id: number | null
  requires_consecutive: boolean
  parallel_group_id: number | null
  academic_year: string
}

export interface TimeSlot {
  id: number
  school_id: number
  day_of_week: number
  period_number: number
  start_time: string
  end_time: string
  label: string | null
}

export interface TeacherUnavailability {
  id: number
  teacher_id: number
  time_slot_id: number
  constraint_type: 'HARD' | 'SOFT'
  reason: string | null
}

export interface Schedule {
  id: number
  school_id: number
  name: string
  academic_year: string
  status: 'DRAFT' | 'GENERATING' | 'COMPLETE' | 'FAILED' | 'PUBLISHED'
  generated_at: string | null
  score: number | null
}

export interface ScheduleEntry {
  id: number
  schedule_id: number
  assignment_id: number | null
  elective_offering_id: number | null
  time_slot_id: number
  room_id: number
  is_locked: boolean
}

export type ElectiveBandType = 'PRACTICAL' | 'LOCAL'

export interface ElectiveOffering {
  id: number
  band_id: number
  subject_id: number
  teacher_id: number
  room_id: number
}

export interface ElectiveBand {
  id: number
  school_id: number
  grade_level: number
  band_type: ElectiveBandType
  name: string
  hours_per_week: number
  requires_consecutive: boolean
  draws_timebank: boolean
  academic_year: string
  offerings: ElectiveOffering[]
}

// API helpers
export const schoolsApi = {
  list: () => api.get<School[]>('/schools').then((r) => r.data),
  create: (body: Omit<School, 'id' | 'weeks_per_year'> & { weeks_per_year?: number }) =>
    api.post<School>('/schools', body).then((r) => r.data),
  update: (id: number, body: Partial<Omit<School, 'id'>>) => api.patch<School>(`/schools/${id}`, body).then((r) => r.data),
  delete: (id: number) => api.delete(`/schools/${id}`),
  seedSubjects: (id: number) => api.post(`/schools/${id}/seed-subjects`).then((r) => r.data),
  validate: (id: number) => api.post(`/schools/${id}/validate`).then((r) => r.data),
  timeBank: (id: number, scheduleId?: number) =>
    api
      .get<SchoolTimeBankRead>(`/schools/${id}/time-bank`, {
        params: scheduleId != null ? { schedule_id: scheduleId } : undefined,
      })
      .then((r) => r.data),
}

export const specialEventsApi = {
  list: (schoolId: number) =>
    api.get<SpecialEvent[]>(`/schools/${schoolId}/special-events`).then((r) => r.data),
  create: (schoolId: number, body: Omit<SpecialEvent, 'id' | 'school_id'>) =>
    api.post<SpecialEvent>(`/schools/${schoolId}/special-events`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: Partial<Omit<SpecialEvent, 'id' | 'school_id'>>) =>
    api.patch<SpecialEvent>(`/schools/${schoolId}/special-events/${id}`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) =>
    api.delete(`/schools/${schoolId}/special-events/${id}`),
}

export const electiveBandsApi = {
  list: (schoolId: number) =>
    api.get<ElectiveBand[]>(`/schools/${schoolId}/elective-bands`).then((r) => r.data),
  create: (schoolId: number, body: {
    grade_level: number; band_type: ElectiveBandType; name: string; hours_per_week: number
    requires_consecutive: boolean; draws_timebank: boolean
    offerings: { subject_id: number; teacher_id: number; room_id: number }[]
  }) => api.post<ElectiveBand>(`/schools/${schoolId}/elective-bands`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: Partial<Omit<ElectiveBand, 'id' | 'school_id' | 'academic_year' | 'offerings'>>) =>
    api.patch<ElectiveBand>(`/schools/${schoolId}/elective-bands/${id}`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) =>
    api.delete(`/schools/${schoolId}/elective-bands/${id}`),
  addOffering: (schoolId: number, bandId: number, body: { subject_id: number; teacher_id: number; room_id: number }) =>
    api.post<ElectiveOffering>(`/schools/${schoolId}/elective-bands/${bandId}/offerings`, body).then((r) => r.data),
  deleteOffering: (schoolId: number, bandId: number, offeringId: number) =>
    api.delete(`/schools/${schoolId}/elective-bands/${bandId}/offerings/${offeringId}`),
}

export const teachersApi = {
  list: (schoolId: number) => api.get<Teacher[]>(`/schools/${schoolId}/teachers`).then((r) => r.data),
  create: (schoolId: number, body: Omit<Teacher, 'id' | 'school_id' | 'is_active'>) =>
    api.post<Teacher>(`/schools/${schoolId}/teachers`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: Partial<Omit<Teacher, 'id' | 'school_id'>>) =>
    api.patch<Teacher>(`/schools/${schoolId}/teachers/${id}`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) => api.delete(`/schools/${schoolId}/teachers/${id}`),
  addSubject: (schoolId: number, teacherId: number, subjectId: number) =>
    api.post(`/schools/${schoolId}/teachers/${teacherId}/subjects`, { subject_id: subjectId }),
}

export const roomsApi = {
  list: (schoolId: number) => api.get<Room[]>(`/schools/${schoolId}/rooms`).then((r) => r.data),
  create: (schoolId: number, body: Omit<Room, 'id' | 'school_id' | 'is_active'>) =>
    api.post<Room>(`/schools/${schoolId}/rooms`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) => api.delete(`/schools/${schoolId}/rooms/${id}`),
}

export const subjectsApi = {
  list: (schoolId: number) => api.get<Subject[]>(`/schools/${schoolId}/subjects`).then((r) => r.data),
  create: (schoolId: number, body: { name: string; short_code: string; category?: string; color_hex?: string | null; required_room_type?: string | null; double_lessons?: boolean; priority?: number }) =>
    api.post<Subject>(`/schools/${schoolId}/subjects`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: { requires_special_room?: boolean; required_room_type?: string | null; color_hex?: string | null; double_lessons?: boolean; priority?: number }) =>
    api.patch<Subject>(`/schools/${schoolId}/subjects/${id}`, body).then((r) => r.data),
}

export const classesApi = {
  list: (schoolId: number) => api.get<StudentClass[]>(`/schools/${schoolId}/classes`).then((r) => r.data),
  create: (schoolId: number, body: Omit<StudentClass, 'id' | 'school_id' | 'is_active'>) =>
    api.post<StudentClass>(`/schools/${schoolId}/classes`, body).then((r) => r.data),
  createBulk: (schoolId: number, body: { grade_start: number; grade_end: number; suffixes: string[]; student_count: number }) =>
    api.post<StudentClass[]>(`/schools/${schoolId}/classes/bulk`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: Partial<Omit<StudentClass, 'id' | 'school_id'>>) =>
    api.patch<StudentClass>(`/schools/${schoolId}/classes/${id}`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) => api.delete(`/schools/${schoolId}/classes/${id}`),
}

export const assignmentsApi = {
  list: (schoolId: number, classId?: number) =>
    api.get<Assignment[]>(`/schools/${schoolId}/assignments`, { params: { class_id: classId } }).then((r) => r.data),
  create: (schoolId: number, body: Omit<Assignment, 'id' | 'school_id'>) =>
    api.post<Assignment>(`/schools/${schoolId}/assignments`, body).then((r) => r.data),
  update: (schoolId: number, id: number, body: Partial<Assignment>) =>
    api.patch<Assignment>(`/schools/${schoolId}/assignments/${id}`, body).then((r) => r.data),
  delete: (schoolId: number, id: number) => api.delete(`/schools/${schoolId}/assignments/${id}`),
  bulkAutoAssign: (schoolId: number) =>
    api.post<{
      created: number
      skipped_no_teacher: number
      grade_totals: {
        grade: number; target_periods: number; achieved_periods: number
        target_clock_hours: number; delivered_clock_hours: number; meets_total: boolean
      }[]
    }>(`/schools/${schoolId}/assignments/bulk-auto-assign`).then((r) => r.data),
}

export const timeslotsApi = {
  list: (schoolId: number) => api.get<TimeSlot[]>(`/schools/${schoolId}/timeslots`).then((r) => r.data),
  create: (schoolId: number, body: Omit<TimeSlot, 'id' | 'school_id'>) =>
    api.post<TimeSlot>(`/schools/${schoolId}/timeslots`, body).then((r) => r.data),
  createBulk: (schoolId: number, body: Omit<TimeSlot, 'id' | 'school_id'>[]) =>
    api.post<TimeSlot[]>(`/schools/${schoolId}/timeslots/bulk`, body).then((r) => r.data),
  delete: (schoolId: number, slotId: number) => api.delete(`/schools/${schoolId}/timeslots/${slotId}`),
}

export const constraintsApi = {
  listTeacherUnavailabilities: (schoolId: number, teacherId: number) =>
    api.get<TeacherUnavailability[]>(`/schools/${schoolId}/teachers/${teacherId}/unavailabilities`).then((r) => r.data),
  addTeacherUnavailability: (schoolId: number, teacherId: number, body: { time_slot_id: number; constraint_type?: 'HARD' | 'SOFT'; reason?: string }) =>
    api.post<TeacherUnavailability>(`/schools/${schoolId}/teachers/${teacherId}/unavailabilities`, body).then((r) => r.data),
  deleteTeacherUnavailability: (schoolId: number, teacherId: number, unavailId: number) =>
    api.delete(`/schools/${schoolId}/teachers/${teacherId}/unavailabilities/${unavailId}`),
}

export interface AccessToken {
  id: number
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  expires_at: string | null
}

export interface AccessTokenCreated extends AccessToken {
  token: string
}

export const tokensApi = {
  list: () => api.get<AccessToken[]>('/auth/personal-tokens').then((r) => r.data),
  create: (body: { name: string; expires_days: number | null }) =>
    api.post<AccessTokenCreated>('/auth/personal-tokens', body).then((r) => r.data),
  revoke: (id: number) => api.delete(`/auth/personal-tokens/${id}`),
}

export const schedulesApi = {
  list: (schoolId: number) => api.get<Schedule[]>(`/schools/${schoolId}/schedules`).then((r) => r.data),
  create: (schoolId: number, body: { name: string; academic_year: string }) =>
    api.post<Schedule>(`/schools/${schoolId}/schedules`, body).then((r) => r.data),
  delete: (schoolId: number, scheduleId: number) =>
    api.delete(`/schools/${schoolId}/schedules/${scheduleId}`),
  generate: (schoolId: number, scheduleId: number) =>
    api.post<Schedule>(`/schools/${schoolId}/schedules/${scheduleId}/generate`).then((r) => r.data),
  entries: (schoolId: number, scheduleId: number) =>
    api.get<ScheduleEntry[]>(`/schools/${schoolId}/schedules/${scheduleId}/entries`).then((r) => r.data),
}
