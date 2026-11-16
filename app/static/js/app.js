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
    });
  }

  // Search filters start collapsed on small screens (results first).
  if (window.matchMedia("(max-width: 59.99rem)").matches) {
    document.querySelectorAll("details[data-collapse-mobile]").forEach((d) => d.removeAttribute("open"));
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
