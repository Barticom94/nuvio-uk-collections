# Nuvio UK Collections

A "Streaming Services" collection for [Nuvio](https://github.com/NuvioMedia/NuvioTV), built for UK viewers.

- `nuvio-collections.json` is the file to import (Nuvio → Settings → Collections → Import → From URL, or paste its contents).
- `covers/` holds the landscape tile artwork for each service.

Each tile opens Popular / New / Top Rated rows (movies and series) for titles on that service in the UK, using TMDB's
watch-provider data (sourced from JustWatch). Hulu has no UK service, so its tile uses the US catalogue.

Ten covers are reused from [mali-king/nuvio-collections](https://github.com/mali-king/nuvio-collections). Artwork shows
stills and service logos that belong to their owners; this repo is a personal, non-commercial setup.
This product uses the TMDB API but is not endorsed or certified by TMDB.
