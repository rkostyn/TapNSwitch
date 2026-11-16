// Match locks are per device (client id), not per user. EventDetail takes the
// lock when a coach opens a match; the scoreboard releases it when they leave.

import { lockMatch, unlockMatch, errorDetail, errorStatus, type ApiMatch, type MatchLockedDetail } from './api'

export type LockResult =
  | { status: 'locked'; match: ApiMatch }
  /** Another device holds the match; `force` takes it over. */
  | { status: 'held'; lockedBy: string }

/** Lock a match for this device. Failures other than "held elsewhere" (423) throw. */
export async function lockForScoring(matchId: string, force: boolean): Promise<LockResult> {
  try {
    return { status: 'locked', match: await lockMatch(matchId, force) }
  } catch (e) {
    if (errorStatus(e) !== 423) throw e
    // Expected: another device holds the lock, so the caller offers a takeover
    const detail = errorDetail(e) as MatchLockedDetail | string | undefined
    const lockedBy = typeof detail === 'object' ? detail.locked_by : undefined
    return { status: 'held', lockedBy: lockedBy ?? 'another coach' }
  }
}

/** Release this device's lock. Never throws; leaving a match must not be blocked by it. */
export async function releaseMatch(matchId: string): Promise<void> {
  try {
    await unlockMatch(matchId)
  } catch (e) {
    // 403 is expected: this device no longer holds the lock (already released,
    // or another device took the match over), so there is nothing to release.
    if (errorStatus(e) === 403) return
    console.error(`Failed to release the lock on match ${matchId}`, e)
  }
}

/** Who holds a lock, for the "In use by …" labels. */
export function holderLabel(lockedBy: string | null, clientId: string): string {
  if (!lockedBy) return ''
  return lockedBy === clientId ? 'this device' : `device ${lockedBy.slice(0, 8)}`
}
