/* Ymmo — page-change motion. Loaded in <head> (not deferred): `pagereveal` must be listened to
   before the first render, and the hidden states of the reveals must be in place before the
   first paint (no flash of content that then hides). Everything here is an enhancement: without
   it, pages change normally and all content is visible. */
(() => {
  "use strict";
  const root = document.documentElement;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // Reveals on scroll are driven by app.js; if it never runs, show everything after load.
  if ("IntersectionObserver" in window) {
    root.classList.add("js-reveal");
    addEventListener("load", () => setTimeout(() => {
      if (!root.dataset.motion) root.classList.remove("js-reveal");
    }, 1500), { once: true });
  }

  // A listing's photo, title and price: on its card (lists, home) and on its own page. Only the
  // listing being opened (or left) gets the shared names, for the duration of the transition.
  const listingId = (url) => url && new URL(url).pathname.match(/^\/biens\/(\d+)$/)?.[1];
  const depth = (url) => {
    const path = new URL(url).pathname;
    return path === "/" ? 0 : listingId(url) ? 2 : 1;
  };
  const share = (id, transition) => {
    const scope = id && document.querySelector(`[data-listing="${id}"]`);
    if (!scope) return;
    scope.querySelectorAll("[data-vt]").forEach((el) => {
      el.style.viewTransitionName = `listing-${el.dataset.vt}-${id}`;
      el.style.viewTransitionClass = `listing ${el.dataset.vt}`;
      transition.finished.finally(() => {
        el.style.viewTransitionName = "";
        el.style.viewTransitionClass = "";
      });
    });
  };

  addEventListener("pageswap", (event) => {
    const { viewTransition: transition, activation } = event;
    if (!transition || !activation) return;
    share(listingId(activation.entry?.url) || listingId(activation.from?.url), transition);
  });

  addEventListener("pagereveal", (event) => {
    const transition = event.viewTransition;
    const activation = window.navigation?.activation;
    if (!transition || !activation?.from) return;
    const from = activation.from.url;
    const to = activation.entry.url;
    // Filters and sort: same list, new request. Only the cards change (a quick cross-fade);
    // nothing moves and nothing is revealed again.
    if (new URL(from).pathname === "/biens" && new URL(to).pathname === "/biens") {
      transition.types.add("refine");
      root.classList.remove("js-reveal");
      return;
    }
    share(listingId(to) || listingId(from), transition);
    // Back/forward: the page is already known, and its scroll position is restored after this
    // event, so what is on screen cannot be told yet. Everything is shown as it is.
    if (activation.navigationType === "traverse") root.classList.remove("js-reveal");
    const step = depth(to) - depth(from)
      || (activation.navigationType === "traverse" ? activation.entry.index - activation.from.index : 0);
    if (step) transition.types.add(step > 0 ? "forward" : "back");
    root.classList.add("vt-arriving");
    // What is already on screen arrives with the page, not revealed on top of it: one movement
    // at a time, and a reveal under the transition would repaint the page's snapshot every frame.
    root.classList.add("vt-settling");
    document.querySelectorAll("[data-reveal], [data-stagger] > *").forEach((el) => {
      if (el.getBoundingClientRect().top < innerHeight) el.classList.add("is-visible");
    });
    transition.finished.finally(() => root.classList.remove("vt-settling", "vt-arriving"));
  });
})();
