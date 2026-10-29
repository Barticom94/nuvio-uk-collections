"""Checks collection files the way Nuvio reads them, then calls every TMDB row live.

  python build/check.py FILE.json [FILE.json ...] [--only TITLE] [--key-json PATH] [--manifest ADDON_ID=PATH_OR_URL]

The TMDB v3 key comes from TMDB_API_KEY, or with --key-json from the tmdbApiKey field of that JSON file
(nothing else in it is read out). It stays in memory: never printed, logged or written.
Add-on rows are checked against their add-on's manifest (catalogue id, type and genre option); --manifest points
one at a local build before it is published. AIOMetadata's manifest needs a config, so its MAL rows are checked
against its catalogue list at v3.8.3 and the live MAL genre list on ElfHosted instead.
Writes build/report.txt (result counts per row) and exits 1 on any failure.

Parser rules mirror NuvioTV dev (d14832e, 28 Oct 2026): CollectionsDataStore.validateCollectionsJson and
parseCollections (Gson into Kotlin classes), TmdbCollectionSourceResolver.resolveDiscover for the requests.
"""
import concurrent.futures as cf, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
THIN = 20
SPOT = 5  # titles per exclusion row checked against GB watch providers
UKX = "com.barticom94.ukextras"
MEDIAFUSION = "stremio.addons.mediafusion|elfhostedtrb"
AIOM = "aio-metadata"
# Every file here is public. "Adult Cast" (a MAL theme) and Adult Swim are not adult content.
ADULT = re.compile(r"hentai|erotica|ecchi|sukebei|xxx|porn|nsfw|\badult(?![ -]swim| cast)|after hours|knaben|hent:", re.I)
LINK_A_BANNED = re.compile(r"vavoo|tvvoo|mediafusion|uksport|uk-sport", re.I)
LINK_A_TITLES = ["Streaming Services", "Movies", "TV Shows", "Anime", "Live TV"]
# Live TV lives in link A only, under the old Live TV files' id, so importing link A replaces a profile's old copy
LIVE_TITLE, LIVE_ID = "Live TV", "7c32c454-b145-5bbb-b89f-4cbc36cf6767"
LIVE_SECTIONS = ["uks.entertainment", "uks.films", "uks.sport", "uks.news", "uks.documentaries", "uks.kids",
                 "uks.music", "uks.lifestyle"]  # Sky's guide order, as in the add-on's manifest
ALLOWED_ADDONS = {"nuvio-collections.json": {UKX, AIOM}, "nuvio-f1-replays.json": {MEDIAFUSION}}  # F1: Adam's file, kept out of the repo
MANIFESTS = {UKX: "https://barticom94.github.io/uk-extras/manifest.json"}
AIOM_TYPES = "https://raw.githubusercontent.com/cedya77/aiometadata/v3.8.3/addon/static/catalog-types.json"
MAL_GENRES = "https://aiometadata.elfhosted.com/api/mal/discover/reference"  # Jikan's list, which the manifest uses
MAL_LEFT_OUT = {"Hentai", "Erotica", "Ecchi", "Harem", "Reverse Harem", "Magical Sex Shift"}  # as in build_uk.py
VALID_SHAPES = {"POSTER", "LANDSCAPE", "SQUARE", "poster", "wide", "square"}
TMDB_TYPES = {"LIST", "COLLECTION", "COMPANY", "NETWORK", "DISCOVER", "PERSON", "DIRECTOR"}
TRAKT_SORTS = {"rank", "added", "title", "released", "runtime", "popularity", "percentage", "votes"}


# ---------- Nuvio's import parser ----------

class ParseFail(Exception):
    pass

