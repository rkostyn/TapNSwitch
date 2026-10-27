<script setup>
  import { ref, onMounted, onUnmounted } from 'vue'
  import { getLaneBoard, getMatchesByEvent, getRoundsByMatch, getThrows } from '../api'
  import { GHOST_DISPLAY_NAME, GHOST_PLAYER_ID } from '../config'
  import { arenaById, arenaLabel as formatArenas } from '../venue'
  import { subscribeTvSnapshot } from '../displaySync'

  const props = defineProps({
    arenaId: { type: String, default: null },
  })

  const snapshot = ref(null)
  const waitingNote = ref('')
  let stopFollow = null
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
      snapshot.value = snapshotFromMatch(live, arena.group, rounds, throws)
      waitingNote.value = ''
    } catch {
      waitingNote.value = waitingNote.value || 'Could not load this lane'
    }
  }

  function snapshotFromMatch(match, group, rounds, throws) {
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
      updatedAt: Date.now(),
    }
  }

  function enterFullscreen() {
    const root = document.documentElement
    if (!document.fullscreenElement && root.requestFullscreen) {
      root.requestFullscreen().catch(() => {})
    }
  }

  onMounted(() => {
    if (props.arenaId) {
      loadArenaMatch()
      pollTimer = setInterval(loadArenaMatch, 2000)
    } else {
      stopFollow = subscribeTvSnapshot(next => {
        snapshot.value = next
        waitingNote.value = next ? '' : 'Waiting for a match from the scoring iPad'
      })
    }
  })

  onUnmounted(() => {
    stopFollow?.()
    if (pollTimer) clearInterval(pollTimer)
  })
</script>

<template>
  <div class="tv" @dblclick="enterFullscreen">
    <template v-if="snapshot">
      <header class="tv-top">
        <p v-if="snapshot.eventName || snapshot.arenaLabel" class="tv-meta">
          <span v-if="snapshot.eventName">{{ snapshot.eventName }}</span>
          <span v-if="snapshot.arenaLabel"> · {{ snapshot.arenaLabel }}</span>
        </p>
        <h1 class="tv-round">
          {{ snapshot.showTiebreak ? 'Tie breaker' : `Round ${snapshot.displayRound} of ${snapshot.totalRounds}` }}
        </h1>
      </header>

      <div class="tv-match">
        <section class="tv-side">
          <h2 class="tv-name">{{ snapshot.leftName }}</h2>
          <ol class="tv-throws">
            <li v-for="(score, i) in snapshot.leftScores" :key="`l-${i}`" :class="{ empty: !score }">
              <template v-if="score">{{ score.value }}<sup v-if="score.drop">d</sup></template>
              <template v-else>—</template>
            </li>
          </ol>
          <p class="tv-total">{{ throwTotal(snapshot.leftScores) }}</p>
        </section>

        <section class="tv-side tv-side-right">
          <h2 class="tv-name">{{ snapshot.rightName }}</h2>
          <ol class="tv-throws">
            <li v-for="(score, i) in snapshot.rightScores" :key="`r-${i}`" :class="{ empty: !score }">
              <template v-if="score">{{ score.value }}<sup v-if="score.drop">d</sup></template>
              <template v-else>—</template>
            </li>
          </ol>
          <p class="tv-total">{{ throwTotal(snapshot.rightScores) }}</p>
        </section>
      </div>

      <table class="tv-rounds">
        <thead>
          <tr>
            <th></th>
            <th v-for="row in snapshot.roundRows" :key="row.round">R{{ row.round }}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>{{ snapshot.player1Name }}</th>
            <td
              v-for="row in snapshot.roundRows"
              :key="`p1-${row.round}`"
              :class="{ win: row.status === 'p1' }"
            >{{ row.t1 ?? '–' }}</td>
          </tr>
          <tr>
            <th>{{ snapshot.player2Name }}</th>
            <td
              v-for="row in snapshot.roundRows"
              :key="`p2-${row.round}`"
              :class="{ win: row.status === 'p2' }"
            >{{ row.t2 ?? '–' }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="snapshot.gameWinner" class="tv-winner">{{ snapshot.gameWinner }} wins</p>
    </template>

    <p v-else class="tv-wait">{{ waitingNote || 'Waiting for a match' }}</p>
  </div>
</template>

<style scoped>
.tv {
  min-height: 100vh;
  padding: clamp(16px, 4vw, 40px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(16px, 3vh, 32px);
  background: #07080c;
  color: #f8fafc;
}

.tv-top {
  text-align: center;
}

.tv-meta {
  margin: 0 0 6px;
  font-size: clamp(0.85rem, 2vw, 1.2rem);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
}

.tv-round {
  margin: 0;
  font-size: clamp(1.6rem, 4vw, 3rem);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #a78bfa;
}

.tv-match {
  width: min(1200px, 100%);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(24px, 6vw, 80px);
}

.tv-name {
  margin: 0 0 12px;
  font-size: clamp(1.8rem, 5vw, 3.4rem);
  line-height: 1.1;
}

.tv-side-right {
  text-align: right;
}

.tv-throws {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tv-throws li {
  font-size: clamp(1.8rem, 5vw, 3.2rem);
  font-weight: bold;
}

.tv-throws li.empty {
  color: #334155;
}

.tv-total {
  margin: 12px 0 0;
  font-size: clamp(2.2rem, 6vw, 4rem);
  font-weight: bold;
  color: #34d399;
  border-top: 3px solid #34d399;
  padding-top: 8px;
}

.tv-rounds {
  border-collapse: collapse;
  font-size: clamp(1rem, 2.4vw, 1.6rem);
}

.tv-rounds th,
.tv-rounds td {
  padding: 8px 22px;
  text-align: center;
}

.tv-rounds thead th {
  color: #a78bfa;
  border-bottom: 2px solid #7c3aed;
}

.tv-rounds tbody th {
  text-align: left;
  color: #e2e8f0;
}

.tv-rounds td.win {
  color: #6ee7b7;
  background: #064e3b;
}

.tv-winner {
  margin: 0;
  font-size: clamp(1.4rem, 3vw, 2.2rem);
  font-weight: bold;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #34d399;
}

.tv-wait {
  margin: 0;
  font-size: clamp(1.4rem, 3vw, 2.2rem);
  color: #64748b;
  text-align: center;
}
</style>
