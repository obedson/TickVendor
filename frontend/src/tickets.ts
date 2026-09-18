/** The holder-facing ticket vocabulary, shared by the wallet, ticket detail and the claim page.
 *
 * The backend sends facts (`status`, `transfer_state`, `checked_in_at`, `checked_out_at`); this
 * module is the single place that turns them into one participant-facing state, so My Tickets,
 * the detail screen and the claim page can never disagree about what a ticket is doing.
 */

import type { OfflineTicket } from './offlineTickets';

export type TicketState =
  | 'refunded'
  | 'cancelled'
  | 'expired'
  | 'checked_out'
  | 'checked_in'
  | 'used'
  | 'unassigned'
  | 'invitation_sent'
  | 'claimed';

/** Every state carries a glyph as well as a colour, so state never depends on colour alone. */
export const TICKET_STATE: Record<TicketState, { label: string; glyph: string; chip: string; help: string }> = {
  refunded: { label: 'Refunded', glyph: '↩', chip: 'chip-default', help: 'This ticket was refunded and is no longer valid for entry.' },
  cancelled: { label: 'Cancelled', glyph: '✕', chip: 'chip-red', help: 'This ticket was cancelled and is no longer valid for entry.' },
  expired: { label: 'Expired', glyph: '⌛', chip: 'chip-default', help: 'This ticket expired before it was used.' },
  checked_out: { label: 'Checked out', glyph: '⇥', chip: 'chip-blue', help: 'You checked in and have since checked out of this event.' },
  checked_in: { label: 'Checked in', glyph: '✓', chip: 'chip-green', help: 'Your attendance at this event is recorded.' },
  used: { label: 'Checked in', glyph: '✓', chip: 'chip-green', help: 'This ticket has been used for entry.' },
  unassigned: { label: 'Unassigned', glyph: '○', chip: 'chip-yellow', help: 'No one holds this ticket yet. Send it to the person who will attend.' },
  invitation_sent: { label: 'Invitation sent', glyph: '↗', chip: 'chip-yellow', help: 'A claim link is outstanding. The ticket moves once it is claimed.' },
  claimed: { label: 'Claimed', glyph: '●', chip: 'chip-teal', help: 'This ticket is held and ready to use.' },
};

/**
 * Resolve the one state a participant should see.
 *
 * Order matters: a refund outranks attendance, and attendance outranks the assignment state,
 * because "checked in" is the fact a participant acts on at the venue.
 */
export function ticketState(ticket: Pick<OfflineTicket,
  'status' | 'transfer_state' | 'checked_in_at' | 'checked_out_at' | 'used_at'>): TicketState {
  if (ticket.status === 'refunded') return 'refunded';
  if (ticket.status === 'cancelled' || ticket.transfer_state === 'cancelled') return 'cancelled';
  if (ticket.status === 'expired') return 'expired';
  if (ticket.checked_out_at) return 'checked_out';
  if (ticket.checked_in_at || ticket.used_at || ticket.transfer_state === 'checked_in') return 'checked_in';
  if (ticket.status === 'used') return 'used';
  if (ticket.transfer_state === 'unassigned') return 'unassigned';
  if (ticket.transfer_state === 'invitation_sent') return 'invitation_sent';
  return 'claimed';
}

/** A ticket can only be handed on while it is still valid for entry and not yet checked in. */
export function isTransferable(ticket: OfflineTicket): boolean {
  if (ticket.status !== 'active') return false;
  if (ticket.used_at || ticket.checked_in_at) return false;
  return ['unassigned', 'invitation_sent', 'claimed'].includes(ticket.transfer_state ?? 'claimed');
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return '';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours && minutes) return `${hours}h ${minutes}m`;
  if (hours) return `${hours}h`;
  if (minutes) return `${minutes}m`;
  return `${seconds}s`;
}

// ── Ticket detail contract (`GET /tickets/{ticket_id}`) ──────────────────────

export type EntitlementState = 'available' | 'locked' | 'redeemed' | 'expired' | 'revoked';

export type TicketEntitlement = {
  id: string;
  name: string;
  description?: string | null;
  quantity: number;
  redemption_mode: string;
  redemption_starts_at?: string | null;
  redemption_ends_at?: string | null;
  requires_check_in: boolean;
  requires_checkout: boolean;
  min_attendance_minutes?: number | null;
  requires_geofence: boolean;
  requires_staff_validation: boolean;
  remaining: number;
  status: EntitlementState;
  locked_reason?: string | null;
  last_redeemed_at?: string | null;
};

export type AttendanceState = {
  attendance_id: string;
  event_id: string;
  ticket_id?: string | null;
  status: string;
  checked_in_at?: string | null;
  checked_out_at?: string | null;
  duration_seconds?: number | null;
  viable_methods: string[];
};

export type TicketDetail = {
  ticket: {
    id: string; public_id: string; qr_token: string; event_id: string; ticket_type_id: string;
    attendee_id: string; order_id?: string | null; status: string; used_at?: string | null;
  };
  event_title: string;
  event_starts_at: string;
  event_ends_at?: string | null;
  venue_name?: string | null;
  venue_address?: string | null;
  ticket_type_name: string;
  self_check_in_enabled: boolean;
  self_checkout_enabled: boolean;
  attendance?: AttendanceState | null;
  entitlements: TicketEntitlement[];
};

export type RedemptionCredential = {
  status: string;
  entitlement: string;
  code?: string | null;
  qr_payload?: string | null;
  expires_at?: string | null;
  remaining?: number | null;
};

export type TransferPreview = {
  status: string;
  claimable: boolean;
  expires_at?: string | null;
  event_title?: string | null;
  event_starts_at?: string | null;
  ticket_type_name?: string | null;
  requires_authentication: boolean;
};

export type StartedTransfer = {
  id: string; ticket_id: string; status: string; expires_at: string;
  claimed_at?: string | null; share_url?: string | null;
};

/** Human wording for a transfer link's own lifecycle, distinct from the ticket's state. */
export const TRANSFER_STATUS_LABEL: Record<string, string> = {
  pending: 'Waiting to be claimed',
  claimed: 'Claimed',
  cancelled: 'Cancelled',
  expired: 'Expired',
};