def validate(text):
    """validateCollectionsJson: returns (ok, message, collections, folders)."""
    if not text.strip(): return False, "empty input", 0, 0
    try: parsed = json.loads(text)
    except ValueError as e: return False, f"json parse: {e}", 0, 0
    if not isinstance(parsed, list): return False, "expected array", 0, 0
    if not parsed: return False, "empty array", 0, 0
    folders = 0
    for i, item in enumerate(parsed):
        if not isinstance(item, dict): return False, f"item {i + 1} not an object", 0, 0
        cid = item.get("id")
        if not isinstance(cid, str) or not cid.strip(): return False, f"collection {i + 1}: missing id", 0, 0
        title = item.get("title")
        if not isinstance(title, str): return False, f"{cid}: missing title", 0, 0
        fl = item.get("folders")
        if not isinstance(fl, list): return False, f"{title}: folders must be an array", 0, 0
        for j, f in enumerate(fl):
            if not isinstance(f, dict): return False, f"{title} folder {j + 1}: invalid", 0, 0
            fid = f.get("id")
            if not isinstance(fid, str) or not fid.strip(): return False, f"{title} folder {j + 1}: missing id", 0, 0
            ft = f.get("title")
            if not isinstance(ft, str): return False, f"{title}/{fid}: missing title", 0, 0
            srcs = f.get("sources") if isinstance(f.get("sources"), list) else f.get("catalogSources")
            if not isinstance(srcs, list): return False, f"{title}/{ft}: sources must be an array", 0, 0
            shape = f.get("tileShape")
            if isinstance(shape, str) and shape not in VALID_SHAPES: return False, f"{title}/{ft}: bad tileShape {shape}", 0, 0
            for k, s in enumerate(srcs):
                if not isinstance(s, dict): return False, f"{title}/{ft} source {k + 1}: invalid", 0, 0
                p = s.get("provider")
                p = p.lower() if isinstance(p, str) else None
                if p in (None, "addon") and not all(isinstance(s.get(x), str) for x in ("addonId", "type", "catalogId")):
                    return False, f"{title}/{ft} source {k + 1}: addon source needs addonId, type, catalogId", 0, 0
                if p == "tmdb" and not isinstance(s.get("tmdbSourceType"), str):
                    return False, f"{title}/{ft} source {k + 1}: missing tmdbSourceType", 0, 0
                tid = s.get("traktListId")
                if p == "trakt" and (not isinstance(tid, (int, float)) or isinstance(tid, bool)):
                    return False, f"{title}/{ft} source {k + 1}: missing traktListId", 0, 0
            folders += 1
    return True, "ok", len(parsed), folders

def _str(v, nullable=True):
    """Gson String field: JSON strings and numbers/booleans read as text; objects and arrays throw."""
    if v is None:
        if nullable: return None
        raise ParseFail("null in a non-null String (Kotlin NPE)")
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (str, int, float)): return str(v)
    raise ParseFail(f"expected string, got {type(v).__name__}")

def _int(v):
    """Gson Int/Long: integral numbers (or numeric strings) only; 1.5 throws."""
    if v is None: return None
    if isinstance(v, bool): raise ParseFail("boolean in an Int field")
    if isinstance(v, str):
        try: v = float(v)
        except ValueError: raise ParseFail(f"bad number {v!r}")
    if isinstance(v, float):
        if not v.is_integer(): raise ParseFail(f"non-integral {v} in an Int field")
        v = int(v)
    if isinstance(v, int): return v
    raise ParseFail(f"expected number, got {type(v).__name__}")

def _float(v):
    if v is None: return None
    if isinstance(v, bool): raise ParseFail("boolean in a Double field")
    try: return float(v)
    except (TypeError, ValueError): raise ParseFail(f"bad number {v!r}")

def _bool(v, default):
    """Gson boolean: JSON true/false, strings via parseBoolean; null keeps the default."""
    if v is None: return default
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() == "true"
    raise ParseFail(f"expected boolean, got {v!r}")

FILTER_INT = {"voteCountGte", "year"}
FILTER_FLOAT = {"voteAverageGte", "voteAverageLte"}
FILTER_STR = {"withGenres", "withoutGenres", "releaseDateGte", "releaseDateLte", "withOriginalLanguage",
              "withOriginCountry", "withKeywords", "withoutKeywords", "withCompanies", "withoutCompanies",
              "withNetworks", "watchRegion", "withWatchProviders", "withoutWatchProviders"}

