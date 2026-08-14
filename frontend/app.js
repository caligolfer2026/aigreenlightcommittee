const ROLES = ["creative", "finance", "marketing", "distribution"];
const ROLE_LABEL = { creative: "CR", finance: "FI", marketing: "MK", distribution: "DI" };

const state = {
  slateName: "default",
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

const slateNameInput = document.getElementById("slate-name-input");
const loadSlateBtn = document.getElementById("load-slate-btn");
const slateList = document.getElementById("slate-list");
const slateCount = document.getElementById("slate-count");
const conveneBtn = document.getElementById("convene-btn");
const filmTitleInput = document.getElementById("film-title-input");
const addFilmBtn = document.getElementById("add-film-btn");
const addFilmStatus = document.getElementById("add-film-status");

const delibFilmCount = document.getElementById("delib-film-count");
const delibFilmTitle = document.getElementById("delib-film-title");
const delibFilmMeta = document.getElementById("delib-film-meta");
const delibTally = document.getElementById("delib-tally");
const agentCardsEl = document.getElementById("agent-cards");
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
async function loadSlate() {
  state.slateName = slateNameInput.value.trim() || "default";
  const resp = await fetch(`/api/slate?slate=${encodeURIComponent(state.slateName)}`);
  state.films = resp.ok ? await resp.json() : [];
  renderSlate();
}

function renderSlate() {
  slateCount.textContent = `Your slate · ${state.films.length}/${MAX_FILMS} films`;
  slateList.innerHTML = "";
  if (state.films.length === 0) {
    slateList.innerHTML = `<div class="slate-empty">No films yet. Add one below, or load an existing slate by name.</div>`;
  } else {
    state.films.forEach((film, i) => {
      const row = document.createElement("div");
      row.className = "slate-item";
      row.innerHTML = `
        <span class="idx mono">${String(i + 1).padStart(2, "0")}</span>
        <span class="title">${escapeHtml(film.title)}</span>
        <button class="remove-btn" data-tmdb-id="${film.tmdb_id}" title="Remove from slate">&times;</button>
      `;
      slateList.appendChild(row);
    });
  }
  conveneBtn.disabled = state.films.length === 0;
  addFilmBtn.disabled = state.films.length >= MAX_FILMS;

  slateList.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tmdbId = Number(btn.dataset.tmdbId);
      state.films = state.films.filter((f) => f.tmdb_id !== tmdbId);
      renderSlate();
    });
  });
}

loadSlateBtn.addEventListener("click", loadSlate);

addFilmBtn.addEventListener("click", addFilm);
filmTitleInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addFilm();
});

async function addFilm() {
  const title = filmTitleInput.value.trim();
  if (!title) return;
  if (state.films.length >= MAX_FILMS) {
    addFilmStatus.textContent = `Slate is full (max ${MAX_FILMS} films).`;
    addFilmStatus.className = "add-film-status error";
    return;
  }
  if (state.films.some((f) => f.title.toLowerCase() === title.toLowerCase())) {
    addFilmStatus.textContent = "Already in your slate.";
    addFilmStatus.className = "add-film-status error";
    return;
  }

  addFilmBtn.disabled = true;
  addFilmStatus.textContent = `Looking up "${title}"...`;
  addFilmStatus.className = "add-film-status";

  try {
    const resp = await fetch(
      `/api/slate/add-film?title=${encodeURIComponent(title)}&slate=${encodeURIComponent(state.slateName)}`,
      { method: "POST" }
    );
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${resp.status})`);
    }
    const film = await resp.json();
    state.films.push(film);
    filmTitleInput.value = "";
    addFilmStatus.textContent = "";
    renderSlate();
  } catch (e) {
    addFilmStatus.textContent = e.message;
    addFilmStatus.className = "add-film-status error";
  } finally {
    addFilmBtn.disabled = state.films.length >= MAX_FILMS;
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
}

function renderAgentCard(cardEl, role, vote) {
  cardEl.innerHTML = `
    <div class="badge role-${role}">${ROLE_LABEL[role]}</div>
    <div class="body">
      <div class="role-name">
        ${role}
        <span class="vote-badge ${vote.vote}">${vote.vote.toUpperCase()}</span>
      </div>
      <div class="argument-text">${escapeHtml(vote.argument)}</div>
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

// ---------- Init ----------
loadSlate();
