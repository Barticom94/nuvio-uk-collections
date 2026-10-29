"""Builds the Nuvio UK collections (import format as in mali-king/nuvio-collections).

  python build/build_uk.py [--key-json PATH] [F1_FILE]
      writes nuvio-collections.json (link A, every profile: Streaming Services, Movies, TV Shows, Anime, Live TV)
      and the art it points at (build/art.py); with F1_FILE, also the F1 Replays collection there (MediaFusion,
      Adam's profile only; the repo copy is nuvio-f1-replays.json)

The first four collections follow the home layout (Modern on Adam's TVs): each folder opens as a page of rows under
a hero, so every folder gets a TMDB backdrop for the hero (picked here, so the build needs the TMDB key the same way
check.py does), our title logo and, outside Streaming Services, our tile. Live TV stays a grid.
Movies and TV Shows reuse mali-king's pack at its v2 tag; Anime's decade rows come from AIOMetadata's Anime
Essentials pack at v3.8.3 and stay out unless MAL_FOLDERS is on (see there).
Both packs are fetched, so the build needs network.
Check the output with build/check.py before publishing.
"""
import json, os, re, sys, urllib.request, uuid
from datetime import date, timedelta

import art, check

NS = uuid.UUID('6f1c2a4e-0b7d-4c1e-9a55-3d2f7e8b9c10')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOISE_TV = "10763|10767|10766"  # News, Talk, Soap
FLOORS = {  # vote-count floors: the curated pack's tiers, plus originals (orig) and Original Films (films)
    "global": dict(pop_m=100, pop_t=50, top_m=1000, top_t=300, new_m=25, new_t=15, orig=20, films=50),
    "mid": dict(pop_m=30, pop_t=20, top_m=200, top_t=80, new_m=10, new_t=5, orig=10, films=50),
    "regional": dict(pop_m=10, pop_t=5, top_m=60, top_t=25, new_m=4, new_t=3, orig=3, films=10),
}
MK_TAG = "https://raw.githubusercontent.com/mali-king/nuvio-collections/v2/"
MK = MK_TAG + "covers/streaming-services/{}.webp"
COVER_BASE = os.environ.get("NUVIO_COVER_BASE", "https://raw.githubusercontent.com/Barticom94/nuvio-uk-collections/main/covers/")
def own(slug): return COVER_BASE + slug + ".webp"
def slug(text): return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", " and ").replace("+", " plus ").replace("'", "")).strip("-")
def tile_url(collection_slug, title): return f"{COVER_BASE}tiles/{collection_slug}-{slug(title)}.webp"
def logo_url(title): return f"{COVER_BASE}logos/{slug(title)}.png"  # one per name: Start here looks the same everywhere

