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
python -m pytest -q
```

`build` is safe to re-run. Past seasons are cached on disk under `data/cache/` (gitignored). The current season expires after 12 hours. football-data.org calls, when a key is present, wait 6.5 seconds between requests so the free tier stays under 10 per minute.

The files in `data/artifacts/` are a snapshot from 20 Oct 2026 (21,900 played matches, 395 clubs, 143 upcoming). Top of the pool:

```
  #      Elo  League                  Club
    1   1711.9  Bundesliga              FC Bayern München
    2   1697.8  La Liga                 FC Barcelona
    3   1675.6  Premier League          Arsenal FC
    4   1662.2  Ligue 1                 Paris Saint-Germain FC
    5   1660.0  Premier League          Manchester City FC
    6   1649.6  Serie A                 FC Internazionale Milano
    7   1641.7  Eredivisie              PSV Eindhoven
    8   1640.5  La Liga                 Real Madrid CF
```

`python -m src.cli match "Arsenal" "Everton"` on that snapshot:

```
  Arsenal FC  vs  Everton FC
  Premier League  ·  Sat, Oct 24, 2026, 9:00 AM CDT
  Win %     Arsenal FC                    51.4%
  Draw                                    28.1%
  Win %     Everton FC                    20.4%
  xG        1.54  –  0.88     1H  0.69  –  0.40
  Over 2.5   43.6%     BTTS   47.3%
  Elo       1676  –  1559   gap +116
```

Kickoffs are America/Chicago. 24 Oct 2026 is still on daylight time; the London source clock is 15:00 BST.

## How a match is scored

**Attack and defense.** Each club's recent matches are time-decayed (half-life about 140 days, window of 18 months). Goals scored and conceded are compared with that league's home and away scoring rate. When a file includes `HxG` / `AxG`, those values are blended with the actual goals (65% xG, 35% goals). A short sample is shrunk toward average.

**Elo.** Every club in 2021-22 starts at 1500 in one pool. After each match the rating moves by a margin multiplier, and by a blend of the goal difference and xG when xG exists. Home teams get 80 Elo points of advantage, except in a one-off final. Between seasons, each rating moves a third of the way back to its league mean. A club entering a league takes the average rating of the clubs that left, so promoted sides start at the level of the sides they replace. Domestic leagues in the pool: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Belgian Pro League, Super Lig, Greek Super League, Scottish Premiership, and the Austrian Bundesliga.

**Score grid.** The two expected-goal figures become a Dixon-Coles grid from 0-0 through 6-6. The low-score correction (rho = -0.10) raises the chance of 0-0 and 1-1 versus two independent Poissons. The grid is scaled so the cells sum to 1. First-half xG is 45% of the full-match figure. That is a split, not a separate half model.

**Report.** The card shows win percentages, xG, over/under, team totals, both teams to score, clean sheets, and the five most likely scorelines. The note covers form and the chance trend, a goals-minus-xG regression flag, attack against the opponent's defense, rest and a European travel week, and a projected game script. Kickoffs are printed in `America/Chicago`.

Logged slate probabilities are kept the first time they are written. Later builds settle them when the result is in `data/artifacts` and report a multiclass Brier score plus home-win calibration bins.

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

Covered: the score grid sums to 1, the Dixon-Coles factors for 0-0, 1-0, 0-1, and 1-1, Elo replay determinism and promotion inheritance, Chicago daylight and standard time, club-name aliases, and prediction settlement.

## Data sources

- [football-data.co.uk](https://www.football-data.co.uk/) league CSVs, including xG columns when the file has them
- [openfootball](https://github.com/openfootball) league JSON and Champions League / Europa / Conference text
- [football-data.org](https://www.football-data.org/) for the current UEFA season when a key is set
- [The Odds API](https://the-odds-api.com/) for kickoff times only
- [clubelo.com](http://clubelo.com/) as a rank-order check, not as an input to the model

## Known limitations

- Absolute Elo points will not match ClubElo. The check is whether the ordering of top clubs agrees. Scales differ because this pool is seeded in 2021. The 20 Oct 2026 build could not fetch `http://api.clubelo.com/2026-10-20` (HTTP 502; HTTPS timed out), so `meta.json` records `clubelo.available: false` and there is no Spearman figure for this snapshot.
- Kickoff clocks from football-data.co.uk and openfootball are treated as `Europe/London`, then shown in Chicago. The Odds API overrides that with a real UTC timestamp when `ODDS_API_KEY` is set. This snapshot was built without that key.
- 2026-27 European cup matches are missing from the openfootball text archive until that repo publishes them, unless `FOOTBALL_DATA_API_KEY` is set. Tournament filters on this snapshot therefore use the 2025-26 campaigns. This environment did not have the key.
- football-data.co.uk's 2026-27 CSVs lag the calendar. La Liga results in the file used here stop in mid-September, so a rest note can say a club last played weeks ago when later matches have simply not been published in that CSV yet.
- The prediction log on this snapshot has 143 pending matches and 0 settled, so Brier and calibration are empty until a later `build` sees final scores.
- Team names are matched through a canonical alias list. A club spelled in a new way can show up twice until the alias is added.
- The goals-minus-xG flag only appears for matches whose source file contains xG.
- Men's competitions only. Player goals, assists, lineups, and injuries are not in this model.

## Next phases

- Backtest the score grid and Elo against settled seasons, beyond the live Brier log.
- Lineups and injuries.
- A player goal and assist model.

## Older code

`legacy/polymarket/` is the old paper-trading simulator. `legacy/signal_scores/` is the old 0-100 hand-weighted bet scorer. Neither is imported by the CLI or the site.
