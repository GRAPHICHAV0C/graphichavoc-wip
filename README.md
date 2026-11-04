# GRAPHIC HAVOC.com — WIP Testing Build

## Temporary GitHub Pages functional test

This package is a **temporary work-in-progress hosting test**, not a public release and not a new numbered site version.

- Root `/` is intentionally pinned to `homepages/001.html`.
- Random homepage selection is temporarily disabled.
- `homepages/001.html` remains the active homepage source and is not removed.
- `/work/` remains fully functional and continues to show the complete project archive.
- Homepage Selected Work card randomization remains active inside homepage `001`.
- Homepage variants `002` and `003` remain in the package but are not selected by the root loader during this test.
- Root and generated `/work/` pages use `noindex, nofollow` for this WIP deployment.
- `robots.txt` does not advertise sitemaps and blocks crawler access to `/homepages/` fragments.
- `.nojekyll` is included for GitHub Pages static-file testing.
- Existing email/contact forms are intentionally unchanged.
- Before a public launch, restore the intended random-homepage loader and review indexing directives.

This build makes `/work/` the single permanent archive/source of truth for both standard projects and featured case studies.


## Homepage 002 — experimental map integration

- Homepage `002` is now an independently packaged experimental module at `homepages/002/`. Its map CSS, JavaScript, configuration, tiles, and hotspot tooling are not merged into the shared site files.
- The production random-homepage architecture remains documented, but this temporary GitHub Pages test pins the root loader to homepage `001`. Homepage-specific asset packaging remains intact for later restoration.
- The existing GRAPHIC HAVOC top navigation remains visually shared. On `002`, clicking it reveals the existing `Communicate w/` contact/footer layer from below the viewport; resuming map exploration hides the layer again.
- The artwork viewer retains pan, wheel/pinch zoom, bounded navigation, intro reveal, hotspot links/modals, and hotspot editing. Use `?homepage=002&edit=1` to load the editor directly during development without waiting for random selection.
- The supplied `build_tiles.py` is now included at `tools/build_tiles.py`. Homepage-specific `build_hotspots.py` remains at `homepages/002/tools/build_hotspots.py`.
- `001` and `003` are otherwise unchanged by this integration.

## Current build behavior

- Preserves the random homepage architecture while allowing each variation to be independently packaged; `001.html` and `003.html` remain direct fragments while `002` is loaded from `homepages/002/index.html`.
- `/work/` remains folder-driven and generates the archive index, permanent project URLs, homepage Selected Work cards, sitemap, image sitemap, and robots.txt.
- Standard projects continue to use the existing project-page template.
- Case-study projects use the richer sticky case-study presentation while remaining permanent `/work/<slug>/` projects.
- Featured case studies are generated into homepage `001.html` from the same `project.md` source used by their permanent `/work/` pages.
- Amplifier uses `CB1` (Light); RELATE uses `CB2` (Dark).
- Case-study logos live inside each project folder as presentation metadata rather than numbered narrative media.
- Case-study media captions use `T1`, sit directly beneath their corresponding media with `S1`, and the following narrative section begins after `S3` from the complete media/caption row.
- YouTube embeds remain supported through `### YOUTUBE: <url>` and do not consume numbered local media positions.
- `.DS_Store`, `__MACOSX`, and AppleDouble `._*` files are ignored.
- Separate generated `*-social.jpg` files are not used. The full-color 1200×630 `preview:` asset is reused for work indexes and Open Graph/social metadata.

## `project.md` presentation metadata

Existing projects default to the standard project presentation, so older `project.md` files do not need to be rewritten immediately.

Case-study projects add:

```md
presentation: case-study
featured: true
color_theme: CB1

logo: project-logo.svg
logo_alt: Accessible project logo description.
```

Supported values:

- `presentation: project | case-study`
- `featured: true | false`
- `color_theme: CB1 | CB2`
- `logo:` and `logo_alt:` are required for `case-study` projects.

`featured: true` makes a case study eligible for the homepage Case Studies section. It remains a normal permanent `/work/` entry and also appears in the `/work/` archive/Selected Work grid.

## Project folder workflow

```text
work/
  project-slug/
    project.md
    project-logo.svg              # optional metadata asset; required for case studies
    01_project_thumbnail.webp
    02_project-media.webp
    ...
```

Numbered filenames define narrative media order. Unnumbered metadata assets such as the case-study logo do not participate in the numbered media sequence.

Intended workflow:

```text
duplicate project folder → rename → replace/add optimized media → edit project.md → build/validate → review → publish
```

## `LAYOUT` controls

