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

  // Header: transparent over the home hero, solid once the page scrolls. Browsers with
  // scroll-driven animations do it in CSS at the pace of the scroll; this is their fallback.
  // Follows reduced motion live, as the CSS does.
  const header = document.querySelector("[data-header]");
  const hasScrollTimelines = window.CSS?.supports?.("animation-timeline: scroll()");
  const stillMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 24);
    const syncHeader = () => {
      if (hasScrollTimelines && !stillMotion.matches) {
        window.removeEventListener("scroll", onScroll);
        header.classList.remove("is-scrolled");
        return;
      }
      // First read on the next frame: reading scrollY during start-up would force a layout.
      requestAnimationFrame(onScroll);
      window.addEventListener("scroll", onScroll, { passive: true });
    };
    syncHeader();
    stillMotion.addEventListener?.("change", syncHeader);
  }

  const reduceMotion = stillMotion.matches;

  // Figures count up to their value once, as they come on screen. The final value stays in the
  // flow as plain, transparent text (screen readers read it, the layout keeps its exact width);
  // the running number is drawn over it (aria-hidden), then the original text comes back.
  const countUp = (el) => {
    const node = [...el.childNodes].find((n) => n.nodeType === 3 && /\d/.test(n.data));
    const raw = node?.data.match(/\d[\d\s,]*/)?.[0].trim();
    // A page arriving through a transition shows its figures as they are (motion.js)
    if (!raw || document.documentElement.classList.contains("vt-settling")) return;
    const target = parseFloat(raw.replace(/\s/g, "").replace(",", "."));
    const decimals = (raw.split(",")[1] || "").length;
    const space = raw.match(/\s/)?.[0] ?? " ";
    // Same grouping as the source ("1250" stays ungrouped), so the running number keeps its width
    const format = new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: /\s/.test(raw),
    });
    const box = document.createElement("span");
    box.className = "count";
    box.innerHTML = '<span class="count-final"></span><span class="count-run" aria-hidden="true"></span>';
    box.firstChild.textContent = node.data;
    node.replaceWith(box);
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / 960);
      const value = format.format(target * (1 - (1 - t) ** 4)).replace(/\s/g, space);
      box.lastChild.textContent = node.data.replace(raw, value);
      if (t < 1) requestAnimationFrame(step);
      else box.replaceWith(node);
    };
    requestAnimationFrame(step);
  };

  // Reveal on scroll, once (motion.js sets .js-reveal before the first paint, CSS holds the
  // hidden states). Lists marked data-stagger reveal their items one after the other, by cycles
  // of 6. Without IntersectionObserver or with reduced motion, nothing is hidden or animated.
  const root = document.documentElement;
  document.querySelectorAll("[data-stagger]").forEach((list) => {
    [...list.children].forEach((item, index) => item.style.setProperty("--reveal-i", index % 6));
  });
  if ("IntersectionObserver" in window && !reduceMotion) {
    root.dataset.motion = "ready";
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(({ isIntersecting, target }) => {
        if (!isIntersecting) return;
        observer.unobserve(target);
        if (target.matches("[data-count]")) countUp(target);
        else target.classList.add("is-visible");
      });
    }, { threshold: 0.15 });
    document.querySelectorAll("[data-reveal], [data-stagger] > *").forEach((el) => observer.observe(el));
    document.querySelectorAll(".hero-stats strong, .band-figures dd, .split-figure, .kpis .kpi-value")
      .forEach((el) => { el.dataset.count = ""; observer.observe(el); });
  }

  // Home hero: live light, fetched only after the page has loaded and gone idle, only while the
  // hero is on screen, never with reduced motion or data saver. The poster stays as the fallback.
  const hero = document.querySelector(".hero[data-light-src]");
  if (hero && !reduceMotion && !navigator.connection?.saveData
      && "IntersectionObserver" in window && "WebGLRenderingContext" in window) {
    const loadScene = () => {
      const observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        import(hero.dataset.lightSrc).then((module) => module.mount(hero)).catch(() => {});
      });
      observer.observe(hero);
    };
    // Wait for the web fonts too: the title's final paint (the LCP) must not queue behind WebGL work.
    const whenIdle = () => (document.fonts?.ready ?? Promise.resolve()).then(() => (
      "requestIdleCallback" in window
        ? window.requestIdleCallback(loadScene, { timeout: 3000 })
        : window.setTimeout(loadScene, 300)));
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
  // Kept in sync on resize/rotation: the summary is hidden on wide screens, so closed filters
  // would otherwise be unreachable there.
  const wide = window.matchMedia("(min-width: 64rem)");
  const openWide = () => {
    if (wide.matches) document.querySelectorAll("details[data-open-wide]").forEach((d) => { d.open = true; });
  };
  openWide();
  wide.addEventListener("change", openWide);

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
    // The amount counts up in 640 ms (--dur-m); screen readers only get the final value.
    const showAmount = (amount) => {
      cancelAnimationFrame(frame);
      if (empty) empty.hidden = true;
      output.classList.remove("is-note");
      output.innerHTML = '<span aria-hidden="true"></span><span class="visually-hidden"></span>';
      const [visual, spoken] = output.children;
      spoken.textContent = formatter.format(amount);
      const from = shown;
      shown = amount;
      if (stillMotion.matches) {
        visual.textContent = formatter.format(amount);
        return;
      }
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / 640);
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
