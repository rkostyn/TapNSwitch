import axios from 'axios'
import { config } from './config'
import { getCookie, setCookie } from './cookies'
import { getOrCreateClientId } from './clientId'

const http = axios.create({ baseURL: config.apiUrl })

const REFRESH_AFTER_MS = 12 * 60 * 60 * 1000

let refreshPromise: Promise<void> | null = null

// Silently swap in a fresh token once the current one is older than 12 hours.
// Uses a bare axios call so it doesn't re-enter this interceptor.
async function refreshToken(token: string, tokenType: string): Promise<void> {
  const { data } = await axios.post(`${config.apiUrl}/auth/refresh`, null, {
    headers: { Authorization: `${tokenType} ${token}` },
  })
  setCookie('access_token', data.access_token, data.expires_in)
  setCookie('token_type', data.token_type, data.expires_in)
  setCookie('token_issued_at', String(Date.now()), data.expires_in)
}

http.interceptors.request.use(async req => {
  // Matches are locked per device, not per user
  req.headers['X-Client-ID'] = getOrCreateClientId()
  let token = getCookie('access_token')
  const tokenType = getCookie('token_type') ?? 'Bearer'
  if (token) {
    const issuedAt = parseInt(getCookie('token_issued_at') ?? '', 10)
    if (!isNaN(issuedAt) && Date.now() - issuedAt > REFRESH_AFTER_MS) {
      refreshPromise ??= refreshToken(token, tokenType).finally(() => { refreshPromise = null })
      // If the refresh fails, continue with the current (still valid) token
      await refreshPromise.catch(() => {})
      token = getCookie('access_token') ?? token
    }
    req.headers.Authorization = `${getCookie('token_type') ?? tokenType} ${token}`
  }
  return req
})

export interface SwissStanding {
  player: string
  points: number
  rounds_won: number
  highest_round: number
  matches_played: number
}

export interface ApiEvent {
  event_id: string
  event_name: string
  players: string[]
  late_players: string[]
  source?: 'manual' | 'checkfront'
  checkfront_booking_code?: string | null
  swiss_matches_per_player: number
  swiss_rounds_per_match: number
  swiss_generated_at: string | null
  swiss_standings: SwissStanding[] | null
  standings_generated_at: string | null
  bracket_rounds_per_match: number
  bracket_generated_at: string | null
  is_finished: boolean
}

export interface ApiMatch {
  match_id: string
  event_id: string | null
  player_1_id: string | null
  player_2_id: string | null
  sequence: number
  match_type: 'swiss' | 'bracket'
  rounds_per_match: number
  bracket_round: number | null
  bracket_slot: number | null
  winner_id: string | null
  is_locked: boolean
  locked_by: string | null
  is_finished: boolean
}

export interface ApiRound {
  round_id: string
  match_id: string
  player_1_id: string
  player_2_id: string
  sequence: number
}

export async function login(username: string, password: string): Promise<{ access_token: string; token_type: string; expires_in: number }> {
  const credentials = btoa(`${username}:${password}`)
  const { data } = await http.post('/auth/login', { credentials })
  return data
}

// --- Events ---------------------------------------------------------------

export async function getEvents(): Promise<ApiEvent[]> {
  const { data } = await http.get('/event')
  return data
}

export async function getEvent(eventId: string): Promise<ApiEvent> {
  const { data } = await http.get(`/event/${eventId}`)
  return data
}

export async function createEvent(name: string, players: string[]): Promise<void> {
  await http.post('/event', { event_name: name, players })
}

export async function finishEvent(eventId: string): Promise<ApiEvent> {
  const { data } = await http.post(`/event/${eventId}/finish`)
  return data
}

export async function addPlayer(eventId: string, playerName: string): Promise<ApiEvent> {
  const { data } = await http.post(`/event/${eventId}/player`, { player_name: playerName })
  return data
}

export async function removePlayer(eventId: string, playerName: string): Promise<ApiEvent> {
  const { data } = await http.delete(`/event/${eventId}/player/${encodeURIComponent(playerName)}`)
  return data
}