# title, watch region, watch-provider ids (main service | its Amazon/Apple channels), floor tier,
# originals networks (pipe list, DISCOVER rows), originals since (streamers only), Original Films companies,
# movies, series, cover
SERVICES = [
    ("Netflix",     "GB", "8|1796",                 "global",   "213",                               "2012-01-01", None,             True,  True,  MK.format("netflix")),
    ("Prime Video", "GB", "9|2100",                 "global",   "1024",                              "2012-01-01", "20580|210099",   True,  True,  MK.format("prime-video")),
    ("Disney+",     "GB", "337",                    "global",   "2739|88",                           None,         "2|3|420|1|6125", True,  True,  MK.format("disney-plus")),  # FX streams in Disney+ here, old FX shows too
    ("Apple TV+",   "GB", "350|2243",               "mid",      "2552",                              "2012-01-01", "194232",         True,  True,  MK.format("apple-tv")),
    ("HBO Max",     "GB", "1899|1825",              "mid",      "49|3186|6783|8304",                 None,         "7429",           True,  True,  MK.format("hbo-max")),
    ("Hulu",        "US", "15",                     "mid",      "453",                               "2012-01-01", None,             False, False, MK.format("hulu")),  # no UK Hulu: originals only
    ("NOW",         "GB", "39|591",                 "mid",      "1063|214|5237|5213|4148|3653|7524", None,         "135346|181068|17685|117455", True,  True,  own("now")),
    ("Paramount+",  "GB", "531|2303|2304|582|1853", "mid",      "4330|6631",                         "2012-01-01", None,             True,  True,  MK.format("paramount-plus")),
    ("BBC iPlayer", "GB", "38",                     "mid",      "4|332|3|1155|9599|100",             None,         "288",            True,  True,  own("bbc-iplayer")),
    ("ITVX",        "GB", "41|2300|598",            "mid",      "9|5871|149|590|261|1159",           None,         None,             True,  True,  own("itvx")),
    ("Channel 4",   "GB", "103|2311",               "mid",      "26|136|1988",                       None,         "6705",           True,  True,  own("channel-4")),
    ("Channel 5",   "GB", "333",                    "mid",      "99",                                None,         None,             True,  True,  own("channel-5")),
    ("Crunchyroll", "GB", "283|1968",               "mid",      "1112",                              "2012-01-01", None,             True,  True,  MK.format("crunchyroll")),
    ("Shudder",     "GB", "99|204",                 "mid",      "2949",                              "2012-01-01", None,             True,  True,  MK.format("shudder")),
    ("MUBI",        "GB", "11|201",                 "mid",      None,                                None,         "204957|15838",   True,  False, MK.format("mubi")),
    ("Discovery+",  "GB", "524|584",                "regional", "4883",                              None,         None,             False, True,  own("discovery-plus")),
    ("WOW",         "GB", "546",                    "regional", "2806",                              None,         None,             False, True,  own("wow-presents-plus")),
]

# UK Extras' id, every profile: the public GitHub Pages install (free channels) or the household's UK TV Worker,
# which serves the same catalogues under the same id plus its own channels in each Live TV section
UKX = "com.barticom94.ukextras"
MEDIAFUSION = "stremio.addons.mediafusion|elfhostedtrb"  # Adam's profile only (F1 Replays, its own file)
NETFLIX_EXTRAS = [("series", "ukx.netflix-top10-shows"), ("movie", "ukx.netflix-top10-films"), ("movie", "ukx.netflix-popular")]

# AIOMetadata's configured manifest id is its package.json name (getManifest.ts: id = buildInfo.name; the
# configure app's FALLBACK_ADDON_ID and Nuvio's own tests use the same). The bare /manifest.json says
# com.aio.metadata, but that is the unconfigured stub nobody installs.
AIOM = "aio-metadata"
# A pack import adds these catalogues without a displayType, so the manifest ids stay unsuffixed. Editing one in
# AIOMetadata's catalogue dialog writes displayType and the manifest id becomes "<id>_anime": set "_anime" then.
AIOM_ID_SUFFIX = ""
AIOM_PACK = "https://raw.githubusercontent.com/cedya77/aiometadata/v3.8.3/public/featured/anime-essentials.json"
# On by Adam's call (29 Oct), before MAL safe mode (sfw) is confirmed on. With sfw off in the AIOMetadata config a
# profile uses, AIOMetadata doesn't ask Jikan to filter, so the decade rows can list Rx hentai. Both of Adam's
# configs had sfw false on 28 Oct. Set False and rebuild to take the Decades folder out again.
# The MAL genre catalogue can't come back as rows: its genres share one catalogue id, so in a page of rows they
# collapse into one (Nuvio keys a row by add-on, type and catalogue, not genre). Anime's genres are TMDB rows instead.
MAL_FOLDERS = True
# Anime keywords left out of every Anime row (TMDB keyword ids): hentai, hentai adaptation, ecchi, etchi, erotica,
# harem, reverse harem, nudity, sexual content, panty shot. TMDB's adult flag only covers outright porn, and link A
# reaches family profiles.
ANIME_SAFE = "198385|384581|195669|285672|325693|9194|238374|281741|329280|356895"