def _source(s):
    """SerializableSource.toDomainSource. All its fields have defaults, so Gson uses the no-arg constructor:
    a missing provider is "addon", but an explicit null provider throws."""
    if not isinstance(s, dict): raise ParseFail("source is not an object")
    provider = _str(s.get("provider", "addon"), nullable=False).lower()
    fl = s.get("filters")
    if fl is not None and not isinstance(fl, dict): raise ParseFail("filters is not an object")
    filters = {}
    for k, v in (fl or {}).items():
        if k in FILTER_INT: v = _int(v)
        elif k in FILTER_FLOAT: v = _float(v)
        elif k in FILTER_STR: v = _str(v)
        else: continue  # unknown keys are ignored by Gson
        if v is not None: filters[k] = v
    title = _str(s.get("title"))
    media_raw = _str(s.get("mediaType"))
    media = media_raw.upper() if media_raw and media_raw.upper() in ("MOVIE", "TV") else "MOVIE"
    sort_raw = _str(s.get("sortBy"))
    if provider == "tmdb":
        t = (_str(s.get("tmdbSourceType")) or "").upper()
        if t not in TMDB_TYPES: return None
        sort = sort_raw if sort_raw and sort_raw.strip() else "popularity.desc"
        if t in ("LIST", "COLLECTION") and sort == "popularity.desc": sort = "original"
        return {"provider": "tmdb", "sourceType": t, "title": title if title and title.strip() else t.capitalize(),
                "tmdbId": _int(s.get("tmdbId")), "mediaType": media, "sortBy": sort, "filters": filters}
    if provider == "trakt":
        lid = _int(s.get("traktListId"))
        if not lid or lid <= 0: return None
        sort = (sort_raw or "").strip().lower()
        how = (_str(s.get("sortHow")) or "").strip().lower()
        return {"provider": "trakt", "title": title if title and title.strip() else f"Trakt list {lid}",
                "traktListId": lid, "mediaType": media, "sortBy": sort if sort in TRAKT_SORTS else "rank",
                "sortHow": how if how in ("asc", "desc") else "asc"}
    a, ty, c = _str(s.get("addonId")), _str(s.get("type")), _str(s.get("catalogId"))
    if not (a and a.strip() and ty and ty.strip() and c and c.strip()): return None
    return {"provider": "addon", "addonId": a, "type": ty, "catalogId": c, "genre": _str(s.get("genre"))}

def parse(text):
    """parseCollections: any exception makes Nuvio import nothing ("invalid or empty"), so raise ParseFail."""
    try: raw = json.loads(text)
    except ValueError as e: raise ParseFail(f"json: {e}")
    if raw is None: return []
    if not isinstance(raw, list): raise ParseFail("not an array")
    out = {}
    for c in raw:
        if not isinstance(c, dict): raise ParseFail("collection is not an object")
        # SerializableCollection/Folder have required params, so Gson skips their defaults: a missing field is
        # null (String/List) or false (Boolean), and a null id, title or folders list throws.
        cid, ctitle = _str(c.get("id"), False), _str(c.get("title"), False)
        if not isinstance(c.get("folders"), list): raise ParseFail(f"{ctitle}: folders missing or not a list")
        folders = []
        for f in c["folders"]:
            if not isinstance(f, dict): raise ParseFail("folder is not an object")
            fid, ftitle = _str(f.get("id"), False), _str(f.get("title"), False)
            if f.get("sources") is not None:
                if not isinstance(f["sources"], list): raise ParseFail(f"{ftitle}: sources not a list")
                parsed = [_source(s) for s in f["sources"]]
                dropped = sum(p is None for p in parsed)
                sources = [p for p in parsed if p]
            else:
                cs = f.get("catalogSources")
                if not isinstance(cs, list): raise ParseFail(f"{ftitle}: no sources and no catalogSources")
                sources, dropped = [], 0
                for s in cs:
                    vals = [_str(s.get(k), False) for k in ("addonId", "type", "catalogId")]
                    sources.append({"provider": "addon", "addonId": vals[0], "type": vals[1], "catalogId": vals[2],
                                    "genre": _str(s.get("genre"))})
            shape = (_str(f.get("tileShape")) or "").lower()
            folders.append({"id": fid, "title": ftitle, "coverImageUrl": _str(f.get("coverImageUrl")),
                            "coverEmoji": _str(f.get("coverEmoji")),
                            "tileShape": {"landscape": "LANDSCAPE", "square": "SQUARE"}.get(shape, "POSTER"),
                            "hideTitle": _bool(f.get("hideTitle"), False), "sources": sources, "dropped": dropped})
        view = (_str(c.get("viewMode")) or "").lower()
        col = {"id": cid, "title": ctitle, "pinToTop": _bool(c.get("pinToTop"), False),
               "viewMode": {"rows": "ROWS", "follow_layout": "FOLLOW_LAYOUT"}.get(view, "TABBED_GRID"),
               "showAllTab": _bool(c.get("showAllTab"), False), "folders": folders}
        out[cid] = col  # associateBy: last value wins, first position kept (same as a Python dict)
    return list(out.values())

