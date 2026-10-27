export interface TvThrow {
  value: number
  drop?: boolean
}

export interface TvRoundRow {
  round: number
  t1: number | null
  t2: number | null
  status: string
}

export interface TvSnapshot {
  player1Name: string
  player2Name: string
  leftName: string
  rightName: string
  leftScores: Array<TvThrow | null>
  rightScores: Array<TvThrow | null>
  totalRounds: number
  displayRound: number
  roundRows: TvRoundRow[]
  eventName: string
  arenaLabel: string
  gameWinner: string | null
  showTiebreak: boolean
  nextMatch: { player1: string; player2: string } | null
  updatedAt: number
}

const STORAGE_KEY = 'tapnswitch.tvSnapshot'
const CHANNEL_NAME = 'tapnswitch-tv'

const channel = typeof BroadcastChannel !== 'undefined'
  ? new BroadcastChannel(CHANNEL_NAME)
  : null

export function publishTvSnapshot(snapshot: Omit<TvSnapshot, 'updatedAt'>): void {
  const payload: TvSnapshot = { ...snapshot, updatedAt: Date.now() }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Private mode or full storage — live channel still works
  }
  channel?.postMessage(payload)
}

export function readStoredTvSnapshot(): TvSnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) as TvSnapshot : null
  } catch {
    return null
  }
}

export function subscribeTvSnapshot(onChange: (snapshot: TvSnapshot | null) => void): () => void {
  onChange(readStoredTvSnapshot())

  const onMessage = (event: MessageEvent<TvSnapshot>) => onChange(event.data)
  channel?.addEventListener('message', onMessage)

  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return
    onChange(event.newValue ? JSON.parse(event.newValue) as TvSnapshot : null)
  }
  window.addEventListener('storage', onStorage)

  return () => {
    channel?.removeEventListener('message', onMessage)
    window.removeEventListener('storage', onStorage)
  }
}
