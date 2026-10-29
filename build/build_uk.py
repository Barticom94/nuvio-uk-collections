"""Builds the Nuvio UK collections (import format as in mali-king/nuvio-collections).

  python build/build_uk.py   writes nuvio-collections.json (link A, every profile: Streaming Services,
                             Movies, TV Shows, Anime) and three Live TV files with one collection id, so a
                             profile imports exactly one: nuvio-live-free.json (no live add-ons),
                             nuvio-live.json (TvVoo and UK Sport) and nuvio-live-adam.json (plus F1 Replays)

Movies and TV Shows reuse mali-king's pack at its v2 tag; Anime's genre and decade tabs come from
AIOMetadata's Anime Essentials pack at v3.8.3 and stay out until MAL_FOLDERS is on (see there).
Both packs are fetched, so the build needs network.
Check the output with build/check.py before publishing.
"""
import json, os, re, urllib.request, uuid
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
MEDIAFUSION = "stremio.addons.mediafusion|elfhostedtrb"  # Adam's profile only (F1 Replays)
NETFLIX_EXTRAS = [("series", "ukx.netflix-top10-shows"), ("movie", "ukx.netflix-top10-films"), ("movie", "ukx.netflix-popular")]

# AIOMetadata's configured manifest id is its package.json name (getManifest.ts: id = buildInfo.name; the
# configure app's FALLBACK_ADDON_ID and Nuvio's own tests use the same). The bare /manifest.json says
# com.aio.metadata, but that is the unconfigured stub nobody installs.
AIOM = "aio-metadata"
# A pack import adds these catalogues without a displayType, so the manifest ids stay unsuffixed. Editing one in
# AIOMetadata's catalogue dialog writes displayType and the manifest id becomes "<id>_anime": set "_anime" then.
AIOM_ID_SUFFIX = ""
AIOM_PACK = "https://raw.githubusercontent.com/cedya77/aiometadata/v3.8.3/public/featured/anime-essentials.json"
# Off until MAL safe mode (sfw) is on in EVERY AIOMetadata config a profile uses. With it off, AIOMetadata doesn't
# ask Jikan to filter, so the genre and decade tabs (School among them) list Rx hentai. Both of Adam's configs had
# sfw false on 29 Oct. Turn this on only once both are confirmed on, then rebuild and run check.py.
MAL_FOLDERS = False
# Hentai, Erotica and Ecchi are MAL's adult genres. Harem, Reverse Harem and Magical Sex Shift go too: link A reaches
# family profiles, and Jikan's sfw filter only removes Rx titles, not R+ fan service.
MAL_LEFT_OUT = {"Hentai", "Erotica", "Ecchi", "Harem", "Reverse Harem", "Magical Sex Shift"}

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
    # Not pinned: Nuvio puts pinned collections above every other home row, and this one sits third.
    return collection("streaming-services-uk", "Streaming Services", folders)

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

def movies(mk):
    m = "movie"
    gb_digital = "|".join(dict.fromkeys(gb_pool() + GB_STORES.split("|")))  # on a UK service or store = out digitally
    return grid_collection("movies", "Movies", [
        ("New", "🆕", [discover("New films", m, "primary_release_date.desc", voteCountGte=25,
                                withWatchProviders=gb_digital, watchRegion="GB")]),
        ("Trending", "🔥", [discover("Trending films", m, None, voteCountGte=20, releaseDateGte=since(180))]),
        # No documentaries, concert films or TV films, as in the pack's Critics' Picks
        ("Top rated", "⭐", [discover("Top rated films", m, "vote_average.desc", voteCountGte=3000, withoutGenres="99|10402|10770")]),
        ("By Genre", "🎭", pack_tabs(mk, "Genres", m)),
        ("By Decade", "📅", pack_tabs(mk, "Decades", m)),
        ("Collections", "🎞️", pack_tabs(mk, "Franchises & Universes", m)),
        ("Moods", "🌗", pack_tabs(mk, "Moods & Themes", m)),
        ("Directors", "🎬", pack_tabs(mk, "Directors", m, MK_DROP_FOLDERS["Directors"])),
        ("Studios", "🏛️", pack_tabs(mk, "Studios", m, MK_DROP_FOLDERS["Studios"])),
        ("World Cinema", "🌍", pack_tabs(mk, "World Cinema", m)),
        ("Critics' picks", "🏆", pack_tabs(mk, "Critics' Picks", m)),
    ])