def live_problems(cols):
    """Link A's Live TV: one collection with LIVE_ID, then one UK Extras tv catalogue per folder in LIVE_SECTIONS order."""
    live = [c for c in cols if c["title"] == LIVE_TITLE]
    if len(live) != 1 or live[0]["id"] != LIVE_ID: return [f"needs one {LIVE_TITLE!r} collection with id {LIVE_ID}"]
    rows = [[(s.get("addonId"), s.get("type"), s.get("catalogId")) for s in f["sources"]] for f in live[0]["folders"]]
    if rows != [[(UKX, "tv", c)] for c in LIVE_SECTIONS]: return [f"{LIVE_TITLE} folders are {rows}"]
    return []

def selftest():
    good = '[{"id":"c","title":"C","folders":[{"id":"f","title":"F","sources":[{"addonId":"a","type":"tv","catalogId":"x"}]}]}]'
    assert validate(good)[0] and parse(good)[0]["folders"][0]["sources"][0]["provider"] == "addon"
    assert parse(good)[0]["showAllTab"] is False  # missing Boolean = false, not the Kotlin default
    for bad in ('[{"id":"c","title":"C"}]',
                '[{"id":"c","title":"C","folders":[{"id":"f","title":"F","sources":[{"provider":null}]}]}]',
                '[{"id":"c","title":"C","folders":[{"id":"f","title":"F","sources":[{"provider":"tmdb",'
                '"tmdbSourceType":"DISCOVER","filters":{"voteCountGte":1.5}}]}]}]'):
        try: parse(bad); raise AssertionError(bad)
        except ParseFail: pass
    dropped = '[{"id":"c","title":"C","folders":[{"id":"f","title":"F","sources":[{"provider":"tmdb","tmdbSourceType":"TRENDING"}]}]}]'
    assert parse(dropped)[0]["folders"][0]["dropped"] == 1
    assert not validate('[{"id":"c","title":"C","folders":[{"id":"f","title":"F","sources":[{"provider":"trakt","traktListId":"9"}]}]}]')[0]
    assert ADULT.search("Ecchi") and ADULT.search("adult") and not ADULT.search("Adult Cast") and not ADULT.search("Adult Swim")
    cats = {AIOM: {("anime", "mal.genres"): {"Action", "Hentai"}}}
    mal = {"provider": "addon", "addonId": AIOM, "type": "anime", "catalogId": "mal.genres_anime", "genre": "Action"}
    assert addon_problem(cats, mal) is None and addon_problem(cats, dict(mal, genre="Hentai"))
    assert addon_problem(cats, dict(mal, genre="Actoin")) and addon_problem(cats, dict(mal, type="series"))
    live = {"id": LIVE_ID, "title": LIVE_TITLE, "folders": [{"sources": [{"addonId": UKX, "type": "tv", "catalogId": c}]}
                                                            for c in LIVE_SECTIONS]}
    assert live_problems([live]) == []
    assert live_problems([dict(live, id="x")]) and live_problems([live, live]) and live_problems([])
    assert live_problems([dict(live, folders=live["folders"][::-1])]), "Sky order"
    assert live_problems([dict(live, folders=live["folders"][:7])]), "a section missing"
    print("selftest ok")


# ---------- TMDB ----------

def load_key(argv):
    if "--key-json" in argv:
        path = argv[argv.index("--key-json") + 1]
        def find(n):
            if isinstance(n, dict):
                if isinstance(n.get("tmdbApiKey"), str) and n["tmdbApiKey"]: return n["tmdbApiKey"]
                n = list(n.values())
            if isinstance(n, list):
                for v in n:
                    r = find(v)
                    if r: return r
            return None
        with open(path, encoding="utf-8") as f:
            key = find(json.load(f))
    else:
        key = os.environ.get("TMDB_API_KEY")
    if not key: sys.exit("no TMDB key (set TMDB_API_KEY or pass --key-json)")
    return key

class Tmdb:
    def __init__(self, key): self._k, self._cache = key, {}
    def get(self, path, params=None):
        q = {k: v for k, v in (params or {}).items() if v is not None}
        ck = path + "?" + urllib.parse.urlencode(sorted(q.items()))
        if ck in self._cache: return self._cache[ck]
        url = f"https://api.themoviedb.org/3/{path}?" + urllib.parse.urlencode({"api_key": self._k, **q})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    d = json.load(r)
                self._cache[ck] = d
                return d
            except urllib.error.HTTPError as e:
                if e.code == 404: return None
                if e.code != 429 and attempt >= 2: raise RuntimeError(f"TMDB {path}: HTTP {e.code}") from None
            except Exception as e:
                if attempt == 4: raise RuntimeError(f"TMDB {path}: " + str(e).replace(self._k, "<key>")) from None
            time.sleep(1.0 * (attempt + 1))

