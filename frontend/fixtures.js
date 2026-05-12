const fixturesList = document.getElementById("fixturesList");

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
  "Southampton": "/static/badges/placeholder.png",
  "Spurs": "/static/badges/spurs.png",
  "Tottenham": "/static/badges/spurs.png",
  "Tottenham Hotspur": "/static/badges/spurs.png",
  "Watford": "/static/badges/watford.png",
  "West Ham": "/static/badges/westham.png",
  "West Ham United": "/static/badges/westham.png",
  "Wolves": "/static/badges/wolves.png",
  "Wolverhampton Wanderers": "/static/badges/wolves.png"
};

function getBadgePath(teamName) {
  return TEAM_BADGES[teamName] || "/static/badges/placeholder.png";
}

async function loadFixtures() {
  try {
    const response = await fetch("/fixtures");

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.fixtures || !Array.isArray(data.fixtures)) {
      throw new Error("fixtures array missing");
    }

    renderFixtures(data.fixtures);
  } catch (error) {
    fixturesList.innerHTML = `<p>Could not load fixtures: ${error.message}</p>`;
  }
}

function renderFixtures(fixtures) {
  fixturesList.innerHTML = "";
  console.log("fixtures:", fixtures);

  if (!fixtures.length) {
    fixturesList.innerHTML = "<p>No fixtures available.</p>";
    return;
  }

  fixtures.forEach((fixture) => {
    const card = document.createElement("div");
    card.className = "fixture-card";

    card.innerHTML = `
      <div class="fixture-date">${fixture.date} ${fixture.time}</div>

      <div class="fixture-teams">
        <div class="fixture-team">
          <img class="fixture-badge" src="${getBadgePath(fixture.home_team)}" alt="${fixture.home_team} badge">
          <span>${fixture.home_team}</span>
        </div>

        <div class="fixture-vs">vs</div>

        <div class="fixture-team">
          <img class="fixture-badge" src="${getBadgePath(fixture.away_team)}" alt="${fixture.away_team} badge">
          <span>${fixture.away_team}</span>
        </div>
      </div>

      <button class="fixture-predict-btn">Predict</button>
    `;

    const button = card.querySelector(".fixture-predict-btn");
    button.addEventListener("click", () => {
      const params = new URLSearchParams({
        home: fixture.home_team,
        away: fixture.away_team
      });

      window.location.href = `/?${params.toString()}`;
    });

    fixturesList.appendChild(card);
  });
}

loadFixtures();