"""Builds the Nuvio UK collections (import format as in mali-king/nuvio-collections).

  python build/build_uk.py   writes nuvio-collections.json (link A, every profile)
                             and nuvio-live.json (link B, profiles with the live-TV add-ons)

Link A pulls nine browse collections from mali-king's pack at its v2 tag, so the build needs network.
Check the output with build/check.py before publishing.
"""
import json, os, urllib.request, uuid
from datetime import date, timedelta

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

UKX = "com.barticom94.ukextras"    # UK Extras add-on (GitHub Pages), every profile
UKS = "com.barticom94.uksport"     # UK Sport add-on (Worker), live-TV profiles only
TVVOO = "org.stremio.vavoo.clean"  # third-party live-TV add-on, live-TV profiles only
NETFLIX_EXTRAS = [("series", "ukx.netflix-top10-shows"), ("movie", "ukx.netflix-top10-films"), ("movie", "ukx.netflix-popular")]

# mali-king v2 pack: collections and folders left out of link A (US and Indian content)
MK_DROP_COLLECTIONS = {"Streaming Services", "Indian Streaming", "Indian Cinema", "Indian Universes"}
MK_DROP_FOLDERS = {
    "Directors": {"S. S. Rajamouli", "Mani Ratnam", "Sanjay Leela Bhansali", "Rajkumar Hirani", "Anurag Kashyap",
                  "Zoya Akhtar", "Lokesh Kanagaraj", "Satyajit Ray"},
    "Studios": {"Yash Raj Films", "Dharma Productions", "Red Chillies", "Hombale Films", "Mythri Movie Makers"},
    "Networks": {"NBC", "ABC", "CBS", "FOX", "The CW"},  # US broadcast networks with no UK channel
}

# Picks: public Trakt lists as (row title, numeric Trakt list id, "MOVIE" or "TV"). The collection is
# left out while this is empty; add lists only after checking their ids and last-updated dates.
PICKS = []

FILMS_FLOOR = {"NOW": 20, "MUBI": 20}  # Sky and MUBI make few films; at 50 votes these rows drop under 20 titles



def discover(title, media, sort, **filters):
    s = {"provider": "tmdb", "tmdbSourceType": "DISCOVER", "title": title, "mediaType": media}
    if sort: s["sortBy"] = sort
    s["filters"] = {k: v for k, v in filters.items() if v is not None}
    return s

def addon(addon_id, type_, catalog_id, genre=None):
    s = {"provider": "addon", "addonId": addon_id, "type": type_, "catalogId": catalog_id}
    if genre: s["genre"] = genre
    return s

def gb_exclusions(own_providers):
    mine = set(own_providers.split("|"))
    pool = [p for s in SERVICES if s[1] == "GB" for p in s[2].split("|")]
    return "|".join(dict.fromkeys(p for p in pool if p not in mine))

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

def folder(folder_id, title, sources, cover=None, emoji=None, hide_title=False):
    return {
        "id": folder_id, "title": title, "coverImageUrl": cover,
        "focusGifUrl": None, "focusGifEnabled": False, "coverEmoji": emoji,
        "tileShape": "LANDSCAPE", "hideTitle": hide_title, "sources": sources,
        "heroBackdropUrl": None, "heroVideoUrl": None, "titleLogoUrl": None,
    }

def collection(slug, title, folders, pin=False, view="ROWS", all_tab=True):
    return {"id": str(uuid.uuid5(NS, "collection:" + slug)), "title": title, "backdropImageUrl": None,
            "pinToTop": pin, "focusGlowEnabled": True, "viewMode": view, "showAllTab": all_tab, "folders": folders}

def fid(slug, title): return str(uuid.uuid5(NS, f"folder:{slug}:{title}"))


def streaming_services():
    folders = [folder(str(uuid.uuid5(NS, "folder:" + s[0])), s[0], tile_sources(*s[:9]), cover=s[9], hide_title=True)
               for s in SERVICES]
    return collection("streaming-services-uk", "Streaming Services", folders, pin=True)

