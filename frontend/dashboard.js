const MODELS = [
  { key: "elo", label: "Elo", color: "var(--model-elo)", colorHex: "#2563eb" },
  { key: "poisson", label: "Poisson", color: "var(--model-poisson)", colorHex: "#f59e0b" },
  { key: "combined", label: "Combined", color: "var(--model-combined)", colorHex: "#00c767" },
];

const fmtPct = v => `${(v * 100).toFixed(1)}%`;
const fmt3 = v => v.toFixed(3);

let DATA = null;

async function init() {
  const errEl = document.getElementById("dashError");
  try {
    const res = await fetch("/dashboard/data");
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    DATA = await res.json();
  } catch (e) {
    errEl.textContent = `Could not load dashboard data: ${e.message}`;
    return;
  }

  document.getElementById("dashSubtext").textContent =
    `${DATA.eval_matches.toLocaleString()} matches, evaluated walk-forward on the identical fixture set for all three models ` +
    `(first ${DATA.min_train_matches} matches held out as training warm-up, not scored for any model).`;

  document.getElementById("dashFootnote").textContent =
    `Elo, Poisson, and Combined are all scored on the same ${DATA.eval_matches.toLocaleString()} matches here — ` +
    `this differs from the walk-forward backtest scripts shipped in src/evaluation, where Elo is scored on every match ` +
    `(no warm-up skip) while Poisson and Combined skip the first ${DATA.min_train_matches}. That mismatch makes a direct ` +
    `Elo-vs-Combined comparison from those scripts' own headline numbers invalid; this page corrects for it.`;

  renderStatCards(DATA.summary);
  populateSeasonFilter(DATA.seasons);
  renderLegend("rollingLegend");
  renderLegend("calibrationLegend");

  drawRollingChart("all");
  drawCalibrationChart("all");
  renderSeasonTable(DATA.season_breakdown, DATA.seasons);

  document.getElementById("seasonFilter").addEventListener("change", e => {
    drawRollingChart(e.target.value);
    drawCalibrationChart(e.target.value);
  });

  document.querySelectorAll(".dash-table-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      const showing = !target.hidden;
      target.hidden = showing;
      btn.textContent = showing ? "View as table" : "Hide table";
    });
  });

  window.addEventListener("resize", debounce(() => {
    const season = document.getElementById("seasonFilter").value;
    drawRollingChart(season);
    drawCalibrationChart(season);
  }, 200));
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function renderStatCards(summary) {
  const container = document.getElementById("dashStats");
  container.innerHTML = MODELS.map(m => {
    const s = summary[m.key];
    return `
      <div class="dash-stat-card">
        <div class="dash-stat-head">
          <span class="dash-stat-dot" style="background:${m.color}"></span>
          <span class="dash-stat-name">${m.label}${m.key === "combined" ? " (production)" : ""}</span>
        </div>
        <div class="dash-stat-row">
          <span class="dash-stat-label">Accuracy (1X2)</span>
          <span class="dash-stat-value">${fmtPct(s.accuracy)}</span>
        </div>
        <div class="dash-stat-row">
          <span class="dash-stat-label">Brier score</span>
          <span class="dash-stat-value">${fmt3(s.brier_score)}</span>
        </div>
        <div class="dash-stat-row">
          <span class="dash-stat-label">Log loss</span>
          <span class="dash-stat-value">${fmt3(s.log_loss)}</span>
        </div>
        <div class="dash-stat-row">
          <span class="dash-stat-label">Matches</span>
          <span class="dash-stat-value">${s.matches.toLocaleString()}</span>
        </div>
      </div>`;
  }).join("");
}

function renderLegend(elId) {
  document.getElementById(elId).innerHTML = MODELS.map(m => `
    <span class="dash-legend-item">
      <span class="dash-legend-swatch" style="background:${m.color}"></span>${m.label}
    </span>`).join("");
}

function populateSeasonFilter(seasons) {
  const sel = document.getElementById("seasonFilter");
  seasons.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    sel.appendChild(opt);
  });
}

// ── Per-model records from raw per-match predictions ────────────────────