# mali-king v2 pack: entries left out of link A (US and Indian content)
MK_DROP_FOLDERS = {
    "Directors": {"S. S. Rajamouli", "Mani Ratnam", "Sanjay Leela Bhansali", "Rajkumar Hirani", "Anurag Kashyap",
                  "Zoya Akhtar", "Lokesh Kanagaraj", "Satyajit Ray"},
    "Studios": {"Yash Raj Films", "Dharma Productions", "Red Chillies", "Hombale Films", "Mythri Movie Makers"},
    "Networks": {"NBC", "ABC", "CBS", "FOX", "The CW"},  # US broadcast networks with no UK channel
}
# Franchises whose first film source is only part of them: the tab says what it holds.
FRANCHISE_TAB = {"Wizarding World": "Harry Potter", "Middle-earth": "The Lord of the Rings",
                 "Alien & Predator": "Alien", "Rocky & Creed": "Rocky", "The Conjuring Universe": "The Conjuring"}

FILMS_FLOOR = {"NOW": 20, "MUBI": 20}  # Sky and MUBI make few films; at 50 votes these rows drop under 20 titles
GB_STORES = "2|10|35|130|192"  # Apple TV Store, Amazon Video, Rakuten TV, Sky Store, YouTube (rent and buy)


def discover(title, media, sort, **filters):
    s = {"provider": "tmdb", "tmdbSourceType": "DISCOVER", "title": title, "mediaType": media}
    if sort: s["sortBy"] = sort
    s["filters"] = {k: v for k, v in filters.items() if v is not None}
    return s

def addon(addon_id, type_, catalog_id, genre=None):
    s = {"provider": "addon", "addonId": addon_id, "type": type_, "catalogId": catalog_id}
    if genre: s["genre"] = genre
    return s

def gb_pool(): return [p for s in SERVICES if s[1] == "GB" for p in s[2].split("|")]

def gb_exclusions(own_providers):
    mine = set(own_providers.split("|"))
    return "|".join(dict.fromkeys(p for p in gb_pool() if p not in mine))

def tile_sources(title, region, providers, floor, nets, since, films, movies, series):
    f = FLOORS[floor]
    out = []
    if nets:  # DISCOVER, not NETWORK: Nuvio's NETWORK rows ignore every network but the first
        orig = dict(withNetworks=nets, voteCountGte=f["orig"], withoutGenres=NOISE_TV, releaseDateGte=since)
        out.append(discover("Biggest Originals", "tv", "vote_count.desc", **orig))
        out.append(discover("Trending Originals", "tv", None, **orig))
    if title == "Netflix":
        out += [addon(UKX, t, c) for t, c in NETFLIX_EXTRAS]
    if films:
        out.append(discover("Original Films", "movie", None, withCompanies=films, voteCountGte=FILMS_FLOOR.get(title, f["films"])))
    if region != "GB":
        return out
    base = dict(withWatchProviders=providers, watchRegion=region)
    excl = dict(base, withoutWatchProviders=gb_exclusions(providers))
    if movies: out.append(discover(f"Only on {title}: Films", "movie", None, voteCountGte=f["pop_m"], **excl))
    if series: out.append(discover(f"Only on {title}: Series", "tv", None, voteCountGte=f["pop_t"], withoutGenres=NOISE_TV, **excl))
    if movies: out.append(discover(f"New on {title}: Films", "movie", "primary_release_date.desc", voteCountGte=f["new_m"], **base))
    if series: out.append(discover(f"New on {title}: Series", "tv", "first_air_date.desc", voteCountGte=f["new_t"], withoutGenres=NOISE_TV, **base))
    if movies: out.append(discover(f"Best only on {title}: Films", "movie", "vote_average.desc", voteCountGte=f["top_m"], **excl))
    if series: out.append(discover(f"Best only on {title}: Series", "tv", "vote_average.desc", voteCountGte=f["top_t"], withoutGenres=NOISE_TV, **excl))
    return out