def discover_request(src, today):
    """TmdbCollectionSourceResolver.resolveDiscover, as query parameters."""
    t, f, sid = src["sourceType"], src["filters"], src["tmdbId"]
    media = "TV" if t == "NETWORK" else src["mediaType"]
    providers = bool(f.get("withWatchProviders")) or bool(f.get("withoutWatchProviders"))
    p = {
        "language": "en-GB", "page": 1,
        "with_companies": str(sid) if t == "COMPANY" and sid is not None else f.get("withCompanies"),
        "vote_count.gte": f.get("voteCountGte"), "with_genres": f.get("withGenres"),
        "vote_average.gte": f.get("voteAverageGte"), "vote_average.lte": f.get("voteAverageLte"),
        "with_original_language": f.get("withOriginalLanguage"), "with_origin_country": f.get("withOriginCountry"),
        "with_keywords": f.get("withKeywords"), "without_keywords": f.get("withoutKeywords"),
        "watch_region": (f.get("watchRegion") or "US") if providers else None,
        "with_watch_providers": f.get("withWatchProviders"),
        "with_watch_monetization_types": "flatrate|free|ads|rent|buy" if f.get("withWatchProviders") else None,
        "without_companies": f.get("withoutCompanies"), "without_genres": f.get("withoutGenres"),
        "without_watch_providers": f.get("withoutWatchProviders"),
    }
    sort = src["sortBy"]
    if media == "MOVIE":
        p.update({"sort_by": "primary_release_date.desc" if sort == "first_air_date.desc" else (sort or "popularity.desc"),
                  "primary_release_date.lte": f.get("releaseDateLte"), "primary_release_date.gte": f.get("releaseDateGte"),
                  "year": f.get("year")})
        return "discover/movie", p
    p.update({"sort_by": "first_air_date.desc" if sort == "primary_release_date.desc" else (sort or "popularity.desc"),
              "with_networks": str(sid) if t == "NETWORK" and sid is not None else f.get("withNetworks"),
              "first_air_date.lte": f.get("releaseDateLte") or (today if t == "NETWORK" else None),
              "with_status": "0|3|4" if t == "NETWORK" else None,
              "first_air_date.gte": f.get("releaseDateGte"), "first_air_date_year": f.get("year")})
    return "discover/tv", p

def resolve(tmdb, src, today):
    """Returns (total, first items as (tmdb_id, title)), like Nuvio's first page."""
    t = src["sourceType"]
    if t in ("DISCOVER", "COMPANY", "NETWORK"):
        d = tmdb.get(*discover_request(src, today))
        if d is None: return 0, []
        return d.get("total_results", 0), [(r["id"], r.get("title") or r.get("name")) for r in d.get("results", [])]
    if t == "COLLECTION":
        d = tmdb.get(f"collection/{src['tmdbId']}", {"language": "en-GB"}) or {}
        parts = d.get("parts") or []
        return len(parts), [(r["id"], r.get("title")) for r in parts]
    if t == "LIST":
        d = tmdb.get(f"list/{src['tmdbId']}", {"language": "en-GB"}) or {}
        items = d.get("items") or []
        return d.get("item_count", len(items)), [(r["id"], r.get("title") or r.get("name")) for r in items]
    d = tmdb.get(f"person/{src['tmdbId']}/combined_credits", {"language": "en-GB"}) or {}
    want = "movie" if src["mediaType"] == "MOVIE" else "tv"
    items = d.get("crew") if t == "DIRECTOR" else d.get("cast")
    items = [r for r in items or [] if r.get("media_type") == want and (t != "DIRECTOR" or (r.get("job") or "").lower() == "director")]
    items = list({r["id"]: r for r in items}.values())
    return len(items), [(r["id"], r.get("title") or r.get("name")) for r in items]

def gb_providers(tmdb, media, tid):
    d = tmdb.get(f"{'tv' if media == 'TV' else 'movie'}/{tid}/watch/providers") or {}
    gb = (d.get("results") or {}).get("GB") or {}
    return {str(p["provider_id"]) for k in ("flatrate", "free", "ads", "rent", "buy") for p in gb.get(k) or []}


