// Single-series bar chart for /stats: uploads per day. Plain SVG, hover tooltip per bar.
(() => {
  "use strict";

  const data = JSON.parse(document.getElementById("daily-data").textContent);
  const box = document.getElementById("daily-chart");
  const tip = document.getElementById("chart-tip");
  const NS = "http://www.w3.org/2000/svg";
  const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  const label = (iso) => dayFmt.format(new Date(`${iso}T00:00:00Z`));

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.append(node);
    return node;
  }

  // "Nice" axis top: 1, 2, 5 x 10^n at or above the max, with a floor so 0-1 data isn't huge.
  function niceMax(v) {
    if (v <= 4) return 4;
    const p = 10 ** Math.floor(Math.log10(v));
    return [1, 2, 5, 10].map((m) => m * p).find((n) => n >= v);
  }

  function draw() {
    box.innerHTML = "";
    const width = box.clientWidth || 600;
    const height = 220;
    const pad = { top: 16, right: 8, bottom: 28, left: 32 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const max = niceMax(Math.max(...data.map((d) => d.count)));
    const y = (v) => pad.top + plotH - (v / max) * plotH;
    const slot = plotW / data.length;
    const gap = 2; // surface gap between adjacent bars
    const barW = Math.max(4, Math.min(28, slot - gap));

    const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "chart-svg" }, box);

    // Recessive grid: baseline + two lines, labelled on the left.
    for (const t of [0, max / 2, max]) {
      el("line", { x1: pad.left, x2: width - pad.right, y1: y(t), y2: y(t), class: t === 0 ? "axis" : "grid" }, svg);
      const tl = el("text", { x: pad.left - 8, y: y(t) + 4, class: "tick", "text-anchor": "end" }, svg);
      tl.textContent = Number.isInteger(t) ? t : t.toFixed(1);
    }

    const peak = data.reduce((a, b) => (b.count > a.count ? b : a), data[0]);
    data.forEach((d, i) => {
      const cx = pad.left + slot * i + slot / 2;
      const x = cx - barW / 2;
      if (d.count > 0) {
        // Rounded data-end on top, square at the baseline.
        const top = y(d.count);
        const h = pad.top + plotH - top;
        const r = Math.min(4, h, barW / 2);
        el("path", {
          d: `M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + h} Z`,
          class: "bar",
        }, svg);
      }
      // Label every third day counting back from today, so today is always labelled and
      // neighbouring labels never collide, even at phone width.
      if ((data.length - 1 - i) % 3 === 0) {
        const xl = el("text", { x: cx, y: height - 8, class: "tick", "text-anchor": "middle" }, svg);
        xl.textContent = label(d.date);
      }
      // Hit target wider and taller than the bar.
      const hit = el("rect", { x: pad.left + slot * i, y: pad.top, width: slot, height: plotH, class: "hit" }, svg);
      hit.addEventListener("pointerenter", () => show(d, cx, y(d.count)));
      hit.addEventListener("pointerleave", hide);
    });

    // Selective direct label: only the peak day.
    if (peak.count > 0) {
      const i = data.indexOf(peak);
      const t = el("text", { x: pad.left + slot * i + slot / 2, y: y(peak.count) - 6, class: "value", "text-anchor": "middle" }, svg);
      t.textContent = peak.count;
    }
  }

  function show(d, x, y) {
    tip.textContent = `${label(d.date)} · ${d.count} image${d.count === 1 ? "" : "s"}`;
    tip.hidden = false;
    const left = Math.min(Math.max(x - tip.offsetWidth / 2, 0), box.clientWidth - tip.offsetWidth);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(y - 40, 0)}px`;
  }

  function hide() {
    tip.hidden = true;
  }

  draw();
  let frame;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(draw);
  });
})();