def folder(folder_id, title, sources, cover=None, emoji=None, hide_title=False, logo=None):
    # heroBackdropUrl is set by heroes(); heroVideoUrl stays off (it would play on focus)
    return {
        "id": folder_id, "title": title, "coverImageUrl": cover,
        "focusGifUrl": None, "focusGifEnabled": False, "coverEmoji": emoji,
        "tileShape": "LANDSCAPE", "hideTitle": hide_title, "sources": sources,
        "heroBackdropUrl": None, "heroVideoUrl": None, "titleLogoUrl": logo,
    }

def collection(slug, title, folders, pin=False, view="ROWS", all_tab=True):
    return {"id": str(uuid.uuid5(NS, "collection:" + slug)), "title": title, "backdropImageUrl": None,
            "pinToTop": pin, "focusGlowEnabled": True, "viewMode": view, "showAllTab": all_tab, "folders": folders}

def fid(slug, title): return str(uuid.uuid5(NS, f"folder:{slug}:{title}"))

# FOLLOW_LAYOUT ("Follow home") opens a folder as a page of rows under a hero, one row per source. The All tab is
# off: with it on, Nuvio adds an All row and its "Load more" pages every row.
MODERN = dict(view="FOLLOW_LAYOUT", all_tab=False)


def streaming_services():
    folders = [folder(str(uuid.uuid5(NS, "folder:" + s[0])), s[0], tile_sources(*s[:9]), cover=s[9], hide_title=True,
                      logo=logo_url(s[0])) for s in SERVICES]
    # Not pinned: Nuvio puts pinned collections above every other home row, and this one sits third.
    return collection("streaming-services-uk", "Streaming Services", folders, **MODERN)

def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

# Nuvio only takes fixed release floors, so Trending is set at build time: rebuild every month or two.
def since(days): return (date.today() - timedelta(days=days)).isoformat()

def pack_tabs(mk, title, media, drop=frozenset()):
    """One source (one tab) per mali-king pack entry: the entry's first `media` row, named after the entry.
    Entries with identical rows share a tab (TMDB's TV genres pair up, such as Action and Adventure)."""
    entries = {f["title"]: f for f in mk[title]["folders"]}
    assert drop <= set(entries), f"pack changed in {title}"
    tabs, seen, skipped = [], {}, []
    for name, f in entries.items():
        if name in drop: continue
        s = next((s for s in f["sources"] if s["mediaType"] == media), None)
        if s is None:
            skipped.append(name)
            continue
        key = json.dumps({k: v for k, v in s.items() if k != "title"}, sort_keys=True)
        if key in seen:
            seen[key]["title"] += " & " + name
            continue
        seen[key] = dict(s, title=FRANCHISE_TAB.get(name, name))
        tabs.append(seen[key])
    if skipped: print(f"  {title}: no {media} row, left out: {', '.join(skipped)}")
    return tabs

def grid_collection(slug, title, spec):
    """spec: (folder title, emoji or cover URL, sources). Every folder opens as one grid per tab (a paged grid when
    it has one source), and the All tab is off: merging dozens of genres or channels into one grid helps nobody."""
    folders = [folder(fid(slug, t), t, s, **({"cover": c} if c.startswith("https://") else {"emoji": c}))
               for t, c, s in spec]
    return collection(slug, title, folders, view="TABBED_GRID", all_tab=False)

def modern_collection(slug_, title, spec):
    """spec: (folder title, sources[, hero sources]). Every folder gets our tile and title logo; hero sources stand
    in for rows heroes() can't read (add-on rows) when picking the folder's backdrop."""
    folders = []
    for t, sources, *hint in spec:
        f = folder(fid(slug_, t), t, sources, cover=tile_url(slug_, t), logo=logo_url(t))
        if hint: f["_hero"] = hint[0]
        folders.append(f)
    return collection(slug_, title, folders, **MODERN)

def split(tabs, groups):
    """groups: (folder title, tab titles). Every tab of a pack folder lands in exactly one of our folders, so a pack
    change shows up here instead of a tab going missing."""
    by = {t["title"]: t for t in tabs}
    names = [n for _, ns in groups for n in ns]
    assert sorted(names) == sorted(by), f"pack changed: {sorted(set(by) ^ set(names))}"
    return [(title, [by[n] for n in ns]) for title, ns in groups]

