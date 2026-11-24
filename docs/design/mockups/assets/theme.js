// projectArthas mock-ups: theme + day/night toggle, number ticker, entrance trigger.
// Load in <head> without defer so the theme applies before first paint.
(function () {
  var KEY = "dips-score-theme";
  var root = document.documentElement;
  var dark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private window: theme still works, just not remembered */ }
  }

  var state = load();
  // a hash like #classical-night (or #timeless-day-still) shows one combination without saving it;
  // "still" turns off the entrance motion so screenshots show the settled page
  var words = location.hash.slice(1).toLowerCase().split(/[-,]/);
  if (words.indexOf("classical") >= 0) state.theme = "classical";
  if (words.indexOf("timeless") >= 0) state.theme = "timeless";
  ["day", "night", "auto"].forEach(function (m) { if (words.indexOf(m) >= 0) state.mode = m; });
  var still = words.indexOf("still") >= 0;
  if (still) reduce = true;
  state.theme = state.theme === "classical" ? "classical" : "timeless";
  state.mode = ["day", "night", "auto"].indexOf(state.mode) >= 0 ? state.mode : "auto";

  function apply() {
    var mode = state.mode === "auto" ? (dark && dark.matches ? "night" : "day") : state.mode;
    root.setAttribute("data-theme", state.theme);
    root.setAttribute("data-mode", mode);
    var buttons = document.querySelectorAll("[data-set-theme],[data-set-mode]");
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      var on = b.hasAttribute("data-set-theme") ? b.getAttribute("data-set-theme") === state.theme
                                                : b.getAttribute("data-set-mode") === state.mode;
      b.setAttribute("aria-pressed", on ? "true" : "false");
    }
  }
  apply();
  if (!still) root.classList.add("js");
  if (dark && dark.addEventListener) dark.addEventListener("change", function () { if (state.mode === "auto") apply(); });

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-set-theme],[data-set-mode]");
    if (!b) return;
    if (b.hasAttribute("data-set-theme")) state.theme = b.getAttribute("data-set-theme");
    else state.mode = b.getAttribute("data-set-mode");
    save({ theme: state.theme, mode: state.mode });
    root.classList.add("theme-swap");
    apply();
    setTimeout(function () { root.classList.remove("theme-swap"); }, 300);
  });

  document.addEventListener("DOMContentLoaded", function () {
    apply();
    // number ticker: <span data-count="75">75</span> counts up from 0; the final value is already in the markup
    if (!reduce) {
      var nums = document.querySelectorAll("[data-count]");
      for (var i = 0; i < nums.length; i++) (function (el) {
        var end = parseFloat(el.getAttribute("data-count")), t0 = null, dur = 700;
        function step(t) {
          if (t0 === null) t0 = t;
          var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
          el.textContent = Math.round(end * e);
          if (p < 1) requestAnimationFrame(step);
        }
        el.textContent = "0";
        requestAnimationFrame(step);
      })(nums[i]);
    }
    requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.add("ready"); }); });
  });
})();
