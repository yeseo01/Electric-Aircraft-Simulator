export type PreviewWaypoint = {
  time_s: number
  east_m: number
  north_m: number
  relative_altitude_m: number
}

export type FlightPreview = {
  sample_count: number
  waypoint_count: number
  duration_s: number
  downsample_sec: number
  coordinate_system: 'local_enu'
  altitude_reference: 'first_pressure_altitude'
  origin: {
    latitude_deg: number
    longitude_deg: number
    pressure_altitude_m: number
  }
  waypoints: PreviewWaypoint[]
}

const issueMessages: Record<string, string> = {
  empty_file: 'The CSV is empty.',
  invalid_encoding: 'Save the CSV with UTF-8 encoding and try again.',
  file_too_large: 'The CSV exceeds 10 MiB.',
  request_too_large: 'The upload exceeds the request size limit.',
  invalid_header: 'Every CSV column must have a name.',
  duplicate_column: 'CSV column names must be unique.',
  missing_column: 'A required column is missing.',
  invalid_csv: 'The CSV syntax could not be read.',
  invalid_row: 'A row has a different number of fields from the header.',
  invalid_number: 'A required value is missing or is not a number.',
  non_finite_value: 'A required value must be finite.',
  out_of_range: 'Latitude or longitude is outside its valid range.',
  negative_time: 'Time must be non-negative.',
  non_increasing_time: 'Time must strictly increase, without duplicates.',
  invalid_time_resolution: 'Time values are too close after conversion to seconds.',
  insufficient_samples: 'The CSV must contain at least two data rows.',
  invalid_downsample_sec: 'The waypoint interval must be finite and positive.',
  invalid_coordinates: 'The CSV could not produce finite waypoint coordinates.',
  missing_file: 'Choose a CSV file before generating a preview.',
  invalid_file: 'The server did not receive a valid file upload.',
  invalid_multipart: 'The upload could not be read. Try again.',
  invalid_request: 'The upload request is invalid.',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isCount(value: unknown): value is number {
  return isFiniteNumber(value) && Number.isInteger(value) && value >= 2
}

// TypeScript describes our contract; this also checks the actual JSON received.
function isFlightPreview(value: unknown): value is FlightPreview {
  if (!isRecord(value) || !isRecord(value.origin)) return false
  return (
    isCount(value.sample_count) &&
    isCount(value.waypoint_count) &&
    value.waypoint_count <= value.sample_count &&
    isFiniteNumber(value.duration_s) && value.duration_s > 0 &&
    isFiniteNumber(value.downsample_sec) && value.downsample_sec > 0 &&
    value.coordinate_system === 'local_enu' &&
    value.altitude_reference === 'first_pressure_altitude' &&
    isFiniteNumber(value.origin.latitude_deg) &&
    isFiniteNumber(value.origin.longitude_deg) &&
    isFiniteNumber(value.origin.pressure_altitude_m) &&
    Array.isArray(value.waypoints) &&
    value.waypoints.length === value.waypoint_count &&
    value.waypoints.every((point: unknown) =>
      isRecord(point) &&
      isFiniteNumber(point.time_s) &&
      isFiniteNumber(point.east_m) &&
      isFiniteNumber(point.north_m) &&
      isFiniteNumber(point.relative_altitude_m),
    )
  )
}

function responseError(status: number, payload: unknown): string {
  if (status >= 500) {
    return 'The preview service is unavailable. Check that the local API is running on port 8000, then try again.'
  }
  if (isRecord(payload) && isRecord(payload.error)) {
    const issues = payload.error.issues
    const issue = Array.isArray(issues) ? issues[0] : undefined
    if (isRecord(issue) && typeof issue.code === 'string' && Object.hasOwn(issueMessages, issue.code)) {
      const details = [
        typeof issue.column === 'string' ? `Column: ${issue.column}.` : '',
        isFiniteNumber(issue.row) && Number.isInteger(issue.row) && issue.row > 0
          ? `CSV line: ${issue.row}.` : '',
      ].filter(Boolean).join(' ')
      return [issueMessages[issue.code], details].filter(Boolean).join(' ')
    }
    if (typeof payload.error.code === 'string' && Object.hasOwn(issueMessages, payload.error.code)) {
      return issueMessages[payload.error.code]
    }
  }
  if (status === 413) return 'The upload exceeds the size limit. Choose a CSV up to 10 MiB.'
  if (status === 422) return 'The CSV could not be validated. Check its required columns and values.'
  return `The preview request failed (HTTP ${status}). Try again.`
}

export async function createFlightPreview(file: File, signal: AbortSignal): Promise<FlightPreview> {
  const form = new FormData()
  form.append('file', file)
  form.append('downsample_sec', '1.0')

  let response: Response
  try {
    response = await fetch('/api/flight-previews', {
      method: 'POST',
      body: form,
      signal,
      cache: 'no-store',
      // The browser sets Content-Type with the multipart boundary for FormData.
    })
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error('Could not reach the preview service. Check that the frontend and local API are running, then try again.')
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch (error) {
    if (signal.aborted) throw error
    if (!response.ok) throw new Error(responseError(response.status, null))
    throw new Error('The preview service returned an unreadable response. Try again.')
  }
  // fetch can resolve normally for HTTP errors such as 422 and 500.
  if (!response.ok) throw new Error(responseError(response.status, payload))
  if (!isFlightPreview(payload)) {
    throw new Error('The preview service returned an unexpected result. Try again.')
  }
  return payload
}
