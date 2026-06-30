import { ScheduleApiError, ScheduleNetworkError } from '../../lib/api'

export function scheduleImportErrorMessage(err: unknown): string {
  if (err instanceof ScheduleNetworkError) {
    return 'Could not reach the schedule import service. Check that the backend is running and retry.'
  }
  if (err instanceof ScheduleApiError) {
    switch (err.code) {
      case 'schedule_file_too_large':
        return 'This file exceeds the 50 MB upload limit.'
      case 'schedule_schema_not_ready':
        return 'Schedule schema is not current. Apply pending database migrations from Data Health admin controls.'
      case 'schedule_multipart_unavailable':
        return 'Schedule import upload is unavailable. Reinstall analytics-ui dependencies (python-multipart) and restart the backend.'
      case 'unsupported_schedule_format':
        return 'Unsupported schedule format. Use Primavera XER, Primavera XML/PMXML, Microsoft Project XML, or CSV with operator mapping.'
      case 'schedule_zip_invalid':
        return 'This .zip package could not be opened. Re-export the package and try again.'
      case 'schedule_zip_too_many_files':
        return 'This .zip package has too many files. Keep it to the schedule files (and any baseline) and retry.'
      case 'schedule_zip_unsafe_path':
        return 'This .zip package contains an unsafe file path and was rejected.'
      case 'schedule_zip_nested_archive':
        return 'This .zip package contains another archive. Unzip it and upload the schedule files directly.'
      case 'schedule_zip_too_large':
        return 'This .zip package is too large once decompressed (150 MB limit). Upload a single schedule file instead.'
      case 'schedule_zip_read_failed':
        return 'A file inside this .zip package could not be read. Re-export the package and retry.'
      case 'schedule_package_no_valid_files':
        return 'This .zip package did not contain a readable Primavera XER, XML/PMXML, MS Project XML, or mapped CSV schedule.'
      case 'schedule_current_project_required':
        return 'This package did not contain a selectable current schedule. Include the current XER or XML schedule file.'
      case 'schedule_package_multiple_current_candidates':
        if (err.payload?.block_reason === 'different_normalized_data_date') {
          return 'This .zip package contains more than one current schedule with different data dates. Upload one current schedule snapshot with any companion baseline files.'
        }
        if (err.payload?.block_reason === 'low_activity_overlap') {
          return 'This .zip package contains current schedules with low activity-ID overlap. Upload one current schedule snapshot with any companion baseline files.'
        }
        return 'This .zip package contains conflicting current schedule snapshots. Upload one current schedule snapshot with any companion baseline files.'
      case 'schedule_parse_failed':
        return 'Could not parse the schedule file. Check that it is valid Primavera XER, Primavera XML/PMXML, Microsoft Project XML, or mapped CSV.'
      case 'schedule_project_required':
        return 'Select an existing project before uploading or committing a schedule.'
      case 'schedule_project_unknown':
        return 'Selected project is not available for schedule import.'
      case 'schedule_import_invalid':
        return err.message || 'Schedule import request was invalid.'
      case 'schedule_project_mismatch':
        return 'Selected project no longer matches the preview. Re-upload the file for the intended project.'
      case 'schedule_import_persistence_failed':
        return 'Schedule import could not be saved completely. No partial version was committed. Create a new preview and try again.'
      case 'duplicate_schedule_version':
        return 'This schedule version already exists. Use the supersede flow to replace it.'
      case 'schedule_supersede_confirmation_required':
        return 'This supersede preview needs explicit confirmation. Click Submit supersede to replace the existing schedule version.'
      case 'schedule_supersede_state_mismatch':
        return 'The supersede confirmation no longer matches the preview. Create a new preview and try again.'
      default:
        return err.message || 'Schedule import failed.'
    }
  }
  return 'Schedule import failed. Check the file format and try again.'
}
