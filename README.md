# Soccer Bet Scout

Men's European club ratings and match breakdowns. One Elo pool covers the top leagues and is tied together by Champions League, Europa League, and Conference League matches. Each upcoming match gets a score grid: win, draw, loss, expected goals, both teams to score, clean sheets, totals, and a short written report.

The site reads files that a scheduled job builds ahead of time. Opening a page does not call football-data.org or The Odds API.

This is a research tool. It does not place bets, and it does not promise an edge.

## What you can run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional keys, see below

python -m src.cli build       # download history, write data/artifacts
python -m src.cli rankings    # Europe club Elo
python -m src.cli rankings --league E0
python -m src.cli rankings --tournament UCL
python -m src.cli slate       # upcoming matches, America/Chicago kickoffs
python -m src.cli match "Arsenal" "Everton"
python -m src.cli team "Arsenal"
python -m src.cli clubelo          # rank check vs clubelo.com, target Spearman above 0.9
python -m pytest -q
```

`build` is safe to re-run. Past seasons are cached on disk under `data/cache/` (gitignored). The current season expires after 12 hours. football-data.org calls, when a key is present, wait 6.5 seconds between requests so the free tier stays under 10 per minute.

The files in `data/artifacts/` are a snapshot from 20 Oct 2026 (21,946 played matches, 394 clubs, 191 upcoming). Top of the pool:

```
  #      Elo  League                  Club
    1   1838.5  La Liga                 FC Barcelona
    2   1830.2  Premier League          Arsenal FC
    3   1795.6  Bundesliga              FC Bayern München
    4   1769.6  La Liga                 Real Madrid CF
    5   1768.0  Premier League          Manchester City FC
    6   1753.2  Ligue 1                 Paris Saint-Germain FC
    7   1706.8  La Liga                 Club Atlético de Madrid
    8   1704.0  Premier League          Liverpool FC
```

`python -m src.cli match "Arsenal" "Everton"` on that snapshot:

```
  Arsenal FC  vs  Everton FC
  Premier League  ·  Sat, Oct 24, 2026, 9:00 AM CDT
  Win %     Arsenal FC                    56.4%
  Draw                                    27.0%
  Win %     Everton FC                    16.5%
  xG        1.62  –  0.77     1H  0.75  –  0.33
  Over 2.5   42.6%     BTTS   44.2%
  Elo       1830  –  1636   gap +194

  First half
    xG  0.75  –  0.33
    W/D/L   41.4 /  44.4 /  14.2
    BTTS  15.9%    Over 0.5  65.5%    Over 1.5  30.5%

  Most likely
    Everton FC under 4.5                          99.9%
    Everton FC under 3.5                          99.2%
    Arsenal FC under 4.5                          97.7%
    Everton FC under 2.5                          95.7%
    Arsenal FC +1.5                               94.8%
