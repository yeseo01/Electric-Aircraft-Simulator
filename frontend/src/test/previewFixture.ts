import type { FlightPreview } from '../api/flightPreviews'

// Artificial stationary flight, shared by client contract and UI tests.
export function previewFixture(): FlightPreview {
  return {
    sample_count: 3,
    waypoint_count: 2,
    duration_s: 2,
    downsample_sec: 1,
    coordinate_system: 'local_enu',
    altitude_reference: 'first_pressure_altitude',
    origin: { latitude_deg: 0, longitude_deg: 0, pressure_altitude_m: 100 },
    waypoints: [
      { time_s: 0, east_m: 0, north_m: 0, relative_altitude_m: 0 },
      { time_s: 2, east_m: 0, north_m: 0, relative_altitude_m: 0 },
    ],
  }
}
