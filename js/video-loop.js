/* GRAPHIC HAVOC — video loop guard
 *
 * Purpose: keep muted autoplay videos looping in every browser, including
 * engines where the native `loop` attribute can fail after the first pass.
 *
 * A known failure mode (documented as a WebKit regression for looping WebM on
 * iOS) leaves the video frozen on its last frame with paused === false and
 * ended === false. No `ended` event fires, so nothing restarts it. This script
 * does not depend on the browser's own loop logic. It watches each video that
 * is on screen and restarts it when it:
 *   1. fires `ended`,
 *   2. sits frozen at the end of its timeline, or
 *   3. was paused by the browser or OS while visible (e.g. autoplay blocked
 *      until the first touch, or Low Power Mode).
 *
 * It never pauses a video and adds no controls. Videos keep their native
 * `loop` attribute, so browsers that loop correctly are not touched.
 *
 * Diagnostics: add ?videodebug=1 to any page URL to show a live status panel
 * (state of every video, loops seen, restarts by this guard, last events).
 * ?videodebug=0 turns it off again. The choice is kept for the browser session.
 */
(() => {
  "use strict";

  const POLL_MS = 100;              // check interval while a video is on screen
  const END_WINDOW_S = 0.25;        // "near the end" = within this many seconds of duration
  const FROZEN_MS = 350;            // time with no progress near the end before restarting
  const PAUSED_RETRY_MS = 1000;     // minimum gap between play() retries on a paused visible video
  const DEBUG_KEY = "graphichavoc:videodebug";

  const stateByVideo = new WeakMap();
  let timer = null;
  let panel = null;
  let debug = false;

  /* ---------- debug flag ---------- */
  try {
    const q = new URLSearchParams(window.location.search).get("videodebug");
    if (q === "1") window.sessionStorage.setItem(DEBUG_KEY, "1");
    if (q === "0") window.sessionStorage.removeItem(DEBUG_KEY);
    debug = window.sessionStorage.getItem(DEBUG_KEY) === "1";
  } catch (_) {
    debug = new URLSearchParams(window.location.search).get("videodebug") === "1";
  }

  /* ---------- helpers ---------- */
  const videos = () => [...document.querySelectorAll("video")];

  function onScreen(video) {
    const r = video.getBoundingClientRect();
    return r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth;
  }

  function stateOf(video) {
    let s = stateByVideo.get(video);
    if (!s) {
      s = { lastTime: -1, lastProgressAt: performance.now(), lastPlayTryAt: 0, loops: 0, restarts: 0, events: [], restartingUntil: 0 };
      stateByVideo.set(video, s);
    }
    return s;
  }

  function note(video, label) {
    const s = stateOf(video);
    s.events.push(label);
    if (s.events.length > 5) s.events.shift();
  }

  function tryPlay(video) {
    const s = stateOf(video);
    s.lastPlayTryAt = performance.now();
    const p = video.play();
    if (p && typeof p.catch === "function") {
      p.catch((err) => note(video, "play-rejected:" + (err && err.name ? err.name : "?")));
    }
  }

  function restart(video, reason) {
    const s = stateOf(video);
    const now = performance.now();
    if (now < s.restartingUntil) return;          // a restart is already in flight
    s.restartingUntil = now + 500;
    s.restarts += 1;
    s.lastTime = -1;
    s.lastProgressAt = now;
    note(video, "restart:" + reason);
    try { video.currentTime = 0; } catch (_) { /* not seekable yet: play() below still retries */ }
    tryPlay(video);
  }

  /* ---------- per-video listeners ---------- */
  function bind(video) {
    const s = stateOf(video);
    if (s.bound) return;
    s.bound = true;

    video.addEventListener("ended", () => { note(video, "ended"); restart(video, "ended"); });
    ["waiting", "stalled", "suspend", "emptied", "error", "pause", "play", "playing"].forEach((name) => {
      video.addEventListener(name, () => {
        if (name === "error") note(video, "error:" + (video.error ? video.error.code : "?"));
        else if (debug) note(video, name);
      });
    });
  }

  /* ---------- main check ---------- */
  function check() {
    if (document.hidden) return;
    const now = performance.now();

    videos().forEach((video) => {
      bind(video);
      if (!onScreen(video)) return;
      const s = stateOf(video);
      const t = video.currentTime;
      const d = video.duration;
      const finite = Number.isFinite(d) && d > 0;

      if (Math.abs(t - s.lastTime) > 0.001) {
        s.lastProgressAt = now;
        if (s.lastTime > 1 && t < s.lastTime - 1) s.loops += 1; // time jumped back: the browser looped natively
        s.lastTime = t;
      }

      /* 1. Paused while visible (browser/OS paused it): resume, rate-limited. */
      if (video.paused && !video.ended && video.readyState >= 2 && now - s.lastPlayTryAt > PAUSED_RETRY_MS) {
        note(video, "resume-paused");
        tryPlay(video);
        return;
      }

      /* 2. Frozen at the end while the browser still reports "playing". */
      if (finite && !video.paused && t >= d - END_WINDOW_S && now - s.lastProgressAt > FROZEN_MS) {
        restart(video, "frozen-at-end");
        return;
      }

      /* 3. Ended flag set but event was missed. */
      if (video.ended) restart(video, "ended-flag");
    });

    if (debug) renderPanel();
  }

  /* ---------- first-touch fallback for blocked autoplay ---------- */
  function resumeVisible() {
    videos().forEach((video) => { if (onScreen(video) && video.paused) tryPlay(video); });
  }
  ["touchstart", "pointerdown", "keydown"].forEach((name) => {
    window.addEventListener(name, resumeVisible, { passive: true, once: true });
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(resumeVisible, 50); });
  window.addEventListener("pageshow", () => setTimeout(resumeVisible, 50));

  /* ---------- diagnostics panel ---------- */
  function renderPanel() {
    if (!panel) {
      panel = document.createElement("pre");
      panel.setAttribute("aria-hidden", "true");
      panel.style.cssText = "position:fixed;left:0;right:0;bottom:0;max-height:45vh;overflow:auto;margin:0;padding:8px;z-index:2147483647;background:rgba(0,0,0,.88);color:#9f9;font:11px/1.35 ui-monospace,Menlo,monospace;white-space:pre-wrap;pointer-events:none";
      document.body.appendChild(panel);
    }
    const ua = navigator.userAgent.replace(/\s+/g, " ");
    const lines = ["videodebug  " + ua, "poll=" + POLL_MS + "ms  guard restarts shown as R, native loops as L"];
    videos().forEach((video, i) => {
      const s = stateOf(video);
      const src = (video.currentSrc || (video.querySelector("source") || {}).src || "").split("/").pop().slice(0, 30);
      const d = Number.isFinite(video.duration) ? video.duration.toFixed(1) : "?";
      lines.push(
        `#${i} ${onScreen(video) ? "ON " : "off"} ${src} t=${video.currentTime.toFixed(2)}/${d} ` +
        `${video.paused ? "PAUSED" : "play"} ${video.ended ? "ENDED " : ""}rs=${video.readyState} ns=${video.networkState} ` +
        `L=${s.loops} R=${s.restarts} [${s.events.join(",")}]`
      );
    });
    panel.textContent = lines.join("\n");
  }

  /* ---------- start ---------- */
  function start() {
    if (timer) return;
    videos().forEach(bind);
    timer = window.setInterval(check, POLL_MS);
  }

  window.GHVideoLoop = { refresh: () => { videos().forEach(bind); } };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
