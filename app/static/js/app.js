/* Ymmo — progressive enhancement only: every feature also works without JavaScript. */
(() => {
  "use strict";

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

  // Lists marked data-stagger reveal their items one after the other (cycle of 6 per row band).
  document.querySelectorAll("[data-stagger]").forEach((list) => {
    [...list.children].forEach((item, index) => {
      item.setAttribute("data-reveal", "");
      item.style.setProperty("--reveal-i", index % 6);
    });
  });

  // Cross-document view transition: the clicked listing photo becomes the detail gallery photo
  // (and the reverse on the way back). Only the photo involved gets the shared name.
  const detailId = (url) => url && new URL(url).pathname.match(/^\/biens\/(\d+)$/)?.[1];
  const cardPhoto = (id) => id && document.querySelector(`.property-card a[href="/biens/${id}"]`)
    ?.closest(".property-card")?.querySelector(".card-media img");
  const nameDuring = (img, transition) => {
    if (!img || !transition) return;
    img.style.viewTransitionName = "listing-photo";
    transition.finished.finally(() => { img.style.viewTransitionName = ""; });
  };
  window.addEventListener("pageswap", (event) => {
    nameDuring(cardPhoto(detailId(event.activation?.entry?.url)), event.viewTransition);
  });
  window.addEventListener("pagereveal", (event) => {
    if (!event.viewTransition || !window.navigation?.activation) return;
    nameDuring(cardPhoto(detailId(navigation.activation.from?.url)), event.viewTransition);
  });

  // Gentle reveal on scroll; skipped entirely when the user prefers reduced motion.
  const revealables = document.querySelectorAll("[data-reveal]");
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const reduceMotion = motionQuery.matches;
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

  // Agencies map: hovering or focusing a city in the list lights its dot, and the reverse.
  const agencies = document.querySelector("[data-agencies]");
  if (agencies) {
    const light = (id) => agencies.querySelectorAll("[data-agency]").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.agency === id);
    });
    const track = (event) => light(event.target.closest("[data-agency]")?.dataset.agency ?? null);
    ["pointerover", "focusin"].forEach((type) => agencies.addEventListener(type, track));
    ["pointerleave", "focusout"].forEach((type) => agencies.addEventListener(type, () => light(null)));
  }

  // Search filters are served collapsed (results first on phones, no layout shift); the wide
  // layout shows them in a side column, so opening them there moves nothing.
  if (window.matchMedia("(min-width: 64rem)").matches) {
    document.querySelectorAll("details[data-open-wide]").forEach((d) => { d.open = true; });
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
    const empty = document.querySelector("[data-estimate-empty]");
    if (empty) empty.hidden = false;
    const formatter = new Intl.NumberFormat("fr-FR", {
      style: "currency", currency: "EUR", maximumFractionDigits: 0,
    });
    let shown = 0;
    let frame = 0;
    const note = (text) => {
      cancelAnimationFrame(frame);
      output.classList.add("is-note");
      output.textContent = text;
    };
    // The amount counts up in 600 ms; screen readers only get the final value.
    const showAmount = (amount) => {
      cancelAnimationFrame(frame);
      if (empty) empty.hidden = true;
      output.classList.remove("is-note");
      output.innerHTML = '<span aria-hidden="true"></span><span class="visually-hidden"></span>';
      const [visual, spoken] = output.children;
      spoken.textContent = formatter.format(amount);
      const from = shown;
      shown = amount;
      if (motionQuery.matches) {
        visual.textContent = formatter.format(amount);
        return;
      }
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / 600);
        const eased = 1 - (1 - t) ** 4;
        visual.textContent = formatter.format(Math.round(from + (amount - from) * eased));
        if (t < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    };
    button.addEventListener("click", async () => {
      const data = Object.fromEntries(
        [...new FormData(form).entries()].filter(([, value]) => value !== "")
      );
      if (!data.surface_m2 || !data.city_id || !data.address) {
        note("Renseignez au moins la surface, l’adresse et la ville.");
        return;
      }
      note("Calcul en cours…");
      try {
        const response = await fetch("/api/estimations/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        const body = await response.json();
        if (!response.ok) {
          note("Vérifiez les informations saisies.");
        } else if (body.estimated_price === null) {
          note("Pas assez de ventes comparables pour estimer ce bien.");
        } else {
          showAmount(Number(body.estimated_price));
        }
      } catch {
        note("Estimation indisponible pour le moment.");
      }
    });
  }
})();
