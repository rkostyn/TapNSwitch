// One event's data and actions for EventDetail: loading the event and its
// matches, the roster (add/remove/late), group-stage config and generation,
// swiss scores, the bracket, per-match rounds, opening a match (with lock
// takeover), switching the event type, and closing the event. Every action shares one busy flag and one
// error message, shown in EventDetail's error banner.

import { computed, ref } from 'vue'
import {
  addPlayer,
  apiErrorMessage,
  errorStatus,
  finishEvent,
  generateBracket,
  generateSwissMatches,
  generateSwissScores,
  getEvent,
  getMatchesByEvent,
  removePlayer,
  setEventType,
  setPlayerLate,
  updateMatchRounds,
  updateSwissConfig,
  type ApiEvent,
  type ApiMatch,
  type EventType,
} from '../api'
import { isDelayedByLate, sortForMatchList } from '../eventMatches'
import { eventTypeOf, eventTypeRules, pairingStyleOf } from '../eventType'
import { lockForScoring } from '../matchLock'
import type { SelectMatchPayload } from '../match'
import type { PairingStyle } from '../config'
import { laneLabel } from '../venue'

export interface EventDetailHooks {
  /** After every successful event load (initial and after regeneration). */
  onLoaded: (event: ApiEvent) => void
  /** A match has been locked for this device and should open on the scoreboard. */
  onMatchSelected: (payload: SelectMatchPayload) => void
  /** The event has been closed. */
  onClosed: () => void
}

