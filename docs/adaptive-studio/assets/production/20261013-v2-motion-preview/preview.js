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
    const rain = [...svg.querySelector("#rain-and-glass-reflections").children];
    const drops = rain.filter(node => ["#071e2c", "#c4dce0"].includes(node.getAttribute("stroke")));
    for (let i = 0; i < drops.length; i += 2) wrap(drops.slice(i, i + 2), "rain-" + ["a", "b", "c"][(i / 2) % 3]);
    wrap([...svg.querySelector("#floor-reflections").children].slice(0, 3), "reflection-light");
    wrap(rain.slice(-2), "reflection-light");
    // The clipping parent and later window joinery stay stationary.
    wrap([...svg.querySelector("#last-train").children], "train-piece");
  } else {
    const lantern = [...svg.querySelector("#engraved-brass-lantern").children];
    wrap(lantern.slice(28, 30), "flame-light");
    wrap([svg.querySelector("#glass-lens-and-warm-irradiance")], "flame-light");
    wrap([...svg.querySelector("#steam").children], "steam-rise");
  }
  const play = preview.querySelector("[data-play]");
  const pause = preview.querySelector("[data-pause]");
  const status = preview.querySelector("output");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let requested = false, pageHidden = false;
  const bounds = art.getBoundingClientRect();
  let onscreen = bounds.bottom > 0 && bounds.top < innerHeight && bounds.right > 0 && bounds.left < innerWidth;
  const update = () => {
    const state = preference.matches ? "reduced" : !requested ? "paused" : (document.hidden || pageHidden) ? "hidden" : !onscreen ? "offscreen" : "playing";
    preview.dataset.state = state;
    play.disabled = preference.matches || requested;
    pause.disabled = !requested;
    status.textContent = {reduced: "Still — reduced motion is enabled.", paused: "Still / paused. Press Play for optional motion.", hidden: "Paused while the document is hidden.", offscreen: "Paused while the artwork is offscreen.", playing: "Playing — optional motion preview."}[state];
  };
  play.addEventListener("click", () => { preview.dataset.motionStarted = "true"; requested = true; update(); });
  pause.addEventListener("click", () => { requested = false; update(); });
  document.addEventListener("visibilitychange", update);
  window.addEventListener("pagehide", () => { pageHidden = true; update(); });
  window.addEventListener("pageshow", () => { pageHidden = false; update(); });
  preference.addEventListener("change", () => { preview.dataset.motionStarted = "false"; requested = false; update(); });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(entries => { onscreen = entries[0].isIntersecting && entries[0].intersectionRatio >= .15; update(); }, {threshold: [0, .15]}).observe(art);
  } else {
    // A browser without observation keeps its complete still instead of running unseen.
    play.disabled = true;
    status.textContent = "Still — this browser cannot observe artwork visibility.";
    return;
  }
  const train = preview.querySelector("[data-train-toggle]");
  if (train) train.addEventListener("change", () => { preview.dataset.train = String(train.checked); });
  update();
})();
