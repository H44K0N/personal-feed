// Keep in step with SOURCES in app/sources.py (keys and short names).
const SHORT = { tu: "TU", kode24: "kode24", vg: "VG", nrk: "NRK", reddit: "r/norge", ars: "Ars" };
const PAGE = 40;

const $ = (id) => document.getElementById(id);
const state = {
  stories: [],
  sources: [],
  ai: false,
  source: remembered("source", ""),
  sort: remembered("sort", "best"),
  showHidden: false,
  shown: PAGE,
};

function remembered(key, fallback) {
  try { return localStorage.getItem(`feed.${key}`) ?? fallback; } catch { return fallback; }
}
function remember(key, value) {
  try { localStorage.setItem(`feed.${key}`, value); } catch { /* private window */ }
}

function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }

function ago(iso) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (minutes < 2) return "nå";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} t`;
  const days = Math.round(hours / 24);
  return days === 1 ? "i går" : `${days} d`;
}

function greet() {
  const hour = new Date().getHours();
  const word = hour < 5 ? "natt" : hour < 10 ? "morgen" : hour < 12 ? "formiddag" : hour < 18 ? "ettermiddag" : "kveld";
  $("greeting").textContent = `God ${word}.`;
  $("today").textContent = new Date().toLocaleDateString("nb-NO", { weekday: "long", day: "numeric", month: "long" });
}

function inSource(story) { return !state.source || story.source === state.source; }

function visible() {
  const list = state.stories.filter((s) => inSource(s) && (state.showHidden || !s.hidden));
  if (state.sort === "new") list.sort((a, b) => b.published_at.localeCompare(a.published_at));
  return list;
}

function renderSources() {
  const list = $("sources");
  list.replaceChildren();
  const all = [{ key: "", name: "alle" }, ...state.sources];
  for (const source of all) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = source.key ? SHORT[source.key] || source.name : source.name;
    button.setAttribute("aria-pressed", String(state.source === source.key));
    if (source.failed) {
      button.classList.add("failed");
      button.title = `${source.name} kunne ikke hentes sist`;
    }
    button.addEventListener("click", () => {
      state.source = source.key;
      state.shown = PAGE;
      remember("source", source.key);
      render();
    });
    li.append(button);
    list.append(li);
  }
}

function card(story) {
  const node = $("story").content.firstElementChild.cloneNode(true);
  node.dataset.id = story.id;
  node.querySelector(".source").textContent = SHORT[story.source] || story.source;
  const time = node.querySelector("time");
  time.dateTime = story.published_at;
  time.textContent = ago(story.published_at);
  time.title = new Date(story.published_at).toLocaleString("nb-NO");
  const link = node.querySelector("h3 a");
  link.href = story.url;
  link.textContent = story.title;
  const summary = node.querySelector(".summary");
  summary.textContent = story.summary;
  summary.hidden = !story.summary;
  const reason = node.querySelector(".reason");
  reason.textContent = story.reason || "";
  reason.hidden = !story.reason;
  if (story.image) {
    const img = node.querySelector(".thumb");
    img.src = story.image;
    img.hidden = false;
    img.addEventListener("error", () => { img.hidden = true; });
  }
  for (const button of node.querySelectorAll(".vote")) {
    button.addEventListener("click", () => vote(story, Number(button.dataset.vote), node));
  }
  paintVote(node, story.vote);
  return node;
}

function paintVote(node, value) {
  for (const button of node.querySelectorAll(".vote")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.vote) === value));
  }
  node.classList.toggle("liked", value === 1);
  node.classList.toggle("dismissed", value === -1);
}

async function vote(story, value, node) {
  const before = story.vote;
  const next = before === value ? 0 : value; // a second click takes it back
  story.vote = next;
  paintVote(node, next);
  try {
    const response = await fetch(`/api/stories/${story.id}/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vote: next }),
    });
    if (!response.ok) throw new Error();
  } catch {
    story.vote = before;
    paintVote(node, before);
    showError("Fikk ikke lagret stemmen. Prøv igjen.");
  }
}

