# Nuvio UK Collections

Collections for [Nuvio](https://github.com/NuvioMedia/NuvioTV), built for UK viewers. Import a file with
Nuvio → Settings → Collections → Import → From URL. Importing adds new collections and replaces ones with the same id.

- `nuvio-collections.json`, for every profile:
  - **Streaming Services**: 17 tiles. Each leads with the service's trending and best rated originals and its own
    films, then "Only on" rows that leave out titles also on the other UK services, then New and "Best only on" rows.
    Hulu has no UK service, so its tile only has its originals. The Netflix tile's Top 10 and Most Popular rows
    come from the UK Extras add-on.
  - **Movies**: Start here (new, trending and top rated films, British films and the critics' picks), Genres, More
    genres, Decades, four franchise folders (superhero and fantasy, sci-fi and horror, action and crime, family),
    three mood folders (crime and suspense; action, sci-fi and monsters; comedy, feel-good and true stories),
    Directors, World directors, Hollywood, animation and indie studios, Asian cinema and World cinema.
  - **TV Shows**: Start here (new, trending and top rated series and trending British series), Genres, Decades,
    Drama networks and Comedy, kids and factual networks.
  - **Anime**: Start here (new, trending and top rated series and films), Genres, Themes (isekai, shonen, mecha,
    sports, school, slice of life, iyashikei, psychological, magical girl) and Decades (below).
  - **Live TV**: one folder per section of Sky's guide, in Sky's order: Entertainment, Films, Sport, News,
    Documentaries, Kids, Music and Lifestyle. Each is one catalogue of the UK Extras add-on: its free channels
    (Samsung TV Plus, Pluto TV and Plex) with what's on now and next. Our household add-on answers to the same id and
    lists its own channels first. Live TV keeps the id of the old Live TV files, so importing this file replaces a
    profile's old copy.
- `nuvio-f1-replays.json` is F1 Replays (MediaFusion), a separate collection for one profile; the build writes it when
  given that path (below). It has its own id, so importing it adds a collection next to these.
- `covers/` holds the landscape tiles for the UK services, `covers/tiles/` our tiles for every other folder and
  `covers/logos/` the title logos.

Streaming Services, Movies, TV Shows and Anime follow the home layout ("Follow home"). On the Modern home, focusing a
folder's tile shows its hero: a backdrop from one of its titles under the folder's title logo. Opening it gives a page
of rows under the same kind of hero, one row per source, with no tabs and no All row. Every row loads when the page
opens, so each folder holds 4 to 15 rows (Hulu has its 2). Live TV opens as a grid, one channel list per folder.

The browse folders in Movies and TV Shows take one row per entry from
[mali-king/nuvio-collections](https://github.com/mali-king/nuvio-collections) (v2), without the US and Indian entries.
Where a franchise has several film series, its row holds the first one (Harry Potter for the Wizarding World).

Every TMDB row runs on Nuvio's own TMDB access, so it needs no catalogue add-on. Availability comes from TMDB's
watch-provider data (sourced from JustWatch). Anime is Japanese-language animation, and every Anime row leaves out
TMDB's hentai, ecchi, erotica, harem, nudity and fan-service keywords. Without UK Extras installed, every Live TV
folder shows "Addon not found" and the Netflix page's Top 10 and Most Popular rows stay as loading placeholders.

Anime Decades uses the Decade catalogues that AIOMetadata adds when you import its Anime Essentials design
(Catalogs → Collections → Featured): `aio-metadata`, type `anime`, `mal.80sDecade` to `mal.20sDecade`. Without
AIOMetadata, its five rows stay as loading placeholders; with AIOMetadata but not the Essentials catalogues, they load
the first 25 titles only. AIOMetadata only hides MAL's adult (Rx) titles when MAL safe mode (sfw) is on, so turn it
on in every AIOMetadata config a profile uses. `MAL_FOLDERS = False` in `build/build_uk.py` takes the folder out.
MAL's genre catalogue can't be used for rows (its genres share one catalogue id, and a page of rows shows them as one
row), so Anime's genres and themes are TMDB rows.

## Rebuild

```sh
python build/build_uk.py --key-json PATH [F1_FILE]
python build/check.py nuvio-collections.json --key-json PATH [F1_FILE]
python build/art.py --sheet
```

Both scripts take the TMDB v3 key from `TMDB_API_KEY`, or with `--key-json` from the `tmdbApiKey` field of a JSON
file, and never print it. `build_uk.py` needs it to pick each folder's hero backdrop: the best known title among the
first rows that isn't rated 18 (horror only where a folder has nothing else) and has a backdrop with no text on it,
never the same title or film series twice in a collection (`HERO_ROW` and `HERO_SKIP` steer the few picks that came
out a poor fit). It then renders the tiles and logos with `build/art.py` (Pillow). `art.py --sheet` also writes
`build/contact-sheet.png`, every Modern folder's tile and logo over dark, bright and its own backdrop, for review; it
isn't committed.

`check.py` reads the files with the same rules as Nuvio's importer, calls every TMDB row, checks add-on rows against
their add-on's manifest (`--manifest ID=PATH` for one not yet published), checks that Live TV has every section in
Sky's order under its fixed id and that no other file reuses a link A collection id, and writes the result counts to
`build/report.txt`. For pages of rows it checks that no two rows in a folder share Nuvio's row key (rows that do
collapse into one), the 4 to 15 rows, the All tab and that every folder has its backdrop, logo and tile, and that every
image loads. It also fails any TMDB row whose sort the nuvio.tv website would swap on upload: the website keeps only
popularity, rating, newest first and (for lists and collections) the original order, and puts newest first on any
series row with another sort or none, so every row names one of those. The Trending rows use fixed date floors set
at build time, so rebuild every month or two.
Nuvio keeps its own copy of a collection at import and doesn't refresh it from the URL, so a rebuild only reaches a
profile after you import the file again there. Trending and New series go by first air date, so a new season of an
older show won't appear in them.

If AIOMetadata ever lists the MAL catalogues as `mal.80sDecade_anime` and so on (it does once a catalogue is edited
there), set `AIOM_ID_SUFFIX = "_anime"` in `build/build_uk.py` and rebuild.

The tiles and logos are set in [Outfit](https://github.com/Outfitio/Outfit-Fonts) (`build/fonts/Outfit.ttf`), which
is under the SIL Open Font License 1.1 (`build/fonts/OFL.txt`). Ten service covers are reused from
mali-king/nuvio-collections. Covers and backdrops show stills and logos that belong to their owners; this repo is a
personal, non-commercial setup.
This product uses the TMDB API but is not endorsed or certified by TMDB.
