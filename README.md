# A Guy Talks

Magazine-format site for SJ (@aguytalks), built from his Substack.

## Build

```
python3 build.py
```

Produces a single self-contained `index.html` — fonts and images embedded,
no network needed to view it. Open it directly or serve the folder.

## What the build does

- Pulls all essays live from `aguytalks.substack.com` (titles, subtitles,
  dates, tags, canonical URLs), caching to `archive.json` as a fallback
- Numbers essays as issues, oldest = 01
- Derives the Departments index from real tag counts
- Embeds Bodoni Moda (latin subset) as a data URI
- Picks up photos from `photos/` — see `photos/HOW-TO.txt`
- Emits pure ASCII, so the page needs no charset declaration

## Layout

```
build.py            the whole build
template.html       markup + styles, with __PLACEHOLDER__ slots
assets/             fonts, and fallback images used until real photos land
photos/             drop SJ's photos here
index.html          output — do not edit by hand, it is regenerated
```

## Design

Bone `#E4E2DC`, ink `#16150F`, one hairline rule, no chromatic accent.
Bodoni Moda for display, system grotesk for body — the Didone/grotesk split
fashion magazines actually use. Crop marks and the numbered strip reference
the Margiela label, since the anti-archive manifesto is the flagship essay.

Full light and dark themes, driven entirely by tokens on `:root`.