export async function setPlayerLate(eventId: string, playerName: string, late: boolean): Promise<ApiEvent> {
  const { data } = await http.put(`/event/${eventId}/player/${encodeURIComponent(playerName)}/late`, { late })
  return data
}

export async function updateSwissConfig(eventId: string, matchesPerPlayer: number, roundsPerMatch: number): Promise<ApiEvent> {
  const { data } = await http.put(`/event/${eventId}/swiss-config`, {
    swiss_matches_per_player: matchesPerPlayer,
    swiss_rounds_per_match: roundsPerMatch,
  })
  return data
}

export async function generateSwissMatches(eventId: string): Promise<ApiMatch[]> {
  const { data } = await http.post(`/event/${eventId}/swiss/generate`)
  return data
}

export async function generateSwissScores(eventId: string): Promise<SwissStanding[]> {
  const { data } = await http.post(`/event/${eventId}/swiss/scores`)
  return data
}

export async function getStandings(eventId: string): Promise<SwissStanding[]> {
  const { data } = await http.get(`/event/${eventId}/standings`)
  return data
}

export async function generateBracket(eventId: string, roundsPerMatch: number): Promise<ApiMatch[]> {
  const { data } = await http.post(`/event/${eventId}/bracket/generate`, { rounds_per_match: roundsPerMatch })
  return data
}

export async function getBracket(eventId: string): Promise<ApiMatch[]> {
  const { data } = await http.get(`/event/${eventId}/bracket`)
  return data
}

// --- Matches ----------------------------------------------------------------

export async function getMatchesByEvent(eventId: string): Promise<ApiMatch[]> {
  const { data } = await http.get(`/match/event/${eventId}`)
  return data
}

export async function lockMatch(matchId: string, force = false): Promise<ApiMatch> {
  const { data } = await http.post(`/match/${matchId}/lock`, null, { params: force ? { force: true } : {} })
  return data
}

export async function unlockMatch(matchId: string): Promise<ApiMatch> {
  const { data } = await http.post(`/match/${matchId}/unlock`)
  return data
}

export async function finishMatch(matchId: string): Promise<ApiMatch> {
  const { data } = await http.post(`/match/${matchId}/finish`)
  return data
}

export async function reopenMatch(matchId: string): Promise<ApiMatch> {
  const { data } = await http.post(`/match/${matchId}/reopen`)
  return data
}

export async function updateMatchRounds(matchId: string, roundsPerMatch: number): Promise<ApiMatch> {
  const { data } = await http.patch(`/match/${matchId}/rounds`, { rounds_per_match: roundsPerMatch })
  return data
}

// --- Rounds & throws --------------------------------------------------------

export async function startRound(matchId: string, player1Id: string, player2Id: string, sequence: number): Promise<ApiRound> {
  const { data } = await http.post('/round', {
    match_id: matchId,
    player_1_id: player1Id,
    player_2_id: player2Id,
    sequence,
  })
  return data
}

export async function getRoundsByMatch(matchId: string): Promise<ApiRound[]> {
  const { data } = await http.get(`/round/match/${matchId}`)
  return data
}

export async function submitThrow(input: {
  playerId: string
  roundId: string
  matchId: string
  eventId?: string | null
  points: number
  isDrop?: boolean
  clutchCalled?: boolean
}): Promise<string> {
  const { data } = await http.post('/throw/submit', {
    player_id: input.playerId,
    round_id: input.roundId,
    match_id: input.matchId,
    event_id: input.eventId ?? null,
    points: input.points,
    is_drop: input.isDrop ?? false,
    clutch_called: input.clutchCalled ?? false,
  })
  return data.throw_id
}

export interface ApiThrow {
  throw_id: string
  timestamp: string
  player_id: string
  round_id: string
  match_id: string
  points: number
  is_drop: boolean
}

export async function getThrows(criteria: { matchId?: string; roundId?: string; eventId?: string }): Promise<ApiThrow[]> {
  const { data } = await http.get('/throw/search', {
    params: {
      match_id: criteria.matchId,
      round_id: criteria.roundId,
      event_id: criteria.eventId,
    },
  })
  return data
}

export async function deleteThrow(throwId: string): Promise<void> {
  await http.delete(`/throw/${throwId}`)
}
