"""Builds the Nuvio UK collections (import format as in mali-king/nuvio-collections).

  python build/build_uk.py [--key-json PATH]
      writes nuvio-collections.json (link A, every profile: Streaming Services, Movies, TV Shows, Anime)
      and the art it points at (build/art.py)

The first four collections follow the home layout (Modern on Adam's TVs): each folder opens as a page of rows under
a hero, so every folder gets a TMDB backdrop for the hero (picked here, so the build needs the TMDB key the same way
check.py does), our title logo and, outside Streaming Services, our tile.
Movies, TV Shows and Anime are the same cards (New and Trending, Top Rated, Genres, Decades, and Collections in
Movies), every row written out here. Anime's decade rows come from AIOMetadata's Anime Essentials pack at v3.8.3
(fetched, so the build needs network) and stay out unless MAL_FOLDERS is on (see there). Ten service covers are
mali-king's (nuvio-collections, v2 tag).
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
def logo_url(title, collection_slug=""):  # a service's logo is its name; a card's is drawn in its collection's style
    return f"{COVER_BASE}logos/{collection_slug and collection_slug + '-'}{slug(title)}.png"

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
# which serves the same catalogues under the same id
UKX = "com.barticom94.ukextras"
NETFLIX_EXTRAS = [("series", "ukx.netflix-top10-shows"), ("movie", "ukx.netflix-top10-films"), ("movie", "ukx.netflix-popular")]

# AIOMetadata's configured manifest id is its package.json name (getManifest.ts: id = buildInfo.name; the
# configure app's FALLBACK_ADDON_ID and Nuvio's own tests use the same). The bare /manifest.json says
# com.aio.metadata, but that is the unconfigured stub nobody installs.
AIOM = "aio-metadata"
# A pack import adds these catalogues without a displayType, so the manifest ids stay unsuffixed. Editing one in
# AIOMetadata's catalogue dialog writes displayType and the manifest id becomes "<id>_anime": set "_anime" then.
AIOM_ID_SUFFIX = ""
AIOM_PACK = "https://raw.githubusercontent.com/cedya77/aiometadata/v3.8.3/public/featured/anime-essentials.json"
# On by Adam's call (29 Oct). MAL safe mode (sfw) decides what these rows can list: with it off, Rx hentai can turn
# up; with it on, AIOMetadata's MAL source drops Rx and R+. The family config has sfw on (29 Oct export; on the live
# install, no hentai or erotica in the first 75 of any decade), Adam's adult config has it off. Set False and
# rebuild to take the Decades folder out again.
# The MAL genre catalogue can't come back as rows: its genres share one catalogue id, so in a page of rows they
# collapse into one (Nuvio keys a row by add-on, type and catalogue, not genre). Anime's genres are TMDB rows instead.
MAL_FOLDERS = True
# Anime keywords left out of every Anime row (TMDB keyword ids): hentai, hentai adaptation, ecchi, etchi, erotica,
# harem, reverse harem, nudity, sexual content, panty shot, erotic, erotic comedy, sex comedy, softcore, lolicon,
# huge breasts, large breasts, rape, sexual abuse, public sex. TMDB's adult flag only covers outright porn, and link A
# reaches family profiles.
ANIME_SAFE = ("198385|384581|195669|285672|325693|9194|238374|281741|329280|356895|"
              "256466|302868|170827|155477|332173|345266|366001|570|739|11512")
# Film keywords left out of every Movies row, for the same reason: pornography, porn industry, softcore, unsimulated
# sex, erotic movie, bdsm (9 Songs, Rocco, Room in Rome and Fifty Shades topped the Music, Documentary, Romance and
# Psychological thriller rows). The MCU row also leaves out short films (the I Am Groot shorts and the specials).
MOVIE_SAFE = "445|18321|155477|282903|190370|158713"
SHORT_FILM = "263548"

# Genre rows: (row, TMDB genre ids, keyword ids[, vote floor]). Every TMDB genre of the type (not TV Movie; on TV not
# News, Talk or Soap), each followed by its sub-genres: a TMDB keyword, or two genres together for romantic comedy.
# Keyword ids checked 29 Oct. Films: superhero 9715, sports 6075, psychological thriller 12565, heist 10051 and bank
# heist 191845, space 9882 and space travel 3801, musical 4344.
MOVIE_GENRES = [
    ("Action", "28", None), ("Superhero", None, "9715"), ("Adventure", "12", None), ("Comedy", "35", None),
    ("Romantic comedy", "10749,35", None), ("Drama", "18", None), ("Sports", None, "6075"), ("Thriller", "53", None),
    ("Psychological thriller", None, "12565"), ("Crime", "80", None), ("Heist", None, "10051|191845"),
    ("Horror", "27", None), ("Sci-fi", "878", None), ("Space", None, "9882|3801"), ("Fantasy", "14", None),
    ("Romance", "10749", None), ("Mystery", "9648", None), ("Animation", "16", None), ("Family", "10751", None),
    ("Documentary", "99", None), ("History", "36", None), ("War", "10752", None), ("Western", "37", None),
    ("Music and concerts", "10402", None), ("Musical", None, "4344")]
# TV: period drama 15060, costume drama 195013, historical drama 192772; medical drama 208788 and hospital 11612; legal
# drama 222517, courtroom 33519, courtroom drama 214780; teen drama 193400; sitcom 193171; police procedural 268067;
# true crime 33722; murder mystery 207046 and whodunit 12570; superhero 9715; supernatural 6152; horror 315058 (TV has
# no horror genre); anthology 9706. Western has few series with 50 votes, so it takes 20.
TV_GENRES = [
    ("Drama", "18", None), ("Period drama", None, "15060|195013|192772"), ("Medical drama", None, "208788|11612"),
    ("Legal drama", None, "222517|33519|214780"), ("Teen drama", None, "193400"), ("Comedy", "35", None),
    ("Sitcom", None, "193171"), ("Crime", "80", None), ("Police procedural", None, "268067"),
    ("True crime", None, "33722"), ("Mystery", "9648", None), ("Murder mystery", None, "207046|12570"),
    ("Action and adventure", "10759", None), ("Superhero", None, "9715"), ("Sci-fi and fantasy", "10765", None),
    ("Supernatural", None, "6152"), ("Horror", None, "315058"), ("Anthology", None, "9706"),
    ("Animation", "16", None), ("Family", "10751", None), ("Kids", "10762", None), ("Documentary", "99", None),
    ("Reality", "10764", None), ("War and politics", "10768", None), ("Western", "37", None, 20)]
# Film series (TMDB collection ids, checked 29 Oct) and their UK Streaming catalogues (uks.franchise.<id>, one each, as
# rows of one catalogue collapse into one). The rows come from UK Streaming; the TMDB sources only pick the hero. The
# MCU has no TMDB collection, so its hero source is its TMDB keyword (180547).
FRANCHISES = [
    ("Star Wars", 10, "star-wars"), ("Harry Potter", 1241, "harry-potter"),
    ("The Lord of the Rings", 119, "lord-of-the-rings"), ("James Bond", 645, "james-bond"),
    ("Mission: Impossible", 87359, "mission-impossible"), ("Jurassic Park", 328, "jurassic-park"),
    ("The Dark Knight trilogy", 263, "dark-knight"), ("Fast & Furious", 9485, "fast-and-furious"),
    ("John Wick", 404609, "john-wick"), ("Bourne", 31562, "bourne"), ("Kingsman", 391860, "kingsman"),
    ("The Hunger Games", 131635, "hunger-games"), ("The Matrix", 2344, "matrix"), ("Avatar", 87096, "avatar"),
    ("Pirates of the Caribbean", 295, "pirates-of-the-caribbean"), ("Indiana Jones", 84, "indiana-jones"),
    ("Back to the Future", 264, "back-to-the-future"), ("The Godfather", 230, "godfather"),
    ("Toy Story", 10194, "toy-story"), ("Shrek", 2150, "shrek"), ("Despicable Me", 86066, "despicable-me"),
    ("How to Train Your Dragon", 89137, "how-to-train-your-dragon"), ("Paddington", 488924, "paddington"),
    ("Wallace & Gromit", 529, "wallace-and-gromit")]
NO_FILLER = "99|10402|10770"  # documentaries, concert films and TV films: out of the broad Top rated film rows

FILMS_FLOOR = {"NOW": 20, "MUBI": 20}  # Sky and MUBI make few films; at 50 votes these rows drop under 20 titles
# Few originals with many votes: at the tier's top rated floor Best Originals drops under 5 titles
BEST_ORIG_FLOOR = {"Channel 5": 10, "Crunchyroll": 10, "Shudder": 10, "Discovery+": 3, "WOW": 3}
# Best Originals left out where it repeats Best exclusive series: of its first 20 titles, this many were in Best
# exclusive series' first 40 (TMDB live, 29 Oct 2026): Netflix 18, Prime Video 17, Disney+ 15, Apple TV+ 18. Kept: NOW
# 11, Paramount+ 10, ITVX 9, HBO Max 7, Channel 4 7, BBC iPlayer 4; Channel 5, Crunchyroll, Shudder, Discovery+, WOW 0.
# Out at 15 or more (75 percent). Hulu has no exclusive rows and MUBI no originals rows, so both keep theirs.
ORIG_REPEATS = {"Netflix", "Prime Video", "Disney+", "Apple TV+"}
GB_STORES = "2|10|35|130|192"  # Apple TV Store, Amazon Video, Rakuten TV, Sky Store, YouTube (rent and buy)


def discover(title, media, sort, **filters):
    s = {"provider": "tmdb", "tmdbSourceType": "DISCOVER", "title": title, "mediaType": media}
    s["sortBy"] = sort or "popularity.desc"  # Nuvio's default, written out for the website
    # The nuvio.tv website, where the household imports these files, keeps only these sorts and swaps any other (or a
    # missing one) for its own default, newest first on series
    assert s["sortBy"] in check.SITE_SORTS, s
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
        out.append(discover(f"{title} - Trending originals", "tv", None, **orig))
        # All time: the best rated of the well known ones (the website can't sort by votes)
        if title not in ORIG_REPEATS:
            out.append(discover(f"{title} - Best originals", "tv", "vote_average.desc",
                                **dict(orig, voteCountGte=BEST_ORIG_FLOOR.get(title, f["top_t"]))))
    if title == "Netflix":
        out += [addon(UKX, t, c) for t, c in NETFLIX_EXTRAS]
    if films:
        out.append(discover(f"{title} - Original films", "movie", None, withCompanies=films, voteCountGte=FILMS_FLOOR.get(title, f["films"])))
    if region != "GB":
        return out
    base = dict(withWatchProviders=providers, watchRegion=region)
    excl = dict(base, withoutWatchProviders=gb_exclusions(providers))
    if movies: out.append(discover(f"{title} - Exclusive films", "movie", None, voteCountGte=f["pop_m"], **excl))
    if series: out.append(discover(f"{title} - Exclusive series", "tv", None, voteCountGte=f["pop_t"], withoutGenres=NOISE_TV, **excl))
    if movies: out.append(discover(f"{title} - New films", "movie", "primary_release_date.desc", voteCountGte=f["new_m"], **base))
    if series: out.append(discover(f"{title} - New series", "tv", "first_air_date.desc", voteCountGte=f["new_t"], withoutGenres=NOISE_TV, **base))
    if movies: out.append(discover(f"{title} - Best exclusive films", "movie", "vote_average.desc", voteCountGte=f["top_m"], **excl))
    if series: out.append(discover(f"{title} - Best exclusive series", "tv", "vote_average.desc", voteCountGte=f["top_t"], withoutGenres=NOISE_TV, **excl))
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

def a_to_z(rows):
    """Genres cards read A to Z (Adam, 29 Oct)."""
    return sorted(rows, key=lambda s: s["title"].casefold())

def modern_collection(slug_, title, spec):
    """spec: (folder title, sources[, hero sources]). Every folder gets our tile and title logo; hero sources stand
    in for rows heroes() can't read (add-on rows) when picking the folder's backdrop."""
    folders = []
    for t, sources, *hint in spec:
        # the tile already shows the card's name, so Nuvio's label under it stays off
        f = folder(fid(slug_, t), t, sources, cover=tile_url(slug_, t), hide_title=True, logo=logo_url(t, slug_))
        if hint: f["_hero"] = hint[0]
        folders.append(f)
    return collection(slug_, title, folders, **MODERN)

def decades(media, first, floor, older=None, **f):
    """One row per decade, newest first: best rated above a vote floor (popularity there follows the season, such as
    horror in October); older = (decade, floor) lowers the floor for that decade and the ones before it."""
    def fl(y): return older[1] if older and y <= older[0] else floor
    return [discover(f"{y}s", media, "vote_average.desc", voteCountGte=fl(y), releaseDateGte=f"{y}-01-01",
                     releaseDateLte=f"{y + 9}-12-31", **f) for y in range(2020, first - 1, -10)]

def film_series(title, tmdb_id):
    return {"provider": "tmdb", "tmdbSourceType": "COLLECTION", "title": title, "tmdbId": tmdb_id, "mediaType": "movie",
            "sortBy": "original"}

def movies():
    m = "movie"
    def film(title, sort, **f): return discover(title, m, sort, **{"withoutKeywords": MOVIE_SAFE, **f})
    # out on a UK service or store
    digital = dict(withWatchProviders="|".join(dict.fromkeys(gb_pool() + GB_STORES.split("|"))), watchRegion="GB")
    return modern_collection("movies", "Movies", [
        ("New and Trending", [
            film("New films", "primary_release_date.desc", voteCountGte=25, **digital),
            film("Trending films", "popularity.desc", voteCountGte=20, releaseDateGte=since(180)),
            film("Trending family films", "popularity.desc", voteCountGte=20, withGenres="10751",
                 releaseDateGte=since(365))]),
        ("Top Rated", [
            film("Top rated films", "vote_average.desc", voteCountGte=3000, withoutGenres=NO_FILLER),
            film("Top rated of the past year", "vote_average.desc", voteCountGte=500, releaseDateGte=since(365),
                 withoutGenres=NO_FILLER),
            film("Top rated of the past five years", "vote_average.desc", voteCountGte=2000,
                 releaseDateGte=since(5 * 365), withoutGenres=NO_FILLER),
            film("Top rated animated films", "vote_average.desc", voteCountGte=2000, withGenres="16"),
            film("Top rated family films", "vote_average.desc", voteCountGte=2000, withGenres="10751",
                 withoutGenres="16"),
            film("Top rated documentaries", "vote_average.desc", voteCountGte=400, withGenres="99")]),
        ("Genres", a_to_z([film(t, "popularity.desc", voteCountGte=100, withGenres=g, withKeywords=k)
                           for t, g, k in MOVIE_GENRES])),
        ("Decades", decades(m, 1950, 1000, withoutKeywords=MOVIE_SAFE)),
        ("Collections", [addon(UKX, m, "uks.franchise." + c) for c in ["mcu"] + [c for _, _, c in FRANCHISES]],
         [film("Marvel Cinematic Universe", "primary_release_date.desc", voteCountGte=200, withKeywords="180547",
               withoutKeywords=f"{MOVIE_SAFE}|{SHORT_FILM}"), *(film_series(t, i) for t, i, _ in FRANCHISES)]),
    ])

def tv_shows():
    t = "tv"
    na = dict(withoutGenres=NOISE_TV, withoutKeywords="210024")  # keyword 210024 (anime): anime is in Anime
    def but(*genres): return dict(na, withoutGenres="|".join((NOISE_TV,) + genres))
    return modern_collection("tv-shows", "TV Shows", [
        ("New and Trending", [
            discover("New series", t, "first_air_date.desc", voteCountGte=10, **na),
            discover("Trending series", t, "popularity.desc", voteCountGte=20, releaseDateGte=since(730), **na),
            discover("Trending documentaries", t, "popularity.desc", voteCountGte=10, withGenres="99",
                     releaseDateGte=since(730), **na)]),
        ("Top Rated", [
            # 1500 votes keeps new hype shows off the top
            discover("Top rated series", t, "vote_average.desc", voteCountGte=1500, **na),
            discover("Top rated new series", t, "vote_average.desc", voteCountGte=300, releaseDateGte=since(730), **na),
            discover("Top rated miniseries", t, "vote_average.desc", voteCountGte=300, withKeywords="11162", **but("99")),
            discover("Top rated crime series", t, "vote_average.desc", voteCountGte=500, withGenres="80", **na),
            discover("Top rated comedies", t, "vote_average.desc", voteCountGte=1000, withGenres="35", **but("16")),
            discover("Top rated animated series", t, "vote_average.desc", voteCountGte=500, withGenres="16", **na),
            discover("Top rated documentaries", t, "vote_average.desc", voteCountGte=150, withGenres="99", **na)]),
        ("Genres", a_to_z([discover(n, t, "popularity.desc", voteCountGte=fl[0] if fl else 50, withGenres=g,
                                    withKeywords=k, **na) for n, g, k, *fl in TV_GENRES])),
        # 300 votes keeps fan-vote titles off the top; the 1960s and 1970s have too few series at 300. The anime
        # keyword stays out: anime would top the older decades
        ("Decades", decades(t, 1960, 300, older=(1970, 100), **na)),
    ])

def anime(pack):
    """Japanese-language animation on Nuvio's own TMDB access, ANIME_SAFE left out of every row. Decades uses the MAL
    catalogues AIOMetadata adds when the Anime Essentials pack is imported (one catalogue id per decade)."""
    widgets = {w["title"]: w["dataSource"]["payload"]["items"] for w in pack["widgets"] if w["type"] == "collection.row"}
    mal = [i["dataSources"][0]["payload"]["aiometadata"]["catalog"]["id"] for i in widgets["Anime by Decade"]]
    assert mal == ["mal.80sDecade", "mal.90sDecade", "mal.00sDecade", "mal.10sDecade", "mal.20sDecade"], mal
    a = dict(withOriginalLanguage="ja", withoutKeywords=ANIME_SAFE)
    def row(title, media, genres="", sort="popularity.desc", floor=20, **f):
        # 20 votes keeps one-season obscurities out of the genre rows
        return discover(title, media, sort, voteCountGte=floor, withGenres="16" + genres, **a, **f)
    def sub(title, keywords): return row(title, "tv", withKeywords=keywords)
    def best(title, media, floor, **f): return row(title, media, sort="vote_average.desc", floor=floor, **f)
    spec = [
        ("New and Trending", [row("New series", "tv", sort="first_air_date.desc", floor=5),
                              row("New films", "movie", sort="primary_release_date.desc", floor=10),
                              row("Trending series", "tv", floor=10, releaseDateGte=since(730)),
                              row("Trending films", "movie", floor=10, releaseDateGte=since(730))]),
        ("Top Rated", [best("Top rated series", "tv", 500), best("Top rated films", "movie", 500),
                       best("Top rated new series", "tv", 50, releaseDateGte=since(730)),
                       best("Top rated new films", "movie", 50, releaseDateGte=since(1095))]),
        # TMDB's TV genres with 16 (10759 Action & Adventure, 35 Comedy, 18 Drama, 9648 Mystery, 10765 Sci-Fi & Fantasy,
        # 10762 Kids), each followed by its sub-genres (TMDB keywords), then the film genres. Romance is only a film
        # genre, so the series rows use its keyword (9840). Kids (10762) stays out of the broad rows, where
        # long-running children's shows would top them. Keyword ids, checked 29 Oct: isekai 237451; martial arts 779;
        # mecha 10046 and giant robot 10891; samurai 1462; sports 6075, baseball 1480, volleyball 5605, basketball
        # 6496, football 13042; slice of life 9914; psychological 272553 and psychological thriller 12565; dark
        # fantasy 177895; supernatural 6152; horror 315058 and j-horror 325319; magical girl 292887, magical girls
        # 358020, magical girl ensemble 382274
        ("Genres", a_to_z([row("Action and adventure", "tv", ",10759", withoutGenres="10762"),
                    sub("Isekai", "237451"), sub("Martial arts", "779"), sub("Mecha", "10046|10891"),
                    sub("Samurai", "1462"), sub("Sports", "6075|1480|5605|6496|13042"),
                    row("Comedy", "tv", ",35", withoutGenres="10762"),
                    row("Romantic comedy", "tv", ",35", withKeywords="9840"), sub("Slice of life", "9914"),
                    row("Drama", "tv", ",18"), row("Romance", "tv", withKeywords="9840"),
                    row("Mystery", "tv", ",9648"), sub("Psychological", "272553|12565"),
                    row("Sci-fi and fantasy", "tv", ",10765", withoutGenres="10762"),
                    sub("Dark fantasy", "177895"), sub("Supernatural", "6152"), sub("Horror", "315058|325319"),
                    sub("Magical girl", "292887|358020|382274"), row("Kids", "tv", ",10762"),
                    row("Action films", "movie", ",28"), row("Adventure films", "movie", ",12"),
                    row("Fantasy films", "movie", ",14"), row("Sci-fi films", "movie", ",878"),
                    row("Romance films", "movie", ",10749"), row("Family films", "movie", ",10751")])),
    ]
    if MAL_FOLDERS:
        # newest first, as in Movies and TV Shows; the hero comes from TMDB's best loved anime before 2000
        spec.append(("Decades", [addon(AIOM, "anime", d + AIOM_ID_SUFFIX) for d in reversed(mal)],
                     [best("", "tv", 300, releaseDateLte="1999-12-31")]))
    return modern_collection("anime", "Anime", spec)


# Hero backdrops: per folder, the first family-safe title (by rating) among each row's best known few (most votes on
# the row's first page: steadier than TMDB's daily popularity), with a backdrop that has no text on it (our logo goes
# over it), never a title or a film series used twice in a collection.
HERO_DEPTH = 5    # best known titles tried per row
HERO_TRIES = 30   # titles looked up per folder at most
# The UK rating, else the US one. A folder's rows already show these titles' posters, so the hero only has to keep
# 18s out and horror out where it can; R and TV-MA (often 18 here) only when the most known titles have nothing else.
CERT_TIER = {**dict.fromkeys(["U", "PG", "12", "12A", "15", "G", "PG-13", "TV-Y", "TV-Y7", "TV-G", "TV-PG", "TV-14"], 0),
             **dict.fromkeys(["R", "TV-MA"], 1)}  # anything else (18, R18, NC-17) never; no rating at all is tier 2
# The row a folder's hero comes from first, where the first row's best known title is a poor face for the folder
HERO_ROW = {("Streaming Services", "Discovery+"): "Discovery+ - Exclusive series",  # its originals include dramas
            ("Streaming Services", "Crunchyroll"): "Crunchyroll - Exclusive series",
            ("Movies", "New and Trending"): "Trending films",  # what's big now
            ("TV Shows", "New and Trending"): "Trending series", ("Anime", "New and Trending"): "Trending series",
            ("Movies", "Decades"): "1980s", ("TV Shows", "Decades"): "1980s"}  # an older decade says "decades"
# Backdrops with text or little in them, and titles too dark for a home screen, found on the contact sheet
HERO_SKIP = {"/86IbFy98QjRIqg6WanKYb9tXNbJ.jpg",  # The Avengers: shop signs, and dim
             "/v38qp4bySLTXYu3MF8r5GD51FN3.jpg",  # One Piece: mostly blank parchment
             ("movie", 77),                       # Memento: its backdrops are handwritten notes or mostly black
             ("tv", 256201)}                      # The Creep Tapes (Shudder)

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
            if (media, r["id"]) in used | HERO_SKIP or tried >= HERO_TRIES: continue
            tried += 1
            d = tmdb.get(f"{media}/{r['id']}", {"append_to_response": "release_dates,content_ratings,images",
                                                 "include_image_language": "null"}) or {}
            ratings = {x["iso_3166_1"]: x.get("rating") for x in (d.get("content_ratings") or {}).get("results", [])}
            for x in (d.get("release_dates") or {}).get("results", []):
                ratings[x["iso_3166_1"]] = next((y["certification"] for y in x["release_dates"] if y["certification"]), None)
            cert = ratings.get("GB") or ratings.get("US")
            tier = CERT_TIER.get(cert, 2 if cert is None else None)
            series = (d.get("belongs_to_collection") or {}).get("id")
            if tier is None or d.get("adult") or ("series", series) in used: continue
            if any(g["id"] == 27 for g in d.get("genres", [])): tier += 0.5  # horror only when the folder has nothing else
            plain = sorted((b for b in (d.get("images") or {}).get("backdrops", [])
                            if b.get("width", 0) >= 1280 and b["file_path"] not in HERO_SKIP),
                           key=lambda b: -(b.get("vote_average") or 0))
            if not plain: continue
            if best is None or tier < best[0]:
                best = (tier, {(media, r["id"]), ("series", series)}, plain[0]["file_path"],
                        d.get("title") or d.get("name"), cert)
            if tier == 0: return best
    return best

def heroes(cols, tmdb):
    today = date.today().isoformat()
    assert set(HERO_ROW) <= {(c["title"], f["title"]) for c in cols for f in c["folders"]}, "HERO_ROW names a lost folder"
    for c in cols:
        if c["viewMode"] != "FOLLOW_LAYOUT": continue
        used = set()
        for f in c["folders"]:
            want = HERO_ROW.get((c["title"], f["title"]))
            first = [s for s in f["sources"] if s.get("title") == want]
            assert want is None or first, f"HERO_ROW: no row {want!r} in {c['title']} / {f['title']}"
            pick = hero_pick(tmdb, f.pop("_hero", []) + first + f["sources"], used, today)
            if pick is None: raise SystemExit(f"no hero backdrop for {c['title']} / {f['title']}")
            _, keys, path, name, cert = pick
            used |= keys - {("series", None)}
            f["heroBackdropUrl"] = "https://image.tmdb.org/t/p/w1280" + path
            print(f"  hero {c['title']} / {f['title']}: {name} ({cert or 'no rating'})")


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
    cols = [streaming_services(), movies(), tv_shows(), anime(fetch(AIOM_PACK))]
    heroes(cols, tmdb)
    write("nuvio-collections.json", cols)
    art.render(cols)