def movies(mk):
    m = "movie"
    gb_digital = "|".join(dict.fromkeys(gb_pool() + GB_STORES.split("|")))  # on a UK service or store = out digitally
    trending = discover("Trending films", m, None, voteCountGte=20, releaseDateGte=since(180))
    return modern_collection("movies", "Movies", [
        ("Start here", [discover("New films", m, "primary_release_date.desc", voteCountGte=25,
                                 withWatchProviders=gb_digital, watchRegion="GB"),
                        trending,
                        # No documentaries, concert films or TV films, as in the pack's Critics' Picks
                        discover("Top rated films", m, "vote_average.desc", voteCountGte=3000, withoutGenres="99|10402|10770"),
                        *pack_tabs(mk, "Critics' Picks", m)], [trending]),  # the hero from what's big now
        *split(pack_tabs(mk, "Genres", m), [
            ("Genres", ["Action", "Adventure", "Comedy", "Drama", "Thriller", "Crime", "Horror", "Sci-Fi", "Fantasy",
                        "Romance", "Mystery"]),
            ("More genres", ["Animation", "Family", "Kids", "Documentary", "History", "War", "Western", "Music"])]),
        ("Decades", pack_tabs(mk, "Decades", m)),
        *split(pack_tabs(mk, "Franchises & Universes", m), [
            ("Superhero and fantasy franchises", ["Marvel Cinematic Universe", "DC Universe", "Spider-Man", "X-Men",
                                                  "Harry Potter", "The Lord of the Rings", "Pirates of the Caribbean",
                                                  "The Hunger Games"]),
            ("Sci-fi and horror franchises", ["Star Wars", "Dune", "Avatar", "The Matrix", "Jurassic Park", "MonsterVerse",
                                              "Alien", "The Terminator", "Planet of the Apes", "Back to the Future",
                                              "Mad Max", "The Conjuring"]),
            ("Action and crime franchises", ["James Bond", "Mission: Impossible", "Fast & Furious", "John Wick", "Bourne",
                                             "Indiana Jones", "Rocky", "The Godfather"]),
            ("Family franchises", ["Toy Story", "Shrek", "Despicable Me", "How to Train Your Dragon", "Kung Fu Panda"])]),
        *split(pack_tabs(mk, "Moods & Themes", m), [
            ("Crime and suspense", ["Mind-Benders", "Heists", "Spies", "Serial Killers", "Whodunits", "Revenge",
                                    "Mafia & Gangsters", "Courtroom", "Political Thrillers", "Neo-Noir", "Survival"]),
            ("Action, sci-fi and monsters", ["Superheroes", "Martial Arts", "Space", "Time Travel", "Dystopia",
                                             "Cyberpunk & AI", "Isekai", "Video Game Adaptations", "Disaster", "Zombies",
                                             "Monsters & Kaiju", "Vampires"]),
            ("Feel-good and true stories", ["True Stories", "Coming of Age", "Sports", "Road Trips", "Musicals",
                                            "Feel-Good", "Christmas", "Dark Comedy", "Satire", "Stand-Up Comedy",
                                            "Nature & Wildlife"])]),
        *split(pack_tabs(mk, "Directors", m, MK_DROP_FOLDERS["Directors"]), [
            ("Directors", ["Christopher Nolan", "Denis Villeneuve", "Quentin Tarantino", "Martin Scorsese",
                           "Steven Spielberg", "David Fincher", "Stanley Kubrick", "Ridley Scott", "James Cameron",
                           "Wes Anderson", "Greta Gerwig", "Paul Thomas Anderson", "Jordan Peele", "Alfred Hitchcock"]),
            ("World directors", ["Bong Joon Ho", "Park Chan-wook", "Hayao Miyazaki", "Guillermo del Toro",
                                 "Akira Kurosawa", "Wong Kar-wai"])]),
        *split(pack_tabs(mk, "Studios", m, MK_DROP_FOLDERS["Studios"]), [
            ("Hollywood studios", ["Marvel Studios", "Lucasfilm", "Walt Disney Pictures", "DC", "Warner Bros.",
                                   "Universal", "Paramount", "20th Century", "Sony Pictures", "Legendary", "Amblin",
                                   "Lionsgate"]),
            ("Animation studios", ["Pixar", "Walt Disney Animation", "DreamWorks Animation", "Illumination",
                                   "Studio Ghibli", "LAIKA", "Aardman"]),
            ("Indie and world studios", ["A24", "NEON", "Blumhouse", "Searchlight", "Toho"])]),
        *split(pack_tabs(mk, "World Cinema", m), [
            ("Asian cinema", ["Korean", "Japanese", "Anime", "Chinese", "Thai", "Filipino"]),
            ("World cinema", ["British", "French", "Spanish", "Italian", "German", "Nordic", "Turkish",
                              "Latin American", "Arabic", "African"])]),
    ])

