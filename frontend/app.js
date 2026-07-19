const API_BASE = "";

const homeTeamSelect = document.getElementById("homeTeam");
const awayTeamSelect = document.getElementById("awayTeam");
const predictBtn = document.getElementById("predictBtn");
const errorMessage = document.getElementById("errorMessage");

const homeProb = document.getElementById("homeProb");
const drawProb = document.getElementById("drawProb");
const awayProb = document.getElementById("awayProb");

const xgHome = document.getElementById("xgHome");
const xgAway = document.getElementById("xgAway");
const xgBarHome = document.getElementById("xgBarHome");
const xgBarAway = document.getElementById("xgBarAway");
const scorelinesPills = document.getElementById("scorelinesPills");

const homeTeamName = document.getElementById("homeTeamName");
const awayTeamName = document.getElementById("awayTeamName");
const matchStatus = document.getElementById("matchStatus");
const recentPredictions = document.getElementById("recentPredictions");
const clearRecentBtn = document.getElementById("clearRecentBtn");

const homeTeamBadge = document.getElementById("homeTeamBadge");
const awayTeamBadge = document.getElementById("awayTeamBadge");
const homeEloEl = document.getElementById("homeElo");
const awayEloEl = document.getElementById("awayElo");
const homeFormEl = document.getElementById("homeForm");
const awayFormEl = document.getElementById("awayForm");
const h2hSection = document.getElementById("h2hSection");
const h2hTitle = document.getElementById("h2hTitle");
const h2hHomeCount = document.getElementById("h2hHomeCount");
const h2hAwayCount = document.getElementById("h2hAwayCount");
const h2hFillHome = document.getElementById("h2hFillHome");
const h2hFillDraw = document.getElementById("h2hFillDraw");
const h2hFillAway = document.getElementById("h2hFillAway");
const h2hSub = document.getElementById("h2hSub");

const barHome = document.getElementById("barHome");
const barDraw = document.getElementById("barDraw");
const barAway = document.getElementById("barAway");

const TEAM_BADGES = {
  "Arsenal": "/static/badges/arsenal.png",
  "Aston Villa": "/static/badges/aston_villa.png",
  "Bournemouth": "/static/badges/bournemouth.png",
  "Brentford": "/static/badges/brentford.png",
  "Brighton": "/static/badges/brighton.png",
  "Brighton & Hove Albion": "/static/badges/brighton.png",
  "Burnley": "/static/badges/burnley.png",
  "Chelsea": "/static/badges/chelsea.png",
  "Crystal Palace": "/static/badges/crystal_palace.png",
  "Everton": "/static/badges/everton.png",
  "Fulham": "/static/badges/fulham.png",
  "Ipswich": "/static/badges/ipswich.png",
  "Ipswich Town": "/static/badges/ipswich.png",
  "Leeds": "/static/badges/leeds.png",
  "Leeds United": "/static/badges/leeds.png",
  "Leicester": "/static/badges/leicester.png",
  "Leicester City": "/static/badges/leicester.png",
  "Liverpool": "/static/badges/liverpool.png",
  "Luton": "/static/badges/luton.png",
  "Luton Town": "/static/badges/luton.png",
  "Manchester City": "/static/badges/manchester_city.png",
  "Manchester United": "/static/badges/manchester_united.png",
  "Newcastle": "/static/badges/newcastle.png",
  "Newcastle United": "/static/badges/newcastle.png",
  "Norwich": "/static/badges/norwich.png",
  "Norwich City": "/static/badges/norwich.png",
  "Nottingham Forest": "/static/badges/nottingham.png",
  "Sheffield United": "/static/badges/sheffield.png",
  "Southampton": "/static/badges/southampton.png",
  "Spurs": "/static/badges/spurs.png",
  "Tottenham": "/static/badges/spurs.png",
  "Tottenham Hotspur": "/static/badges/spurs.png",
  "Watford": "/static/badges/watford.png",
  "West Ham": "/static/badges/westham.png",
  "West Ham United": "/static/badges/westham.png",
  "Wolves": "/static/badges/wolves.png",
  "Wolverhampton Wanderers": "/static/badges/wolves.png",
  "Sunderland": "/static/badges/sunderland.png",
  "Hull City": "/static/badges/hull.png",
  "Coventry City": "/static/badges/coventry.png",
};

