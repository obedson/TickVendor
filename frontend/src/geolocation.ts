/** The one browser-location engine for the whole product.
 *
 * Physical-task evidence, ticket self check-in, self check-out and geofenced benefit redemption
 * all need the same thing: a single `getCurrentPosition` call whose failures are classified so
 * the participant is told which failure actually happened. Duplicating that call per surface is
 * how those surfaces drift apart, so every caller goes through `currentPosition` and only the
 * wording differs.
 *
 * The participant-facing text stays in `location.ts` — this module carries the classification.
 */

import { locationErrorMessage } from './location';

export type Position = { latitude: number; longitude: number; accuracy_meters: number };

/** Which failure happened, so a caller can add surface-specific guidance without re-deriving it. */
export type LocationFailureKind =
  | 'unsupported'
  | 'denied'
  | 'unavailable'
  | 'timeout'
  | 'request_failed';

const KIND_BY_CODE: Record<number, LocationFailureKind> = {
  1: 'denied',
  2: 'unavailable',
  3: 'timeout',
};

export class LocationFailure extends Error {
  constructor(public readonly kind: LocationFailureKind, message: string) {
    super(message);
    this.name = 'LocationFailure';
  }
}

/**
 * Ask the browser for one high-accuracy fix.
 *
 * Rejects with `LocationFailure`; never resolves with a partial or stale reading, because a
 * geofence decision made on a stale coordinate is worse than no decision.
 */
export async function currentPosition(
  options: { timeout?: number; maximumAge?: number } = {},
): Promise<Position> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    throw new LocationFailure('unsupported', 'Location is not supported by this browser.');
  }
  const position = await new Promise<GeolocationPosition>((resolve, reject) => {
    try {
      navigator.geolocation.getCurrentPosition(
        resolve,
        (failure: GeolocationPositionError) => {
          const kind = KIND_BY_CODE[failure.code] ?? 'request_failed';
          reject(new LocationFailure(kind, locationErrorMessage(failure)));
        },
        {
          enableHighAccuracy: true,
          timeout: options.timeout ?? 10000,
          maximumAge: options.maximumAge ?? 0,
        },
      );
    } catch {
      reject(new LocationFailure('request_failed', 'Location could not be requested.'));
    }
  });
  return {
    latitude: position.coords.latitude,
    longitude: position.coords.longitude,
    accuracy_meters: position.coords.accuracy,
  };
}
