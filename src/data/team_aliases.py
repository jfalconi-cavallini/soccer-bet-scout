"""
team_aliases.py

A lookup table mapping team name variations to a canonical form.

Why we need this:
  - Bookmakers write "Manchester City"
  - Polymarket writes "Manchester City FC"
  - They're the same team but string matching fails

  - Worse: "Manchester City" and "Manchester United" both contain
    "manchester" so word-level matching confuses them

The solution: map every known variation to one clean canonical name,
then match canonicals against each other. Exact match only.
"""

# Keys   = any variation we might see in the wild (lowercase)
# Values = our canonical name (what we use internally)

TEAM_ALIASES: dict[str, str] = {

    # --- Premier League ---
    "arsenal":                    "arsenal",
    "arsenal fc":                 "arsenal",

    "everton":                    "everton",
    "everton fc":                 "everton",

    "manchester city":            "manchester_city",
    "manchester city fc":         "manchester_city",
    "man city":                   "manchester_city",

    "manchester united":          "manchester_united",
    "manchester united fc":       "manchester_united",
    "man united":                 "manchester_united",
    "man utd":                    "manchester_united",

    "chelsea":                    "chelsea",
    "chelsea fc":                 "chelsea",

    "newcastle united":           "newcastle",
    "newcastle united fc":        "newcastle",
    "newcastle":                  "newcastle",

    "west ham united":            "west_ham",
    "west ham united fc":         "west_ham",
    "west ham":                   "west_ham",

    "tottenham hotspur":          "tottenham",
    "tottenham hotspur fc":       "tottenham",
    "spurs":                      "tottenham",
    "tottenham":                  "tottenham",

    "liverpool":                  "liverpool",
    "liverpool fc":               "liverpool",

    "aston villa":                "aston_villa",
    "aston villa fc":             "aston_villa",

    "brighton":                   "brighton",
    "brighton & hove albion":     "brighton",
    "brighton and hove albion":   "brighton",
    "brighton hove albion":       "brighton",

    "brentford":                  "brentford",
    "brentford fc":               "brentford",

    "fulham":                     "fulham",
    "fulham fc":                  "fulham",

    "wolverhampton wanderers":    "wolves",
    "wolves":                     "wolves",

    "crystal palace":             "crystal_palace",
    "crystal palace fc":          "crystal_palace",

    "bournemouth":                "bournemouth",
    "afc bournemouth":            "bournemouth",

    "nottingham forest":          "nottm_forest",
    "nottingham forest fc":       "nottm_forest",

    "leicester city":             "leicester",
    "leicester city fc":          "leicester",
    "leicester":                  "leicester",

    "ipswich town":               "ipswich",
    "ipswich":                    "ipswich",

    "burnley":                    "burnley",
    "burnley fc":                 "burnley",

    "sunderland":                 "sunderland",
    "sunderland afc":             "sunderland",

    # --- La Liga ---
    "real madrid":                "real_madrid",
    "real madrid cf":             "real_madrid",

    "barcelona":                  "barcelona",
    "fc barcelona":               "barcelona",

    "atletico madrid":            "atletico_madrid",
    "atlético madrid":            "atletico_madrid",
    "atletico de madrid":         "atletico_madrid",

    "sevilla":                    "sevilla",
    "sevilla fc":                 "sevilla",

    "real sociedad":              "real_sociedad",
    "real betis":                 "real_betis",
    "villarreal":                 "villarreal",
    "villarreal cf":              "villarreal",
    "athletic bilbao":            "athletic_bilbao",
    "athletic club":              "athletic_bilbao",
    "valencia":                   "valencia",
    "valencia cf":                "valencia",
    "osasuna":                    "osasuna",
    "girona":                     "girona",
    "girona fc":                  "girona",

    # --- Serie A ---
    "juventus":                   "juventus",
    "ac milan":                   "ac_milan",
    "milan":                      "ac_milan",
    "inter milan":                "inter_milan",
    "inter":                      "inter_milan",
    "internazionale":             "inter_milan",
    "as roma":                    "roma",
    "roma":                       "roma",
    "ssc napoli":                 "napoli",
    "napoli":                     "napoli",
    "lazio":                      "lazio",
    "ss lazio":                   "lazio",
    "atalanta":                   "atalanta",
    "fiorentina":                 "fiorentina",
    "acf fiorentina":             "fiorentina",
    "torino":                     "torino",
    "torino fc":                  "torino",
    "parma":                      "parma",
    "parma calcio":               "parma",
    "como":                       "como",
    "como 1907":                  "como",

    # --- Bundesliga ---
    "bayern munich":              "bayern",
    "fc bayern munich":           "bayern",
    "fc bayern münchen":          "bayern",
    "borussia dortmund":          "dortmund",
    "bayer leverkusen":           "leverkusen",
    "rb leipzig":                 "leipzig",
    "eintracht frankfurt":        "frankfurt",
    "vfb stuttgart":              "stuttgart",
    "borussia mönchengladbach":   "gladbach",
    "hamburger sv":               "hamburger_sv",
    "1. fc köln":                 "koln",
    "fc köln":                    "koln",

    # --- Ligue 1 ---
    "paris saint-germain":        "psg",
    "paris saint germain":        "psg",
    "psg":                        "psg",
    "olympique marseille":        "marseille",
    "marseille":                  "marseille",
    "olympique lyonnais":         "lyon",
    "lyon":                       "lyon",
    "as monaco":                  "monaco",
    "monaco":                     "monaco",
    "lille":                      "lille",
    "losc lille":                 "lille",
    "rennes":                     "rennes",
    "stade rennais":              "rennes",
    "nice":                       "nice",
    "ogc nice":                   "nice",
    "angers":                     "angers",
    "angers sco":                 "angers",

    # --- Bundesliga (additional) ---
    "1. fc heidenheim":           "heidenheim",
    "fc heidenheim":              "heidenheim",
    "heidenheim":                 "heidenheim",
    "augsburg":                   "augsburg",
    "fc augsburg":                "augsburg",
    "sc freiburg":                "freiburg",
    "freiburg":                   "freiburg",
    "fsv mainz 05":               "mainz",
    "mainz 05":                   "mainz",
    "mainz":                      "mainz",
    "tsg hoffenheim":             "hoffenheim",
    "hoffenheim":                 "hoffenheim",
    "vfl wolfsburg":              "wolfsburg",
    "wolfsburg":                  "wolfsburg",
    "werder bremen":              "werder_bremen",
    "sv werder bremen":           "werder_bremen",
    "union berlin":               "union_berlin",
    "1. fc union berlin":         "union_berlin",
    "borussia monchengladbach":   "gladbach",
    "fc st. pauli":               "st_pauli",
    "st. pauli":                  "st_pauli",

    # --- Ligue 1 (additional) ---
    "auxerre":                    "auxerre",
    "aj auxerre":                 "auxerre",
    "brest":                      "brest",
    "stade brestois":             "brest",
    "le havre":                   "le_havre",
    "le havre ac":                "le_havre",
    "lorient":                    "lorient",
    "fc lorient":                 "lorient",
    "metz":                       "metz",
    "fc metz":                    "metz",
    "nantes":                     "nantes",
    "fc nantes":                  "nantes",
    "paris fc":                   "paris_fc",
    "rc lens":                    "lens",
    "lens":                       "lens",
    "strasbourg":                 "strasbourg",
    "rc strasbourg":              "strasbourg",
    "toulouse":                   "toulouse",
    "toulouse fc":                "toulouse",

    # --- Serie A (additional) ---
    "atalanta bc":                "atalanta",
    "bologna":                    "bologna",
    "bologna fc":                 "bologna",
    "cagliari":                   "cagliari",
    "cagliari calcio":            "cagliari",
    "cremonese":                  "cremonese",
    "us cremonese":               "cremonese",
    "genoa":                      "genoa",
    "genoa cfc":                  "genoa",
    "hellas verona":              "verona",
    "verona":                     "verona",
    "lecce":                      "lecce",
    "us lecce":                   "lecce",
    "pisa":                       "pisa",
    "ac pisa":                    "pisa",
    "sassuolo":                   "sassuolo",
    "us sassuolo":                "sassuolo",
    "udinese":                    "udinese",
    "udinese calcio":             "udinese",

    # --- La Liga (additional) ---
    "alavés":                     "alaves",
    "deportivo alaves":           "alaves",
    "alaves":                     "alaves",
    "ca osasuna":                 "osasuna",
    "celta vigo":                 "celta_vigo",
    "rc celta":                   "celta_vigo",
    "elche cf":                   "elche",
    "elche":                      "elche",
    "espanyol":                   "espanyol",
    "rcd espanyol":               "espanyol",
    "getafe":                     "getafe",
    "getafe cf":                  "getafe",
    "levante":                    "levante",
    "levante ud":                 "levante",
    "mallorca":                   "mallorca",
    "rcd mallorca":               "mallorca",
    "oviedo":                     "oviedo",
    "real oviedo":                "oviedo",
    "rayo vallecano":             "rayo_vallecano",

    # --- Eredivisie (Netherlands) ---
    "ajax":                       "ajax",
    "afc ajax":                   "ajax",
    "az alkmaar":                 "az_alkmaar",
    "az":                         "az_alkmaar",
    "excelsior":                  "excelsior",
    "sbv excelsior":              "excelsior",
    "fc twente enschede":         "twente",
    "fc twente":                  "twente",
    "twente":                     "twente",
    "fc utrecht":                 "utrecht",
    "utrecht":                    "utrecht",
    "fc volendam":                "volendam",
    "volendam":                   "volendam",
    "fc zwolle":                  "zwolle",
    "pec zwolle":                 "zwolle",
    "feyenoord":                  "feyenoord",
    "fortuna sittard":            "fortuna_sittard",
    "go ahead eagles":            "go_ahead_eagles",
    "groningen":                  "groningen",
    "fc groningen":               "groningen",
    "heerenveen":                 "heerenveen",
    "sc heerenveen":              "heerenveen",
    "heracles almelo":            "heracles",
    "heracles":                   "heracles",
    "nac breda":                  "nac_breda",
    "nac":                        "nac_breda",
    "nec nijmegen":               "nec",
    "nec":                        "nec",
    "psv eindhoven":              "psv",
    "psv":                        "psv",
    "sc telstar":                 "telstar",
    "telstar":                    "telstar",
    "sparta rotterdam":           "sparta_rotterdam",

    # --- Primeira Liga (Portugal) ---
    "avs futebol sad":            "avs",
    "alverca":                    "alverca",
    "arouca":                     "arouca",
    "fc arouca":                  "arouca",
    "benfica":                    "benfica",
    "sl benfica":                 "benfica",
    "cf estrela":                 "estrela",
    "estoril":                    "estoril",
    "estoril praia":              "estoril",
    "famalicão":                  "famalicao",
    "famalicao":                  "famalicao",
    "fc famalicao":               "famalicao",
    "fc midtjylland":             "midtjylland",
    "gil vicente":                "gil_vicente",
    "moreirense fc":              "moreirense",
    "nacional":                   "nacional",
    "cd nacional":                "nacional",
    "fc porto":                   "porto",
    "porto":                      "porto",
    "rio ave fc":                 "rio_ave",
    "rio ave":                    "rio_ave",
    "sc braga":                   "braga",
    "braga":                      "braga",
    "santa clara":                "santa_clara",
    "cd santa clara":             "santa_clara",
    "sporting lisbon":            "sporting_cp",
    "sporting cp":                "sporting_cp",
    "tondela":                    "tondela",
    "cd tondela":                 "tondela",
    "vitória sc":                 "vitoria_sc",
    "vitoria sc":                 "vitoria_sc",
    "vitoria de guimaraes":       "vitoria_sc",

    # --- Super Lig (Turkey) ---
    "alanyaspor":                 "alanyaspor",
    "antalyaspor":                "antalyaspor",
    "basaksehir":                 "basaksehir",
    "istanbul basaksehir":        "basaksehir",
    "besiktas jk":                "besiktas",
    "besiktas":                   "besiktas",
    "eyüpspor":                   "eyupspor",
    "eyupspor":                   "eyupspor",
    "fatih karagümrük":           "karagumruk",
    "fatih karagumruk":           "karagumruk",
    "fenerbahce":                 "fenerbahce",
    "fenerbahçe":                 "fenerbahce",
    "galatasaray":                "galatasaray",
    "gazişehir gaziantep":        "gaziantep",
    "gaziantep":                  "gaziantep",
    "genclerbirligi sk":          "genclerbirligi",
    "genclerbirligi":             "genclerbirligi",
    "goztepe":                    "goztepe",
    "kasimpasa sk":               "kasimpasa",
    "kasimpasa":                  "kasimpasa",
    "kayserispor":                "kayserispor",
    "kocaelispor":                "kocaelispor",
    "samsunspor":                 "samsunspor",
    "torku konyaspor":            "konyaspor",
    "konyaspor":                  "konyaspor",
    "trabzonspor":                "trabzonspor",
    "çaykur rizespor":            "rizespor",
    "caykur rizespor":            "rizespor",
    "rizespor":                   "rizespor",

    # --- MLS ---
    "atlanta united fc":          "atlanta_united",
    "atlanta united":             "atlanta_united",
    "austin fc":                  "austin_fc",
    "cf montreal":                "montreal",
    "charlotte fc":               "charlotte_fc",
    "chicago fire":               "chicago_fire",
    "chicago fire fc":            "chicago_fire",
    "colorado rapids":            "colorado_rapids",
    "columbus crew sc":           "columbus_crew",
    "columbus crew":              "columbus_crew",
    "d.c. united":                "dc_united",
    "dc united":                  "dc_united",
    "fc cincinnati":              "fc_cincinnati",
    "fc dallas":                  "fc_dallas",
    "houston dynamo":             "houston_dynamo",
    "houston dynamo fc":          "houston_dynamo",
    "inter miami cf":             "inter_miami",
    "inter miami":                "inter_miami",
    "la galaxy":                  "la_galaxy",
    "los angeles fc":             "lafc",
    "lafc":                       "lafc",
    "minnesota united fc":        "minnesota_united",
    "minnesota united":           "minnesota_united",
    "nashville sc":               "nashville_sc",
    "new england revolution":     "new_england_revolution",
    "new york city fc":           "nycfc",
    "nycfc":                      "nycfc",
    "new york red bulls":         "red_bulls",
    "ny red bulls":               "red_bulls",
    "orlando city sc":            "orlando_city",
    "orlando city":               "orlando_city",
    "philadelphia union":         "philadelphia_union",
    "portland timbers":           "portland_timbers",
    "real salt lake":             "real_salt_lake",
    "san diego fc":               "san_diego_fc",
    "san jose earthquakes":       "san_jose_earthquakes",
    "seattle sounders fc":        "seattle_sounders",
    "seattle sounders":           "seattle_sounders",
    "sporting kansas city":       "sporting_kc",
    "st. louis city sc":          "st_louis_city",
    "toronto fc":                 "toronto_fc",
    "vancouver whitecaps fc":     "vancouver_whitecaps",
    "vancouver whitecaps":        "vancouver_whitecaps",

    # --- European competitions (extra teams) ---
    "bodø/glimt":                 "bodo_glimt",
    "bodo/glimt":                 "bodo_glimt",
    "bodo glimt":                 "bodo_glimt",
    "ferencváros tc":             "ferencvaros",
    "ferencvaros":                "ferencvaros",
    "krc genk":                   "genk",
    "genk":                       "genk",
    "panathinaikos fc":           "panathinaikos",
    "panathinaikos":              "panathinaikos",
    "leeds united":               "leeds",
    "leeds united fc":            "leeds",

    # --- NBA ---
    "los angeles lakers":         "lakers",
    "lakers":                     "lakers",
    "boston celtics":             "celtics",
    "celtics":                    "celtics",
    "golden state warriors":      "warriors",
    "warriors":                   "warriors",
    "milwaukee bucks":            "bucks",
    "bucks":                      "bucks",
    "miami heat":                 "heat",
    "heat":                       "heat",
    "phoenix suns":               "suns",
    "suns":                       "suns",
    "denver nuggets":             "nuggets",
    "nuggets":                    "nuggets",
    "philadelphia 76ers":         "sixers",
    "76ers":                      "sixers",
    "new york knicks":            "knicks",
    "knicks":                     "knicks",
    "brooklyn nets":              "nets",
    "nets":                       "nets",
    "chicago bulls":              "bulls",
    "bulls":                      "bulls",
    "cleveland cavaliers":        "cavaliers",
    "cavaliers":                  "cavaliers",
    "atlanta hawks":              "hawks",
    "hawks":                      "hawks",
    "dallas mavericks":           "mavericks",
    "mavericks":                  "mavericks",
    "memphis grizzlies":          "grizzlies",
    "grizzlies":                  "grizzlies",
    "minnesota timberwolves":     "timberwolves",
    "timberwolves":               "timberwolves",
    "new orleans pelicans":       "pelicans",
    "pelicans":                   "pelicans",
    "oklahoma city thunder":      "thunder",
    "thunder":                    "thunder",
    "orlando magic":              "magic",
    "magic":                      "magic",
    "detroit pistons":            "pistons",
    "pistons":                    "pistons",
    "washington wizards":         "wizards",
    "wizards":                    "wizards",
    "sacramento kings":           "kings",
    "kings":                      "kings",
    "portland trail blazers":     "blazers",
    "blazers":                    "blazers",
    "toronto raptors":            "raptors",
    "raptors":                    "raptors",
    "indiana pacers":             "pacers",
    "pacers":                     "pacers",
    "charlotte hornets":          "hornets",
    "hornets":                    "hornets",
    "san antonio spurs":          "spurs_nba",
    "utah jazz":                  "jazz",
    "jazz":                       "jazz",
    "houston rockets":            "rockets",
    "rockets":                    "rockets",
    "los angeles clippers":       "clippers",
    "clippers":                   "clippers",
}