def tv_shows(mk):
    t = "tv"
    trending = discover("Trending series", t, None, voteCountGte=20, withoutGenres=NOISE_TV, releaseDateGte=since(730))
    return modern_collection("tv-shows", "TV Shows", [
        ("Start here", [discover("New series", t, "first_air_date.desc", voteCountGte=10, withoutGenres=NOISE_TV),
                        trending,
                        # 1500 votes keeps new hype shows off the top; keyword 210024 (anime) leaves anime to the Anime collection
                        discover("Top rated series", t, "vote_average.desc", voteCountGte=1500, withoutGenres=NOISE_TV,
                                 withoutKeywords="210024"),
                        # Two more so the page isn't three rows: British shows (no reality, 10764), and the most voted
                        # series of all time
                        discover("Trending British series", t, None, voteCountGte=10, withOriginCountry="GB",
                                 withoutGenres=NOISE_TV + "|10764", releaseDateGte=since(730)),
                        discover("Fan favourites", t, "vote_count.desc", withoutGenres=NOISE_TV, withoutKeywords="210024")],
         [trending]),
        ("Genres", pack_tabs(mk, "Genres", t)),
        ("Decades", pack_tabs(mk, "Decades", t)),
        *split(pack_tabs(mk, "Networks", t, MK_DROP_FOLDERS["Networks"]), [
            ("Drama networks", ["HBO", "FX", "AMC", "Showtime", "BBC", "Channel 4", "ITV", "tvN", "JTBC"]),
            ("Comedy, kids and factual networks", ["Comedy Central", "Adult Swim", "Cartoon Network", "Nickelodeon",
                                                   "Disney Channel", "National Geographic", "Discovery", "History"])]),
    ])

