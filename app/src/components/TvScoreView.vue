<script setup>
  import { ref, onMounted, onUnmounted } from 'vue'
  import ScoreVisual from './ScoreVisual.vue'
  import { getLaneBoard, getMatchesByEvent, getRoundsByMatch, getThrows, getTvSnapshot } from '../api'
  import { GHOST_DISPLAY_NAME, GHOST_PLAYER_ID } from '../config'
  import { arenaById, arenaLabel as formatArenas } from '../venue'
  import { nextUpMatch } from '../nextMatch'

  const props = defineProps({
    arenaId: { type: String, default: null },
  })

  const snapshot = ref(null)
  const waitingNote = ref('')
  let pollTimer = null

  const nameOf = id => (id === GHOST_PLAYER_ID ? GHOST_DISPLAY_NAME : id)

  function throwTotal(scores) {
    return (scores ?? []).reduce((sum, item) => sum + (item ? item.value : 0), 0)
  }

  async function loadArenaMatch() {
    const arenaId = props.arenaId
    if (!arenaId) return
    try {
      const board = await getLaneBoard()
      const arena = board.arenas.find(item => item.arena_id === arenaId)
      if (!arena?.group) {
        snapshot.value = null
        waitingNote.value = `${arenaById(arenaId)?.name ?? arenaId} is open`
        return
      }
      const matches = await getMatchesByEvent(arena.group.event_id)
      const live = matches.find(match => match.is_locked && !match.is_finished)
        ?? matches.find(match => !match.is_finished)
      if (!live?.player_1_id || !live?.player_2_id) {
        snapshot.value = null
        waitingNote.value = `${arena.group.event_name} · waiting for a match`
        return
      }
      const [rounds, throws] = await Promise.all([
        getRoundsByMatch(live.match_id),
        getThrows({ matchId: live.match_id }),
      ])
      snapshot.value = snapshotFromMatch(live, arena.group, rounds, throws, matches)
      waitingNote.value = ''
    } catch {
      waitingNote.value = waitingNote.value || 'Could not load this lane'
    }
  }

  function snapshotFromMatch(match, group, rounds, throws, matches) {
    const byRoundId = Object.fromEntries(rounds.map(round => [round.round_id, round.sequence]))
    const bySeq = {}
    for (const item of throws) {
      const seq = byRoundId[item.round_id]
      if (!seq) continue
      const bucket = bySeq[seq] ?? { s1: [], s2: [] }
      const side = item.player_id === match.player_1_id ? bucket.s1 : bucket.s2
      side.push({ value: item.points, drop: !!item.is_drop })
      bySeq[seq] = bucket
    }
    const totalRounds = match.rounds_per_match
    const currentRound = Math.min(
      Math.max(...Object.keys(bySeq).map(Number), 1),
      totalRounds,
    )
    const live = bySeq[currentRound] ?? { s1: [], s2: [] }
    const pad = arr => Array.from({ length: 5 }, (_, i) => arr[i] ?? null)
    const swapped = (currentRound - 1) % 2 === 1
    const p1 = nameOf(match.player_1_id)
    const p2 = nameOf(match.player_2_id)
    const leftScores = swapped ? pad(live.s2) : pad(live.s1)
    const rightScores = swapped ? pad(live.s1) : pad(live.s2)
    const roundRows = Array.from({ length: totalRounds }, (_, i) => {
      const seq = i + 1
      const row = bySeq[seq]
      if (!row) return { round: seq, t1: null, t2: null, status: 'pending' }
      const t1 = throwTotal(row.s1)
      const t2 = throwTotal(row.s2)
      return { round: seq, t1, t2, status: t1 > t2 ? 'p1' : t2 > t1 ? 'p2' : 'in-progress' }
    })
    return {
      player1Name: p1,
      player2Name: p2,
      leftName: swapped ? p2 : p1,
      rightName: swapped ? p1 : p2,
      leftScores,
      rightScores,
      totalRounds,
      displayRound: currentRound,
      roundRows,
      eventName: group.event_name ?? '',
      arenaLabel: formatArenas(group.arena_ids),
      gameWinner: match.winner_id ? nameOf(match.winner_id) : null,
      showTiebreak: false,
      nextMatch: (() => {
        const finished = Object.values(bySeq).filter(row =>
          (row.s1?.length ?? 0) >= 5 && (row.s2?.length ?? 0) >= 5
        ).length
        if (finished < 2) return null
        const upcoming = nextUpMatch(matches, match.match_id)
        return upcoming
          ? { player1: nameOf(upcoming.player_1_id), player2: nameOf(upcoming.player_2_id) }
          : null
      })(),
      updatedAt: Date.now(),
    }
  }

  function enterFullscreen() {
    const root = document.documentElement
    if (!document.fullscreenElement && root.requestFullscreen) {
      root.requestFullscreen().catch(() => {})
    }
  }

  async function loadSnapshot() {
    try {
      const live = await getTvSnapshot()
      if (live) {
        snapshot.value = live
        waitingNote.value = ''
        return
      }
    } catch {
      // Fall through to the lane poll when the TV has no snapshot yet
    }
    if (props.arenaId) {
      await loadArenaMatch()
      return
    }
    snapshot.value = null
    waitingNote.value = 'Waiting for a match from the scoring iPad'
  }

  onMounted(() => {
    loadSnapshot()
    pollTimer = setInterval(loadSnapshot, 1000)
  })

  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
  })
</script>

<template>
  <div class="tv" @dblclick="enterFullscreen">
    <template v-if="snapshot">
      <p v-if="snapshot.eventName || snapshot.arenaLabel" class="tv-meta">
        <span v-if="snapshot.eventName">{{ snapshot.eventName }}</span>
        <span v-if="snapshot.arenaLabel"> · {{ snapshot.arenaLabel }}</span>
      </p>
      <ScoreVisual
        :leftName="snapshot.leftName"
        :rightName="snapshot.rightName"
        :player1Name="snapshot.player1Name"
        :player2Name="snapshot.player2Name"
        :leftScores="snapshot.leftScores"
        :rightScores="snapshot.rightScores"
        :displayRound="snapshot.displayRound"
        :totalRounds="snapshot.totalRounds"
        :showTiebreak="snapshot.showTiebreak"
        :roundRows="snapshot.roundRows"
      />
      <p v-if="snapshot.gameWinner" class="tv-winner">{{ snapshot.gameWinner }} wins</p>
      <p v-if="snapshot.nextMatch" class="tv-next">
        Next match is {{ snapshot.nextMatch.player1 }} and {{ snapshot.nextMatch.player2 }}
      </p>
    </template>

    <p v-else class="tv-wait">{{ waitingNote || 'Waiting for a match' }}</p>
  </div>
</template>

<style scoped>
.tv {
  min-height: 100vh;
  padding: 24px 16px 40px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0b0d12;
  color: #e2e8f0;
}

.tv-meta {
  margin: 0 0 8px;
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #34d399;
}

.tv-winner {
  margin: 20px 0 0;
  font-size: 1.1rem;
  font-weight: bold;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #34d399;
}

.tv-next {
  margin: 12px 0 0;
  font-size: 1rem;
  color: #e2e8f0;
}

.tv-wait {
  margin: 0;
  font-size: 1.2rem;
  color: #64748b;
  text-align: center;
}
</style>
