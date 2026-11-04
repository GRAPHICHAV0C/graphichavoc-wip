(() => {
  "use strict";

  /* GRAPHIC HAVOC.com — TEMPORARY GITHUB PAGES WIP TEST BUILD
   * Root homepage loading is intentionally pinned to homepage 001.
   * The production random-homepage architecture is temporarily disabled for
   * functional hosting tests. Do not treat this as the final public behavior.
   */
  const TEST_HOMEPAGE_FILE = "homepages/001.html";
  const app = document.getElementById("app");


  function initializeAnimatedTitle() {
    const canonicalTitle = document.title;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reduceMotion) return;

    const states = [
      "[ GRAPHIC HAVOC ]",
      "[ 6RAPHIC HAVOC ]",
      "[ 6R@PHIC HAVOC ]",
      "[ 6R@PHiC HAvOC ]",
      "[ GRAPHIC HAVOC ]"
    ];
    let i = 0;
    let timer = null;

    const start = () => {
      if (timer) return;
      timer = window.setInterval(() => {
        if (!document.hidden) {
          document.title = states[i % states.length];
          i += 1;
        }
      }, 1450);
    };

    const stop = () => {
      if (timer) { window.clearInterval(timer); timer = null; }
      document.title = canonicalTitle;
    };

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop(); else start();
    });

    window.setTimeout(start, 1000);
  }

  function resetContactState(form) {
    form.classList.remove("is-validation-error", "is-success");
  }

  function setValidationError(form) {
    form.classList.remove("is-success");
    form.classList.add("is-validation-error");
  }

  function setSuccess(form) {
    form.classList.remove("is-validation-error");
    form.classList.add("is-success");
  }

  function normalizeUrlField(form) {
    const urlField = form.querySelector('input[name="url"]');
    if (!urlField) return;

    const value = urlField.value.trim();
    if (!value) return;

    const hasProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(value);
    const hasSchemePrefix = /^[a-z][a-z0-9+.-]*:/i.test(value);

    // Make common entries such as graphichavoc.com or www.graphichavoc.com
    // valid without forcing the visitor to type https://. Malformed scheme
    // entries such as "http:" remain untouched so validation can catch them.
    if (!hasProtocol && !hasSchemePrefix) {
      urlField.value = `https://${value}`;
    }
  }

  function formIsComplete(form) {
    return [...form.querySelectorAll("[required]")].every((field) => {
      return field.value.trim() !== "" && field.checkValidity();
    });
  }

  async function submitToWeb3Forms(form) {
    const formData = new FormData(form);

    const response = await fetch("https://api.web3forms.com/submit", {
      method: "POST",
      body: formData
    });

    let result = null;
    try {
      result = await response.json();
    } catch (_) {
      /* Web3Forms normally returns JSON; HTTP status remains the fallback. */
    }

    return response.ok && (result?.success ?? true);
  }

  function initializeContactForm() {
    const form = document.querySelector(".contact-form");
    if (!form) return;

    form.addEventListener("input", () => {
      if (form.classList.contains("is-validation-error")) {
        resetContactState(form);
      }
    });

    const urlField = form.querySelector('input[name="url"]');
    urlField?.addEventListener("blur", () => normalizeUrlField(form));

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      if (form.classList.contains("is-success")) return;

      normalizeUrlField(form);

      if (!formIsComplete(form)) {
        setValidationError(form);
        const firstInvalid = form.querySelector(":invalid");
        firstInvalid?.focus();
        return;
      }

      const submitButton = form.querySelector(".contact-form__submit");
      if (submitButton) submitButton.disabled = true;

      try {
        const submitted = await submitToWeb3Forms(form);
        if (submitted) {
          setSuccess(form);
          form.reset();
        }
      } catch (error) {
        console.error("Web3Forms submission failed:", error);
        /* Network/API failure state is intentionally not designed yet. */
      } finally {
        if (submitButton && !form.classList.contains("is-success")) {
          submitButton.disabled = false;
        }
      }
    });

    const params = new URLSearchParams(window.location.search);
    const previewState = params.get("form-state");
    if (previewState === "success") setSuccess(form);
    if (previewState === "error") setValidationError(form);
  }


  function initializeMediaDefaults() {
    document.querySelectorAll("video").forEach((video) => {
      video.autoplay = true;
      video.loop = true;
      video.muted = true;
      video.playsInline = true;
      video.setAttribute("autoplay", "");
      video.setAttribute("loop", "");
      video.setAttribute("muted", "");
      video.setAttribute("playsinline", "");
      video.play().catch(() => {
        /* Muted autoplay can still be blocked in unusual browser conditions. */
      });
    });

    document.querySelectorAll("lottie-player").forEach((player) => {
      player.setAttribute("autoplay", "");
      player.setAttribute("loop", "");
    });
  }


  function setHomepageVariantClass() {
    const variantRoot = app.querySelector('[data-homepage-variant]');
    const variant = variantRoot?.dataset.homepageVariant?.trim();
    if (!variant) return;

    [...document.documentElement.classList]
      .filter((name) => name.startsWith('homepage-variant--'))
      .forEach((name) => document.documentElement.classList.remove(name));

    document.documentElement.classList.add(`homepage-variant--${variant}`);
  }

  function appendStylesheet(source) {
    return new Promise((resolve, reject) => {
      const link = document.createElement('link');
      for (const attribute of source.attributes) {
        link.setAttribute(attribute.name, attribute.value);
      }
      link.dataset.homepageAssetLoaded = 'true';
      link.addEventListener('load', resolve, { once: true });
      link.addEventListener('error', () => reject(new Error(`Stylesheet failed: ${link.href}`)), { once: true });
      document.head.appendChild(link);
    });
  }

  function appendScript(source) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      for (const attribute of source.attributes) {
        script.setAttribute(attribute.name, attribute.value);
      }
      script.dataset.homepageAssetLoaded = 'true';
      script.addEventListener('load', resolve, { once: true });
      script.addEventListener('error', () => reject(new Error(`Script failed: ${script.src}`)), { once: true });
      document.body.appendChild(script);
    });
  }

  async function loadHomepageAssets() {
    const template = app.querySelector('template[data-homepage-assets]');
    if (!template) return;

    const assets = [...template.content.children];
    template.remove();

    // CSS first, then scripts in declaration order. This keeps each homepage's
    // implementation inside its own package while the root loader remains generic.
    for (const asset of assets.filter((node) => node.tagName === 'LINK')) {
      await appendStylesheet(asset);
    }
    for (const asset of assets.filter((node) => node.tagName === 'SCRIPT')) {
      await appendScript(asset);
    }
  }


  function randomIndex(maxExclusive) {
    if (maxExclusive <= 1) return 0;

    if (window.crypto?.getRandomValues) {
      const maxUint32 = 0x100000000;
      const limit = maxUint32 - (maxUint32 % maxExclusive);
      const values = new Uint32Array(1);
      do {
        window.crypto.getRandomValues(values);
      } while (values[0] >= limit);
      return values[0] % maxExclusive;
    }

    return Math.floor(Math.random() * maxExclusive);
  }

  function shuffleChildren(container) {
    if (!container) return;
    const items = [...container.children];
    for (let i = items.length - 1; i > 0; i -= 1) {
      const j = randomIndex(i + 1);
      [items[i], items[j]] = [items[j], items[i]];
    }
    items.forEach((item) => container.appendChild(item));
  }

  function initializeRandomizedOrder() {
    shuffleChildren(app.querySelector(".selected-work-index__grid"));
  }

  function initializeHomepage() {
    setHomepageVariantClass();
    initializeRandomizedOrder();
    initializeMediaDefaults();
    initializeContactForm();
  }

  async function loadHomepage() {
    const selectedFile = TEST_HOMEPAGE_FILE;

    try {
      const fragmentUrl = `${selectedFile}?v=v021`;
      const response = await fetch(fragmentUrl, {
        cache: "no-store",
        credentials: "same-origin"
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      app.innerHTML = await response.text();
      initializeHomepage();
      await loadHomepageAssets();
      document.documentElement.classList.add("is-ready");
      console.info(`Loaded WIP testing homepage: ${selectedFile}`);
    } catch (error) {
      console.error("Homepage load failed:", error);
      app.innerHTML = `
        <section class="fallback">
          <h1>Homepage unavailable.</h1>
          <p>Please refresh the page or check the homepage manifest.</p>
        </section>
      `;
      document.documentElement.classList.add("is-ready");
    }
  }

  initializeAnimatedTitle();
  loadHomepage();
})();