# ---------- run ----------

def strings(node):
    if isinstance(node, dict):
        for v in node.values(): yield from strings(v)
    elif isinstance(node, list):
        for v in node: yield from strings(v)
    elif isinstance(node, str): yield node

def head_ok(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200 and r.headers.get("Content-Type", "").startswith("image/")
    except Exception:
        return False

def get_json(src):
    if not src.startswith("https://"):
        with open(src, encoding="utf-8") as f: return json.load(f)
    with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "nuvio-uk-check"}), timeout=30) as r:
        return json.load(r)

def addon_catalogues(argv, warns):
    """{addon id: {(type, catalogue id): genre options}} for the add-ons we can see; an unreadable one only warns."""
    srcs = dict(MANIFESTS)
    for i, a in enumerate(argv):
        if a == "--manifest":
            k, _, v = argv[i + 1].partition("=")
            srcs[k] = v
    out = {}
    for addon_id, src in srcs.items():
        try:
            out[addon_id] = {(c["type"], c["id"]): {o for e in c.get("extra", []) if e["name"] == "genre" for o in e.get("options") or []}
                             for c in get_json(src)["catalogs"]}
        except Exception as e:
            warns.append(f"{addon_id}: manifest not read from {src} ({e}), its rows are unchecked")
    try:
        genres = {g["name"] for g in get_json(MAL_GENRES)["genres"]}
        out[AIOM] = {("anime", "mal." + k): genres for k in get_json(AIOM_TYPES)["mal"]}
    except Exception as e:
        warns.append(f"{AIOM}: MAL catalogue or genre list not read ({e}), its rows are unchecked")
    return out

def addon_problem(cats, s):
    """None when the row matches its add-on's catalogue (and genre option), else what is wrong."""
    known = cats.get(s["addonId"])
    if known is None: return None
    cid = re.sub(r"_anime$", "", s["catalogId"]) if s["addonId"] == AIOM else s["catalogId"]  # displayType suffix
    if (s["type"], cid) not in known: return f"no {s['type']} catalogue {s['catalogId']}"
    if s["genre"] and s["genre"] not in known[(s["type"], cid)]: return f"genre {s['genre']!r} is not an option"
    if s["addonId"] == AIOM and s["genre"] in MAL_LEFT_OUT: return f"genre {s['genre']} must stay out"
    return None