def canonicalize(name: str) -> str | None:
    """
    Convert a team name to its canonical form.

    Parameters:
        name (str): Any team name variation

    Returns:
        str: Canonical name if found, None if unknown
    """
    return TEAM_ALIASES.get(name.lower().strip())


def both_teams_canonical_match(
    home: str,
    away: str,
    question: str,
) -> tuple[bool, int]:
    """
    Check if both team canonicals appear in a Polymarket question.

    This is the correct way to match teams:
    1. Canonicalize both bookmaker team names
    2. For each word/phrase in the question, try to canonicalize it
    3. Check if both canonicals appear

    Parameters:
        home     : Home team from bookmakers
        away     : Away team from bookmakers  
        question : Polymarket question text

    Returns:
        tuple[bool, int]: (matched, confidence 0-100)
    """
    home_canon = canonicalize(home)
    away_canon = canonicalize(away)

    # If we don't recognize either team, we can't match reliably
    if not home_canon or not away_canon:
        return False, 0

    # Try to find canonical forms of teams mentioned in the question
    q_lower = question.lower()
    found_canonicals = set()

    for alias, canonical in TEAM_ALIASES.items():
        if alias in q_lower:
            found_canonicals.add(canonical)

    home_found = home_canon in found_canonicals
    away_found = away_canon in found_canonicals

    if home_found and away_found:
        return True, 100  # Perfect canonical match

    return False, 0