function outcomeSide(pHome, pDraw, pAway) {
  if (pHome >= pDraw && pHome >= pAway) return "H";
  if (pDraw >= pHome && pDraw >= pAway) return "D";
  return "A";
}

function recordsForModel(matches, modelKey) {
  return matches.map(m => {
    const pHome = m[`${modelKey}_p_home`];
    const pDraw = m[`${modelKey}_p_draw`];
    const pAway = m[`${modelKey}_p_away`];
    const side = outcomeSide(pHome, pDraw, pAway);
    const predictedProb = Math.max(pHome, pDraw, pAway);
    return { date: m.date, correct: side === m.ftr ? 1 : 0, predictedProb };
  });
}

function rollingAccuracy(records, targetPoints = 15) {
  const chunkSize = Math.max(15, Math.round(records.length / targetPoints));
  const out = [];
  for (let start = 0; start < records.length; start += chunkSize) {
    const chunk = records.slice(start, start + chunkSize);
    if (chunk.length < chunkSize / 2) continue;
    const correct = chunk.reduce((a, r) => a + r.correct, 0);
    out.push({ date: chunk[chunk.length - 1].date, accuracy: correct / chunk.length, n: chunk.length });
  }
  return out;
}

function calibrationCurve(records, buckets = 8) {
  const sorted = [...records].sort((a, b) => a.predictedProb - b.predictedProb);
  const n = sorted.length;
  const bucketSize = Math.max(1, Math.floor(n / buckets));
  const out = [];
  for (let start = 0; start < n; start += bucketSize) {
    const chunk = sorted.slice(start, start + bucketSize);
    if (!chunk.length) continue;
    const meanPred = chunk.reduce((a, r) => a + r.predictedProb, 0) / chunk.length;
    const observed = chunk.reduce((a, r) => a + r.correct, 0) / chunk.length;
    out.push({ predicted: meanPred, observed, n: chunk.length });
  }
  return out;
}

function filteredMatches(season) {
  return season === "all" ? DATA.matches : DATA.matches.filter(m => m.season === season);
}

// ── SVG line chart (shared by both panels) ───────────────────────────────

const MARGIN = { top: 16, right: 20, bottom: 32, left: 42 };

function svgSize(svgEl) {
  const rect = svgEl.getBoundingClientRect();
  return { width: Math.max(rect.width, 300), height: rect.height || 320 };
}

function drawRollingChart(season) {
  const svg = document.getElementById("rollingChart");
  const tooltip = document.getElementById("rollingTooltip");
  const matches = filteredMatches(season);
  const targetPoints = season === "all" ? 17 : 6;

  const seriesByModel = {};
  MODELS.forEach(m => {
    seriesByModel[m.key] = rollingAccuracy(recordsForModel(matches, m.key), targetPoints);
  });

  renderLineChart(svg, tooltip, {
    seriesByModel,
    xKey: "date",
    yKey: "accuracy",
    yDomain: [0.3, 0.75],
    yTickFormat: fmtPct,
    xIsCategory: true,
    tooltipLabel: (pt) => `${fmtPct(pt.accuracy)} (${pt.n} matches)`,
  });

  renderTable("rollingTableWrap", ["Date", "Elo", "Poisson", "Combined", "Matches"], (() => {
    const dates = seriesByModel.elo.map(p => p.date);
    return dates.map((d, i) => [
      d,
      fmtPct(seriesByModel.elo[i]?.accuracy ?? NaN),
      fmtPct(seriesByModel.poisson[i]?.accuracy ?? NaN),
      fmtPct(seriesByModel.combined[i]?.accuracy ?? NaN),
      String(seriesByModel.elo[i]?.n ?? ""),
    ]);
  })());
}