def mali_king_browse():
    with urllib.request.urlopen(MK_TAG + "nuvio-collections.json", timeout=60) as r:
        pack = json.load(r)
    titles = {c["title"] for c in pack}
    missing = (MK_DROP_COLLECTIONS | set(MK_DROP_FOLDERS)) - titles
    assert not missing, f"pack changed, not found: {missing}"
    out = []
    for c in pack:
        if c["title"] in MK_DROP_COLLECTIONS: continue
        drop = MK_DROP_FOLDERS.get(c["title"], set())
        assert drop <= {f["title"] for f in c["folders"]}, f"pack changed in {c['title']}"
        # Unpinned, so each profile can order or hide these rows on home (pinned rows always sit on top).
        out.append(dict(c, pinToTop=False, folders=[f for f in c["folders"] if f["title"] not in drop]))
    return out

def trending():
    # Nuvio only takes fixed release floors, so these are set at build time: rebuild every month or two.
    def since(days): return (date.today() - timedelta(days=days)).isoformat()
    rows = [
        discover("Trending Films", "movie", None, voteCountGte=20, releaseDateGte=since(180)),
        discover("Trending Series", "tv", None, voteCountGte=20, withoutGenres=NOISE_TV, releaseDateGte=since(730)),
        discover("Trending Anime", "tv", None, voteCountGte=10, withGenres="16", withOriginalLanguage="ja", releaseDateGte=since(730)),
    ]
    return collection("trending", "Trending", [folder(fid("trending", "Trending now"), "Trending now", rows, emoji="🔥")])

def picks():
    rows = [{"provider": "trakt", "title": t, "traktListId": i, "mediaType": m, "sortBy": "rank", "sortHow": "asc"}
            for t, i, m in PICKS]
    return collection("picks", "Picks", [folder(fid("picks", "Picks"), "Picks", rows, emoji="⭐")])

FREE_GENRES = [(None, "All channels", "📺"), ("News", "News", "📰"), ("Entertainment", "Entertainment", "🎭"),
               ("Movies", "Films", "🎬"), ("Kids", "Kids", "🧸"), ("Sport", "Sport", "⚽"),
               ("Documentary", "Documentaries", "🌍"), ("Music", "Music", "🎵"), ("Lifestyle", "Lifestyle", "🏡")]

def free_tv():
    folders = [folder(fid("free-tv", t), t, [addon(UKX, "tv", "ukx.free", g)], emoji=e) for g, t, e in FREE_GENRES]
    return collection("free-tv", "Free TV", folders, view="TABBED_GRID", all_tab=False)

LIVE_FOLDERS = [("Sport", addon(UKS, "tv", "uks.sport"), "⚽"),
                ("News", addon(TVVOO, "tv", "vavoo_tv_uk", "News"), "📰"),
                ("Kids", addon(TVVOO, "tv", "vavoo_tv_uk", "Kids"), "🧸"),
                ("Films", addon(TVVOO, "tv", "vavoo_tv_uk", "Movies"), "🎬"),
                ("Documentaries", addon(TVVOO, "tv", "vavoo_tv_uk", "Documentary"), "🌍"),
                ("All channels", addon(TVVOO, "tv", "vavoo_tv_uk"), "📺")]

def live():
    folders = [folder(fid("live", t), t, [s], emoji=e) for t, s, e in LIVE_FOLDERS]
    return collection("live", "Live", folders, view="TABBED_GRID", all_tab=False)


def write(name, data):
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    rows = sum(len(fo["sources"]) for c in data for fo in c["folders"])
    print(f"{name}: {len(data)} collections, {sum(len(c['folders']) for c in data)} folders, {rows} rows, "
          f"{os.path.getsize(path)} bytes")

if __name__ == "__main__":
    link_a = [streaming_services(), *mali_king_browse(), trending()]
    if PICKS: link_a.append(picks())
    link_a.append(free_tv())
    write("nuvio-collections.json", link_a)
    write("nuvio-live.json", [live()])
