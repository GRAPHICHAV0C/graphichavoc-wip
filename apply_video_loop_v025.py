#!/usr/bin/env python3
"""Bump the video-loop.js cache-busting version v024 -> v025. Run from the site root (current)."""
import pathlib, sys
changed = 0
for name in ("index.html", "tools/build_work.py"):
    p = pathlib.Path(name)
    if not p.exists():
        sys.exit(f"ERROR: {name} not found. Run this from the current folder.")
    t = p.read_text(encoding="utf-8")
    if "js/video-loop.js?v=v025" in t:
        print(f"already v025: {name}"); continue
    n = t.count("js/video-loop.js?v=v024")
    if n == 0:
        sys.exit(f"ERROR: no video-loop.js?v=v024 reference in {name}")
    p.write_text(t.replace("js/video-loop.js?v=v024", "js/video-loop.js?v=v025"), encoding="utf-8")
    print(f"PATCHED  {name}: {n} reference(s) -> v025"); changed += 1
print("\nNext: python3 tools/build_work.py")