def anime(pack):
    """Japanese-language animation on Nuvio's own TMDB access, ANIME_SAFE left out of every row. Decades uses the MAL
    catalogues AIOMetadata adds when the Anime Essentials pack is imported (one catalogue id per decade)."""
    widgets = {w["title"]: w["dataSource"]["payload"]["items"] for w in pack["widgets"] if w["type"] == "collection.row"}
    decades = [i["dataSources"][0]["payload"]["aiometadata"]["catalog"]["id"] for i in widgets["Anime by Decade"]]
    assert decades == ["mal.80sDecade", "mal.90sDecade", "mal.00sDecade", "mal.10sDecade", "mal.20sDecade"], decades
    a = dict(withOriginalLanguage="ja", withoutKeywords=ANIME_SAFE)
    def row(title, media, genres="", **f):  # 20 votes keeps one-season obscurities out of the genre and theme rows
        return discover(title, media, None, voteCountGte=20, withGenres="16" + genres, **a, **f)
    def theme(title, keywords): return row(title, "tv", withKeywords=keywords)
    trending = discover("Trending series", "tv", None, voteCountGte=10, releaseDateGte=since(730), withGenres="16", **a)
    spec = [
        ("Start here", [discover("New series", "tv", "first_air_date.desc", voteCountGte=5, withGenres="16", **a),
                        discover("New films", "movie", "primary_release_date.desc", voteCountGte=10, withGenres="16", **a),
                        trending,
                        discover("Trending films", "movie", None, voteCountGte=10, releaseDateGte=since(730), withGenres="16", **a),
                        discover("Top rated series", "tv", "vote_average.desc", voteCountGte=500, withGenres="16", **a),
                        discover("Top rated films", "movie", "vote_average.desc", voteCountGte=500, withGenres="16", **a)],
         [trending]),
        # TMDB's TV genres: 10759 Action & Adventure, 35 Comedy, 18 Drama, 9648 Mystery, 10762 Kids. Romance is only a
        # film genre, so the series row uses its keyword (9840). Kids (10762) stays out of the broad rows, where
        # long-running children's shows would top them.
        ("Genres", [row("Action and adventure", "tv", ",10759", withoutGenres="10762"),
                    row("Comedy", "tv", ",35", withoutGenres="10762"),
                    row("Drama", "tv", ",18"),
                    row("Romance", "tv", withKeywords="9840"),
                    row("Mystery", "tv", ",9648"),
                    row("Kids", "tv", ",10762"),
                    row("Action films", "movie", ",28"),
                    row("Fantasy films", "movie", ",14"),
                    row("Family films", "movie", ",10751")]),
        # TMDB keyword ids, checked 29 Oct: isekai 237451, shounen 207826, mecha 10046 and giant robot 10891; sports
        # 6075, baseball 1480, volleyball 5605, basketball 6496, football 13042; high school 6270, school 10873,
        # school life 190116; slice of life 9914; iyashikei 291483; psychological 272553 and psychological thriller
        # 12565; magical girl 292887, magical girls 358020, magical girl ensemble 382274
        ("Themes", [theme("Isekai", "237451"), theme("Shounen", "207826"), theme("Mecha", "10046|10891"),
                    theme("Sports", "6075|1480|5605|6496|13042"), theme("School", "6270|10873|190116"),
                    theme("Slice of life", "9914"), theme("Iyashikei (healing)", "291483"),
                    theme("Psychological", "272553|12565"), theme("Magical girl", "292887|358020|382274")]),
    ]
    if MAL_FOLDERS:
        # newest first, as in Movies and TV Shows; the hero comes from TMDB's best loved anime before 2000
        spec.append(("Decades", [addon(AIOM, "anime", d + AIOM_ID_SUFFIX) for d in reversed(decades)],
                     [discover("", "tv", "vote_count.desc", withGenres="16", releaseDateLte="1999-12-31", **a)]))
    return modern_collection("anime", "Anime", spec)


# Hero backdrops: per folder, the first family-safe title (by rating) among each row's best known few (most votes on
# the row's first page: steadier than TMDB's daily popularity), with a backdrop that has no text on it (our logo goes
# over it), never one used twice in a collection.
HERO_DEPTH = 5    # best known titles tried per row
HERO_TRIES = 30   # titles looked up per folder at most
# The UK rating, else the US one. A folder's rows already show these titles' posters, so the hero only has to keep
# 18s out and horror out where it can; R and TV-MA (often 18 here) only when the most known titles have nothing else.
CERT_TIER = {**dict.fromkeys(["U", "PG", "12", "12A", "15", "G", "PG-13", "TV-Y", "TV-Y7", "TV-G", "TV-PG", "TV-14"], 0),
             **dict.fromkeys(["R", "TV-MA"], 1)}  # anything else (18, R18, NC-17) never; no rating at all is tier 2

