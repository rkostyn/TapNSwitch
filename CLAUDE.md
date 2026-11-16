# CLAUDE.md

Requirements notes for AI coding assistants working on this repo. One section per area.

## Global

This app should be written with IPad's in mind.
  - We also want to support desktop and phones just in case.

## Admin

When a user puts in the wrong password and the API returns a 401, notify them of the password being wrong.
When a user is successfully logged in, remove the login and register buttons and replace it with the users name.
When a user logs in their token is valid for a week.  
If a users token is older than 12 hours, refresh the token without prompting the user.
When a user is logged in, show the events button, allowing them to create events.
  - On the left of the username, and you show the client ID?
Any event, throw, match, game is only stored in mongodb for a year.  

## Events

As a user I want the ability to add player to an event. 
As a user I want to mark throwers as “late”, delaying the games until later.
As a user I want to Automatically building a swiss/round robin bracket for the throwers in that group:
  - Default style is round robin (everyone plays everyone once)
  - Staff can switch a group to Swiss if they want fewer matches per thrower
  - Ability to control how many rounds and how many matches for the group
  - Default should be 2 matches of 2 rounds per thrower
  - When a match is completed, move it to the bottom of the list, making it easier to know who is up next.
  - If player is late, shuffle their matches to the bottom but before the completed matches.
  - Ability to go back to previously played matches and rounds within those matches to adjust scoring
  - Users have a manual button to generate final swiss scores to allow the coach to go back and edit, if needed
  - Following the end of the swiss round, a screen should show all throwers with their scores, sorted by highest points. 
  - If tied in total points, use the following as tie breakers: 
    - First, the number of rounds won
    - Second, the person with the highest round takes it.
  - A manual button to generate the single elimination tournament bracket
  - Ability to edit the number of rounds in the tournament matches at the start…I’d recommend immediately after clicking to start the bracket. The default should be 3 rounds per match.
  - Ability to modify the number of rounds from 3 to 1…this will help if the coach is running low on time during the tournament. 
When the swiss stage is generated, collapse the player section.
Show a visual bracket after a swiss style tournament of the tournament…coaches will select matches from that visual bracket
  - This introduce a new tab, defaulting to the bracket. This gives users the ability to go back if needed.
  - If the bracket doesn't fill completely, because there isn't a perfect amount of players, the ones with the best standings get "by" matches, winning their first round.
If a match selected is already selected by a different coach/ipad, a notice should be provided with the option to override and take that match over
  - A match is locked by client_id not user in this case.
    - Any match in progress is assumed to be locked.  There is no need to tell what client_id has the lock. 
    - It is helpful to know if the device you are on has the lock.  ( I just don't need to know the UUID ).
If a user is playing an event match, when the match is complete show the events page instead of a new match.
As a user, I have a button to close an event. 
As a user, by default I don't see closed events.

Baltimore floor (keep this simple):
  - 6 colored arenas: red, green, blue, yellow, white, black
  - Each arena has 2 lanes, so 12 lanes and two people can throw at the same time
  - Checkfront bookings become groups. Staff put a group on one or more colors
  - Group size hints how many arenas they need: 1–6 → 1, 7–10 → 2, 11–20 → 3
  - If Checkfront's item name mentions a color, that color is suggested
  - Closing an event frees its colors so the next group can use them

For tournament events the default match style is Swiss (see Tournament below).

## Game

As a user, if I select a round, I can update the scores even if the match is finished.


A game of axes is considered a draw if there are equal rounds taken between players.  Ties do no count for either player.
If a game is tied, then there is a tie breaker. 
A tie breaker is a single throw for each side. If both sides get a bull, they can go for clutch.
In a tie breaker, if three clutches in a row are missed players must go back down to hit bulls.  If they both hit their bulls they can go up for clutch again.
In a tie breaker, this can use the same buttons.  It should also prevent the match from being finished.

## Tournament

A tournament is a type of event, chosen when the event is created (and changeable until matches are generated). It runs in the same app as everyday play.

Keep standard events as-is for everyday / Checkfront group play.
Tournament events are for tournament days.

As a coach I want to load a tournament bracket from AxeScores.
As a coach I want to load a tournament bracket from an Urban bracket.
As a coach I want Swiss generation to deal matches onto that group's lanes.
  - Default match style is Swiss (optional round robin)
  - Occupied colors expand to 2 lanes each (Red · Lane 1 / Red · Lane 2)
  - Generated matches rotate across those lanes
As a coach I want to assign players from that bracket onto Baltimore lanes.
  - 6 colored arenas: red, green, blue, yellow, white, black
  - Each arena has 2 lanes, so two people can throw at the same time
As a coach I want to score those tournament matches on the assigned lanes.
As a coach I want the floor view to show which bracket match is on which color.
