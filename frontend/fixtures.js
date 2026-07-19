const fixturesList = document.getElementById("fixturesList");
const matchdayLabel = document.getElementById("matchdayLabel");
const prevBtn = document.getElementById("prevMatchday");
const nextBtn = document.getElementById("nextMatchday");

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
  "Ipswich Town": "/static/badges/ipswich.png",
  "Ipswich": "/static/badges/ipswich.png",
  "Leeds United": "/static/badges/leeds.png",
  "Leeds": "/static/badges/leeds.png",
  "Leicester City": "/static/badges/leicester.png",
  "Leicester": "/static/badges/leicester.png",
  "Liverpool": "/static/badges/liverpool.png",
  "Luton Town": "/static/badges/luton.png",
  "Manchester City": "/static/badges/manchester_city.png",
  "Manchester United": "/static/badges/manchester_united.png",
  "Newcastle United": "/static/badges/newcastle.png",
  "Newcastle": "/static/badges/newcastle.png",
  "Nottingham Forest": "/static/badges/nottingham.png",
  "Sheffield United": "/static/badges/sheffield.png",
  "Southampton": "/static/badges/southampton.png",
  "Tottenham": "/static/badges/spurs.png",
  "Tottenham Hotspur": "/static/badges/spurs.png",
  "West Ham United": "/static/badges/westham.png",
  "West Ham": "/static/badges/westham.png",
  "Wolves": "/static/badges/wolves.png",
};

function getBadge(team) {
  return TEAM_BADGES[team] || "/static/badges/placeholder.png";
}

// All fixtures grouped by matchday
let matchdays = {};
let sortedMatchdays = [];
let currentIndex = 0;

async function loadFixtures() {
  try {
    const res = await fetch("/fixtures");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.fixtures || !data.fixtures.length) {
      const msg = data.message || "No fixtures available yet. Check back once the 2025/26 schedule is announced.";
      fixturesList.innerHTML = `<div class="fixtures-empty">${msg}</div>`;
      return;
    }

    // Group by matchday
    matchdays = {};
    data.fixtures.forEach(f => {
      if (!matchdays[f.matchday]) matchdays[f.matchday] = [];
      matchdays[f.matchday].push(f);
    });
    sortedMatchdays = Object.keys(matchdays).map(Number).sort((a, b) => a - b);

    // Start on the first matchday (or nearest upcoming)
    currentIndex = 0;
    updateNav();
    await renderMatchday(sortedMatchdays[currentIndex]);
  } catch (err) {
    fixturesList.innerHTML = `<div class="fixtures-error">Could not load fixtures: ${err.message}</div>`;
  }
}

function updateNav() {
  const md = sortedMatchdays[currentIndex];
  matchdayLabel.textContent = `Matchweek ${md}`;
  prevBtn.disabled = currentIndex === 0;
  nextBtn.disabled = currentIndex === sortedMatchdays.length - 1;
}

prevBtn.addEventListener("click", async () => {
  if (currentIndex > 0) {
    currentIndex--;
    updateNav();
    await renderMatchday(sortedMatchdays[currentIndex]);
  }
});

nextBtn.addEventListener("click", async () => {
  if (currentIndex < sortedMatchdays.length - 1) {
    currentIndex++;
    updateNav();
    await renderMatchday(sortedMatchdays[currentIndex]);
  }
});

async function renderMatchday(matchday) {
  const fixtures = matchdays[matchday] || [];
  fixturesList.innerHTML = "";

  // Build all cards with loading states first
  const cards = fixtures.map(f => {
    const card = document.createElement("div");
    card.className = "fixture-card";
    card.innerHTML = `
      <div class="fixture-meta">
        <span class="fixture-date-time">${f.date} · ${f.time}</span>
      </div>
      <div class="fixture-teams">
        <div class="fixture-team">
          <img class="fixture-badge" src="${getBadge(f.home_team)}" alt="${f.home_team}"
               onerror="this.src='/static/badges/placeholder.png'">
          <span>${f.home_team}</span>
        </div>
        <span class="fixture-vs">vs</span>
        <div class="fixture-team fixture-team-away">
          <img class="fixture-badge" src="${getBadge(f.away_team)}" alt="${f.away_team}"
               onerror="this.src='/static/badges/placeholder.png'">
          <span>${f.away_team}</span>
        </div>
      </div>
      <div class="fixture-prediction">
        <span class="fixture-pred-loading">Loading prediction…</span>
      </div>
    `;
    fixturesList.appendChild(card);
    return { card, fixture: f };
  });

  // Fetch predictions in parallel
  await Promise.all(cards.map(({ card, fixture }) =>
    fetchAndRenderPrediction(card, fixture.home_team, fixture.away_team)
  ));
}

async function fetchAndRenderPrediction(card, home, away) {
  const predEl = card.querySelector(".fixture-prediction");
  try {
    const params = new URLSearchParams({ home, away });
    const res = await fetch(`/predict?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();

    const pH = (d.p_home * 100).toFixed(1);
    const pD = (d.p_draw * 100).toFixed(1);
    const pA = (d.p_away * 100).toFixed(1);
    const topScore = d.top_scorelines?.[0];
    const scoreText = topScore
      ? `${topScore.home_goals}–${topScore.away_goals} (${(topScore.prob * 100).toFixed(1)}%)`
      : "—";

    predEl.innerHTML = `
      <div class="fixture-prob-row">
        <span class="fixture-prob-home">${pH}%</span>
        <div class="fixture-prob-bar">
          <div class="fixture-bar-h" id="bh-${home}-${away}"></div>
          <div class="fixture-bar-d" id="bd-${home}-${away}"></div>
          <div class="fixture-bar-a" id="ba-${home}-${away}"></div>
        </div>
        <span class="fixture-prob-away">${pA}%</span>
      </div>
      <div class="fixture-pred-footer">
        <span>Draw <strong>${pD}%</strong></span>
        <span>·</span>
        <span>xG <strong>${Number(d.xg_home).toFixed(2)}</strong> – <strong>${Number(d.xg_away).toFixed(2)}</strong></span>
        <span>·</span>
        <span>Top score: <strong>${scoreText}</strong></span>
      </div>
    `;

    // Animate bars after DOM insertion
    requestAnimationFrame(() => {
      const bh = document.getElementById(`bh-${home}-${away}`);
      const bd = document.getElementById(`bd-${home}-${away}`);
      const ba = document.getElementById(`ba-${home}-${away}`);
      if (bh) bh.style.width = `${pH}%`;
      if (bd) bd.style.width = `${pD}%`;
      if (ba) ba.style.width = `${pA}%`;
    });
  } catch {
    predEl.innerHTML = `<span class="fixture-pred-error">Prediction unavailable</span>`;
  }
}

loadFixtures();
