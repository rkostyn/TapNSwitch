import { describe, expect, it } from 'vitest'
import { computed, ref } from 'vue'
import type { ApiEvent } from '../api'
import {
  EVENT_TYPE_OPTIONS,
  defaultPairingStyleFor,
  eventTypeOf,
  eventTypeRules,
  pairingStyleOf,
} from '../eventType'

type TypedEvent = Pick<ApiEvent, 'event_type' | 'pairing_style'>

describe('eventTypeOf', () => {
  it('reads the event type', () => {
    expect(eventTypeOf({ event_type: 'tournament' })).toBe('tournament')
    expect(eventTypeOf({ event_type: 'standard' })).toBe('standard')
  })

  it('treats a missing type, or no event, as standard', () => {
    expect(eventTypeOf({})).toBe('standard')
    expect(eventTypeOf(null)).toBe('standard')
    expect(eventTypeOf(undefined)).toBe('standard')
  })
})

describe('defaultPairingStyleFor', () => {
  it('is round robin for standard groups and Swiss for tournaments', () => {
    expect(defaultPairingStyleFor('standard')).toBe('round_robin')
    expect(defaultPairingStyleFor('tournament')).toBe('swiss')
  })
})

describe('pairingStyleOf', () => {
  it('keeps a stored style whatever the type', () => {
    expect(pairingStyleOf({ event_type: 'tournament', pairing_style: 'round_robin' })).toBe('round_robin')
    expect(pairingStyleOf({ event_type: 'standard', pairing_style: 'swiss' })).toBe('swiss')
  })

  it("falls back to the type's default when the style is missing", () => {
    expect(pairingStyleOf({ event_type: 'tournament' })).toBe('swiss')
    expect(pairingStyleOf({ event_type: 'standard' })).toBe('round_robin')
    expect(pairingStyleOf({})).toBe('round_robin')
  })
})

describe('eventTypeRules', () => {
  it('standard: round robin first, floor wording', () => {
    const rules = eventTypeRules('standard')
    expect(rules.tournament).toBe(false)
    expect(rules.defaultPairingStyle).toBe('round_robin')
    expect(rules.styleOptions.map(o => o.value)).toEqual(['round_robin', 'swiss'])
  })

  it('tournament: Swiss first, tournament wording', () => {
    const rules = eventTypeRules('tournament')
    expect(rules.tournament).toBe(true)
    expect(rules.defaultPairingStyle).toBe('swiss')
    expect(rules.styleOptions.map(o => o.value)).toEqual(['swiss', 'round_robin'])
  })

  it('follows the event when its type is switched', () => {
    const event = ref<TypedEvent | null>({ event_type: 'standard' })
    const rules = computed(() => eventTypeRules(eventTypeOf(event.value)))
    expect(rules.value.tournament).toBe(false)
    event.value = { event_type: 'tournament', pairing_style: 'swiss' }
    expect(rules.value.tournament).toBe(true)
    expect(rules.value.styleOptions[0]?.value).toBe('swiss')
  })
})

describe('EVENT_TYPE_OPTIONS', () => {
  it('offers standard first, as the default', () => {
    expect(EVENT_TYPE_OPTIONS.map(o => o.value)).toEqual(['standard', 'tournament'])
  })
})