def tv_shows(mk):
    t = "tv"
    return grid_collection("tv-shows", "TV Shows", [
        ("New", "🆕", [discover("New series", t, "first_air_date.desc", voteCountGte=10, withoutGenres=NOISE_TV)]),
        ("Trending", "🔥", [discover("Trending series", t, None, voteCountGte=20, withoutGenres=NOISE_TV, releaseDateGte=since(730))]),
        # 1500 votes keeps new hype shows off the top; keyword 210024 (anime) leaves anime to the Anime collection
        ("Top rated", "⭐", [discover("Top rated series", t, "vote_average.desc", voteCountGte=1500, withoutGenres=NOISE_TV,
                                      withoutKeywords="210024")]),
        ("By Genre", "🎭", pack_tabs(mk, "Genres", t)),
        ("By Decade", "📅", pack_tabs(mk, "Decades", t)),
        ("Networks", "📡", pack_tabs(mk, "Networks", t, MK_DROP_FOLDERS["Networks"])),
    ])

def anime(pack):
    """New, Trending and Top rated run on Nuvio's own TMDB access (Japanese-language animation). By Genre and
    By Decade use the MAL catalogues AIOMetadata adds when the Anime Essentials pack is imported."""
    widgets = {w["title"]: w["dataSource"]["payload"]["items"] for w in pack["widgets"] if w["type"] == "collection.row"}
    def order(item):  # the pack numbers its cards: 1 to 21 genres, 22 to 73 themes, 74 to 78 demographics
        n = int(re.search(r"/(\d+)-[^/]*$", item["imageURL"]).group(1))
        return (0 if n < 22 else 2 if n < 74 else 1, n)
    genres = [i["dataSources"][0]["payload"]["genre"] for i in sorted(widgets["Anime by Genre"], key=order)]
    assert MAL_LEFT_OUT <= set(genres) and len(genres) == 78, "Anime Essentials pack changed"
    decades = [i["dataSources"][0]["payload"]["aiometadata"]["catalog"]["id"] for i in widgets["Anime by Decade"]]
    assert decades == ["mal.80sDecade", "mal.90sDecade", "mal.00sDecade", "mal.10sDecade", "mal.20sDecade"], decades
    a = dict(withGenres="16", withOriginalLanguage="ja")
    def mal(catalog_id, genre=None): return addon(AIOM, "anime", catalog_id + AIOM_ID_SUFFIX, genre)
    spec = [
        ("New", "🆕", [discover("Series", "tv", "first_air_date.desc", voteCountGte=5, **a),
                       discover("Films", "movie", "primary_release_date.desc", voteCountGte=10, **a)]),
        ("Trending", "🔥", [discover("Series", "tv", None, voteCountGte=10, releaseDateGte=since(730), **a),
                            discover("Films", "movie", None, voteCountGte=10, releaseDateGte=since(730), **a)]),
        ("Top rated", "⭐", [discover("Series", "tv", "vote_average.desc", voteCountGte=500, **a),
                             discover("Films", "movie", "vote_average.desc", voteCountGte=500, **a)]),
    ]
    if MAL_FOLDERS:
        spec += [("By Genre", "🎭", [mal("mal.genres", g) for g in genres if g not in MAL_LEFT_OUT]),
                 ("By Decade", "📅", [mal(d) for d in reversed(decades)])]  # newest first, as in Movies and TV Shows
    return grid_collection("anime", "Anime", spec)

# Live TV folders. An add-on source has no title in Nuvio, so each tab reads "<catalogue name> · <genre>".
SPORT = ("Sport", "⚽", [addon(UKS, "tv", "uks.sport")])
LIVE_CHANNELS = ("Live channels", "📺", [addon(TVVOO, "tv", "vavoo_tv_uk", g) for g in ("News", "Kids", "Movies", "Documentary", None)])
FREE_CHANNELS = ("Free channels", "📡", [addon(UKX, "tv", "ukx.free", g) for g in
                                         ("News", "Entertainment", "Movies", "Kids", "Sport", "Documentary", "Music", "Lifestyle", None)])
F1_REPLAYS = ("F1 Replays", "🏁", [addon(MEDIAFUSION, "series", "formula_racing")])

def live_tv(*spec):
    # One id in all three files (the old Live id), so importing another file replaces the profile's copy.
    return grid_collection("live", "Live TV", spec)


def write(name, data):
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    rows = sum(len(fo["sources"]) for c in data for fo in c["folders"])
    print(f"{name}: {len(data)} collections, {sum(len(c['folders']) for c in data)} folders, {rows} rows, "
          f"{os.path.getsize(path)} bytes")

if __name__ == "__main__":
    mk = {c["title"]: c for c in fetch(MK_TAG + "nuvio-collections.json")}
    write("nuvio-collections.json", [streaming_services(), movies(mk), tv_shows(mk), anime(fetch(AIOM_PACK))])
    write("nuvio-live-free.json", [live_tv(FREE_CHANNELS)])
    write("nuvio-live.json", [live_tv(SPORT, LIVE_CHANNELS, FREE_CHANNELS)])
    write("nuvio-live-adam.json", [live_tv(SPORT, LIVE_CHANNELS, FREE_CHANNELS, F1_REPLAYS)])