```md
LAYOUT: full
LAYOUT: half
LAYOUT: half-stack
```

Current behavior:

- `full` = full available media width.
- `half` = half-width media. Consecutive `half` blocks pair left/right in document order.
- `half-stack` = consecutive media stack vertically in one half-width column and can pair with an adjacent `half` block. This supports asymmetric compositions such as two 16:9 media/caption blocks stacked beside one taller 4:5 block.
- A single unpaired `half` defaults to the left side.
- On the provisional phone breakpoint, all layouts collapse to one full-width vertical stream in document order.
- A leading `LAYOUT: half` before opening copy continues to pair standard project opening copy with its opening media.

## Case-study section copy

Normal case-study sections use the established structure:

```md
## Section Title

Section copy...
```

RELATE currently contains one existing editorial exception where the first paragraph sits below the section title in the left column and remaining copy sits in the right column. That is represented with the optional case-study-only directive:

```md
## A Library of Individual Voices

COPY_LAYOUT: split

Lead paragraph...

Remaining copy...
```

The final unlabelled case-study statement is authored as:

```md
## Outcome

Outcome copy...
```

The renderer uses the case-study outcome treatment without displaying the word “Outcome.”

## Media blocks

Local media:

```md
### 03_project-image.webp

LAYOUT: full

CAPTION: Concise factual caption.

ALT: Descriptive alternative text.
```

YouTube:

```md
### YOUTUBE: https://youtu.be/VIDEO_ID

LAYOUT: full

CAPTION: Concise factual caption.

ALT: Accessible description of the embedded video.
```

Every rendered case-study image/video/embed uses the same `CAPTION:` source. YouTube `ALT:` is used as the iframe title/accessible label.

## Current FPO case-study assets

Amplifier and RELATE use supplied FPO SVGs for unfinished media slots so the case-study system can be evaluated at correct aspect ratios. These files are intentionally obvious placeholders and should be replaced in-place with final optimized media as it becomes available.

Amplifier preserves the real `04_amplifier-iconography.webm` supplied in the current local build. RELATE preserves its two existing motion assets as numbered project media.

## Build / validation

From the current project root:

```bash
cd /Volumes/SSD_4TB_01A/GRAPHICHAVOC/web/2026/graphichavoc-dot-com/current
python3 tools/build_work.py
```

A successful build reports the project folders found and:

```text
Validation passed.
```

The builder validates required metadata, referenced files, preview dimensions, lowercase narrative media names, sequential numeric prefixes, captions, ALT text, case-study theme/logo metadata, and supported layout directives.

## Local testing

Use two Terminal tabs/windows.

### Terminal 1 — local server

```bash
cd /Volumes/SSD_4TB_01A/GRAPHICHAVOC/web/2026/graphichavoc-dot-com
python3 -m http.server 8000
```

Leave this running.

### Terminal 2 — rebuild `/work/`

```bash
cd /Volumes/SSD_4TB_01A/GRAPHICHAVOC/web/2026/graphichavoc-dot-com
python3 tools/build_work.py
```

Review:

- `http://localhost:8000/`
- `http://localhost:8000/work/`
- `http://localhost:8000/work/amplifier-security-identity-system/`
- `http://localhost:8000/work/relate/`
- existing standard project pages such as `/work/americas-veterans/`

Do not test the random homepage loader through `file://`; homepage fragments are loaded with `fetch()`.

## iPhone / mobile testing over local Wi-Fi

1. Connect the Mac and iPhone to the same Wi-Fi network.
2. Leave `python3 -m http.server 8000` running from the project root.
3. Find the Mac Wi-Fi LAN IP:

   ```bash
   ipconfig getifaddr en0
   ```

4. On iPhone Safari open `http://<Mac-IP>:8000/`.
5. Test homepage, `/work/`, case studies, standard projects, touch behavior, portrait/landscape, and media loading.
6. Re-run `python3 tools/build_work.py` after project changes and refresh Safari; the server does not need restarting.
7. Stop the server with `Control + C` when finished.

## WIP notes

- Amplifier and RELATE currently contain FPO media intentionally; their final project imagery can be replaced progressively without changing the case-study template.
- RELATE now inherits the same caption-under-media behavior defined by the updated Amplifier case-study specification even though the current RELATE PDF diagram has not yet been redrawn with captions.
- The phone breakpoint remains provisional until dedicated responsive case-study specifications are finalized.


### v019b spacing correction
- Standalone standard `/work/<slug>/` project pages now begin flush at the top; `.project-page` no longer adds extra top padding.
- Standalone case-study pages remain flush at the top from the v019a correction.
