const ROLES = ["creative", "finance", "marketing", "distribution"];
const ROLE_LABEL = { creative: "CR", finance: "FI", marketing: "MK", distribution: "DI" };

const state = {
  // Unique per page load so pitches never land in a shared/leftover slate
  // from a previous session -- every visit starts from an empty slate.
  slateName: `pitch-${Date.now()}`,
  films: [],
  sessionId: null,
  filmIndex: 0,
  votesByFilm: {}, // tmdb_id -> {role: voteObj}
};

// ---------- DOM refs ----------
const screens = {
  landing: document.getElementById("screen-landing"),
  deliberation: document.getElementById("screen-deliberation"),
  verdict: document.getElementById("screen-verdict"),
};

const MAX_FILMS = 5;

const slateList = document.getElementById("slate-list");
const slateCount = document.getElementById("slate-count");
const conveneBtn = document.getElementById("convene-btn");
const pitchInput = document.getElementById("pitch-input");
const addPitchBtn = document.getElementById("add-pitch-btn");
const addFilmStatus = document.getElementById("add-film-status");

const delibFilmCount = document.getElementById("delib-film-count");
const delibFilmTitle = document.getElementById("delib-film-title");
const delibFilmMeta = document.getElementById("delib-film-meta");
const delibTally = document.getElementById("delib-tally");
const agentCardsEl = document.getElementById("agent-cards");
const aggregationBanner = document.getElementById("aggregation-banner");
const nextFilmBtn = document.getElementById("next-film-btn");

const verdictCardsEl = document.getElementById("verdict-cards");
const restartBtn = document.getElementById("restart-btn");

// ---------- Screen switching ----------
function showScreen(name) {
  for (const [key, el] of Object.entries(screens)) {
    el.classList.toggle("hidden", key !== name);
  }
}

// ---------- Landing ----------
function genreHistorySummary(film) {
  const payload = film.payload || {};
  const genre = (payload.genres && payload.genres[0]) || null;
  const historical = payload.genreHistoricalPerformance || [];
  const withFinancials = historical.filter((h) => h.budget && h.boxOfficeWorldwide);

  if (!genre) return "Genre unknown -- no historical comp data.";
  if (withFinancials.length === 0) {
    return `${escapeHtml(genre)} -- no historical box office data available for comps.`;
  }

  const avgMultiple =
    withFinancials.reduce((sum, h) => sum + h.boxOfficeWorldwide / h.budget, 0) /
    withFinancials.length;
  const avgBoxOffice =
    withFinancials.reduce((sum, h) => sum + h.boxOfficeWorldwide, 0) / withFinancials.length;

  return (
    `${escapeHtml(genre)} comps historically return <span class="multiple">${avgMultiple.toFixed(1)}x</span> budget ` +
    `(avg $${(avgBoxOffice / 1e6).toFixed(0)}M worldwide, ${withFinancials.length} films: ${withFinancials
      .map((h) => escapeHtml(h.title))
      .join(", ")})`
  );
}

function renderSlate() {
  slateCount.textContent = `Your slate · ${state.films.length}/${MAX_FILMS} films`;
  slateList.innerHTML = "";
  if (state.films.length === 0) {
    slateList.innerHTML = `<div class="slate-empty">No films yet. Pitch one below to get started.</div>`;
  } else {
    state.films.forEach((film, i) => {
      const row = document.createElement("div");
      row.className = "slate-item";
      row.innerHTML = `
        <div class="slate-item-row">
          <span class="idx mono">${String(i + 1).padStart(2, "0")}</span>
          <span class="title">${escapeHtml(film.title)}</span>
          <button class="remove-btn" data-tmdb-id="${film.tmdb_id}" title="Remove from slate">&times;</button>
        </div>
        <div class="genre-history">${genreHistorySummary(film)}</div>
      `;
      slateList.appendChild(row);
    });
  }
  conveneBtn.disabled = state.films.length === 0;
  addPitchBtn.disabled = state.films.length >= MAX_FILMS;

  slateList.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tmdbId = Number(btn.dataset.tmdbId);
      state.films = state.films.filter((f) => f.tmdb_id !== tmdbId);
      renderSlate();
    });
  });
}