def main(argv):
    files = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--only", "--key-json", "--manifest"))]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    tmdb = Tmdb(load_key(argv))
    today = date.today().isoformat()
    fails, warns, report, jobs, covers = [], [], [], [], set()
    link_a_ids, other_cols = set(), []
    cats = addon_catalogues(argv, warns)

    for path in files:
        text = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        ok, msg, nc, nf = validate(text)
        print(f"{name}: {len(text.encode('utf-8'))} bytes; validate: {msg} ({nc} collections, {nf} folders)")
        if not ok: fails.append(f"{name}: validate: {msg}"); continue
        try: cols = parse(text)
        except ParseFail as e: fails.append(f"{name}: import would fail: {e}"); continue
        raw = json.loads(text)
        if len(cols) != len(raw): fails.append(f"{name}: duplicate collection ids ({len(raw)} -> {len(cols)})")
        ids = [f["id"] for c in cols for f in c["folders"]]
        if len(ids) != len(set(ids)): warns.append(f"{name}: duplicate folder ids")
        for c in cols:
            for f in c["folders"]:
                if f["dropped"]: fails.append(f"{name}: {c['title']}/{f['title']}: {f['dropped']} source(s) dropped on import")
                if not f["sources"]: fails.append(f"{name}: {c['title']}/{f['title']}: no sources")
                if f["coverImageUrl"]: covers.add(f["coverImageUrl"])
        for s in strings(raw):
            if "—" in s or "–" in s: fails.append(f"{name}: dash in {s!r}")
            if ADULT.search(s): fails.append(f"{name}: adult text {s!r}")
        addon_ids = sorted({s["addonId"] for c in cols for f in c["folders"] for s in f["sources"] if s["provider"] == "addon"})
        print(f"  add-on ids used: {addon_ids or 'none'}")
        if set(addon_ids) - ALLOWED_ADDONS.get(name, set(addon_ids)):
            fails.append(f"{name}: uses add-ons it must not {set(addon_ids) - ALLOWED_ADDONS[name]}")
        if name == "nuvio-collections.json":  # link A: every profile
            if [c["title"] for c in cols] != LINK_A_TITLES: fails.append(f"{name}: collections are {[c['title'] for c in cols]}")
            for s in strings(raw):
                if LINK_A_BANNED.search(s): fails.append(f"{name}: banned text {s!r}")
            fails += [f"{name}: {p}" for p in live_problems(cols)]
            link_a_ids |= {c["id"] for c in cols}
        else:
            other_cols += [(name, c) for c in cols]
        for c in cols:
            if only and c["title"] != only and not any(f["title"] == only for f in c["folders"]): continue
            for f in c["folders"]:
                if only and c["title"] != only and f["title"] != only: continue
                for s in f["sources"]:
                    where = f"{c['title']} / {f['title']} / {s.get('title') or s.get('catalogId')}"
                    if s["provider"] != "tmdb":
                        problem = addon_problem(cats, s) if s["provider"] == "addon" else None
                        if problem: fails.append(f"{name}: {where}: {problem}")
                        seen = s["provider"] == "addon" and s["addonId"] in cats
                        report.append(f"{name} | {where} | {s['provider']} {s.get('addonId') or s.get('traktListId')}"
                                      f" {s.get('catalogId', '')} {s.get('genre') or ''} | "
                                      + ("catalogue checked" if seen and not problem else problem or "not checked here"))
                        continue
                    if s["sourceType"] == "NETWORK" and s["filters"].get("withNetworks"):
                        warns.append(f"{where}: NETWORK row ignores withNetworks")
                    jobs.append((name, where, s))

    def run(job):
        name, where, s = job
        total, items = resolve(tmdb, s, today)
        spot = []
        excl = s["filters"].get("withoutWatchProviders")
        if excl and items:
            own, banned = set(s["filters"]["withWatchProviders"].split("|")), set(excl.split("|"))
            for tid, title in items[:SPOT]:
                gb = gb_providers(tmdb, s["mediaType"], tid)
                spot.append((title, bool(gb & own), sorted(gb & banned)))
        return name, where, total, items, spot, s["sourceType"] in ("DISCOVER", "COMPANY", "NETWORK")

    for name, c in other_cols:  # importing another file next to link A must add, not replace
        if c["id"] in link_a_ids | {LIVE_ID} or c["title"] == LIVE_TITLE:
            fails.append(f"{name}: {c['title']} reuses a link A collection id or the title {LIVE_TITLE!r}")
    print(f"calling TMDB for {len(jobs)} rows")
    results = []
    with cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(run, jobs): results.append(r)
    thin = 0
    for name, where, total, items, spot, open_ended in results:
        # thin only means something for open-ended rows; a franchise or a filmography is complete as it is
        flag = "EMPTY" if total == 0 else ("THIN" if total < THIN and open_ended else "ok")
        if total == 0: fails.append(f"{where}: no results")
        elif flag == "THIN": thin += 1
        line = f"{name} | {where} | {total} | {flag} | " + "; ".join(t or "?" for _, t in items[:3])
        for title, has_own, hit in spot:
            if hit: fails.append(f"{where}: {title} is also on excluded provider(s) {hit} in GB")
            if not has_own: warns.append(f"{where}: {title} has none of the tile's providers in GB")
        if spot: line += f" | exclusion spot-check {sum(not h for _, _, h in spot)}/{len(spot)} clean"
        report.append(line)
    if covers:
        with cf.ThreadPoolExecutor(8) as ex:
            bad = [u for u, ok in zip(sorted(covers), ex.map(head_ok, sorted(covers))) if not ok]
        print(f"covers: {len(covers) - len(bad)}/{len(covers)} load as images")
        fails += [f"cover not loading: {u}" for u in bad]

    head = [f"Checked {date.today()} against TMDB live. Rows: {len(results)} TMDB, thin (<{THIN}): {thin}, "
            f"failures: {len(fails)}, warnings: {len(warns)}", ""]
    with open(os.path.join(HERE, "report.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + ["FAIL " + x for x in fails] + ["WARN " + x for x in warns] + [""] + report) + "\n")
    print(head[0])
    for x in fails: print("FAIL", x)
    for x in warns[:40]: print("WARN", x)
    return 1 if fails else 0

if __name__ == "__main__":
    if "--selftest" in sys.argv: selftest(); sys.exit(0)
    sys.exit(main(sys.argv[1:]))
