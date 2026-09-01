export type LocationError = Pick<GeolocationPositionError, 'code'>;

export function locationErrorMessage(error: LocationError): string {
  if (error.code === 1) {
    return 'Location permission was denied. Allow location access or use event QR or organizer verification.';
  }
  if (error.code === 2) {
    return 'Location is unavailable. Move to an open area or use event QR or organizer verification.';
  }
  if (error.code === 3) {
    return 'Location request timed out. Try again or use event QR or organizer verification.';
  }
  return 'Location could not be verified. Use event QR or organizer verification.';
}
