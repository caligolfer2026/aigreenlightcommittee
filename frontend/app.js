const ROLES = ["creative", "finance", "marketing", "distribution"];

let currentSessionId = null;
let films = [];
let pollHandle = null;

const filmsEl = document.getElementById("films");
const sessionLabelEl = document.getElementById("session-label");
const slateInput = document.getElementById("slate-input");
const startBtn = document.getElementById("start-btn");

startBtn.addEventListener("click", startSession);

async function startSession() {
  const slate = slateInput.value.trim() || "default";

  const slateResp = await fetch(`/api/slate?slate=${encodeURIComponent(slate)}`);
  films = await slateResp.json();

  const sessionResp = await fetch(`/api/session?slate=${encodeURIComponent(slate)}`, {
    method: "POST",
  });
  const { session_id } = await sessionResp.json();
  currentSessionId = session_id;
  sessionLabelEl.textContent = `Session ${session_id} · slate: ${slate} · ${films.length} film(s)`;

  render({}, {});
  if (pollHandle) clearInterval(pollHandle);
  pollHandle = setInterval(poll, 3000);
  poll();
}

async function poll() {
  if (!currentSessionId) return;

  const [votesResp, scoresResp] = await Promise.all([
    fetch(`/api/session/${currentSessionId}/votes`),
    fetch(`/api/session/${currentSessionId}/scores`),
  ]);
  const votes = await votesResp.json();
  const scores = await scoresResp.json();

  const votesByTmdbId = {};
  for (const v of votes) {
    (votesByTmdbId[v.tmdb_id] ??= []).push(v);
  }
  const scoresByTmdbId = {};
  for (const s of scores) {
    scoresByTmdbId[s.tmdb_id] = s;
  }

  render(votesByTmdbId, scoresByTmdbId);
}

function render(votesByTmdbId, scoresByTmdbId) {
  filmsEl.innerHTML = "";
  for (const film of films) {
    const card = document.createElement("div");
    card.className = "film-card";

    const votes = votesByTmdbId[film.tmdb_id] || [];
    const votesByRole = {};
    for (const v of votes) votesByRole[v.role] = v;

    const score = scoresByTmdbId[film.tmdb_id];

    card.innerHTML = `
      <h2>${escapeHtml(film.title)}</h2>
      <div class="meta">${film.release_date || "release date unknown"}</div>
      <div class="votes">
        ${ROLES.map((role) => renderVote(role, votesByRole[role])).join("")}
      </div>
      ${score ? renderScore(score) : ""}
    `;
    filmsEl.appendChild(card);
  }
}

function renderVote(role, vote) {
  if (!vote) {
    return `<div class="vote"><div class="role">${role}</div><div class="pending">waiting…</div></div>`;
  }
  return `
    <div class="vote">
      <div class="role">${role}</div>
      <div class="call ${vote.vote}">${vote.vote.toUpperCase()}</div>
      <div class="argument">${escapeHtml(vote.argument)}</div>
    </div>
  `;
}

function renderScore(score) {
  return `
    <div class="score">
      <span class="grade">Grade: ${escapeHtml(String(score.grade))}</span>
      <div class="argument">${escapeHtml(score.rationale)}</div>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
