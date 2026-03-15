# ⚽ Soccer Bet Scout

A data-driven soccer betting analysis tool that combines bookmaker consensus odds, real team statistics, and H2H history to surface high-confidence bet signals across top European leagues.

Built in Python. No BS, no black box — every signal comes with full reasoning.

---

## What It Does

Runs two analysis modes:

**1. Full Scout (`scorer.py`)** — scans all upcoming games across supported leagues and ranks them by bet signal strength across 4 bet types.

**2. Pick Analyzer (`pick_analyzer.py`)** — you give it your specific picks and it gives you a deep breakdown with a plain-English confidence rating: `STRONG / GOOD / LEAN / SKIP`.

---

## Bet Types Scored

| Bet | What it looks for |
|-----|-------------------|
| **Away Win** | Strong away form, weak home team, favorable H2H |
| **Away -1.5** | Dominant away team, high scoring rate, leaky home defense |
| **Win + Over 2.5** | High-scoring environment, both teams concede freely |
| **Win + BTTS** | Competitive game, both teams score regularly, low clean sheet rate |

---

## Data Sources

| Source | What we use it for | Cost |
|--------|-------------------|------|
| [football-data.org](https://www.football-data.org/) | Standings, form, match history, H2H | Free |
| [The Odds API](https://the-odds-api.com/) | Bookmaker consensus probabilities | Free tier (500 req/mo) |

---

## Supported Leagues

- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League
- 🇪🇸 La Liga
- 🇮🇹 Serie A
- 🇩🇪 Bundesliga
- 🇫🇷 Ligue 1
- 🇵🇹 Primeira Liga
- 🇳🇱 Eredivisie
- 🏆 UEFA Champions League
- 🏆 UEFA Europa League

---

## Project Structure

```
polymarket-bot/
├── src/
│   ├── data/
│   │   ├── market_reader.py     # Fetches Polymarket market data
│   │   ├── parser.py            # Parses raw market JSON
│   │   ├── odds_data.py         # Bookmaker consensus via The Odds API
│   │   ├── football_stats.py    # Team profiles, form, H2H via football-data.org
│   │   └── team_aliases.py      # Canonical team name matching (130+ teams)
│   ├── strategy/
│   │   ├── scorer.py            # Full game scanner — all upcoming games
│   │   ├── bet_profiler.py      # Scores each game across 4 bet types
│   │   └── pick_analyzer.py     # Deep analysis on your specific picks
│   └── simulator/
│       └── simulator.py         # Paper trading engine
├── logs/
│   └── cache/                   # API response cache (1hr TTL)
├── .env                         # API keys (never committed)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourusername/polymarket-bot.git
cd polymarket-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get API keys

| Key | Where to get it |
|-----|----------------|
| `FOOTBALL_DATA_KEY` | [football-data.org/client/register](https://www.football-data.org/client/register) — free, no card |
| `ODDS_API_KEY` | [the-odds-api.com](https://the-odds-api.com/) — free tier, 500 req/month |

### 3. Add keys to `.env`

```bash
FOOTBALL_DATA_KEY=your_key_here
ODDS_API_KEY=your_key_here
```

---

## Usage

### Scan all upcoming games

```bash
python3 -m src.strategy.scorer
```

Fetches all upcoming games in supported leagues, pulls real team stats, and prints every game ranked by strongest bet signal.

> ⚠️ First run takes ~10-15 minutes due to the football-data.org free tier rate limit (10 req/min). All responses are cached for 1 hour — subsequent runs are instant.

### Analyze your specific picks

Edit `MY_PICKS` at the top of `pick_analyzer.py`:

```python
MY_PICKS = [
    ("Arsenal",       "Everton",          "soccer_epl",              "home_win"),
    ("Lyon",          "Le Havre",         "soccer_france_ligue_one", "away_win"),
    ("Inter Milan",   "Atalanta BC",      "soccer_italy_serie_a",    "home_btts"),
    ("Borussia Dortmund", "Augsburg",     "soccer_germany_bundesliga","home_over25"),
]
```

Then run:

```bash
python3 -m src.strategy.pick_analyzer
```

You'll get a full breakdown per pick including form, goals/game, H2H, bet model score, and a plain-English confidence verdict.

---

## How the Scoring Works

### Team Profile (per team, last 10 games)
- Overall form score (W=3pts, D=1pt, L=0pts normalized to 0-100)
- Home-specific and away-specific form scores
- Goals scored/conceded per game (overall, home, away)
- Clean sheet rate
- BTTS rate

### H2H (time-weighted)
Recent meetings count more than old ones:
- Last 1 year → weight 1.0
- 1-2 years → weight 0.7
- 2-3 years → weight 0.4
- 3+ years → weight 0.2

### Win Probability
Combined from standings (35%), form (40%), H2H (25%) with a +5% home advantage boost.

### Bet Signal Score (0-100)
Each bet type has its own weighted formula:

| Bet | Key factors |
|-----|-------------|
| Away Win | Away form 40% + home team weakness 30% + H2H 15% + stats 15% |
| Away -1.5 | Away scoring rate 35% + home defensive weakness 35% + away form 20% + H2H 10% |
| Win + Over 2.5 | Goals environment 40% + stronger team form 30% + H2H avg goals 20% + no clean sheets 10% |
| Win + BTTS | Both teams BTTS rate 40% + no clean sheets 30% + H2H BTTS 20% + competitiveness 10% |

---

## Confidence Ratings

| Rating | Meaning |
|--------|---------|
| 🔥 STRONG | Bet model + stats + H2H all align |
| ✅ GOOD | Two of three factors support the pick |
| ⚠️ LEAN | One factor supports it, use caution |
| ❌ SKIP | Model disagrees or no data available |

---

## Rate Limiting

football-data.org free tier: **10 requests/minute**

The bot enforces a 6.5s delay between every API call. All responses are cached locally for 1 hour so you only hit the API on the first run of the day.

If you're running the full scanner frequently, consider upgrading to a paid football-data.org plan to remove the rate limit.

---

## Requirements

```
requests
python-dotenv
pytz
```

Install with:
```bash
pip install -r requirements.txt
```

---

## Roadmap

- [ ] Injury data layer (requires paid API-Football plan)
- [ ] Starting lineup detection (squad rotation before CL/EL)
- [ ] Live trading execution via Polymarket CLOB API
- [ ] Signal logging and outcome tracking for edge validation
- [ ] Parlay builder — combines highest-confidence picks into slips

---

## Disclaimer

This tool is for **research and educational purposes only**. It does not guarantee betting outcomes. Always gamble responsibly and within your means.

---