function animateValue(element, from, to, duration, formatter) {
  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = formatter(from + (to - from) * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function setLoading(loading) {
  predictBtn.classList.toggle("loading", loading);
  predictBtn.disabled = loading;
}

function renderForm(el, form) {
  if (!el) return;
  el.innerHTML = "";
  if (!form || !form.length) return;
  form.forEach(result => {
    const dot = document.createElement("span");
    dot.className = `form-dot form-${result}`;
    dot.title = result === "W" ? "Win" : result === "D" ? "Draw" : "Loss";
    el.appendChild(dot);
  });
}

function renderH2H(data) {
  if (!data || data.total === 0) { h2hSection.style.display = "none"; return; }
  h2hSection.style.display = "";
  h2hTitle.textContent = `Last ${data.total} head-to-head`;
  h2hHomeCount.textContent = data.home_wins;
  h2hAwayCount.textContent = data.away_wins;
  const t = data.total;
  requestAnimationFrame(() => {
    h2hFillHome.style.width = `${(data.home_wins / t * 100).toFixed(1)}%`;
    h2hFillDraw.style.width = `${(data.draws / t * 100).toFixed(1)}%`;
    h2hFillAway.style.width = `${(data.away_wins / t * 100).toFixed(1)}%`;
  });
  h2hSub.textContent = `${data.draws} draw${data.draws !== 1 ? "s" : ""}`;
}

function applyFixtureFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const home = params.get("home");
  const away = params.get("away");

  if (!home || !away) return;

  if ([...homeTeamSelect.options].some((o) => o.value === home)) {
    homeTeamSelect.value = home;
  }
  if ([...awayTeamSelect.options].some((o) => o.value === away)) {
    awayTeamSelect.value = away;
  }

  updateTeamNames();
}

async function loadTeams() {
  try {
    errorMessage.textContent = "";
    const response = await fetch("/teams");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.teams || !Array.isArray(data.teams)) throw new Error("teams array missing");

    homeTeamSelect.innerHTML = '<option value="">Select home team</option>';
    awayTeamSelect.innerHTML = '<option value="">Select away team</option>';

    data.teams.forEach((team) => {
      const homeOption = document.createElement("option");
      homeOption.value = team;
      homeOption.textContent = team;

      const awayOption = document.createElement("option");
      awayOption.value = team;
      awayOption.textContent = team;

      homeTeamSelect.appendChild(homeOption);
      awayTeamSelect.appendChild(awayOption);
    });

    applyFixtureFromQuery();
  } catch (error) {
    errorMessage.textContent = `Could not load teams: ${error.message}`;
  }
}

function getBadgePath(teamName) {
  return TEAM_BADGES[teamName] || "/static/badges/placeholder.png";
}

function setBadge(imgElement, teamName) {
  imgElement.onerror = () => {
    imgElement.onerror = null;
    imgElement.src = "/static/badges/placeholder.png";
  };
  imgElement.src = getBadgePath(teamName);
  imgElement.alt = `${teamName || "Team"} badge`;
}

function updateTeamNames() {
  const homeTeam = homeTeamSelect.value || "Home Team";
  const awayTeam = awayTeamSelect.value || "Away Team";
  homeTeamName.textContent = homeTeam;
  awayTeamName.textContent = awayTeam;
  setBadge(homeTeamBadge, homeTeamSelect.value);
  setBadge(awayTeamBadge, awayTeamSelect.value);
}

homeTeamSelect.addEventListener("change", updateTeamNames);
awayTeamSelect.addEventListener("change", updateTeamNames);

function getRecentPredictions() {
  try {
    return JSON.parse(localStorage.getItem("recentPredictions")) || [];
  } catch {
    return [];
  }
}

function saveRecentPredictions(items) {
  localStorage.setItem("recentPredictions", JSON.stringify(items));
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString();
}

function renderRecentPredictions() {
  const items = getRecentPredictions();

  if (!items.length) {
    recentPredictions.innerHTML = '<p class="empty-recent">No predictions yet.</p>';
    return;
  }

  recentPredictions.innerHTML = "";

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "recent-item";

    const scorelinesText = item.topScorelines
      .map((s) => `${s.home_goals}–${s.away_goals} (${(s.prob * 100).toFixed(1)}%)`)
      .join(", ");

    card.innerHTML = `
      <div class="recent-item-top">
        <p class="recent-fixture">
          <img class="recent-badge" src="${getBadgePath(item.homeTeam)}" alt="${item.homeTeam}">
          ${item.homeTeam} vs
          <img class="recent-badge" src="${getBadgePath(item.awayTeam)}" alt="${item.awayTeam}">
          ${item.awayTeam}
        </p>
        <span class="recent-time">${formatTime(item.createdAt)}</span>
      </div>
      <div class="recent-row">
        <span>Home: <strong>${item.homeProb}%</strong></span>
        <span>Draw: <strong>${item.drawProb}%</strong></span>
        <span>Away: <strong>${item.awayProb}%</strong></span>
      </div>
      <div class="recent-row">
        <span>Home xG: <strong>${item.homeXg}</strong></span>
        <span>Away xG: <strong>${item.awayXg}</strong></span>
      </div>
      <div class="recent-scorelines">
        <strong>Top scorelines:</strong> ${scorelinesText}
      </div>
    `;

    recentPredictions.appendChild(card);
  });
}

function addRecentPrediction(data, homeTeam, awayTeam) {
  const items = getRecentPredictions();

  items.unshift({
    homeTeam,
    awayTeam,
    homeProb: (data.p_home * 100).toFixed(1),
    drawProb: (data.p_draw * 100).toFixed(1),
    awayProb: (data.p_away * 100).toFixed(1),
    homeXg: Number(data.xg_home).toFixed(2),
    awayXg: Number(data.xg_away).toFixed(2),
    topScorelines: (data.top_scorelines || []).slice(0, 3),
    createdAt: Date.now()
  });

  saveRecentPredictions(items.slice(0, 5));
  renderRecentPredictions();
}

