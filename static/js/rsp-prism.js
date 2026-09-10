(function () {
  "use strict";

  var root = document.documentElement;
  var storage = window.localStorage;
  var themeKey = "rsp-prism-theme";
  var soundKey = "rsp-prism-sound";
  var audioCtx = null;

  function prefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function currentThemePreference() {
    return storage.getItem(themeKey) || "auto";
  }

  function applyTheme(mode) {
    var dark = mode === "dark" || (mode === "auto" && prefersDark());
    root.classList.toggle("rsp-dark", dark);
    root.dataset.rspTheme = mode;
  }

  function soundEnabled() {
    return storage.getItem(soundKey) === "on";
  }

  function ensureAudio() {
    if (!audioCtx) {
      var AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) audioCtx = new AudioContext();
    }
    return audioCtx;
  }

  function playUiSound(type) {
    if (!soundEnabled()) return;
    var ctx = ensureAudio();
    if (!ctx) return;

    if (ctx.state === "suspended") ctx.resume();

    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    var now = ctx.currentTime;

    osc.type = "sine";
    osc.frequency.setValueAtTime(type === "toggle" ? 620 : 470, now);
    osc.frequency.exponentialRampToValueAtTime(type === "toggle" ? 780 : 560, now + 0.06);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.035, now + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.075);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.08);
  }

  function addRipple(event, element) {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var rect = element.getBoundingClientRect();
    var ripple = document.createElement("span");
    ripple.className = "rsp-ripple";
    ripple.style.left = (event.clientX - rect.left) + "px";
    ripple.style.top = (event.clientY - rect.top) + "px";
    element.classList.add("rsp-ripple-host");
    element.appendChild(ripple);
    window.setTimeout(function () { ripple.remove(); }, 620);
  }

  function addClickFeedback(element) {
    element.classList.remove("rsp-click-pop");
    void element.offsetWidth;
    element.classList.add("rsp-click-pop");
    window.setTimeout(function () { element.classList.remove("rsp-click-pop"); }, 280);
  }

  function interactiveTarget(target) {
    return target.closest("a, button, .btn, .action-card, .class-card, .payment-option, summary");
  }

  function createControls() {
    var controls = document.createElement("div");
    controls.className = "rsp-ui-controls";
    controls.setAttribute("aria-label", "تنظیمات ظاهری RSP");

    var themeButton = document.createElement("button");
    themeButton.type = "button";
    themeButton.className = "rsp-ui-control";
    themeButton.setAttribute("aria-label", "تغییر حالت روشن و تاریک");
    themeButton.title = "حالت روشن / تاریک";

    var soundButton = document.createElement("button");
    soundButton.type = "button";
    soundButton.className = "rsp-ui-control";
    soundButton.setAttribute("aria-label", "روشن یا خاموش کردن صدای رابط کاربری");
    soundButton.title = "صدای رابط کاربری";

    function refreshButtons() {
      var mode = currentThemePreference();
      var dark = root.classList.contains("rsp-dark");
      themeButton.textContent = dark ? "☀️" : "🌙";
      themeButton.classList.toggle("is-active", mode !== "auto");
      themeButton.dataset.mode = mode;

      var sound = soundEnabled();
      soundButton.textContent = sound ? "🔊" : "🔇";
      soundButton.classList.toggle("is-off", !sound);
      soundButton.classList.toggle("is-active", sound);
    }

    themeButton.addEventListener("click", function () {
      var next = root.classList.contains("rsp-dark") ? "light" : "dark";
      storage.setItem(themeKey, next);
      applyTheme(next);
      playUiSound("toggle");
      refreshButtons();
    });

    soundButton.addEventListener("click", function () {
      var next = soundEnabled() ? "off" : "on";
      storage.setItem(soundKey, next);
      if (next === "on") playUiSound("toggle");
      refreshButtons();
    });

    controls.appendChild(themeButton);
    controls.appendChild(soundButton);
    document.body.appendChild(controls);
    refreshButtons();
  }

  applyTheme(currentThemePreference());

  document.addEventListener("DOMContentLoaded", function () {
    createControls();

    document.addEventListener("click", function (event) {
      var target = interactiveTarget(event.target);
      if (!target) return;
      addRipple(event, target);
      addClickFeedback(target);
      if (!target.closest(".rsp-ui-controls")) playUiSound("click");
    });
  });

  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var syncAutoTheme = function () {
      if (currentThemePreference() === "auto") applyTheme("auto");
    };
    if (media.addEventListener) media.addEventListener("change", syncAutoTheme);
  }
})();
