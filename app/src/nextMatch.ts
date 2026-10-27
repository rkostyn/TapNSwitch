export function nextUpMatch<T extends {
  match_id: string
  player_1_id?: string | null
  player_2_id?: string | null
  is_finished?: boolean
  sequence?: number
}>(matches: T[], currentMatchId?: string | null): T | null {
  const upcoming = matches.filter(match =>
    !match.is_finished
    && match.match_id !== currentMatchId
    && match.player_1_id
    && match.player_2_id
  )
  upcoming.sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))
  return upcoming[0] ?? null
}
