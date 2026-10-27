# Tournaments

This is a copy of the current TapNSwitch app, set aside for **tournament.ratscores.com**.

The repo root (`../app`, `../api`) stays as **standard scoring**: Checkfront groups, Baltimore lanes, everyday play.

This folder is where tournament work goes:

- Load a bracket from AxeScores or an Urban bracket
- Assign players from that bracket onto Baltimore lanes
- Score tournament matches on those lanes

Same starting code as the lane-aware app (6 arenas × 2 lanes). From here the two apps can diverge.

## Local ports (so both apps can run)

| | Standard scoring | Tournaments |
|---|---|---|
| Frontend | 5173 / 8000 | 5174 / 8010 |
| API | 8001 | 8002 |
