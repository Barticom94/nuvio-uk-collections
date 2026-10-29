# Nuvio UK Collections

Collections for [Nuvio](https://github.com/NuvioMedia/NuvioTV), built for UK viewers. Import a file with
Nuvio → Settings → Collections → Import → From URL. Importing adds new collections and replaces ones with the same id.

- `nuvio-collections.json`, for every profile:
  - **Streaming Services**: 17 tiles. Each leads with the service's biggest and trending originals and its own films,
    then "Only on" rows that leave out titles also on the other UK services, then New and "Best only on" rows.
    Hulu has no UK service, so its tile only has its originals. The Netflix tile's Top 10 and Most Popular rows
    come from the UK Extras add-on.
  - Genres, Franchises & Universes, Moods & Themes, Directors, Studios, World Cinema, Networks, Critics' Picks and
    Decades from [mali-king/nuvio-collections](https://github.com/mali-king/nuvio-collections) (v2), without the
    US and Indian rows.
  - **Trending** (films, series and anime) and **Free TV** (from the UK Extras add-on).
- `nuvio-live.json`: a Live collection for profiles that have the UK Sport and live-TV add-ons.
- `covers/` holds the landscape tile artwork for the UK services.

Every TMDB row runs on Nuvio's own TMDB access, so it needs no catalogue add-on. Without UK Extras installed,
the Netflix Top 10 and Most Popular rows and the Free TV folders show "Addon not found". Availability comes from TMDB's
watch-provider data (sourced from JustWatch).

## Rebuild

```sh
python build/build_uk.py
TMDB_API_KEY=... python build/check.py nuvio-collections.json nuvio-live.json
```

`check.py` reads the files with the same rules as Nuvio's importer, calls every TMDB row and writes the result
counts to `build/report.txt`. The Trending rows use fixed date floors set at build time, so rebuild every month or two.
Nuvio keeps its own copy of a collection at import and doesn't refresh it from the URL, so a rebuild only reaches a
profile after you import link A again there. Trending Series and Trending Anime go by first air date, so a new season
of an older show won't appear in them.

Ten service covers and all browse covers are reused from mali-king/nuvio-collections. Artwork shows stills and logos
that belong to their owners; this repo is a personal, non-commercial setup.
This product uses the TMDB API but is not endorsed or certified by TMDB.
