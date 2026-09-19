/** The rules behind the three participant self-service switches on an event's attendance config.
 *
 * They live here rather than inline in the screen because they are a small state machine — checkout
 * depends on check-in, and the checkout window depends on checkout — and a rule that only exists as
 * a JSX condition is a rule nothing can check.
 */

export type SelfServiceFields = {
  self_check_in_enabled: boolean;
  self_checkout_enabled: boolean;
  checkout_opens_at: string | null;
};

/**
 * Resolve a self check-in / self checkout switch into the self-service state it leaves behind.
 *
 * Self checkout is the second half of one journey: a participant who cannot check themselves in can
 * never reach a checkout, so the server refuses the pair outright ("self checkout requires self
 * check-in"). This keeps the form's own state inside that rule — enabling checkout without check-in
 * is simply not applied, and turning check-in off takes checkout down with it.
 *
 * A checkout window is kept only while checkout is on. The input that edits it is hidden when
 * checkout is off, and a setting nobody can see must not be saved behind them.
 */
export function resolveSelfServiceToggle(
  config: SelfServiceFields,
  field: 'self_check_in_enabled' | 'self_checkout_enabled',
  enabled: boolean,
): SelfServiceFields {
  if (field === 'self_check_in_enabled') {
    return enabled
      ? { ...config, self_check_in_enabled: true }
      : { ...config, self_check_in_enabled: false, self_checkout_enabled: false, checkout_opens_at: null };
  }
  // Check-in off: the switch does not move, so the state the form holds is one the API accepts.
  if (enabled && !config.self_check_in_enabled) return { ...config, self_checkout_enabled: false };
  return {
    ...config,
    self_checkout_enabled: enabled,
    checkout_opens_at: enabled ? config.checkout_opens_at : null,
  };
}

/** `datetime-local` speaks wall-clock; the API speaks instants. Convert at the boundary only. */
export function toCheckoutInput(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

/** The instant to store for a wall-clock input. Blank means there is no window, which is null. */
export function toCheckoutInstant(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