export function useEventDetail(eventId: () => string, hooks: EventDetailHooks) {
  const event = ref<ApiEvent | null>(null)
  const matches = ref<ApiMatch[]>([])
  const loading = ref(true)
  const error = ref('')
  const busy = ref(false)

  // Roster and group-stage form
  const newPlayer = ref('')
  const pairingStyle = ref<PairingStyle>('round_robin')
  const configMatches = ref(2)
  const configRounds = ref(2)
  // After Swiss matches exist, adding a player re-opens the generate controls so
  // the schedule can be rebuilt to include them.
  const needsRegen = ref(false)

  // Bracket prompt
  const showBracketPrompt = ref(false)
  const bracketRounds = ref(3)

  // Takeover state: a match another device holds, awaiting override confirmation
  const takeover = ref<{ match: ApiMatch; lockedBy: string } | null>(null)

  const latePlayers = computed(() => event.value?.late_players ?? [])
  const swissMatches = computed(() => matches.value.filter(m => m.match_type === 'swiss'))
  const sortedSwissMatches = computed(() => sortForMatchList(swissMatches.value, latePlayers.value))
  const lateMatch = (m: ApiMatch) => isDelayedByLate(m, latePlayers.value)
  const bracketMatches = computed(() => matches.value.filter(m => m.match_type === 'bracket'))
  const swissGenerated = computed(() => !!event.value?.swiss_generated_at)
  const bracketGenerated = computed(() => !!event.value?.bracket_generated_at)
  const standings = computed(() => event.value?.swiss_standings ?? null)

  // Type-dependent choices (default style, toggle order, hints), following the
  // event's own type, so they update when staff switch it.
  const eventType = computed<EventType>(() => eventTypeOf(event.value))
  const rules = computed(() => eventTypeRules(eventType.value))
  // The API refuses a type change (409) once matches or a bracket exist
  const canChangeType = computed(() =>
    !!event.value
    && !event.value.is_finished
    && !swissGenerated.value
    && !bracketGenerated.value
    && matches.value.length === 0,
  )

  // Show the event's stored group-stage settings in the form
  function applyStoredConfig(loaded: ApiEvent) {
    pairingStyle.value = pairingStyleOf(loaded)
    configMatches.value = loaded.swiss_matches_per_player
    configRounds.value = loaded.swiss_rounds_per_match
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const loaded = await getEvent(eventId())
      event.value = loaded
      applyStoredConfig(loaded)
      hooks.onLoaded(loaded)
    } catch (e) {
      console.error(`Failed to load event ${eventId()}`, e)
      event.value = null
      error.value = 'Failed to load event.'
      loading.value = false
      return
    }
    try {
      matches.value = await getMatchesByEvent(eventId())
    } catch (e) {
      // Still show the event; the match list is just empty until a reload works
      console.error(`Failed to load matches for event ${eventId()}`, e)
      matches.value = []
      error.value = 'Could not load this event\'s matches.'
    }
    loading.value = false
  }

  async function run(action: () => Promise<void>, fallback: string) {
    error.value = ''
    busy.value = true
    try {
      await action()
    } catch (e) {
      console.error(fallback, e)
      error.value = apiErrorMessage(e, fallback)
    } finally {
      busy.value = false
    }
  }

  async function submitAddPlayer() {
    const name = newPlayer.value.trim()
    if (!name) return
    await run(async () => {
      event.value = await addPlayer(eventId(), name)
      newPlayer.value = ''
      // A new player needs matches — surface the generate controls again.
      if (swissGenerated.value) needsRegen.value = true
    }, 'Failed to add player.')
  }

  async function removePlayerFromEvent(player: string) {
    await run(async () => {
      event.value = await removePlayer(eventId(), player)
      // The schedule no longer matches the roster — offer to rebuild it.
      if (swissGenerated.value) needsRegen.value = true
    }, 'Failed to remove player.')
  }

  async function toggleLate(player: string) {
    if (!event.value) return
    const late = !event.value.late_players.includes(player)
    await run(async () => {
      event.value = await setPlayerLate(eventId(), player, late)
    }, 'Failed to update player.')
  }

  async function saveConfigAndGenerate() {
    await run(async () => {
      event.value = await updateSwissConfig(
        eventId(), configMatches.value, configRounds.value, pairingStyle.value,
      )
      await generateSwissMatches(eventId())
      needsRegen.value = false
      await load()
    }, 'Failed to generate matches.')
  }

  // Roster changed after generation: rebuild the schedule (before any scores) or
  // append matches for late entrants (after). Config is left as-is.
  async function regenerateMatches() {
    await run(async () => {
      await generateSwissMatches(eventId())
      needsRegen.value = false
      await load()
    }, 'Failed to update matches.')
  }

  async function generateScores() {
    await run(async () => {
      const result = await generateSwissScores(eventId())
      if (event.value) event.value = { ...event.value, swiss_standings: result }
    }, 'Failed to generate swiss scores.')
  }

  async function confirmBracket() {
    await run(async () => {
      await generateBracket(eventId(), bracketRounds.value)
      showBracketPrompt.value = false
      await load()
    }, 'Failed to generate bracket.')
  }

  async function changeMatchRounds(match: ApiMatch, rounds: number) {
    await run(async () => {
      await updateMatchRounds(match.match_id, rounds)
      await load()
    }, 'Failed to update rounds.')
  }

  async function selectMatch(match: ApiMatch) {
    if (!match.player_1_id || !match.player_2_id) {
      error.value = 'Both players must be decided before this match can start.'
      return
    }
    // Finished matches open directly — scores stay editable after the fact
    await acquire(match, false)
  }

  async function acquire(match: ApiMatch, force: boolean) {
    error.value = ''
    busy.value = true
    try {
      const result = await lockForScoring(match.match_id, force)
      if (result.status === 'held') {
        takeover.value = { match, lockedBy: result.lockedBy }
      } else {
        const locked = result.match
        hooks.onMatchSelected({ match: locked, event: event.value, arenaLabel: laneLabel(locked.arena_id) })
      }
    } catch (e) {
      console.error(`Failed to lock match ${match.match_id}`, e)
      error.value = apiErrorMessage(e, 'Failed to select match.')
    } finally {
      busy.value = false
    }
  }

  async function confirmTakeover() {
    if (!takeover.value) return
    const match = takeover.value.match
    takeover.value = null
    await acquire(match, true)
  }

  // Standard <-> tournament, until matches are generated. The API resets the
  // pairing style to the new type's default, so the form follows the reply.
  async function changeEventType(type: EventType) {
    if (!event.value || type === eventType.value || !canChangeType.value) return
    error.value = ''
    busy.value = true
    try {
      const updated = await setEventType(eventId(), type)
      event.value = updated
      applyStoredConfig(updated)
    } catch (e) {
      console.error(`Failed to change event ${eventId()} to ${type}`, e)
      const conflict = errorStatus(e) === 409
      const message = apiErrorMessage(e, conflict
        ? 'Matches have already been generated, so the event type can no longer change.'
        : 'Failed to change the event type.')
      // A 409 means matches exist (likely generated on another device): reload
      // so the screen shows them and the type control locks, then explain.
      if (conflict) await load()
      error.value = message
    } finally {
      busy.value = false
    }
  }

  async function closeEvent() {
    await run(async () => {
      event.value = await finishEvent(eventId())
      hooks.onClosed()
    }, 'Failed to close the event.')
  }

  return {
    event,
    matches,
    loading,
    error,
    busy,
    newPlayer,
    pairingStyle,
    configMatches,
    configRounds,
    needsRegen,
    showBracketPrompt,
    bracketRounds,
    takeover,
    sortedSwissMatches,
    lateMatch,
    bracketMatches,
    swissGenerated,
    bracketGenerated,
    standings,
    eventType,
    rules,
    canChangeType,
    load,
    submitAddPlayer,
    removePlayerFromEvent,
    toggleLate,
    saveConfigAndGenerate,
    regenerateMatches,
    generateScores,
    confirmBracket,
    changeMatchRounds,
    selectMatch,
    confirmTakeover,
    changeEventType,
    closeEvent,
  }
}
