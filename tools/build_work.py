#!/usr/bin/env python3
"""GRAPHIC HAVOC /work static builder.

Source of truth: work/<slug>/project.md + project media.
Generated files: work/index.html, work/<slug>/index.html, homepage Selected Work
cards, sitemap.xml, image-sitemap.xml, and robots.txt.

Supports:
- local media assets referenced as ### filename.ext
- inline YouTube embeds referenced as ### YOUTUBE: https://youtu.be/...
- LAYOUT: full / half / half-stack for media blocks
- project and case-study presentations from the same project.md schema

The single full-color 1200x630 preview asset named in project.md is reused for the
work indexes and Open Graph/social metadata. Generated HTML should not be edited
by hand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
import re
import sys
from typing import List, Union
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

try:
    from PIL import Image
except Exception:
    Image = None

ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT / "work"
HOME_001 = ROOT / "homepages" / "001.html"
SITE = "https://graphichavoc.com"

IGNORED_NAMES = {".DS_Store"}
IGNORED_PREFIXES = ("._",)
STALE_SOCIAL_SUFFIX = "-social.jpg"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MEDIA_EXTS = {".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webm", ".mp4"}
IMAGE_EXTS = {".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg"}
YOUTUBE_HOSTS = {"youtu.be", "www.youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com"}


@dataclass
class Media:
    filename: str | None
    caption: str
    alt: str
    layout: str | None = None
    kind: str = "file"
    embed_url: str | None = None

    @property
    def ref(self) -> str:
        return self.filename if self.kind == "file" else (self.embed_url or "")


@dataclass
class Section:
    heading: str
    paragraphs: List[str] = field(default_factory=list)
    media_before: List[Media] = field(default_factory=list)
    copy_layout: str = "standard"


@dataclass
class Project:
    folder: Path
    meta: dict
    intro: List[str]
    intro_layout: str | None
    opening_media: Media
    sections: List[Section]
    trailing_media: List[Media]

    @property
    def slug(self): return self.meta["slug"]
    @property
    def title(self): return self.meta["title"]
    @property
    def year(self): return str(self.meta.get("year", ""))
    @property
    def disciplines(self): return self.meta.get("disciplines", [])
    @property
    def description(self): return self.meta["description"]
    @property
    def preview(self): return self.meta["preview"]
    @property
    def preview_alt(self): return self.meta["preview_alt"]
    @property
    def presentation(self): return self.meta.get("presentation", "project")
    @property
    def featured(self): return bool(self.meta.get("featured", False))
    @property
    def color_theme(self): return self.meta.get("color_theme", "CB1")
    @property
    def logo(self): return self.meta.get("logo")
    @property
    def logo_alt(self): return self.meta.get("logo_alt", "")


def parse_frontmatter(lines: List[str]):
    if not lines or lines[0].strip() != "---":
        raise ValueError("project.md must begin with YAML-style front matter delimited by ---")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("project.md front matter is missing its closing ---")

    meta = {}
    current_list = None
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list:
            meta[current_list].append(line[4:].strip())
            continue
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"Unsupported front matter line: {line}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            meta[key] = []
            current_list = key
        else:
            if value.lower() in {"true", "false"}:
                meta[key] = value.lower() == "true"
            else:
                meta[key] = int(value) if value.isdigit() else value
            current_list = None
    return meta, lines[end + 1:]


def normalize_layout(value: str, context: str):
    layout = value.strip().lower()
    if layout not in {"full", "half", "half-stack"}:
        raise ValueError(f"{context}: LAYOUT must be 'full', 'half', or 'half-stack', found '{value}'")
    return layout


def normalize_copy_layout(value: str, context: str):
    layout = value.strip().lower()
    if layout not in {"standard", "split"}:
        raise ValueError(f"{context}: COPY_LAYOUT must be 'standard' or 'split', found '{value}'")
    return layout


def extract_youtube_id(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        raise ValueError(f"Unsupported YouTube URL: {url}")

    video_id = ""
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.path.startswith("/embed/"):
        video_id = parsed.path.split("/embed/", 1)[1].split("/")[0]
    elif parsed.path.startswith("/shorts/"):
        video_id = parsed.path.split("/shorts/", 1)[1].split("/")[0]

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        raise ValueError(f"Could not extract a valid YouTube video ID from: {url}")
    return video_id


def normalize_youtube_url(url: str) -> str:
    # Keep captions off on initial load where YouTube permits it.
    # YouTube does not document cc_load_policy=0, so do not use it.
    # Omitting cc_load_policy avoids forcing captions on; cc_lang_pref sets
    # the preferred caption language if the viewer chooses to enable captions.
    return f"https://www.youtube-nocookie.com/embed/{extract_youtube_id(url)}?rel=0&cc_lang_pref=en"


def parse_body(lines: List[str]):
    tokens: List[Union[str, Media, tuple]] = []
    i = 0
    paragraph = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            text = " ".join(x.strip() for x in paragraph if x.strip()).strip()
            if text:
                tokens.append(text)
            paragraph = []

    while i < len(lines):
        raw = lines[i].rstrip()
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            i += 1
            continue
        if stripped.startswith("LAYOUT:"):
            flush_paragraph()
            tokens.append(("layout", normalize_layout(stripped[len("LAYOUT:"):], "project body")))
            i += 1
            continue
        if stripped.startswith("COPY_LAYOUT:"):
            flush_paragraph()
            tokens.append(("copy_layout", normalize_copy_layout(stripped[len("COPY_LAYOUT:"):], "project body")))
            i += 1
            continue
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush_paragraph()
            tokens.append(("section", stripped[3:].strip()))
            i += 1
            continue
        if stripped.startswith("### YOUTUBE:"):
            flush_paragraph()
            raw_url = stripped[len("### YOUTUBE:"):].strip()
            embed_url = normalize_youtube_url(raw_url)
            caption = None
            alt = None
            layout = None
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if s.startswith("LAYOUT:"):
                    if layout is not None:
                        raise ValueError(f"YouTube entry {raw_url} contains more than one LAYOUT directive")
                    layout = normalize_layout(s[len("LAYOUT:"):], f"YouTube entry {raw_url}")
                    i += 1
                    continue
                if s.startswith("CAPTION:"):
                    caption = s[len("CAPTION:"):].strip()
                    i += 1
                    continue
                if s.startswith("ALT:"):
                    alt = s[len("ALT:"):].strip()
                    i += 1
                    continue
                break
            if caption is None or alt is None:
                raise ValueError(f"YouTube entry {raw_url} requires both CAPTION: and ALT:")
            tokens.append(Media(None, caption, alt, layout, kind="youtube", embed_url=embed_url))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            filename = stripped[4:].strip()
            caption = None
            alt = None
            layout = None
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if s.startswith("LAYOUT:"):
                    if layout is not None:
                        raise ValueError(f"Media entry {filename} contains more than one LAYOUT directive")
                    layout = normalize_layout(s[len("LAYOUT:"):], f"Media entry {filename}")
                    i += 1
                    continue
                if s.startswith("CAPTION:"):
                    caption = s[len("CAPTION:"):].strip()
                    i += 1
                    continue
                if s.startswith("ALT:"):
                    alt = s[len("ALT:"):].strip()
                    i += 1
                    continue
                break
            if caption is None or alt is None:
                raise ValueError(f"Media entry {filename} requires both CAPTION: and ALT:")
            tokens.append(Media(filename, caption, alt, layout, kind="file"))
            continue
        paragraph.append(raw)
        i += 1
    flush_paragraph()
    return tokens


def load_project(folder: Path) -> Project:
    md = folder / "project.md"
    lines = md.read_text(encoding="utf-8").splitlines()
    meta, body_lines = parse_frontmatter(lines)

    required = ["schema_version", "title", "slug", "year", "disciplines", "description", "preview", "preview_alt"]
    for key in required:
        if key not in meta or meta[key] in ("", [], None):
            raise ValueError(f"{md}: missing required field '{key}'")
    if meta["schema_version"] != 1:
        raise ValueError(f"{md}: unsupported schema_version {meta['schema_version']}")
    if not SLUG_RE.fullmatch(meta["slug"]):
        raise ValueError(f"{md}: malformed slug '{meta['slug']}'")
    if folder.name != meta["slug"]:
        raise ValueError(f"{md}: folder name must match slug '{meta['slug']}'")

    meta.setdefault("presentation", "project")
    meta.setdefault("featured", False)
    meta.setdefault("color_theme", "CB1")
    if meta["presentation"] not in {"project", "case-study"}:
        raise ValueError(f"{md}: presentation must be 'project' or 'case-study'")
    if not isinstance(meta["featured"], bool):
        raise ValueError(f"{md}: featured must be true or false")
    if str(meta["color_theme"]).upper() not in {"CB1", "CB2"}:
        raise ValueError(f"{md}: color_theme must be CB1 or CB2")
    meta["color_theme"] = str(meta["color_theme"]).upper()
    if meta["presentation"] == "case-study":
        for key in ("logo", "logo_alt"):
            if key not in meta or meta[key] in ("", None):
                raise ValueError(f"{md}: case-study presentation requires '{key}'")

    tokens = parse_body(body_lines)
    intro_layout = None
    idx = 0
    if idx < len(tokens) and isinstance(tokens[idx], tuple) and tokens[idx][0] == "layout":
        intro_layout = tokens[idx][1]
        idx += 1

    if intro_layout == "half-stack":
        raise ValueError(f"{md}: opening copy LAYOUT supports only 'full' or 'half'; 'half-stack' is media-only")

    intro = []
    while idx < len(tokens) and isinstance(tokens[idx], str):
        intro.append(tokens[idx])
        idx += 1
    if idx >= len(tokens) or not isinstance(tokens[idx], Media):
        raise ValueError(f"{md}: body must contain intro copy followed by at least one media item")
    opening_media = tokens[idx]
    idx += 1

    pending_media: List[Media] = []
    sections: List[Section] = []
    while idx < len(tokens):
        tok = tokens[idx]
        if isinstance(tok, Media):
            pending_media.append(tok)
            idx += 1
            continue
        if isinstance(tok, tuple) and tok[0] == "layout":
            raise ValueError(f"{md}: standalone LAYOUT directives are currently supported only before opening copy; media LAYOUT belongs inside each media entry")
        if isinstance(tok, tuple) and tok[0] == "copy_layout":
            raise ValueError(f"{md}: COPY_LAYOUT must immediately follow a section heading")
        if isinstance(tok, tuple) and tok[0] == "section":
            heading = tok[1]
            idx += 1
            copy_layout = "standard"
            if idx < len(tokens) and isinstance(tokens[idx], tuple) and tokens[idx][0] == "copy_layout":
                copy_layout = tokens[idx][1]
                idx += 1
            paras = []
            while idx < len(tokens) and isinstance(tokens[idx], str):
                paras.append(tokens[idx])
                idx += 1
            if not paras:
                raise ValueError(f"{md}: section '{heading}' requires descriptive copy")
            sections.append(Section(heading, paras, pending_media, copy_layout))
            pending_media = []
            continue
        if isinstance(tok, str):
            raise ValueError(f"{md}: body copy must follow a section heading after the opening media")
        idx += 1

    project = Project(folder, meta, intro, intro_layout, opening_media, sections, pending_media)
    validate_project(project)
    return project


def media_files_in_folder(folder: Path):
    """Return only numbered narrative media. Unnumbered metadata assets such
    as project logos are intentionally excluded from the ordered media inventory.
    """
    files = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        if p.name in IGNORED_NAMES or p.name.startswith(IGNORED_PREFIXES):
            continue
        if p.name.endswith(STALE_SOCIAL_SUFFIX):
            continue
        if p.suffix.lower() in MEDIA_EXTS and re.match(r"^\d{2}_", p.name):
            files.append(p.name)
    return sorted(files)


def cleanup_stale_social_files():
    for folder in WORK_DIR.iterdir():
        if not folder.is_dir() or folder.name == "__MACOSX" or folder.name.startswith("."):
            continue
        for path in folder.glob(f"*{STALE_SOCIAL_SUFFIX}"):
            path.unlink()
            print(f"Removed stale generated social preview: {path.relative_to(ROOT)}")


def numeric_prefix(name: str):
    m = re.match(r"^(\d{2})_", name)
    return int(m.group(1)) if m else None


def image_dimensions(path: Path):
    if path.suffix.lower() == ".svg":
        try:
            root = ET.parse(path).getroot()
            width = root.attrib.get("width", "").replace("px", "")
            height = root.attrib.get("height", "").replace("px", "")
            if width and height:
                return int(float(width)), int(float(height))
            viewbox = root.attrib.get("viewBox", "").split()
            if len(viewbox) == 4:
                return int(float(viewbox[2])), int(float(viewbox[3]))
        except Exception:
            return None
        return None
    if Image is None:
        return None
    with Image.open(path) as im:
        return im.size


def validate_project(p: Project):
    all_refs = [p.preview, p.opening_media.ref]
    all_refs += [m.ref for s in p.sections for m in s.media_before]
    all_refs += [m.ref for m in p.trailing_media]
    if len(all_refs) != len(set(all_refs)):
        duplicates = sorted({x for x in all_refs if all_refs.count(x) > 1})
        raise ValueError(f"{p.slug}: duplicate media references: {duplicates}")

    refs = [p.preview]
    if p.opening_media.kind == "file" and p.opening_media.filename:
        refs.append(p.opening_media.filename)
    refs += [m.filename for s in p.sections for m in s.media_before if m.kind == "file" and m.filename]
    refs += [m.filename for m in p.trailing_media if m.kind == "file" and m.filename]

    for name in refs:
        path = p.folder / name
        if not path.is_file():
            raise ValueError(f"{p.slug}: referenced media file does not exist: {name}")
        if name != name.lower():
            raise ValueError(f"{p.slug}: media filenames must be lowercase: {name}")

    preview_path = p.folder / p.preview
    if preview_path.suffix.lower() in IMAGE_EXTS:
        dims = image_dimensions(preview_path)
        if dims and dims != (1200, 630):
            raise ValueError(f"{p.slug}: preview must be 1200x630, found {dims[0]}x{dims[1]}")
        if preview_path.stat().st_size > 1_000_000:
            print(f"WARNING: {p.slug}: preview exceeds 1 MB ({preview_path.stat().st_size} bytes)")

    if p.presentation == "case-study":
        logo_path = p.folder / str(p.logo)
        if not logo_path.is_file():
            raise ValueError(f"{p.slug}: logo asset does not exist: {p.logo}")

    actual = media_files_in_folder(p.folder)
    if sorted(refs) != actual:
        missing_from_md = sorted(set(actual) - set(refs))
        missing_files = sorted(set(refs) - set(actual))
        details = []
        if missing_from_md:
            details.append(f"unreferenced media {missing_from_md}")
        if missing_files:
            details.append(f"missing files {missing_files}")
        raise ValueError(f"{p.slug}: " + "; ".join(details))

    numbers = []
    for name in actual:
        n = numeric_prefix(name)
        if n is None:
            raise ValueError(f"{p.slug}: media filename requires two-digit sequence prefix: {name}")
        numbers.append(n)
    expected = list(range(1, len(numbers) + 1))
    if sorted(numbers) != expected:
        raise ValueError(f"{p.slug}: media sequence numbers must be consecutive {expected}, found {sorted(numbers)}")

    ref_numbers = [numeric_prefix(name) for name in refs]
    if all(n is not None for n in ref_numbers) and ref_numbers != sorted(ref_numbers):
        print(f"WARNING: {p.slug}: project.md media references are out of numeric filename order: {ref_numbers}")


def preview_mime(filename: str):
    ext = Path(filename).suffix.lower()
    return {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }.get(ext, "image/webp")


def media_html(p: Project, m: Media, level="../../"):
    alt = escape(m.alt, quote=True)
    cap = escape(m.caption)
    layout_class = f" project-media--{m.layout}" if m.layout else ""

    if m.kind == "youtube":
        src = escape(m.embed_url or "", quote=True)
        asset = (
            f'<iframe class="project-media__asset" src="{src}" title="{alt}" '
            'loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
            'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            'allowfullscreen style="aspect-ratio:16/9;border:0;"></iframe>'
        )
    else:
        src = escape(m.filename or "", quote=True)
        ext = Path(m.filename or "").suffix.lower()
        if ext in {".webm", ".mp4"}:
            mime = "video/webm" if ext == ".webm" else "video/mp4"
            asset = f'<video class="project-media__asset" autoplay loop muted playsinline preload="metadata" aria-label="{alt}"><source src="{src}" type="{mime}"></video>'
        else:
            asset = f'<img class="project-media__asset" src="{src}" alt="{alt}" loading="lazy">'

    return f'''<figure class="project-media{layout_class}">
      {asset}
      <figcaption class="project-media__caption t1">{cap}</figcaption>
    </figure>'''


def _consume_half_stack(media: List[Media], start: int):
    items = []
    i = start
    while i < len(media) and (media[i].layout or "full") == "half-stack":
        items.append(media[i])
        i += 1
    return items, i


def media_group_html(p: Project, media: List[Media]):
    """Render standard project media in document order.

    full = full-width row
    half = half-width item; consecutive halves pair left/right
    half-stack = consecutive items grouped into one half-width column and paired
    with an adjacent half item when present.
    """
    if not media:
        return ""

    if all(m.layout is None for m in media):
        cls = "project-media-group project-media-group--legacy-single" if len(media) == 1 else "project-media-group project-media-group--legacy-grid"
        return f'<div class="{cls}">\n' + "\n".join(media_html(p, m) for m in media) + "\n</div>"

    groups = []
    i = 0
    while i < len(media):
        m = media[i]
        layout = m.layout or "full"

        if layout == "full":
            groups.append('<div class="project-media-group project-media-group--full">\n' + media_html(p, m) + "\n</div>")
            i += 1
            continue

        if layout == "half-stack":
            stack, next_i = _consume_half_stack(media, i)
            stack_html = '<div class="project-media-stack">\n' + "\n".join(media_html(p, item) for item in stack) + "\n</div>"
            if next_i < len(media) and (media[next_i].layout or "full") == "half":
                groups.append('<div class="project-media-group project-media-group--half">\n' + stack_html + "\n" + media_html(p, media[next_i]) + "\n</div>")
                i = next_i + 1
            else:
                groups.append('<div class="project-media-group project-media-group--half">\n' + stack_html + "\n</div>")
                i = next_i
            continue

        # half followed by a half-stack run -> half left, stack right.
        if layout == "half" and i + 1 < len(media) and (media[i + 1].layout or "full") == "half-stack":
            stack, next_i = _consume_half_stack(media, i + 1)
            stack_html = '<div class="project-media-stack">\n' + "\n".join(media_html(p, item) for item in stack) + "\n</div>"
            groups.append('<div class="project-media-group project-media-group--half">\n' + media_html(p, m) + "\n" + stack_html + "\n</div>")
            i = next_i
            continue

        half_items = [m]
        if i + 1 < len(media) and (media[i + 1].layout or "full") == "half":
            half_items.append(media[i + 1])
            i += 2
        else:
            i += 1
        groups.append('<div class="project-media-group project-media-group--half">\n' + "\n".join(media_html(p, item) for item in half_items) + "\n</div>")

    return "\n".join(groups)


def standard_contact_footer():
    return f"""<div class="dark-zone">
    <footer class="contact sc1" id="contact" aria-labelledby="contact-title">
      <div class="sw contact-wrap">
        <div class="grid-16 contact-grid">
          <h2 class="contact-title t4 w3" id="contact-title">Communicate w/</h2>
          <form class="contact-form" action="https://api.web3forms.com/submit" method="POST" novalidate>
            <input type="hidden" name="access_key" value="41d082aa-315b-4534-b735-3c4187c5c1a7">
            <div class="contact-form__fields">
              <label><span class="sr-only">First Name</span><input name="firstname" type="text" autocomplete="given-name" placeholder="First Name" required></label>
              <label><span class="sr-only">Last Name</span><input name="lastname" type="text" autocomplete="family-name" placeholder="Last Name" required></label>
              <label><span class="sr-only">Email Address</span><input name="email" type="email" autocomplete="email" placeholder="Email Address" required></label>
              <label><span class="sr-only">Company and/or Project Name</span><input name="company_project" type="text" placeholder="Company &amp;/or Project Name" required></label>
              <label><span class="sr-only">URL</span><input name="url" type="url" inputmode="url" placeholder="URL" required></label>
            </div>
            <div class="contact-form__message">
              <label class="contact-form__textarea-wrap"><span class="sr-only">Your message</span><textarea name="message" placeholder="Your message..." required></textarea></label>
              <div class="contact-form__state" aria-live="polite" aria-atomic="true"></div>
              <button class="contact-form__submit" type="submit">SEND</button>
            </div>
            <div class="contact-form__success" role="status" aria-live="polite" aria-atomic="true">THANKS TALK SOON</div>
          </form>
          <div class="footer-wordmark" role="img" aria-label="GRAPHIC HAVOC"></div>
        </div>
      </div>
    </footer>
  </div>"""


def contact_footer(prefix: str):
    return f'''<div class="dark-zone">
    <footer class="contact sc1 project-contact" id="contact" aria-labelledby="contact-title">
      <div class="sw contact-wrap">
        <div class="grid-16 contact-grid">
          <h2 class="contact-title t4 w3" id="contact-title">Get in touch to<br>collaborate or<br>continue to<br><a class="project-contact__work-link" href="{prefix}work/">view more work.</a></h2>
          <form class="contact-form" action="https://api.web3forms.com/submit" method="POST" novalidate>
            <input type="hidden" name="access_key" value="41d082aa-315b-4534-b735-3c4187c5c1a7">
            <div class="contact-form__fields">
              <label><span class="sr-only">First Name</span><input name="firstname" type="text" autocomplete="given-name" placeholder="First Name" required></label>
              <label><span class="sr-only">Last Name</span><input name="lastname" type="text" autocomplete="family-name" placeholder="Last Name" required></label>
              <label><span class="sr-only">Email Address</span><input name="email" type="email" autocomplete="email" placeholder="Email Address" required></label>
              <label><span class="sr-only">Company and/or Project Name</span><input name="company_project" type="text" placeholder="Company &amp;/or Project Name" required></label>
              <label><span class="sr-only">URL</span><input name="url" type="url" inputmode="url" placeholder="URL" required></label>
            </div>
            <div class="contact-form__message">
              <label class="contact-form__textarea-wrap"><span class="sr-only">Your message</span><textarea name="message" placeholder="Your message..." required></textarea></label>
              <div class="contact-form__state" aria-live="polite" aria-atomic="true"></div>
              <button class="contact-form__submit" type="submit">SEND</button>
            </div>
            <div class="contact-form__success" role="status" aria-live="polite" aria-atomic="true">THANKS TALK SOON</div>
          </form>
          <div class="footer-wordmark" role="img" aria-label="GRAPHIC HAVOC"></div>
        </div>
      </div>
    </footer>
  </div>'''



def case_asset_html(m: Media, asset_prefix: str):
    alt = escape(m.alt, quote=True)
    cap = escape(m.caption)
    if m.kind == "youtube":
        src = escape(m.embed_url or "", quote=True)
        asset = (
            f'<iframe class="case-media" src="{src}" title="{alt}" loading="lazy" '
            'referrerpolicy="strict-origin-when-cross-origin" '
            'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            'allowfullscreen style="aspect-ratio:16/9;border:0;"></iframe>'
        )
    else:
        src = escape(asset_prefix + (m.filename or ""), quote=True)
        ext = Path(m.filename or "").suffix.lower()
        if ext in {".webm", ".mp4"}:
            mime = "video/webm" if ext == ".webm" else "video/mp4"
            asset = f'<video class="case-media" autoplay loop muted playsinline preload="metadata" aria-label="{alt}"><source src="{src}" type="{mime}"></video>'
        else:
            asset = f'<img class="case-media" src="{src}" alt="{alt}" loading="lazy">'
    return f'''<figure class="case-media-figure">
      {asset}
      <figcaption class="case-media-figure__caption t1">{cap}</figcaption>
    </figure>'''


def case_media_group_html(media: List[Media], asset_prefix: str):
    if not media:
        return ""
    groups = []
    i = 0
    while i < len(media):
        m = media[i]
        layout = m.layout or "full"
        if layout == "full":
            groups.append('<div class="case-media-group case-media-group--full">\n' + case_asset_html(m, asset_prefix) + "\n</div>")
            i += 1
            continue
        if layout == "half-stack":
            stack, next_i = _consume_half_stack(media, i)
            stack_html = '<div class="case-media-stack">\n' + "\n".join(case_asset_html(item, asset_prefix) for item in stack) + "\n</div>"
            if next_i < len(media) and (media[next_i].layout or "full") == "half":
                groups.append('<div class="case-media-grid">\n' + stack_html + "\n" + case_asset_html(media[next_i], asset_prefix) + "\n</div>")
                i = next_i + 1
            else:
                groups.append('<div class="case-media-grid">\n' + stack_html + "\n</div>")
                i = next_i
            continue
        if layout == "half" and i + 1 < len(media) and (media[i + 1].layout or "full") == "half-stack":
            stack, next_i = _consume_half_stack(media, i + 1)
            stack_html = '<div class="case-media-stack">\n' + "\n".join(case_asset_html(item, asset_prefix) for item in stack) + "\n</div>"
            groups.append('<div class="case-media-grid">\n' + case_asset_html(m, asset_prefix) + "\n" + stack_html + "\n</div>")
            i = next_i
            continue
        half_items = [m]
        if i + 1 < len(media) and (media[i + 1].layout or "full") == "half":
            half_items.append(media[i + 1])
            i += 2
        else:
            i += 1
        groups.append('<div class="case-media-grid">\n' + "\n".join(case_asset_html(item, asset_prefix) for item in half_items) + "\n</div>")
    return "\n".join(groups)


def render_case_section(section: Section, media: List[Media], asset_prefix: str):
    media_html = case_media_group_html(media, asset_prefix)
    heading = escape(section.heading)
    heading_id = escape(slugify_heading(section.heading), quote=True)
    if section.copy_layout == "split" and len(section.paragraphs) > 1:
        lead = f'<p>{escape(section.paragraphs[0])}</p>'
        right = "\n".join(f'<p>{escape(x)}</p>' for x in section.paragraphs[1:])
        copy_html = f'''<div class="case-caption-grid case-caption-grid--with-lead-copy">
          <div class="case-lead-column">
            <h3 class="case-lead t3 w2" id="{heading_id}">{heading}</h3>
            <div class="case-lead-copy t2 w1">{lead}</div>
          </div>
          <div class="case-copy t2 w1">{right}</div>
        </div>'''
    else:
        right = "\n".join(f'<p>{escape(x)}</p>' for x in section.paragraphs)
        copy_html = f'''<div class="case-caption-grid">
          <h3 class="case-lead t3 w2" id="{heading_id}">{heading}</h3>
          <div class="case-copy t2 w1">{right}</div>
        </div>'''
    return f'''<section class="case-row" aria-labelledby="{heading_id}">
      {media_html}
      {copy_html}
    </section>'''


def render_case_study_article(p: Project, asset_prefix: str = ""):
    theme = p.color_theme.lower()
    overview = "\n".join(f'<p>{escape(x)}</p>' for x in p.intro)
    logo_src = escape(asset_prefix + str(p.logo), quote=True)
    logo_alt = escape(p.logo_alt, quote=True)

    outcome = None
    narrative_sections = []
    first = True
    for section in p.sections:
        if section.heading.strip().lower() == "outcome":
            outcome = section
            continue
        media = list(section.media_before)
        if first:
            media = [p.opening_media] + media
            first = False
        narrative_sections.append(render_case_section(section, media, asset_prefix))

    if first:
        narrative_sections.append(case_media_group_html([p.opening_media], asset_prefix))

    if p.trailing_media:
        narrative_sections.append(case_media_group_html(p.trailing_media, asset_prefix))

    outcome_html = ""
    if outcome:
        outcome_copy = " ".join(outcome.paragraphs)
        outcome_html = f'''<section class="case-outcome" aria-label="{escape(p.title, quote=True)} outcome">
        <p class="case-outcome__copy t3 w2">{escape(outcome_copy)}</p>
      </section>'''

    return f'''<article class="case-study case-study--{theme}" aria-labelledby="{escape(p.slug, quote=True)}-case-title">
      <header class="case-study__identity">
        <h2 class="case-study__label t4 w3" id="{escape(p.slug, quote=True)}-case-title">Case<br>Study<span class="sr-only">: {escape(p.title)}</span></h2>
        <div class="client-mark">
          <img class="client-mark__image" src="{logo_src}" alt="{logo_alt}">
        </div>
        <div class="case-study__overview t1 w1">{overview}</div>
      </header>
      <div class="case-study__narrative">{''.join(narrative_sections)}</div>
      {outcome_html}
    </article>'''


def render_case_study_page(p: Project):
    title_display = escape(p.title)
    canonical = f"{SITE}/work/{p.slug}/"
    og_image = f"{canonical}{p.preview}"
    og_image_type = preview_mime(p.preview)
    keywords = ", ".join(p.disciplines)
    jsonld = f'''{{
      "@context": "https://schema.org",
      "@graph": [
        {{"@type":"CreativeWork","@id":"{canonical}#work","name":{json_string(p.title)},"url":"{canonical}","description":{json_string(p.description)},"dateCreated":{json_string(p.year)},"creator":{{"@type":"Organization","name":"GRAPHIC HAVOC","url":"{SITE}/"}},"keywords":{json_string(keywords)},"image":"{og_image}"}},
        {{"@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"GRAPHIC HAVOC","item":"{SITE}/"}},{{"@type":"ListItem","position":2,"name":"Work","item":"{SITE}/work/"}},{{"@type":"ListItem","position":3,"name":{json_string(p.title)},"item":"{canonical}"}}]}}
      ]
    }}'''
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_display} — GRAPHIC HAVOC</title>
  <meta name="description" content="{escape(p.description, quote=True)}">
  <meta name="robots" content="noindex, nofollow">
  <meta name="author" content="GRAPHIC HAVOC">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="GRAPHIC HAVOC">
  <meta property="og:title" content="{title_display} — GRAPHIC HAVOC">
  <meta property="og:description" content="{escape(p.description, quote=True)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:type" content="{og_image_type}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{escape(p.preview_alt, quote=True)}">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title_display} — GRAPHIC HAVOC">
  <meta name="twitter:description" content="{escape(p.description, quote=True)}">
  <meta name="twitter:image" content="{og_image}">
  <meta name="twitter:image:alt" content="{escape(p.preview_alt, quote=True)}">
  <script type="application/ld+json">{jsonld}</script>
  <link rel="stylesheet" href="../../css/styles.css?v=v019bc">
  <script>document.documentElement.classList.add("js");</script>
  <script src="../../js/work.js?v=v021-random1-random1" defer></script>
</head>
<body class="work-case-study-page" id="top">
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header" aria-label="Primary">
    <a class="brand-tab" href="#contact" aria-label="GRAPHIC HAVOC — go to contact form"><span class="brand-tab__mark" aria-hidden="true"></span><span class="sr-only">GRAPHIC HAVOC</span></a>
  </header>
  <main id="main-content">
    <h1 class="sr-only">{title_display}</h1>
    <section class="case-studies case-studies--standalone" aria-label="Case Study">
      {render_case_study_article(p)}
    </section>
  </main>
  {contact_footer('../../')}
</body>
</html>'''

def render_project(p: Project):
    if p.presentation == "case-study":
        return render_case_study_page(p)

    title_display = escape(p.title)
    disciplines = " + ".join(escape(x) for x in p.disciplines)
    intro = "\n".join(f'<p>{escape(x)}</p>' for x in p.intro)

    blocks = []
    for s in p.sections:
        blocks.append(media_group_html(p, s.media_before))
        copy = "\n".join(f'<p>{escape(x)}</p>' for x in s.paragraphs)
        blocks.append(f'''<section class="project-section" aria-labelledby="{escape(slugify_heading(s.heading), quote=True)}">
          <h2 class="project-section__title t3 w2" id="{escape(slugify_heading(s.heading), quote=True)}">{escape(s.heading)}</h2>
          <div class="project-section__copy t2 w1">{copy}</div>
        </section>''')
    if p.trailing_media:
        blocks.append(media_group_html(p, p.trailing_media))

    canonical = f"{SITE}/work/{p.slug}/"
    og_image = f"{canonical}{p.preview}"
    og_image_type = preview_mime(p.preview)
    keywords = ", ".join(p.disciplines)
    jsonld = f'''{{
      "@context": "https://schema.org",
      "@graph": [
        {{"@type":"CreativeWork","@id":"{canonical}#work","name":{json_string(p.title)},"url":"{canonical}","description":{json_string(p.description)},"dateCreated":{json_string(p.year)},"creator":{{"@type":"Organization","name":"GRAPHIC HAVOC","url":"{SITE}/"}},"keywords":{json_string(keywords)},"image":"{og_image}"}},
        {{"@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"GRAPHIC HAVOC","item":"{SITE}/"}},{{"@type":"ListItem","position":2,"name":"Work","item":"{SITE}/work/"}},{{"@type":"ListItem","position":3,"name":{json_string(p.title)},"item":"{canonical}"}}]}}
      ]
    }}'''

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_display} — GRAPHIC HAVOC</title>
  <meta name="description" content="{escape(p.description, quote=True)}">
  <meta name="robots" content="noindex, nofollow">
  <meta name="author" content="GRAPHIC HAVOC">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="GRAPHIC HAVOC">
  <meta property="og:title" content="{title_display} — GRAPHIC HAVOC">
  <meta property="og:description" content="{escape(p.description, quote=True)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:type" content="{og_image_type}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{escape(p.preview_alt, quote=True)}">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title_display} — GRAPHIC HAVOC">
  <meta name="twitter:description" content="{escape(p.description, quote=True)}">
  <meta name="twitter:image" content="{og_image}">
  <meta name="twitter:image:alt" content="{escape(p.preview_alt, quote=True)}">
  <script type="application/ld+json">{jsonld}</script>
  <link rel="stylesheet" href="../../css/styles.css?v=v019bc">
  <script>document.documentElement.classList.add("js");</script>
  <script src="../../js/work.js?v=v021-random1-random1" defer></script>
</head>
<body class="work-project-page" id="top">
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header" aria-label="Primary">
    <a class="brand-tab" href="#contact" aria-label="GRAPHIC HAVOC — go to contact form"><span class="brand-tab__mark" aria-hidden="true"></span><span class="sr-only">GRAPHIC HAVOC</span></a>
  </header>
  <main id="main-content">
    <article class="project-page sc1">
      <div class="sw grid-16 project-intro project-intro--{p.intro_layout or 'half'}">
        <div class="project-intro__copy">
          <p class="project-byline t1">{disciplines} by GRAPHIC HAVOC for:</p>
          <h1 class="project-title t4 w3">{title_display}</h1>
          <div class="project-intro__body t2 w1">{intro}</div>
        </div>
        <div class="project-intro__media project-intro__media--{p.opening_media.layout or 'half'}">{media_html(p, p.opening_media)}</div>
      </div>
      <div class="project-stream sw">{''.join(blocks)}</div>
    </article>
  </main>
  {contact_footer('../../')}
</body>
</html>'''


def slugify_heading(s: str):
    x = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return x or "section"


def json_string(s):
    import json
    return json.dumps(str(s), ensure_ascii=False)


def homepage_card(p: Project):
    disciplines = ", ".join(p.disciplines)
    return f'''<a class="work-card" href="work/{escape(p.slug, quote=True)}/" aria-label="{escape(p.title, quote=True)} — {escape(disciplines, quote=True)}">
      <img class="work-card__image" src="work/{escape(p.slug, quote=True)}/{escape(p.preview, quote=True)}" alt="{escape(p.preview_alt, quote=True)}" loading="lazy" width="1200" height="630">
      <span class="work-card__overlay"><span class="work-card__title t2 w1">{escape(p.title)}</span><span class="work-card__disciplines t1">{escape(disciplines)}</span></span>
    </a>'''


def patch_homepage(projects: List[Project]):
    html = HOME_001.read_text(encoding="utf-8")

    case_start = "<!-- GENERATED_CASE_STUDIES_START -->"
    case_end = "<!-- GENERATED_CASE_STUDIES_END -->"
    featured = [p for p in projects if p.presentation == "case-study" and p.featured]
    case_articles = [render_case_study_article(p, f"work/{p.slug}/") for p in featured]
    case_generated = case_start + "\n" + "\n".join(case_articles) + "\n    " + case_end
    if case_start not in html or case_end not in html:
        raise ValueError("Homepage is missing generated case-study markers")
    html = re.sub(re.escape(case_start) + r".*?" + re.escape(case_end), case_generated, html, flags=re.S)

    start = "<!-- GENERATED_WORK_CARDS_START -->"
    end = "<!-- GENERATED_WORK_CARDS_END -->"
    cards = [homepage_card(p) for p in projects]
    generated = start + "\n" + "\n".join(cards) + "\n" + end
    if start not in html or end not in html:
        raise ValueError("Homepage is missing generated work card markers")
    html = re.sub(re.escape(start) + r".*?" + re.escape(end), generated, html, flags=re.S)
    HOME_001.write_text(html, encoding="utf-8")


def render_work_index(projects: List[Project]):
    canonical = f"{SITE}/work/"
    cards = "\n".join(
        f'''<a class="work-card" href="{escape(p.slug, quote=True)}/" aria-label="{escape(p.title, quote=True)} — {escape(', '.join(p.disciplines), quote=True)}">
          <img class="work-card__image" src="{escape(p.slug, quote=True)}/{escape(p.preview, quote=True)}" alt="{escape(p.preview_alt, quote=True)}" loading="lazy" width="1200" height="630">
          <span class="work-card__overlay"><span class="work-card__title t2 w1">{escape(p.title)}</span><span class="work-card__disciplines t1">{escape(', '.join(p.disciplines))}</span></span>
        </a>''' for p in projects)
    itemlist = ",".join(f'{{"@type":"ListItem","position":{i+1},"url":"{SITE}/work/{p.slug}/","name":{json_string(p.title)}}}' for i, p in enumerate(projects))
    jsonld = f'{{"@context":"https://schema.org","@type":"CollectionPage","name":"GRAPHIC HAVOC Work","url":"{canonical}","mainEntity":{{"@type":"ItemList","itemListElement":[{itemlist}]}}}}'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Work — GRAPHIC HAVOC</title>
  <meta name="description" content="GRAPHIC HAVOC projects and collaborations across disciplines, industries, formats, and executions.">
  <meta name="robots" content="noindex, nofollow"><meta name="author" content="GRAPHIC HAVOC"><link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website"><meta property="og:site_name" content="GRAPHIC HAVOC"><meta property="og:title" content="Work — GRAPHIC HAVOC"><meta property="og:description" content="GRAPHIC HAVOC projects and collaborations across disciplines, industries, formats, and executions."><meta property="og:url" content="{canonical}">
  <script type="application/ld+json">{jsonld}</script>
  <link rel="stylesheet" href="../css/styles.css?v=v019bc"><script>document.documentElement.classList.add("js");</script><script src="../js/work.js?v=v021-random1-random1" defer></script>
</head>
<body class="work-index-page" id="top">
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header" aria-label="Primary"><a class="brand-tab" href="#contact" aria-label="GRAPHIC HAVOC — go to contact form"><span class="brand-tab__mark" aria-hidden="true"></span><span class="sr-only">GRAPHIC HAVOC</span></a></header>
  <main id="main-content">
    <section class="work-index sc2" aria-label="GRAPHIC HAVOC work">
      <div class="work-index__grid" data-randomize-order>{cards}</div>
    </section>
  </main>
  {standard_contact_footer()}
</body>
</html>'''


def write_sitemaps(projects: List[Project]):
    urls = [f"{SITE}/", f"{SITE}/work/"] + [f"{SITE}/work/{p.slug}/" for p in projects]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls) + '\n</urlset>\n'
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    from xml.sax.saxutils import escape as xml_escape
    image_rows = []
    for p in projects:
        page = f"{SITE}/work/{p.slug}/"
        media = [(p.preview, p.preview_alt)]
        if p.opening_media.kind == "file" and p.opening_media.filename and Path(p.opening_media.filename).suffix.lower() in IMAGE_EXTS:
            media.append((p.opening_media.filename, p.opening_media.caption))
        media += [(m.filename, m.caption) for s in p.sections for m in s.media_before if m.kind == "file" and m.filename and Path(m.filename).suffix.lower() in IMAGE_EXTS]
        media += [(m.filename, m.caption) for m in p.trailing_media if m.kind == "file" and m.filename and Path(m.filename).suffix.lower() in IMAGE_EXTS]
        entries = []
        for name, caption in media:
            entries.append(f"<image:image><image:loc>{page}{xml_escape(name)}</image:loc><image:caption>{xml_escape(caption)}</image:caption></image:image>")
        image_rows.append(f"  <url><loc>{page}</loc>{''.join(entries)}</url>")
    image_sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + "\n".join(image_rows) + '\n</urlset>\n'
    (ROOT / "image-sitemap.xml").write_text(image_sitemap, encoding="utf-8")
    (ROOT / "robots.txt").write_text("User-agent: *\nDisallow: /homepages/\n", encoding="utf-8")


def discover_projects():
    projects = []
    for folder in sorted(WORK_DIR.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name == "__MACOSX" or folder.name.startswith("."):
            continue
        if (folder / "project.md").is_file():
            projects.append(load_project(folder))
    if not projects:
        raise ValueError("No project folders with project.md found")
    return projects


def main():
    try:
        cleanup_stale_social_files()
        projects = discover_projects()
        for p in projects:
            (p.folder / "index.html").write_text(render_project(p), encoding="utf-8")
        (WORK_DIR / "index.html").write_text(render_work_index(projects), encoding="utf-8")
        patch_homepage(projects)
        write_sitemaps(projects)
        print(f"Built {len(projects)} project(s): " + ", ".join(p.slug for p in projects))
        print("Validation passed.")
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