```

Kickoffs are America/Chicago. 24 Oct 2026 is still on daylight time; the Premier League source clock is 15:00 BST.

## How a match is scored

**Attack and defense.** Each club's recent matches are time-decayed (half-life about 140 days, window of 18 months) and adjusted for the opponent: a goal against a strong defense counts for more. When a file includes `HxG` / `AxG`, those values are blended with the actual goals (65% xG, 35% goals). A short sample is shrunk toward average. After the fit, each league's scoring baseline is rescaled so the matches in that window predict the goals that were actually scored. An attack above 1.00 creates more than a typical side. A defense above 1.00 allows more.

**Elo.** The result that moves a rating is a win, draw, or loss (1 / 0.5 / 0). A margin multiplier still makes a 4-0 move more than a 1-0, and xG is blended in when the file has it. The multiplier is not applied on top of a second goal-difference curve. Home teams get 80 Elo points of advantage, except in a one-off final, and that same 80 is added back into the goal model for non-neutral matches. Opening ratings in 2021-22 follow the UEFA association coefficients from the end of 2020/21, centered on 1500, so England starts above Greece. Clubs that only appear in Europe are seeded 175 points below the covered-league average and regress there between seasons. A club inside a domestic league regresses a third of the way back to its league mean. A club entering a league takes the average rating of the clubs that left. Domestic leagues in the pool: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Belgian Pro League, Super Lig, Greek Super League, Scottish Premiership, and the Austrian Bundesliga.

**Score grid.** The two expected-goal figures become a Dixon-Coles grid from 0-0 through 6-6. The low-score correction (rho = -0.10) raises the chance of 0-0 and 1-1 versus two independent Poissons. The grid is scaled so the cells sum to 1. First-half xG is each team's fitted share of its full-match figure, taken from historical half-time scores in that league and shrunk toward the league when the club has a long enough sample. A league needs 40 matches and 80 goals before its share is used. Cups and thin leagues use the average of the fitted leagues, or 45% when none qualify. Shares stay between 30% and 62%. The second half is the remaining xG on its own grid. The two halves are independent given that split; they are not a correlated two-half state model.

**Report.** The card shows win percentages, xG, over/under, team totals, both teams to score, clean sheets, and the five most likely scorelines. It also shows the first-half and second-half grids (xG, result, both teams to score, over 0.5 and 1.5, and the top scorelines) and a Most likely panel. That panel ranks both-teams-to-score, match and team totals, double chance, handicap spreads, and the result / total / both-teams combinations by model probability. The slate shows the top three of that list. The note covers form and the chance trend, a goals-minus-xG regression flag, attack against the opponent's defense, rest and a European travel week, and a projected game script. Kickoffs are printed in `America/Chicago`. Each league filter shows the date of the last result on file. Form and rest are withheld when that file, or one club's own results, stop more than 14 days behind the match.

Logged slate probabilities are kept the first time they are written. A rebuild inside the 24 hours before kickoff stores one refresh beside that first call, and settlement scores the refresh. The same log stores the new market probabilities on the call that will be scored. Settlement skips an integer handicap push and skips a half market when the half-time score is missing. The calibration report bins home, draw, and away, plus both teams to score, over 2.5, first-half both teams to score, and first-half over 0.5.

## Environment variables

Copy `.env.example` to `.env`. Never commit `.env` or a real key.

| Name | Required | Used for |
| --- | --- | --- |
| `FOOTBALL_DATA_API_KEY` | No | Current-season UEFA results and UTC kickoffs from football-data.org. `FOOTBALL_DATA_KEY` is still accepted as a legacy alias. |
| `ODDS_API_KEY` | No | Kickoff timestamps from The Odds API. Prices are not stored. |
| `CRON_SECRET` | No | Vercel sends this to `/api/cron/refresh`. The route only reports when the artifacts were built. |

Without those keys the model still runs on football-data.co.uk and openfootball. The free football-data.org plan may also refuse Europa League or Conference League; those competitions still load from openfootball text files through 2025-26.

## Web app

The Next.js app is the repository root, which is what Vercel detects.

- `/` Europe club Elo, with filters for all Europe, each league, and UCL / Europa / Conference
- `/teams/[id]` rating history
- `/matches` upcoming slate
- `/matches/[id]` the breakdown card

```bash
npm install
npm run dev     # http://localhost:3000
npm run build
```

### Deploy on Vercel

Do not create the project from here. In the Vercel dashboard, import this GitHub repo. The framework preset is Next.js. Root directory stays the repo root. No API keys are required on Vercel for pages to render, because the pages only read `data/artifacts`.

Optional: if you turn on Vercel Cron, set `CRON_SECRET` in the project environment. The daily cron calls `GET /api/cron/refresh` and returns the artifact timestamp. It does not download match data.

The rebuild itself is `.github/workflows/refresh-artifacts.yml` (11:00 UTC, or run it by hand). Add repository secrets `FOOTBALL_DATA_API_KEY` and `ODDS_API_KEY` if you want the live UEFA sync and bookmaker kickoff times. The action commits updated JSON to `main`, and Vercel redeploys from that commit.

## Tests

```bash
python -m pytest -q
```

Covered: the score grid sums to 1, the Dixon-Coles factors for 0-0, 1-0, 0-1, and 1-1, opponent-adjusted league totals within 0.15 goals, Elo replay determinism and promotion inheritance, UEFA league seeds, Chicago daylight and standard time, Central European cup kickoffs, club-name aliases, the men's-competition guard, stale form notes, and prediction settlement including the day-before refresh.

## Data sources

- [football-data.co.uk](https://www.football-data.co.uk/) league CSVs, including xG columns when the file has them
- [openfootball](https://github.com/openfootball) league JSON and Champions League / Europa / Conference text
- [football-data.org](https://www.football-data.org/) for the current UEFA season when a key is set
- [The Odds API](https://the-odds-api.com/) for kickoff times only
- [clubelo.com](http://clubelo.com/) as a rank-order check, not as an input to the model

## Known limitations

- Absolute Elo points will not match ClubElo. The check is whether the ordering of top clubs agrees (target Spearman above 0.9). Scales differ because this pool is seeded in 2021 from UEFA coefficients. The 20 Oct 2026 build could not fetch `http://api.clubelo.com/2026-10-20` (HTTP 502), so `meta.json` records `clubelo.available: false`. Re-run `python -m src.cli clubelo` when that API answers.
- football-data.co.uk clocks are UK local time. openfootball league files use each country's local time. UEFA text files use Central European time (a 21:00 slot is 19:00 UTC in summer). The Odds API overrides those with a real UTC timestamp when `ODDS_API_KEY` is set. This snapshot was built without that key.
- This snapshot loaded the 2026-27 Champions League (144 matches) and the current La Liga season (88 played out of 380) from football-data.org. The Champions League filter is the live season. Europa League returned 403 on this plan, and Conference League is not in the competition list, so those two filters still read "2025-26 entrants".
- football-data.co.uk's 2026-27 CSVs still lag some leagues. La Liga on this snapshot is through 19 Oct 2026, filled from football-data.org. Premier League, Serie A, Ligue 1, and the other CSV leagues are still through 11 or 12 Oct 2026. Austria is through 2 Nov 2025.
- The prediction log on this snapshot has 143 pending matches and 0 settled, so Brier and the home, draw, and away bins are empty until a later `build` sees final scores. None of those matches were inside 24 hours of kickoff at build time, so no refresh row is stored yet.
- Team names are matched through a canonical alias list. A club spelled in a new way can show up twice until the alias is added.
- The goals-minus-xG flag only appears for matches whose source file contains xG.
- Men's competitions only. Player goals, assists, lineups, and injuries are not in this model.

## Next phases

- Backtest the score grid and Elo against settled seasons, beyond the live Brier log.
- Lineups and injuries.
- A player goal and assist model.

## Older code

`legacy/polymarket/` is the old paper-trading simulator. `legacy/signal_scores/` is the old 0-100 hand-weighted bet scorer. Neither is imported by the CLI or the site.
