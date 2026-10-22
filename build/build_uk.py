"""Builds a UK 'Streaming Services' collection for Nuvio (import format as in mali-king/nuvio-collections)."""
import json, sys, uuid

NS = uuid.UUID('6f1c2a4e-0b7d-4c1e-9a55-3d2f7e8b9c10')
NOISE_TV = "10763|10767|10766"  # News, Talk, Soap
FLOORS = {  # vote-count floors, same tiers as the curated pack
    "global": dict(pop_m=100, pop_t=50, top_m=1000, top_t=300, new_m=25, new_t=15),
    "mid": dict(pop_m=30, pop_t=20, top_m=200, top_t=80, new_m=10, new_t=5),
    "regional": dict(pop_m=10, pop_t=5, top_m=60, top_t=25, new_m=4, new_t=3),
}
import os
MK = "https://raw.githubusercontent.com/mali-king/nuvio-collections/v2/covers/streaming-services/{}.webp"
# Our own 1600x900 covers (scratchpad/covers/out/<slug>.webp) once hosted; set NUVIO_COVER_BASE to the folder URL.
COVER_BASE = os.environ.get("NUVIO_COVER_BASE", "https://COVER-HOST-NOT-SET.invalid/nuvio-covers/")
def own(slug): return COVER_BASE + slug + ".webp"
# title, watch region, watch-provider ids (main service | its Amazon/Apple channels), floor,
# originals (TMDB network id; a "a|b|c" string = several networks via Discover; None = no row),
# originals since (streamers only; broadcasters keep their back catalogue), movies, series, cover url
SERVICES = [
    ("Netflix",     "GB", "8|1796",                 "global",   213,       "2012-01-01", True,  True,  MK.format("netflix")),
    ("Prime Video", "GB", "9|2100",                 "global",   1024,      "2012-01-01", True,  True,  MK.format("prime-video")),
    ("Disney+",     "GB", "337",                    "global",   2739,      "2012-01-01", True,  True,  MK.format("disney-plus")),
    ("Apple TV+",   "GB", "350|2243",               "mid",      2552,      "2012-01-01", True,  True,  MK.format("apple-tv")),
    ("HBO Max",     "GB", "1899|1825",              "mid",      49,        None,         True,  True,  MK.format("hbo-max")),
    ("Hulu",        "US", "15",                     "mid",      453,       "2012-01-01", True,  True,  MK.format("hulu")),  # no UK Hulu: US catalogue
    ("NOW",         "GB", "39|591",                 "mid",      None,      None,         True,  True,  own("now")),
    ("Paramount+",  "GB", "531|2303|2304|582|1853", "mid",      4330,      "2012-01-01", True,  True,  MK.format("paramount-plus")),
    ("BBC iPlayer", "GB", "38",                     "mid",      "4|332|3", None,         True,  True,  own("bbc-iplayer")),
    ("ITVX",        "GB", "41|2300|598",            "mid",      9,         None,         True,  True,  own("itvx")),
    ("Channel 4",   "GB", "103|2311",               "mid",      26,        None,         True,  True,  own("channel-4")),
    ("Channel 5",   "GB", "333",                    "mid",      None,      None,         True,  True,  own("channel-5")),
    ("Crunchyroll", "GB", "283|1968",               "mid",      1112,      "2012-01-01", True,  True,  MK.format("crunchyroll")),
    ("Shudder",     "GB", "99|204",                 "mid",      2949,      "2012-01-01", True,  True,  MK.format("shudder")),
    ("MUBI",        "GB", "11|201",                 "mid",      None,      None,         True,  False, MK.format("mubi")),
    ("Discovery+",  "GB", "524|584",                "regional", None,      None,         False, True,  own("discovery-plus")),
    ("WOW",         "GB", "546",                    "regional", None,      None,         False, True,  own("wow-presents-plus")),
]

def discover(title, media, sort, **filters):
    s = {"provider": "tmdb", "tmdbSourceType": "DISCOVER", "title": title, "mediaType": media}
    if sort: s["sortBy"] = sort
    s["filters"] = {k: v for k, v in filters.items() if v is not None}
    return s

def sources(region, providers, floor, originals, since, movies, series):
    f = FLOORS[floor]
    base = dict(withWatchProviders=providers, watchRegion=region)
    out = []
    if isinstance(originals, int):
        out.append({"provider": "tmdb", "tmdbSourceType": "NETWORK", "title": "Originals", "tmdbId": originals,
                    "mediaType": "tv", "filters": {k: v for k, v in
                                                   {"withoutGenres": NOISE_TV, "releaseDateGte": since}.items() if v}})
    elif originals:
        out.append(discover("Originals", "tv", None, withNetworks=originals, voteCountGte=20, withoutGenres=NOISE_TV))
    if movies: out.append(discover("Popular Movies", "movie", None, voteCountGte=f["pop_m"], **base))
    if series: out.append(discover("Popular Series", "tv", None, voteCountGte=f["pop_t"], withoutGenres=NOISE_TV, **base))
    if movies: out.append(discover("New Movies", "movie", "primary_release_date.desc", voteCountGte=f["new_m"], **base))
    if series: out.append(discover("New Series", "tv", "first_air_date.desc", voteCountGte=f["new_t"], withoutGenres=NOISE_TV, **base))
    if movies: out.append(discover("Top Rated Movies", "movie", "vote_average.desc", voteCountGte=f["top_m"], **base))
    if series: out.append(discover("Top Rated Series", "tv", "vote_average.desc", voteCountGte=f["top_t"], withoutGenres=NOISE_TV, **base))
    return out

folders = []
for title, region, prov, floor, orig, since, mv, tv, cover in SERVICES:
    folders.append({
        "id": str(uuid.uuid5(NS, "folder:" + title)),
        "title": title,
        "coverImageUrl": cover,
        "focusGifUrl": None, "focusGifEnabled": False, "coverEmoji": None,
        "tileShape": "LANDSCAPE", "hideTitle": True,
        "sources": sources(region, prov, floor, orig, since, mv, tv),
        "heroBackdropUrl": None, "heroVideoUrl": None, "titleLogoUrl": None,
    })

collections = [{
    "id": str(uuid.uuid5(NS, "collection:streaming-services-uk")),
    "title": "Streaming Services",
    "backdropImageUrl": None,
    "pinToTop": True,
    "focusGlowEnabled": True,
    "viewMode": "ROWS",
    "showAllTab": True,
    "folders": folders,
}]

json.dump(collections, open(sys.argv[1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump(collections, open(sys.argv[2], "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
print("folders:", len(folders), "sources:", sum(len(f["sources"]) for f in folders))
