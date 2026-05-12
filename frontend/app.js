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
const scorelinesList = document.getElementById("scorelinesList");

const homeTeamName = document.getElementById("homeTeamName");
const awayTeamName = document.getElementById("awayTeamName");
const matchStatus = document.getElementById("matchStatus");
const recentPredictions = document.getElementById("recentPredictions");
const clearRecentBtn = document.getElementById("clearRecentBtn");

const homeTeamBadge = document.getElementById("homeTeamBadge");
const awayTeamBadge = document.getElementById("awayTeamBadge");

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
  "Wolverhampton Wanderers": "/static/badges/wolves.png"
};

function applyFixtureFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const home = params.get("home");
  const away = params.get("away");

  if (!home || !away) {
    return;
  }

  if ([...homeTeamSelect.options].some((option) => option.value === home)) {
    homeTeamSelect.value = home;
  }

  if ([...awayTeamSelect.options].some((option) => option.value === away)) {
    awayTeamSelect.value = away;
  }

  updateTeamNames();
}

async function loadTeams() {
  try {
    errorMessage.textContent = "";

    const response = await fetch("/teams");
    console.log("teams status:", response.status);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    console.log("teams data:", data);
    console.log("backend team names:", data.teams);

    if (!data.teams || !Array.isArray(data.teams)) {
      throw new Error("teams array missing");
    }

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

    console.log("teams loaded successfully");
  } catch (error) {
    console.error("loadTeams error:", error);
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
      .map((score) => `${score.home_goals}-${score.away_goals} (${(score.prob * 100).toFixed(1)}%)`)
      .join(", ");

    card.innerHTML = `
      <div class="recent-item-top">
        <p class="recent-fixture">
          <img class="recent-badge" src="${getBadgePath(item.homeTeam)}" alt="${item.homeTeam} badge">
          ${item.homeTeam} vs
          <img class="recent-badge" src="${getBadgePath(item.awayTeam)}" alt="${item.awayTeam} badge">
          ${item.awayTeam}
        </p>
        <span class="recent-time">${formatTime(item.createdAt)}</span>
      </div>

      <div class="recent-row">
        <span>Home: ${item.homeProb}%</span>
        <span>Draw: ${item.drawProb}%</span>
        <span>Away: ${item.awayProb}%</span>
      </div>

      <div class="recent-row">
        <span>Home xG: ${item.homeXg}</span>
        <span>Away xG: ${item.awayXg}</span>
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

  const trimmed = items.slice(0, 5);
  saveRecentPredictions(trimmed);
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
  matchStatus.textContent = "Loading...";

  try {
    const params = new URLSearchParams({ home: homeTeam, away: awayTeam });
    const response = await fetch(`${API_BASE}/predict?${params}`);

    if (!response.ok) {
      throw new Error("Prediction failed");
    }

    const data = await response.json();

    homeProb.textContent = `${(data.p_home * 100).toFixed(1)}%`;
    drawProb.textContent = `${(data.p_draw * 100).toFixed(1)}%`;
    awayProb.textContent = `${(data.p_away * 100).toFixed(1)}%`;

    barHome.style.width = `${(data.p_home * 100).toFixed(1)}%`;
    barDraw.style.width = `${(data.p_draw * 100).toFixed(1)}%`;
    barAway.style.width = `${(data.p_away * 100).toFixed(1)}%`;

    xgHome.textContent = Number(data.xg_home).toFixed(2);
    xgAway.textContent = Number(data.xg_away).toFixed(2);

    scorelinesList.innerHTML = "";

    if (data.top_scorelines && data.top_scorelines.length > 0) {
      data.top_scorelines.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = `${item.home_goals}-${item.away_goals} (${(item.prob * 100).toFixed(1)}%)`;
        scorelinesList.appendChild(li);
      });
    } else {
      scorelinesList.innerHTML = "<li>No scorelines returned</li>";
    }

    addRecentPrediction(data, homeTeam, awayTeam);

    matchStatus.textContent = "Prediction ready";
  } catch (error) {
    matchStatus.textContent = "Prediction";
    errorMessage.textContent = "Could not generate prediction.";
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
    // non-critical — leave dashes in place
  }
}

setBadge(homeTeamBadge, "");
setBadge(awayTeamBadge, "");

loadTeams();
loadModelPerf();
renderRecentPredictions();