(() => {
  "use strict";
  const preview = document.querySelector("[data-motion-preview]");
  if (!preview) return;
  const art = preview.querySelector("[data-motion-art]");
  const svg = art.querySelector("svg");
  const wrap = (nodes, className) => {
    if (!nodes.length) return;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", "motion-piece " + className);
    nodes[0].before(group);
    nodes.forEach(node => group.append(node));
  };
  if (preview.dataset.asset === "las") {
    const rain = svg.querySelector("#rain-and-glass-reflections");
    const weather = document.createElementNS("http://www.w3.org/2000/svg", "g");
    weather.setAttribute("id", "preview-falling-rain");
    weather.setAttribute("data-preview-layer", "falling-rain");
    weather.setAttribute("class", "preview-overlay");
    const lanes = [1101,1136,1172,1204,1237,1274,1302,1334,1369,1401,1435,1472,1501,1535,1558,1189];
    lanes.forEach((x, i) => {
      const drop = document.createElementNS("http://www.w3.org/2000/svg", "g");
      drop.setAttribute("id", "motion-rain-drop-" + (i + 1));
      drop.setAttribute("class", "motion-piece falling-rain");
      drop.style.setProperty("--phase", (-i * .123) + "s");
      const streak = document.createElementNS("http://www.w3.org/2000/svg", "path");
      streak.setAttribute("d", "M" + x + " -100l-2 " + (28 + (i % 3) * 8));
      streak.setAttribute("fill", "none");
      streak.setAttribute("stroke", "#c4dce0");
      streak.setAttribute("stroke-width", "4.25");
      streak.setAttribute("stroke-linecap", "round");
      streak.setAttribute("opacity", ".64");
      drop.append(streak); weather.append(drop);
    });
    // Native preview-only strokes inherit the stationary window clip; the
    // accepted static glass/rivulets remain unchanged underneath.
    rain.append(weather);
    wrap([...svg.querySelector("#floor-reflections").children].slice(0, 3), "reflection-light");
    wrap([...rain.children].slice(-3, -1), "reflection-light");
    wrap([...svg.querySelector("#last-train").children], "train-piece");
  } else {
    const lantern = [...svg.querySelector("#engraved-brass-lantern").children];
    wrap(lantern.slice(28, 30), "flame-motion");
    wrap([svg.querySelector("#glass-lens-and-warm-irradiance")], "flame-light");
    const steam = svg.querySelector("#steam");
    const original = [...steam.children];
    const secondary = document.createElementNS("http://www.w3.org/2000/svg", "g");
    secondary.setAttribute("id", "motion-steam-secondary");
    secondary.setAttribute("data-preview-layer", "rising-steam");
    secondary.setAttribute("class", "motion-piece steam-rise steam-secondary preview-overlay");
    original.forEach(node => { const copy = node.cloneNode(true); copy.setAttribute("transform", "translate(12 0)"); secondary.append(copy); });
    wrap(original, "steam-rise");
    steam.append(secondary);
  }
  const play = preview.querySelector("[data-play]");
  const pause = preview.querySelector("[data-pause]");
  const status = preview.querySelector("output");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  const observationAvailable = "IntersectionObserver" in window;
  let requested = false, pageHidden = false;
  const bounds = art.getBoundingClientRect();
  let onscreen = bounds.bottom > 0 && bounds.top < innerHeight && bounds.right > 0 && bounds.left < innerWidth;
  const update = () => {
    const state = !observationAvailable ? "unsupported" : preference.matches ? "reduced" : !requested ? "paused" : (document.hidden || pageHidden) ? "hidden" : !onscreen ? "offscreen" : "playing";
    preview.dataset.state = state;
    play.disabled = !observationAvailable || preference.matches || requested;
    pause.disabled = !requested;
    status.textContent = {unsupported: "Still — this browser cannot observe artwork visibility.", reduced: "Still — reduced motion is enabled.", paused: "Still / paused. Press Play for optional motion.", hidden: "Paused while the document is hidden.", offscreen: "Paused while the artwork is offscreen.", playing: "Playing — optional motion preview."}[state];
  };
  play.addEventListener("click", () => { preview.dataset.motionStarted = "true"; requested = true; update(); });
  pause.addEventListener("click", () => { requested = false; update(); });
  document.addEventListener("visibilitychange", update);
  window.addEventListener("pagehide", () => { pageHidden = true; update(); });
  window.addEventListener("pageshow", () => { pageHidden = false; update(); });
  preference.addEventListener("change", () => { preview.dataset.motionStarted = "false"; requested = false; update(); });
  if (observationAvailable) {
    new IntersectionObserver(entries => { onscreen = entries[0].isIntersecting && entries[0].intersectionRatio >= .15; update(); }, {threshold: [0, .15]}).observe(art);
  } else {
    // A browser without observation keeps its complete still instead of running unseen.
    update();
    return;
  }
  const train = preview.querySelector("[data-train-toggle]");
  if (train) train.addEventListener("change", () => { preview.dataset.train = String(train.checked); });
  update();
})();