function render() {
  renderSources();
  for (const button of document.querySelectorAll("[data-sort]")) {
    button.setAttribute("aria-pressed", String(button.dataset.sort === state.sort));
  }
  const list = visible();
  const stories = $("stories");
  stories.replaceChildren(...list.slice(0, state.shown).map(card));
  if (!list.length) {
    const empty = document.createElement("li");
    empty.className = "notice";
    empty.textContent = state.stories.length ? "Ingen saker her ennå." : "Ingen saker ennå. Trykk Oppdater for å hente dem.";
    stories.append(empty);
  }
  $("more").hidden = list.length <= state.shown;

  const hidden = state.stories.filter((s) => inSource(s) && s.hidden).length;
  const toggle = $("toggle-hidden");
  toggle.hidden = !hidden;
  toggle.textContent = state.showHidden ? `Skjul de ${hidden} igjen` : `Vis ${plural(hidden, "skjult sak", "skjulte saker")}`;

  const day = Date.now() - 24 * 3600 * 1000;
  const fresh = state.stories.filter((s) => new Date(s.published_at) > day && !s.hidden).length;
  const total = state.stories.filter((s) => !s.hidden).length;
  let lede = `${plural(fresh, "ny sak", "nye saker")} siste døgn, ${total} i alt.`;
  if (hidden) lede += ` ${hidden} er brettet bort som lite interessante.`;
  if (!state.ai) lede += " Sortert etter stemmene dine; Gemini er ikke satt opp.";
  $("lede").textContent = lede;
}

function showError(message) {
  const error = $("error");
  error.textContent = message;
  error.hidden = !message;
}

function showRefreshed(iso) {
  const when = iso ? ago(iso) : "";
  $("refreshed").textContent = !when ? "" : when === "nå" || when === "i går" ? `oppdatert ${when}` : `oppdatert for ${when} siden`;
}

async function load() {
  try {
    const response = await fetch("/api/feed");
    if (!response.ok) throw new Error();
    const data = await response.json();
    Object.assign(state, { stories: data.stories, sources: data.sources, ai: data.ai });
    showRefreshed(data.refreshed_at);
    showError("");
    render();
  } catch {
    showError("Fikk ikke hentet feeden. Prøv å laste siden på nytt.");
  }
}

async function refresh() {
  const button = $("refresh");
  button.disabled = true;
  button.textContent = "Henter …";
  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    if (!response.ok && response.status !== 429) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Fikk ikke oppdatert.");
    }
    await load();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Oppdater";
  }
}

async function loadInterests() {
  try {
    const response = await fetch("/api/interests");
    if (response.ok) $("interests-text").value = (await response.json()).text;
  } catch { /* the form still works */ }
}

async function saveInterests(event) {
  event.preventDefault();
  const status = $("interests-status");
  status.classList.remove("error");
  try {
    const response = await fetch("/api/interests", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("interests-text").value }),
    });
    if (!response.ok) throw new Error();
    status.textContent = state.ai ? "Lagret. Nye saker sorteres etter dette ved neste oppdatering." : "Lagret.";
  } catch {
    status.classList.add("error");
    status.textContent = "Fikk ikke lagret. Prøv igjen.";
  }
}

for (const button of document.querySelectorAll("[data-sort]")) {
  button.addEventListener("click", () => {
    state.sort = button.dataset.sort;
    state.shown = PAGE;
    remember("sort", state.sort);
    render();
  });
}
$("more").addEventListener("click", () => { state.shown += PAGE; render(); });
$("toggle-hidden").addEventListener("click", () => { state.showHidden = !state.showHidden; render(); });
$("refresh").addEventListener("click", refresh);
$("interests").addEventListener("submit", saveInterests);

greet();
load();
loadInterests();