function drawCalibrationChart(season) {
  const svg = document.getElementById("calibrationChart");
  const tooltip = document.getElementById("calibrationTooltip");
  const matches = filteredMatches(season);
  const buckets = season === "all" ? 10 : 6;

  const seriesByModel = {};
  MODELS.forEach(m => {
    seriesByModel[m.key] = calibrationCurve(recordsForModel(matches, m.key), buckets);
  });

  renderLineChart(svg, tooltip, {
    seriesByModel,
    xKey: "predicted",
    yKey: "observed",
    xDomain: [0.3, 1.0],
    yDomain: [0.3, 1.0],
    xTickFormat: fmtPct,
    yTickFormat: fmtPct,
    xIsCategory: false,
    referenceDiagonal: true,
    tooltipLabel: (pt) => `predicted ${fmtPct(pt.predicted)} → actual ${fmtPct(pt.observed)} (${pt.n})`,
  });

  renderTable("calibrationTableWrap", ["Model", "Predicted prob.", "Observed frequency", "Matches"],
    MODELS.flatMap(m => seriesByModel[m.key].map(pt => [
      m.label, fmtPct(pt.predicted), fmtPct(pt.observed), String(pt.n),
    ]))
  );
}

function renderLineChart(svgEl, tooltipEl, opts) {
  const { width, height } = svgSize(svgEl);
  const w = width - MARGIN.left - MARGIN.right;
  const h = height - MARGIN.top - MARGIN.bottom;

  svgEl.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svgEl.innerHTML = "";

  const allPoints = MODELS.flatMap(m => opts.seriesByModel[m.key]);
  if (!allPoints.length) return;

  let categories = [];
  let xScale;
  if (opts.xIsCategory) {
    categories = [...new Set(allPoints.map(p => p[opts.xKey]))];
    xScale = (v) => MARGIN.left + (categories.indexOf(v) / Math.max(1, categories.length - 1)) * w;
  } else {
    const [xMin, xMax] = opts.xDomain;
    xScale = (v) => MARGIN.left + ((v - xMin) / (xMax - xMin)) * w;
  }
  const [yMin, yMax] = opts.yDomain;
  const yScale = (v) => MARGIN.top + h - ((v - yMin) / (yMax - yMin)) * h;

  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");

  // gridlines + y ticks
  const yTicks = 5;
  for (let i = 0; i <= yTicks; i++) {
    const v = yMin + (i / yTicks) * (yMax - yMin);
    const y = yScale(v);
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", MARGIN.left);
    line.setAttribute("x2", MARGIN.left + w);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", "dash-axis-line");
    g.appendChild(line);

    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", MARGIN.left - 8);
    label.setAttribute("y", y + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("class", "dash-axis-label");
    label.textContent = opts.yTickFormat ? opts.yTickFormat(v) : v.toFixed(2);
    g.appendChild(label);
  }

  // x ticks — cap density to what actually fits (~70px per date label)
  const maxTicks = Math.max(2, Math.floor(w / 70));
  const xTickValues = opts.xIsCategory
    ? categories.filter((_, i) => i % Math.ceil(categories.length / maxTicks || 1) === 0)
    : [opts.xDomain[0], (opts.xDomain[0] + opts.xDomain[1]) / 2, opts.xDomain[1]];
  xTickValues.forEach(v => {
    const x = xScale(v);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", x);
    label.setAttribute("y", MARGIN.top + h + 20);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "dash-axis-label");
    label.textContent = opts.xTickFormat ? opts.xTickFormat(v) : v;
    g.appendChild(label);
  });

  // baseline axis
  const axis = document.createElementNS(ns, "line");
  axis.setAttribute("x1", MARGIN.left);
  axis.setAttribute("x2", MARGIN.left + w);
  axis.setAttribute("y1", MARGIN.top + h);
  axis.setAttribute("y2", MARGIN.top + h);
  axis.setAttribute("class", "dash-axis-line");
  g.appendChild(axis);

  // reference diagonal (calibration chart only) — neutral, not a model colour
  if (opts.referenceDiagonal) {
    const ref = document.createElementNS(ns, "line");
    ref.setAttribute("x1", xScale(opts.xDomain[0]));
    ref.setAttribute("y1", yScale(opts.xDomain[0]));
    ref.setAttribute("x2", xScale(opts.xDomain[1]));
    ref.setAttribute("y2", yScale(opts.xDomain[1]));
    ref.setAttribute("class", "dash-ref-line");
    g.appendChild(ref);
  }

  // series lines + points
  MODELS.forEach(m => {
    const pts = opts.seriesByModel[m.key];
    if (!pts.length) return;
    const d = pts.map((p, i) =>
      `${i === 0 ? "M" : "L"} ${xScale(p[opts.xKey])} ${yScale(p[opts.yKey])}`
    ).join(" ");
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    path.setAttribute("class", "dash-series-line");
    path.setAttribute("stroke", m.color);
    g.appendChild(path);

    pts.forEach(p => {
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", xScale(p[opts.xKey]));
      c.setAttribute("cy", yScale(p[opts.yKey]));
      c.setAttribute("r", 4.5);
      c.setAttribute("fill", m.color);
      c.setAttribute("class", "dash-series-point");
      g.appendChild(c);
    });
  });

  svgEl.appendChild(g);

  // hover layer: nearest-point crosshair + tooltip, keyed on x position
  const hoverTarget = document.createElementNS(ns, "rect");
  hoverTarget.setAttribute("x", MARGIN.left);
  hoverTarget.setAttribute("y", MARGIN.top);
  hoverTarget.setAttribute("width", w);
  hoverTarget.setAttribute("height", h);
  hoverTarget.setAttribute("class", "dash-hover-target");
  svgEl.appendChild(hoverTarget);

  const crosshair = document.createElementNS(ns, "line");
  crosshair.setAttribute("y1", MARGIN.top);
  crosshair.setAttribute("y2", MARGIN.top + h);
  crosshair.setAttribute("class", "dash-crosshair");
  crosshair.style.display = "none";
  svgEl.appendChild(crosshair);

  const referencePoints = opts.xIsCategory ? categories : (opts.seriesByModel[MODELS[0].key] || []).map(p => p[opts.xKey]);

  hoverTarget.addEventListener("mousemove", (evt) => {
    const rect = svgEl.getBoundingClientRect();
    const mouseX = evt.clientX - rect.left;
    const scaleX = width / rect.width;
    const svgX = mouseX * scaleX;

    let nearest = null;
    let nearestDist = Infinity;
    referencePoints.forEach(v => {
      const px = xScale(v);
      const dist = Math.abs(px - svgX);
      if (dist < nearestDist) { nearestDist = dist; nearest = v; }
    });
    if (nearest == null) return;

    crosshair.setAttribute("x1", xScale(nearest));
    crosshair.setAttribute("x2", xScale(nearest));
    crosshair.style.display = "block";

    const rows = MODELS.map(m => {
      const pt = opts.seriesByModel[m.key].find(p => p[opts.xKey] === nearest);
      return pt ? { model: m, pt } : null;
    }).filter(Boolean);
    if (!rows.length) return;

    tooltipEl.innerHTML = `
      <div class="dash-tooltip-title">${opts.xIsCategory ? nearest : (opts.xTickFormat ? opts.xTickFormat(nearest) : nearest)}</div>
      ${rows.map(r => `
        <div class="dash-tooltip-row">
          <span class="dash-tooltip-dot" style="background:${r.model.color}"></span>
          ${r.model.label}: ${opts.tooltipLabel(r.pt)}
        </div>`).join("")}
    `;
    tooltipEl.style.left = `${mouseX}px`;
    tooltipEl.style.top = `${(yScale(rows[0].pt[opts.yKey]) / scaleX)}px`;
    tooltipEl.hidden = false;
  });

  hoverTarget.addEventListener("mouseleave", () => {
    crosshair.style.display = "none";
    tooltipEl.hidden = true;
  });
}

function renderTable(containerId, headers, rows) {
  const container = document.getElementById(containerId);
  container.innerHTML = `
    <table class="dash-table">
      <thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>`;
}

function renderSeasonTable(breakdown, seasons) {
  const rows = [];
  seasons.forEach(season => {
    MODELS.forEach(m => {
      const s = breakdown[season][m.key];
      rows.push([season, m.label, fmtPct(s.accuracy), fmt3(s.brier_score), fmt3(s.log_loss), String(s.matches)]);
    });
  });
  renderTable("seasonTableWrap", ["Season", "Model", "Accuracy", "Brier", "Log loss", "Matches"], rows);
}

init();