clearRecentBtn.addEventListener("click", () => {
  localStorage.removeItem("recentPredictions");
  renderRecentPredictions();
});

predictBtn.addEventListener("click", async () => {
  const homeTeam = homeTeamSelect.value;
  const awayTeam = awayTeamSelect.value;

  errorMessage.textContent = "";

  if (!homeTeam || !awayTeam) {
    errorMessage.textContent = "Please select both teams.";
    return;
  }

  if (homeTeam === awayTeam) {
    errorMessage.textContent = "Home and away teams must be different.";
    return;
  }

  updateTeamNames();
  matchStatus.textContent = "Loading…";
  setLoading(true);

  try {
    const params = new URLSearchParams({ home: homeTeam, away: awayTeam });

    const safeJson = async (url) => {
      try { const r = await fetch(url); return r.ok ? r.json() : null; } catch { return null; }
    };

    const [data, homeFormData, awayFormData, h2hData] = await Promise.all([
      fetch(`${API_BASE}/predict?${params}`).then(r => { if (!r.ok) throw new Error("Prediction failed"); return r.json(); }),
      safeJson(`${API_BASE}/form?team=${encodeURIComponent(homeTeam)}&n=5`),
      safeJson(`${API_BASE}/form?team=${encodeURIComponent(awayTeam)}&n=5`),
      safeJson(`${API_BASE}/h2h?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&n=10`),
    ]);

    // Probability boxes with count-up
    const ANIM = 550;
    animateValue(homeProb, 0, data.p_home * 100, ANIM, v => `${v.toFixed(1)}%`);
    animateValue(drawProb, 0, data.p_draw * 100, ANIM, v => `${v.toFixed(1)}%`);
    animateValue(awayProb, 0, data.p_away * 100, ANIM, v => `${v.toFixed(1)}%`);

    // Probability bars
    requestAnimationFrame(() => {
      barHome.style.width = `${(data.p_home * 100).toFixed(1)}%`;
      barDraw.style.width = `${(data.p_draw * 100).toFixed(1)}%`;
      barAway.style.width = `${(data.p_away * 100).toFixed(1)}%`;
    });

    // xG with count-up and bars
    animateValue(xgHome, 0, data.xg_home, ANIM, v => v.toFixed(2));
    animateValue(xgAway, 0, data.xg_away, ANIM, v => v.toFixed(2));

    const totalXg = data.xg_home + data.xg_away;
    const homeRatio = totalXg > 0 ? (data.xg_home / totalXg) * 100 : 50;
    requestAnimationFrame(() => {
      xgBarHome.style.width = `${homeRatio.toFixed(1)}%`;
    });

    // Elo ratings
    if (data.r_home) homeEloEl.textContent = `Elo ${Math.round(data.r_home)}`;
    if (data.r_away) awayEloEl.textContent = `Elo ${Math.round(data.r_away)}`;

    // Form dots
    renderForm(homeFormEl, homeFormData?.form);
    renderForm(awayFormEl, awayFormData?.form);

    // H2H bar
    renderH2H(h2hData);

    // Scoreline pills
    scorelinesPills.innerHTML = "";
    if (data.top_scorelines && data.top_scorelines.length > 0) {
      data.top_scorelines.forEach((item) => {
        const pill = document.createElement("div");
        pill.className = "scoreline-pill";
        pill.innerHTML = `
          <span class="scoreline-score">${item.home_goals}–${item.away_goals}</span>
          <span class="scoreline-prob">${(item.prob * 100).toFixed(1)}%</span>
        `;
        scorelinesPills.appendChild(pill);
      });
    } else {
      scorelinesPills.innerHTML = '<span class="scoreline-empty">No scorelines returned</span>';
    }

    addRecentPrediction(data, homeTeam, awayTeam);
    matchStatus.textContent = "Prediction ready";
  } catch (error) {
    matchStatus.textContent = "Prediction";
    errorMessage.textContent = "Could not generate prediction.";
  } finally {
    setLoading(false);
  }
});

async function loadModelPerf() {
  try {
    const res = await fetch(`${API_BASE}/backtest/summary`);
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("perfAccuracy").textContent = `${(data.accuracy_1x2 * 100).toFixed(1)}%`;
    document.getElementById("perfBrier").textContent = data.brier_score.toFixed(3);
    document.getElementById("perfLogLoss").textContent = data.log_loss.toFixed(3);
    document.getElementById("perfMatches").textContent = data.matches.toLocaleString();
  } catch {
    // non-critical — leave dashes
  }
}

setBadge(homeTeamBadge, "");
setBadge(awayTeamBadge, "");

loadTeams();
loadModelPerf();
renderRecentPredictions();
