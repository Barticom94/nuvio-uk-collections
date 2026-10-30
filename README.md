# Nuvio UK Collections

Collections for [Nuvio](https://github.com/NuvioMedia/NuvioTV), built for UK viewers. Import a file with
Nuvio → Settings → Collections → Import → From URL. Importing adds new collections and replaces ones with the same id.

- `nuvio-collections.json`, for every profile:
  - **Streaming Services**: 17 tiles. Each row is named "<service> - <row>". Each tile leads with the service's trending and
    best rated originals and its own films, then Exclusive rows that leave out titles also on the other UK services,
    then New and Best exclusive rows. Netflix, Prime Video, Disney+ and Apple TV+ have no Best originals row: there
    it repeated Best exclusive series (15 to 18 of its first 20 titles were in that row's first 40 on 29 Oct).
    Hulu has no UK service, so its tile only has its originals. The Netflix tile's Top 10 and Most Popular rows
    come from the UK Extras add-on.
  - **Movies**: New and Trending (new, trending and family films), Top Rated (all time, the past year, the
    past five years, animated, family, documentaries), Genres (TMDB's film genres but TV Movie, each followed by its
    sub-genres: superhero, romantic comedy, sports, psychological thriller, heist, space, musical), Decades (1950s to
    2020s) and Collections (the MCU and 24 film series, from Star Wars and James Bond to Paddington and Wallace &
    Gromit, from the UK Streaming add-on: see below).
  - **TV Shows**: New and Trending (new and trending series, trending documentaries), Top Rated (all time,
    new, miniseries, crime, comedies, animated, documentaries), Genres (TMDB's TV genres but News, Talk and
    Soap, with period, medical, legal and teen drama, sitcom, police procedural, true crime, murder mystery,
    superhero, supernatural, horror and anthology) and Decades (1960s to 2020s).
  - **Anime**: New and Trending (new and trending series and films), Top Rated (all time and new, series and films),
    Genres (TMDB genre rows for series, with isekai, martial arts, mecha, samurai, sports, romantic comedy, slice of
    life, psychological, dark fantasy, supernatural, horror and magical girl, then film genres) and Decades (below).
  - Live TV moved out of Nuvio to TiviMate on 29 Oct (Nuvio has no guide grid), with its own add-on; the household's
    UK Streaming add-on no longer has channel catalogues.
- `covers/` holds the landscape tiles for the UK services, `covers/tiles/` our illustrated tiles for the cards of
  Movies, TV Shows and Anime, and `covers/logos/` the title logos (one per service, one per card). The art of the
  cards before 29 Oct (Start Here, Themes, Moods, Directors, Studios, Networks and the rest) stays for profiles that
  haven't imported the new file yet; delete it once they all have.

Streaming Services, Movies, TV Shows and Anime follow the home layout ("Follow home"). On the Modern home, focusing a
folder's tile shows its hero: a backdrop from one of its titles under the folder's title logo. Opening it gives a page
of rows under the same kind of hero, one row per source, with no tabs and no All row. Every row loads when the page
opens, so each folder holds 3 to 25 rows (Hulu has its 2).

Every row of Movies, TV Shows and Anime is written out in `build/build_uk.py` (TMDB genre, keyword and collection ids,
checked 29 Oct). Rows sorted by rating all have a vote floor. TV Shows leaves out TMDB's anime keyword, as anime has
its own collection. Every Movies TMDB row leaves out TMDB's pornography, porn industry, softcore, unsimulated sex,
erotic movie and bdsm keywords.

Every TMDB row runs on Nuvio's own TMDB access, so it needs no catalogue add-on. Availability comes from TMDB's
watch-provider data (sourced from JustWatch). Anime is Japanese-language animation, and every Anime row leaves out
TMDB's hentai, ecchi, erotica, harem, nudity, fan-service and sexual violence keywords. Without UK Extras installed, the Netflix
page's Top 10 and Most Popular rows stay as loading placeholders.

Movies' Collections rows are add-on rows: the household's UK Streaming add-on, which answers to UK Extras' id
(`com.barticom94.ukextras`), has one movie catalogue per film series, `uks.franchise.mcu` to
`uks.franchise.wallace-and-gromit` (`FRANCHISES` in `build/build_uk.py`), named as the rows are. Each series needs its
own catalogue id, as rows of one catalogue collapse into one. The UK Extras add-on on GitHub Pages doesn't have them,
so on a profile with that install (or neither) these rows stay as loading placeholders. The folder's hero still comes
from TMDB: the series' TMDB collections (and the MCU keyword, short films left out) pick it.

Anime Decades rows come from UK Streaming's weekly anime lists: MAL's titles ranked by members, one hidden
catalogue per decade, type `anime`, `ukx.anime-2020s` to `ukx.anime-1980s` (`ANIME_DECADES` in `build/build_uk.py`).
On a profile whose add-on doesn't list them, its five rows stay as loading placeholders. `MAL_FOLDERS = False` in
`build/build_uk.py` takes the folder out.
MAL's genre catalogue can't be used for rows (its genres share one catalogue id, and a page of rows shows them as one
row), so Anime's genres are TMDB rows.

## Rebuild

```sh
python build/build_uk.py --key-json PATH
python build/check.py nuvio-collections.json --key-json PATH
python build/art.py --sheet
```

Both scripts take the TMDB v3 key from `TMDB_API_KEY`, or with `--key-json` from the `tmdbApiKey` field of a JSON
file, and never print it. `build_uk.py` needs it to pick each folder's hero backdrop: the best known title among the
first rows that isn't rated 18 (horror only where a folder has nothing else) and has a backdrop with no text on it,
never the same title or film series twice in a collection (`HERO_ROW` and `HERO_SKIP` steer the few picks that came
out a poor fit). It then renders the tiles and logos with `build/art.py`. `art.py --sheet` also writes
`build/contact-sheet.png`, every card's tile and logo over dark, bright and its own backdrop, for review; it isn't
committed.

The card art is our own illustration, drawn in `build/art.py` as SVG and rendered by headless Edge (or Chrome, with
`EDGE=path`; muted, in a throwaway profile) to WebP tiles and PNG logos; the same build gives the same files. Each type
has a look of its own: Movies is cinema (velvet red, brass, film strip), TV Shows broadcast (petrol blue, scan lines,
test-card bars) and Anime manga pop (bright skies, ink outlines, halftone, speed lines). Each card has a
motif: New and Trending rises, Top Rated has a star, Genres a mosaic of genre glyphs, Decades the decades and
Collections a box set and a reel. The glyphs are drawn there too, so no icon set is needed. The
services' logos are their names in white, drawn with Pillow.

`check.py` reads the files with the same rules as Nuvio's importer, calls every TMDB row, checks add-on rows against
their add-on's manifest (`--manifest ID=PATH` for one not yet published; UK Extras' rows are checked against its
GitHub Pages manifest, so the Collections and Anime Decades rows need `--manifest com.barticom94.ukextras=` UK
Streaming's manifest file or URL), checks that no other file reuses a link A
collection id, and writes the result counts to
`build/report.txt`. For pages of rows it checks that no two rows in a folder share Nuvio's row key (rows that do
collapse into one), the 3 to 25 rows, the All tab and that every folder has its backdrop, logo and tile, and that every
image loads. It also fails any TMDB row whose sort the nuvio.tv website would swap on upload: the website keeps only
popularity, rating, newest first and (for lists and collections) the original order, and puts newest first on any
series row with another sort or none, so every row names one of those. A row sorted by rating needs a vote floor. The Trending rows use fixed date floors set
at build time, so rebuild every month or two.
Nuvio keeps its own copy of a collection at import and doesn't refresh it from the URL, so a rebuild only reaches a
profile after you import the file again there. Trending and New series go by first air date, so a new season of an
older show won't appear in them.

The tiles and logos are set in [Outfit](https://github.com/Outfitio/Outfit-Fonts) (`build/fonts/Outfit.ttf`), which
is under the SIL Open Font License 1.1 (`build/fonts/OFL.txt`). Ten service covers are reused from
mali-king/nuvio-collections. Covers and backdrops show stills and logos that belong to their owners; this repo is a
personal, non-commercial setup.
This product uses the TMDB API but is not endorsed or certified by TMDB.