addPitchBtn.addEventListener("click", addPitch);
pitchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addPitch();
});

async function addPitch() {
  const pitch = pitchInput.value.trim();
  if (!pitch) return;
  if (state.films.length >= MAX_FILMS) {
    addFilmStatus.textContent = `Slate is full (max ${MAX_FILMS} films).`;
    addFilmStatus.className = "add-film-status error";
    return;
  }

  addPitchBtn.disabled = true;
  addFilmStatus.textContent = `Evaluating pitch...`;
  addFilmStatus.className = "add-film-status";

  try {
    const resp = await fetch(
      `/api/slate/add-pitch?pitch=${encodeURIComponent(pitch)}&slate=${encodeURIComponent(state.slateName)}`,
      { method: "POST" }
    );
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${resp.status})`);
    }
    const film = await resp.json();
    state.films.push(film);
    pitchInput.value = "";
    addFilmStatus.textContent = "";
    renderSlate();
  } catch (e) {
    addFilmStatus.textContent = e.message;
    addFilmStatus.className = "add-film-status error";
  } finally {
    addPitchBtn.disabled = state.films.length >= MAX_FILMS;
  }
}

conveneBtn.addEventListener("click", async () => {
  const resp = await fetch(`/api/session?slate=${encodeURIComponent(state.slateName)}`, { method: "POST" });
  const { session_id } = await resp.json();
  state.sessionId = session_id;
  state.filmIndex = 0;
  state.votesByFilm = {};
  showScreen("deliberation");
  runFilm(state.filmIndex);
});

// ---------- Deliberation ----------
async function runFilm(index) {
  const film = state.films[index];
  delibFilmCount.textContent = `Film ${index + 1} of ${state.films.length}`;
  delibFilmTitle.textContent = film.title;
  delibFilmMeta.textContent = film.release_date || "release date unknown";
  nextFilmBtn.disabled = true;
  nextFilmBtn.textContent = index === state.films.length - 1 ? "See the Verdict" : "Next Film";

  state.votesByFilm[film.tmdb_id] = {};
  updateTally(film);
  aggregationBanner.classList.add("hidden");

  agentCardsEl.innerHTML = "";
  const cardEls = {};
  for (const role of ROLES) {
    const card = document.createElement("div");
    card.className = "agent-card";
    card.innerHTML = `
      <div class="badge role-${role}">${ROLE_LABEL[role]}</div>
      <div class="body">
        <div class="role-name">${role}</div>
        <div class="reviewing">Reviewing pre-release data<span class="dots"></span></div>
      </div>
    `;
    agentCardsEl.appendChild(card);
    cardEls[role] = card;
  }

  await Promise.all(
    ROLES.map(async (role) => {
      const resp = await fetch(
        `/api/session/${state.sessionId}/agent-run?film_id=${film.id}&role=${role}&slate=${encodeURIComponent(state.slateName)}`,
        { method: "POST" }
      );
      const vote = await resp.json();
      state.votesByFilm[film.tmdb_id][role] = vote;
      renderAgentCard(cardEls[role], role, vote);
      updateTally(film);
    })
  );

  nextFilmBtn.disabled = false;
  await renderAggregation(film);
}

function renderAgentCard(cardEl, role, vote) {
  const confidence = vote.confidence != null ? `${vote.confidence}% confident` : "";
  cardEl.innerHTML = `
    <div class="badge role-${role}">${ROLE_LABEL[role]}</div>
    <div class="body">
      <div class="role-name">
        ${role}
        <span class="vote-badge ${vote.vote}">${vote.vote.toUpperCase()}${confidence ? ` &middot; ${confidence}` : ""}</span>
      </div>
      <div class="argument-text">${escapeHtml(vote.argument)}</div>
    </div>
  `;
}

async function renderAggregation(film) {
  const resp = await fetch(
    `/api/session/${state.sessionId}/aggregate?tmdb_id=${film.tmdb_id}`
  );
  if (!resp.ok) return;
  const decision = await resp.json();

  aggregationBanner.className = `aggregation-banner outcome-${decision.outcome}`;
  aggregationBanner.innerHTML = `
    <div class="aggregation-outcome">Committee decision: ${decision.outcome.toUpperCase()}</div>
    <div class="aggregation-detail">
      Confidence-weighted score ${decision.confidenceWeightedScore}/100 &middot;
      ${decision.greenlightCount} greenlight / ${decision.passCount} pass &middot;
      avg confidence ${decision.averageConfidence}%
    </div>
  `;
}

function updateTally(film) {
  const votes = Object.values(state.votesByFilm[film.tmdb_id] || {});
  const green = votes.filter((v) => v.vote === "greenlight").length;
  const pass = votes.filter((v) => v.vote === "pass").length;
  delibTally.textContent = `${green} greenlight · ${pass} pass · ${4 - votes.length} pending`;
}

nextFilmBtn.addEventListener("click", () => {
  if (state.filmIndex < state.films.length - 1) {
    state.filmIndex += 1;
    runFilm(state.filmIndex);
  } else {
    showScreen("verdict");
    runVerdict();
  }
});

// ---------- Verdict ----------
async function runVerdict() {
  verdictCardsEl.innerHTML = "";
  for (const film of state.films) {
    const card = document.createElement("div");
    card.className = "verdict-card";
    card.innerHTML = `<h3>${escapeHtml(film.title)}</h3><div class="reviewing">Revealing actual results<span class="dots"></span></div>`;
    verdictCardsEl.appendChild(card);

    try {
      const resp = await fetch(
        `/api/session/${state.sessionId}/score-run?tmdb_id=${film.tmdb_id}&slate=${encodeURIComponent(state.slateName)}`,
        { method: "POST" }
      );
      if (!resp.ok) throw new Error(await resp.text());
      const score = await resp.json();

      const votes = Object.values(state.votesByFilm[film.tmdb_id] || {});
      const chips = votes
        .map((v) => `<span class="chip">${v.role}: ${v.vote}</span>`)
        .join("");

      card.innerHTML = `
        <h3>${escapeHtml(film.title)}</h3>
        <div class="verdict-grade">Grade: ${escapeHtml(String(score.grade))}</div>
        <div class="verdict-rationale">${escapeHtml(score.rationale)}</div>
        <div class="verdict-tally">${chips}</div>
      `;
    } catch (e) {
      card.innerHTML = `<h3>${escapeHtml(film.title)}</h3><div class="reviewing">No actual results loaded for this film yet.</div>`;
    }
  }
}

restartBtn.addEventListener("click", () => {
  state.sessionId = null;
  state.filmIndex = 0;
  state.votesByFilm = {};
  showScreen("landing");
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Intro ----------
const INTRO_TOTAL_MS = 9600; // last line's delay + its own hold/fade duration
const introOverlay = document.getElementById("intro-overlay");
const introSkipBtn = document.getElementById("intro-skip-btn");

function dismissIntro() {
  if (!introOverlay) return;
  introOverlay.classList.add("intro-hidden");
  setTimeout(() => introOverlay.remove(), 1200);
}

if (introOverlay) {
  if (sessionStorage.getItem("introShown")) {
    introOverlay.remove();
  } else {
    sessionStorage.setItem("introShown", "1");
    const introTimer = setTimeout(dismissIntro, INTRO_TOTAL_MS);
    introSkipBtn.addEventListener("click", () => {
      clearTimeout(introTimer);
      dismissIntro();
    });
  }
}

// ---------- Init ----------
renderSlate();
