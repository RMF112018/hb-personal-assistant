import { Navigate, useParams } from 'react-router-dom'

export function ScheduleActivitiesRedirect() {
  const { scheduleVersionKey = '' } = useParams()
  const version = encodeURIComponent(scheduleVersionKey)
  return <Navigate to={`/schedules/activities?version=${version}`} replace />
}