def hero_pick(tmdb, sources, used, today):
    best, tried = None, 0
    for s in sources:
        p = check._source(s)
        if p is None or p["provider"] != "tmdb": continue
        media = "tv" if p["mediaType"] == "TV" or p["sourceType"] == "NETWORK" else "movie"
        _, items = check.resolve_raw(tmdb, p, today)
        items = sorted((r for r in items[:20] if r.get("backdrop_path") and not r.get("adult")),
                       key=lambda r: -(r.get("vote_count") or 0))[:HERO_DEPTH]
        for r in items:
            if (media, r["id"]) in used or tried >= HERO_TRIES: continue
            tried += 1
            d = tmdb.get(f"{media}/{r['id']}", {"append_to_response": "release_dates,content_ratings,images",
                                                 "include_image_language": "null"}) or {}
            ratings = {x["iso_3166_1"]: x.get("rating") for x in (d.get("content_ratings") or {}).get("results", [])}
            for x in (d.get("release_dates") or {}).get("results", []):
                ratings[x["iso_3166_1"]] = next((y["certification"] for y in x["release_dates"] if y["certification"]), None)
            cert = ratings.get("GB") or ratings.get("US")
            tier = CERT_TIER.get(cert, 2 if cert is None else None)
            if tier is None or d.get("adult"): continue
            if any(g["id"] == 27 for g in d.get("genres", [])): tier += 0.5  # horror only when the folder has nothing else
            plain = sorted((b for b in (d.get("images") or {}).get("backdrops", []) if b.get("width", 0) >= 1280),
                           key=lambda b: -(b.get("vote_average") or 0))
            if not plain: continue
            if best is None or tier < best[0]:
                best = (tier, (media, r["id"]), plain[0]["file_path"], d.get("title") or d.get("name"), cert)
            if tier == 0: return best
    return best

def heroes(cols, tmdb):
    today = date.today().isoformat()
    for c in cols:
        if c["viewMode"] != "FOLLOW_LAYOUT": continue
        used = set()
        for f in c["folders"]:
            pick = hero_pick(tmdb, f.pop("_hero", []) + f["sources"], used, today)
            if pick is None: raise SystemExit(f"no hero backdrop for {c['title']} / {f['title']}")
            _, key, path, name, cert = pick
            used.add(key)
            f["heroBackdropUrl"] = "https://image.tmdb.org/t/p/w1280" + path
            print(f"  hero {c['title']} / {f['title']}: {name} ({cert or 'no rating'})")

# Live TV: one folder per section of Sky's guide, in Sky's order, each one catalogue (so one paged grid). The Worker
# lists its channels then the section's free ones; the Pages install lists the free ones only.
LIVE_SECTIONS = [("Entertainment", "📺"), ("Films", "🎬"), ("Sport", "⚽"), ("News", "📰"),
                 ("Documentaries", "🦁"), ("Kids", "🧸"), ("Music", "🎵"), ("Lifestyle", "🏡")]

def live_tv():
    # The old Live TV files' id (and Sport's folder id), so importing link A replaces a profile's old copy.
    return grid_collection("live", "Live TV", [(t, e, [addon(UKX, "tv", "uks." + t.lower())]) for t, e in LIVE_SECTIONS])

def f1_replays():
    # Its own id: importing it next to link A adds a collection and replaces none.
    return grid_collection("f1-replays", "F1 Replays", [("F1 Replays", "🏁", [addon(MEDIAFUSION, "series", "formula_racing")])])


def write(name, data):
    path = os.path.join(ROOT, name)  # an absolute name stays as it is
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    rows = sum(len(fo["sources"]) for c in data for fo in c["folders"])
    print(f"{os.path.basename(name)}: {len(data)} collections, {sum(len(c['folders']) for c in data)} folders, {rows} rows, "
          f"{os.path.getsize(path)} bytes")

if __name__ == "__main__":
    args = sys.argv[1:]
    tmdb = check.Tmdb(check.load_key(args))
    f1 = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--key-json")]
    mk = {c["title"]: c for c in fetch(MK_TAG + "nuvio-collections.json")}
    cols = [streaming_services(), movies(mk), tv_shows(mk), anime(fetch(AIOM_PACK)), live_tv()]
    heroes(cols, tmdb)
    write("nuvio-collections.json", cols)
    art.render(cols)
    if f1: write(f1[0], [f1_replays()])
