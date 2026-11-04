# Homepage 002 — Experimental Artwork Map

Homepage `002` is packaged as an independent experimental homepage module. Its map-specific CSS, JavaScript, configuration, tiles, and hotspot helper remain inside this directory so the experiment can evolve without coupling `001` or `003` to the map implementation.

## Runtime structure

```text
homepages/002/
  index.html
  css/styles.css
  js/viewer.js
  js/hotspots.js
  js/intro.js
  js/contact-panel.js
  config/map.json
  config/hotspots.json
  tiles/
  tools/build_hotspots.py
```

The shared root loader reads the variant's `data-homepage-assets` template and loads only the assets declared by this homepage. `app.js` does not contain map-specific file paths.

## Interaction

- The shared GRAPHIC HAVOC navigation remains fixed at the top.
- Clicking GRAPHIC HAVOC slides the existing `Communicate w/` contact/footer layer up from below the browser.
- Pointer, touch, or wheel interaction with the map slides the contact/footer layer back down.
- The viewer retains pan, wheel/pinch zoom, intro reveal, hotspots, links/modals, and the local hotspot editor.

## Hotspot editor

Run the site from the website root and open:

```text
http://localhost:8000/?homepage=002&edit=1
```

The `homepage=002` development override loads this variation directly; `edit=1` opens the hotspot editor automatically. Editing remains local until exported. Publish the exported JSON by replacing `homepages/002/config/hotspots.json`. The Markdown helper remains at `homepages/002/tools/build_hotspots.py`.

## Tile generation

The supplied tile builder is kept at the website-level development tools path:

```text
tools/build_tiles.py
```

It accepts one 4096 × 4096 source image, destination, region coordinates, and optional WebP quality. It generates the 21 A/B/C WebP tiles for that region.
