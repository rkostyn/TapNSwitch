// Every event-screen decision that depends on the event's type (an everyday
// floor group vs a tournament) lives here, keyed off the event's own
// `event_type`, so standard groups and tournaments run side by side.

import type { ApiEvent, EventType } from './api'
import type { PairingStyle } from './config'

export interface EventTypeRules {
  /** Tournament wording for the group-stage style hints. */
  tournament: boolean
  /** Style selected for an event whose stored style is missing or unknown. */
  defaultPairingStyle: PairingStyle
  /** Style toggle order: the type's default first. */
  styleOptions: { value: PairingStyle; label: string }[]
}

/** Choices for the event type toggle, standard (the default) first. */
export const EVENT_TYPE_OPTIONS: { value: EventType; label: string }[] = [
  { value: 'standard', label: 'Standard group' },
  { value: 'tournament', label: 'Tournament' },
]

/** An event's type; a missing or unknown value (older events) is standard. */
export function eventTypeOf(event: Pick<ApiEvent, 'event_type'> | null | undefined): EventType {
  return event?.event_type === 'tournament' ? 'tournament' : 'standard'
}

/** Group-stage style a new event of this type starts with. */
export function defaultPairingStyleFor(type: EventType): PairingStyle {
  return type === 'tournament' ? 'swiss' : 'round_robin'
}

/** The event's stored pairing style, or its type's default when missing or unknown. */
export function pairingStyleOf(event: Pick<ApiEvent, 'event_type' | 'pairing_style'>): PairingStyle {
  return event.pairing_style === 'round_robin' || event.pairing_style === 'swiss'
    ? event.pairing_style
    : defaultPairingStyleFor(eventTypeOf(event))
}

export function eventTypeRules(type: EventType): EventTypeRules {
  const tournament = type === 'tournament'
  return {
    tournament,
    defaultPairingStyle: defaultPairingStyleFor(type),
    // The type's default style is offered first: round robin on the floor, Swiss for tournaments
    styleOptions: tournament
      ? [{ value: 'swiss', label: 'Swiss' }, { value: 'round_robin', label: 'Round robin' }]
      : [{ value: 'round_robin', label: 'Round robin' }, { value: 'swiss', label: 'Swiss' }],
  }
}
