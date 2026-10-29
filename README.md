# Nuvio UK Collections

Collections for [Nuvio](https://github.com/NuvioMedia/NuvioTV), built for UK viewers. Import a file with
Nuvio → Settings → Collections → Import → From URL. Importing adds new collections and replaces ones with the same id.

- `nuvio-collections.json`, for every profile:
  - **Streaming Services**: 17 tiles. Each leads with the service's biggest and trending originals and its own films,
    then "Only on" rows that leave out titles also on the other UK services, then New and "Best only on" rows.
    Hulu has no UK service, so its tile only has its originals. The Netflix tile's Top 10 and Most Popular rows
    come from the UK Extras add-on.
  - **Movies**: New (the newest films on a UK service or store), Trending, Top rated, By Genre, By Decade,
    Collections (film series), Moods, Directors, Studios, World Cinema and Critics' picks.
  - **TV Shows**: New, Trending, Top rated, By Genre, By Decade and Networks.
  - **Anime**: New, Trending and Top rated (series and films). By Genre and By Decade are built but held back (below).
- Live TV, one collection in three versions with the same id, so a profile keeps whichever it imported last:
  - `nuvio-live-free.json`: Free channels, from the UK Extras add-on.
  - `nuvio-live.json`: Sport (UK Sport add-on), Live channels (TvVoo) and Free channels.
  - `nuvio-live-adam.json`: the same plus F1 Replays (MediaFusion).
- `covers/` holds the landscape tile artwork for the UK services.

Every folder opens as a grid with one tab per source. Nuvio loads every tab of a folder when it opens, so the big ones
(Moods and Collections, about 30 tabs each) take a moment longer.

The browse folders in Movies and TV Shows take one tab per entry from
[mali-king/nuvio-collections](https://github.com/mali-king/nuvio-collections) (v2), without the US and Indian entries.
Where a franchise has several film series, its tab holds the first one (Harry Potter for the Wizarding World).

Every TMDB row runs on Nuvio's own TMDB access, so it needs no catalogue add-on. Availability comes from TMDB's
watch-provider data (sourced from JustWatch). Without UK Extras installed, the Netflix Top 10 and Most Popular rows
and Free channels show "Addon not found".

Anime By Genre and By Decade use the MAL catalogues that AIOMetadata adds when you import its Anime Essentials design
(Catalogs → Collections → Featured): the Genre and Decade catalogues (`aio-metadata`, type `anime`, `mal.genres` and
`mal.80sDecade` to `mal.20sDecade`). AIOMetadata only hides MAL's adult (Rx) titles when MAL
safe mode (sfw) is on, so turn it on in every AIOMetadata config a profile uses; with it off, ordinary tabs such as
Romance can list hentai. MAL's adult genres plus Harem, Reverse Harem and Magical Sex Shift stay out either way.
`MAL_FOLDERS = False` in `build/build_uk.py` takes both folders out.

A folder only shows "Addon not found" when no installed add-on has the id `aio-metadata`. With AIOMetadata installed
but the Essentials catalogues missing, the tabs still load, with no paging (the first 25 titles only). Each tab reads
"catalogue name · genre", so renaming the imported Genre catalogue in AIOMetadata (to "Anime", say) gives cleaner tabs.

## Rebuild

```sh
python build/build_uk.py
TMDB_API_KEY=... python build/check.py nuvio-collections.json nuvio-live-free.json nuvio-live.json nuvio-live-adam.json
```

`check.py` reads the files with the same rules as Nuvio's importer, calls every TMDB row, checks add-on rows against
their add-on's manifest (`--manifest ID=PATH` for one not yet published) and writes the result counts to
`build/report.txt`. The Trending rows use fixed date floors set at build time, so rebuild every month or two.
Nuvio keeps its own copy of a collection at import and doesn't refresh it from the URL, so a rebuild only reaches a
profile after you import the file again there. Trending and New series go by first air date, so a new season of an
older show won't appear in them.

If AIOMetadata ever lists the MAL catalogues as `mal.genres_anime` and so on (it does once a catalogue is edited
there), set `AIOM_ID_SUFFIX = "_anime"` in `build/build_uk.py` and rebuild.

Ten service covers are reused from mali-king/nuvio-collections. Artwork shows stills and logos that belong to their
owners; this repo is a personal, non-commercial setup.
This product uses the TMDB API but is not endorsed or certified by TMDB.
