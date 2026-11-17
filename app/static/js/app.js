/* Ymmo — progressive enhancement only: every feature also works without JavaScript. */
(() => {
  "use strict";
  document.documentElement.classList.remove("no-js");

  // Mobile navigation toggle (disclosure pattern).
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      nav.dataset.open = String(!open);
      header?.classList.toggle("is-open", !open);
    });
  }

  // Header: transparent over the home hero, solid once the page scrolls.
  const header = document.querySelector("[data-header]");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 24);
    // First read on the next frame: reading scrollY during start-up would force a layout.
    requestAnimationFrame(onScroll);
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Gentle reveal on scroll; skipped entirely when the user prefers reduced motion.
  const revealables = document.querySelectorAll("[data-reveal]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (revealables.length && "IntersectionObserver" in window && !reduceMotion) {
    document.documentElement.classList.add("js-reveal");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealables.forEach((el) => observer.observe(el));
  }

  // Home hero: 3D arcade, fetched only after the page has loaded and gone idle, only while the
  // hero is on screen, never with reduced motion or data saver. The SVG stays as the fallback.
  const hero = document.querySelector(".hero[data-arcade-src]");
  if (hero && !reduceMotion && !navigator.connection?.saveData
      && "IntersectionObserver" in window && "WebGLRenderingContext" in window) {
    const loadArcade = () => {
      const observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        import(hero.dataset.arcadeSrc).then((module) => module.mount(hero)).catch(() => {});
      });
      observer.observe(hero);
    };
    // Wait for the web fonts too: the title's final paint (the LCP) must not queue behind 3D work.
    const whenIdle = () => (document.fonts?.ready ?? Promise.resolve()).then(() => (
      "requestIdleCallback" in window
        ? window.requestIdleCallback(loadArcade, { timeout: 3000 })
        : window.setTimeout(loadArcade, 300)));
    if (document.readyState === "complete") whenIdle();
    else window.addEventListener("load", whenIdle, { once: true });
  }

  // Search filters start collapsed on small screens (results first).
  if (window.matchMedia("(max-width: 59.99rem)").matches) {
    document.querySelectorAll("details[data-collapse-mobile]").forEach((d) => d.removeAttribute("open"));
  }

  // Tables that scroll sideways become keyboard-focusable regions named after their caption.
  const wraps = document.querySelectorAll(".table-wrap");
  const syncScrollable = () => wraps.forEach((wrap) => {
    if (wrap.scrollWidth > wrap.clientWidth + 1) {
      wrap.tabIndex = 0;
      wrap.setAttribute("role", "region");
      const caption = wrap.querySelector("caption");
      wrap.setAttribute("aria-label", caption ? caption.textContent.trim() : "Tableau défilant");
    } else {
      wrap.removeAttribute("tabindex");
      wrap.removeAttribute("role");
      wrap.removeAttribute("aria-label");
    }
  });
  if (wraps.length) {
    syncScrollable();
    // Also when a <details> opens (hidden tables have no width until then).
    document.querySelectorAll("details").forEach((d) => d.addEventListener("toggle", syncScrollable));
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(syncScrollable, 150);
    });
  }

  // Confirmation before destructive actions.
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Sort selector submits on change.
  document.querySelectorAll("form[data-autosubmit] select").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });

  // Move focus to the error summary so screen-reader users hear it first.
  const summary = document.querySelector("[data-autofocus]");
  if (summary) summary.focus();

  // Instant price estimate on the "sell my property" page.
  const form = document.getElementById("estimate-form");
  const button = document.querySelector("[data-estimate-preview]");
  const output = document.getElementById("estimate-result");
  if (form && button && output) {
    button.hidden = false;
    const formatter = new Intl.NumberFormat("fr-FR", {
      style: "currency", currency: "EUR", maximumFractionDigits: 0,
    });
    button.addEventListener("click", async () => {
      const data = Object.fromEntries(
        [...new FormData(form).entries()].filter(([, value]) => value !== "")
      );
      if (!data.surface_m2 || !data.city_id || !data.address) {
        output.textContent = "Renseignez au moins la surface, l'adresse et la ville.";
        return;
      }
      output.textContent = "Calcul en cours…";
      try {
        const response = await fetch("/api/estimations/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        const body = await response.json();
        if (!response.ok) {
          output.textContent = "Vérifiez les informations saisies.";
        } else if (body.estimated_price === null) {
          output.textContent = "Pas assez de ventes comparables pour estimer ce bien.";
        } else {
          output.textContent = formatter.format(Number(body.estimated_price));
        }
      } catch {
        output.textContent = "Estimation indisponible pour le moment.";
      }
    });
  }
})();
