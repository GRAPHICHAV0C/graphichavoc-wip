(() => {
  "use strict";


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
    shuffleChildren(document.querySelector(".work-index__grid"));
  }

  function resetContactState(form) { form.classList.remove("is-validation-error", "is-success"); }
  function setValidationError(form) { form.classList.remove("is-success"); form.classList.add("is-validation-error"); }
  function setSuccess(form) { form.classList.remove("is-validation-error"); form.classList.add("is-success"); }

  function normalizeUrlField(form) {
    const urlField = form.querySelector('input[name="url"]');
    if (!urlField) return;
    const value = urlField.value.trim();
    if (!value) return;
    const hasProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(value);
    const hasSchemePrefix = /^[a-z][a-z0-9+.-]*:/i.test(value);
    if (!hasProtocol && !hasSchemePrefix) urlField.value = `https://${value}`;
  }

  function formIsComplete(form) {
    return [...form.querySelectorAll("[required]")].every((field) => field.value.trim() !== "" && field.checkValidity());
  }

  async function submitToWeb3Forms(form) {
    const response = await fetch("https://api.web3forms.com/submit", { method: "POST", body: new FormData(form) });
    let result = null;
    try { result = await response.json(); } catch (_) {}
    return response.ok && (result?.success ?? true);
  }

  function initializeContactForm() {
    const form = document.querySelector(".contact-form");
    if (!form) return;
    form.addEventListener("input", () => { if (form.classList.contains("is-validation-error")) resetContactState(form); });
    form.querySelector('input[name="url"]')?.addEventListener("blur", () => normalizeUrlField(form));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.classList.contains("is-success")) return;
      normalizeUrlField(form);
      if (!formIsComplete(form)) {
        setValidationError(form);
        form.querySelector(":invalid")?.focus();
        return;
      }
      const submitButton = form.querySelector(".contact-form__submit");
      if (submitButton) submitButton.disabled = true;
      try {
        if (await submitToWeb3Forms(form)) { setSuccess(form); form.reset(); }
      } catch (error) {
        console.error("Web3Forms submission failed:", error);
      } finally {
        if (submitButton && !form.classList.contains("is-success")) submitButton.disabled = false;
      }
    });
    const previewState = new URLSearchParams(location.search).get("form-state");
    if (previewState === "success") setSuccess(form);
    if (previewState === "error") setValidationError(form);
  }

  initializeRandomizedOrder();
  initializeContactForm();
  document.documentElement.classList.add("is-ready");
})();
