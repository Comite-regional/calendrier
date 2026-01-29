/* Calendrier Comité régional – v0.5
   - Concours : concours.csv (séparateur ;)
   - Dates clés : dates_cles.csv (séparateur ;)
*/

const els = {
  tabs: Array.from(document.querySelectorAll(".tab")),
  views: {
    calendar: document.getElementById("view-calendar"),
    timeline: document.getElementById("view-timeline"),
    about: document.getElementById("view-about"),
  },
  calendarEl: document.getElementById("calendar"),
  ticker: document.getElementById("ticker"),
  tickerItems: document.getElementById("ticker-items"),
  details: document.getElementById("details"),
  upcoming: document.getElementById("upcoming"),
  nextImportant: document.getElementById("next-important"),
  timeline: document.getElementById("timeline"),
  pillToday: document.getElementById("pill-today"),

  fSearch: document.getElementById("f-search"),
  fDiscipline: document.getElementById("f-discipline"),
  fEtat: document.getElementById("f-etat"),

  btnToday: document.getElementById("btn-today"),
  btnReset: document.getElementById("btn-reset"),
};

const state = {
  rawEvents: [],
  filteredEvents: [],
  calendar: null,
  keyDates: [],
};

let __tooltipEl = null;
function showTooltip(ev, text){
  if (!__tooltipEl){
    __tooltipEl = document.createElement("div");
    __tooltipEl.className = "fc-tooltip";
    document.body.appendChild(__tooltipEl);
  }
  __tooltipEl.innerHTML = text;
  moveTooltip(ev);
  __tooltipEl.style.display = "block";
}
function moveTooltip(ev){
  if (!__tooltipEl) return;
  const pad = 14;
  __tooltipEl.style.left = (ev.clientX + pad) + "px";
  __tooltipEl.style.top  = (ev.clientY + pad) + "px";
}
function hideTooltip(){
  if (__tooltipEl) __tooltipEl.style.display = "none";
}


function eventIconHtml(disciplineRaw){
  const d = (disciplineRaw || "").toLowerCase();

  const svgTAE = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='8' stroke='currentColor' stroke-width='2'/><circle cx='12' cy='12' r='3' stroke='currentColor' stroke-width='2'/><path d='M12 2v3M12 19v3M2 12h3M19 12h3' stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>`;
  const svg18  = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='7.5' r='4' stroke='currentColor' stroke-width='2'/><circle cx='7.5' cy='16.5' r='4' stroke='currentColor' stroke-width='2'/><circle cx='16.5' cy='16.5' r='4' stroke='currentColor' stroke-width='2'/></svg>`;
  const svgCamp = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='9' stroke='currentColor' stroke-width='2'/><circle cx='12' cy='12' r='5.5' stroke='currentColor' stroke-width='2' opacity='0.8'/><circle cx='12' cy='12' r='2' fill='currentColor'/></svg>`;
  const svgBeur = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'><circle cx='12' cy='12' r='9' stroke='currentColor' stroke-width='2'/><circle cx='12' cy='12' r='6' stroke='currentColor' stroke-width='2'/><circle cx='12' cy='12' r='3' fill='currentColor'/></svg>`;

  if (d.includes("campagne")) return `<span class="ev-ico ev-ico-svg" aria-label="Campagne">${svgCamp}</span>`;
  if (d.includes("beursault")) return `<span class="ev-ico ev-ico-svg" aria-label="Beursault">${svgBeur}</span>`;
  if (d.includes("tae") || d.includes("extérieur") || d.includes("exterieur")) return `<span class="ev-ico ev-ico-svg" aria-label="TAE">${svgTAE}</span>`;
  if (d.includes("18m") || d.includes("salle") || d.includes("tir en salle") || d.includes("18 m")) return `<span class="ev-ico ev-ico-svg" aria-label="Tir 18m">${svg18}</span>`;

  if (d.includes("3d")) return '<span class="ev-ico"><i class="ti ti-paw"></i></span>';
  if (d.includes("nature")) return '<span class="ev-ico"><i class="ti ti-leaf"></i></span>';
  if (d.includes("loisir")) return '<span class="ev-ico"><i class="ti ti-mood-smile"></i></span>';

  return '';
}

function disciplineClass(disciplineRaw){
  const d = (disciplineRaw || "").toLowerCase();
  if (d.includes("campagne")) return "disc-campagne";
  if (d.includes("18m") || d.includes("salle") || d.includes("tir en salle") || d.includes("18 m")) return "disc-18m";
  if (d.includes("nature")) return "disc-nature";
  if (d.includes("3d")) return "disc-3d";
  if (d.includes("beursault")) return "disc-beursault";
  if (d.includes("tae") || d.includes("extérieur") || d.includes("exterieur")) return "disc-tae";
  if (d.includes("loisir")) return "disc-loisir";
  return "";
}

function fmtDateFR(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { weekday: "short", year: "numeric", month: "short", day: "numeric" });
}
function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean))).sort((a,b) => a.localeCompare(b, "fr"));
}
function safeText(s) {
  return String(s ?? "").replace(/[<>]/g, "");
}
function parseFrDate(value) {
  if (value == null || value === "") return null;
  const s = String(value).trim();
  const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) {
    const dd = String(m[1]).padStart(2,"0");
    const mm = String(m[2]).padStart(2,"0");
    const yy = m[3];
    return `${yy}-${mm}-${dd}`;
  }
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return s;
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0,10);
  return null;
}
function inclusiveEndToExclusive(endIso) {
  if (!endIso) return null;
  const d = new Date(endIso + "T00:00:00");
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0,10);
}

/* CSV parsing */
function parseCsvLine(line, sep=";") {
  const out = [];
  let cur = "";
  let inQ = false;
  for (let i=0; i<line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQ && line[i+1] === '"') { cur += '"'; i++; }
      else inQ = !inQ;
    } else if (ch === sep && !inQ) {
      out.push(cur); cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map(s => s.trim());
}
async function loadCsvUrl(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Impossible de charger " + url);
  return await res.text();
}

/* Concours */
function rowsToConcoursEvents(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim().length);
  if (!lines.length) return [];
  const header = parseCsvLine(lines[0]);
  const idx = Object.fromEntries(header.map((h,i)=>[h,i]));
  const get = (row, name) => {
    const i = idx[name];
    return (i == null) ? "" : (row[i] ?? "");
  };

  const events = [];
  for (let li=1; li<lines.length; li++) {
    const row = parseCsvLine(lines[li]);
    const start = parseFrDate(get(row, "Date Début"));
    if (!start) continue;
    const endInc = parseFrDate(get(row, "Date Fin")) || start;
    const endEx = inclusiveEndToExclusive(endInc);

    events.push({
      title: safeText(get(row, "Nom de l'épreuve") || "Concours"),
      start,
      end: endEx,
      allDay: true,
      extendedProps: {
        discipline: safeText(get(row, "Discipline") || ""),
        lieu: safeText(get(row, "Lieu") || ""),
        organisateur: safeText(get(row, "Organisateur") || ""),
        etat: safeText(get(row, "Etat") || ""),
        mandat_url: safeText(get(row, "Mandat") || ""),
        agrement: safeText(get(row, "Agrément") || ""),
        formule: safeText(get(row, "Formule") || ""),
        caracteristiques: safeText(get(row, "Caractéristiques") || ""),
        date_fin_inclusive: endInc,
      }
    });
  }
  return events;
}

function buildFilters(events) {
  const disciplines = uniq(events.map(e => e.extendedProps?.discipline));
  const etats = uniq(events.map(e => e.extendedProps?.etat));
  els.fDiscipline.innerHTML = `<option value="">Toutes</option>` + disciplines.map(d => `<option>${d}</option>`).join("");
  els.fEtat.innerHTML = `<option value="">Tous</option>` + etats.map(s => `<option>${s}</option>`).join("");
}

function applyFilters() {
  const q = els.fSearch.value.trim().toLowerCase();
  const disc = els.fDiscipline.value;
  const etat = els.fEtat.value;

  state.filteredEvents = state.rawEvents.filter(e => {
    const p = e.extendedProps || {};
    if (disc && p.discipline !== disc) return false;
    if (etat && p.etat !== etat) return false;
    if (q) {
      const hay = `${e.title} ${p.organisateur||""} ${p.lieu||""} ${p.discipline||""} ${p.caracteristiques||""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (state.calendar) {
    state.calendar.removeAllEvents();
    state.calendar.addEventSource(state.filteredEvents);
  }
  renderUpcoming();
}

function renderDetails(event) {
  const p = event.extendedProps || {};
  const start = event.startStr;
  const endInc = p.date_fin_inclusive || event.startStr;

  const parts = [
    `<div class="v"><strong>${safeText(event.title)}</strong></div>`,
    `<div class="k">Dates</div><div class="v">${fmtDateFR(start)}${endInc && endInc!==start ? " → " + fmtDateFR(endInc) : ""}</div>`,
    p.discipline ? `<div class="k">Discipline</div><div class="v">${safeText(p.discipline)}</div>` : "",
    p.lieu ? `<div class="k">Lieu</div><div class="v">${safeText(p.lieu)}</div>` : "",
    p.organisateur ? `<div class="k">Organisateur</div><div class="v">${safeText(p.organisateur)}</div>` : "",
    p.etat ? `<div class="k">État</div><div class="v"><span class="badge">${safeText(p.etat)}</span></div>` : "",
    p.mandat_url ? `<div class="k">Mandat</div><div class="v"><a class="btn" href="${p.mandat_url}" target="_blank" rel="noopener noreferrer">📄 Ouvrir le mandat</a></div>` : "",
  ].filter(Boolean);

  els.details.classList.remove("muted");
  els.details.innerHTML = parts.join("");
}

function renderUpcoming() {
  const today = new Date(); today.setHours(0,0,0,0);
  const upcoming = state.filteredEvents
    .map(e => ({ e, d: new Date(e.start + "T00:00:00") }))
    .filter(x => x.d >= today)
    .sort((a,b) => a.d - b.d)
    .slice(0, 8);

  if (!upcoming.length) {
    els.upcoming.innerHTML = `<div class="muted">Aucun concours trouvé avec ces filtres.</div>`;
    return;
  }

  els.upcoming.innerHTML = upcoming.map(x => {
    const p = x.e.extendedProps || {};
    return `
      <div class="item">
        <strong>${safeText(x.e.title)}</strong>
        <div class="muted">${fmtDateFR(x.e.start)} • ${safeText(p.lieu || "")}</div>
        <span class="badge">${safeText(p.discipline || "Concours")}</span>
      </div>
    `;
  }).join("");
}

function initCalendar() {
  const isMobile = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  state.calendar = new FullCalendar.Calendar(els.calendarEl, {
    locale: "fr",
    height: "auto",
    firstDay: 1,
    buttonText: { dayGridMonth: "Mois", listMonth: "Liste" },
    displayEventTime: false,
    allDayText: "",
    initialView: "listMonth",
    headerToolbar: isMobile
      ? { left: "prev,next", center: "title", right: "listMonth,dayGridMonth" }
      : { left: "prev,next", center: "title", right: "listMonth,dayGridMonth" },
    dayMaxEvents: isMobile ? 3 : 4,
    expandRows: true,
    eventClick: (info) => { info.jsEvent.preventDefault(); renderDetails(info.event); },
    eventDidMount: (info) => {
      const cls = disciplineClass(info.event.extendedProps?.discipline);
      if (cls) info.el.classList.add(cls);

      const icon = eventIconHtml(info.event.extendedProps?.discipline);
      if (icon) {
        const titleEl = info.el.querySelector(".fc-event-title");
        if (titleEl && !titleEl.dataset.iconified) {
          const docIcon = info.event.extendedProps?.mandat_url ? `<span class="ev-ico" title="Mandat disponible"><i class="ti ti-file-description"></i></span>` : ``;
          titleEl.innerHTML = icon + docIcon + titleEl.innerHTML;
          titleEl.dataset.iconified = "1";
        }
      }
    },
    eventMouseEnter: (info) => {
      const p = info.event.extendedProps || {};
      const lieu = p.lieu ? safeText(p.lieu) : "Lieu non précisé";
      const disc = p.discipline ? safeText(p.discipline) : "Concours";
      const doc = p.mandat_url ? " • 📄 Mandat" : "";
      showTooltip(info.jsEvent, `<span class="t">${safeText(info.event.title)}</span><span class="m">${lieu} • ${disc}${doc}</span>`);
    },
    eventMouseLeave: () => hideTooltip(),
    eventMouseMove: (info) => moveTooltip(info.jsEvent)
  });
  state.calendar.render();

  // If user rotates or resizes, switch view appropriately (without being annoying)
  let lastMobile = isMobile;
  window.addEventListener("resize", () => {
    const nowMobile = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
    if (!state.calendar) return;
    if (nowMobile !== lastMobile) {
      state.calendar.changeView(nowMobile ? "listMonth" : "dayGridMonth");
      lastMobile = nowMobile;
    }
  });
}

function resetFilters() {
  els.fSearch.value = "";
  els.fDiscipline.value = "";
  els.fEtat.value = "";
  applyFilters();
  els.details.classList.add("muted");
  els.details.textContent = "Cliquez sur un concours dans le calendrier.";
}

/* Dates clés */
function normalizeImportance(s) {
  const v = (s || "").toLowerCase().trim();
  if (["haute","high","urgent"].includes(v)) return "haute";
  if (["moyenne","medium"].includes(v)) return "moyenne";
  if (["basse","low"].includes(v)) return "basse";
  return v || "moyenne";
}
function rowsToKeyDates(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim().length);
  if (!lines.length) return [];
  const header = parseCsvLine(lines[0]);
  const idx = Object.fromEntries(header.map((h,i)=>[h,i]));
  const get = (row, name) => {
    const i = idx[name];
    return (i == null) ? "" : (row[i] ?? "");
  };

  const items = [];
  for (let li=1; li<lines.length; li++) {
    const row = parseCsvLine(lines[li]);
    const titre = get(row, "titre");
    const d1 = parseFrDate(get(row, "date_debut"));
    if (!titre || !d1) continue;
    const d2 = parseFrDate(get(row, "date_fin")) || d1;

    items.push({
      type: get(row, "type") || "evenement",
      title: titre,
      date: d1,
      range_end: d2,
      lieu: get(row, "lieu") || "",
      approx: get(row, "precision") || "",
      importance: normalizeImportance(get(row, "importance")),
    });
  }
  items.sort((a,b) => a.date.localeCompare(b.date));
  return items;
}
function normalizeKeyDates() {
  return state.keyDates.map(x => {
    const start = x.date;
    const end = x.range_end || x.date;
    return { ...x, start, end };
  }).sort((a,b) => a.start.localeCompare(b.start));
}
function tlStatus(item, todayIso) {
  const end = item.end;
  if (end < todayIso) return "past";
  if (item.start <= todayIso && end >= todayIso) return "today";
  return "upcoming";
}


function laneKey(t){
  const v = (t||"").toLowerCase();
  if (v.includes("deadline") || v.includes("candidature") || v.includes("limite")) return "deadlines";
  if (v.includes("champion")) return "championnats";
  if (v.includes("regroup") || v.includes("stage")) return "regroupements";
  if (v.includes("institution")) return "institutionnel";
  if (v.includes("dre")) return "dre";
  if (v.includes("trjn")) return "trjn";
  return "autres";
}
function laneLabel(k){
  return ({
    deadlines: "Échéances",
    championnats: "Championnats",
    regroupements: "Regroupements",
    institutionnel: "Institutionnel",
    dre: "DRE",
    trjn: "TRJ / TRJN",
    autres: "Autres",
  })[k] || k;
}
const LANE_ORDER = ["deadlines","institutionnel","championnats","dre","trjn","regroupements","autres"];

function monthKey(iso){ return iso.slice(0,7); }
function monthLabel(iso){
  const [y,m] = iso.slice(0,7).split("-").map(Number);
  const fr = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  return `${fr[m-1]} ${y}`;
}
function daysUntil(iso){
  const d = new Date(iso + "T00:00:00");
  const t = new Date(); t.setHours(0,0,0,0);
  return Math.round((d - t) / (1000*60*60*24));
}


function vtTypeClass(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  // surveillance: deadlines & calendar launches
  if (t.includes("deadline") || t.includes("limite") || title.includes("date limite") || title.includes("clôture") || title.includes("cloture") || title.includes("candidature"))
    return "deadline";
  if (title.includes("lancement") || title.includes("ouverture") || title.includes("publication") || title.includes("calendrier"))
    return "launch";
  if (t.includes("champion")) return "championship";
  if (t.includes("dre")) return "dre";
  if (t.includes("trj") || t.includes("trjn")) return "trj";
  if (t.includes("regroup") || t.includes("stage")) return "group";
  return "other";
}


function keyDatesWithin(daysMax){
  const today = new Date(); today.setHours(0,0,0,0);
  const todayIso = today.toISOString().slice(0,10);
  return normalizeKeyDates()
    .filter(i => tlStatus(i, todayIso) !== "past")
    .map(i => ({...i, j: daysUntil(i.start)}))
    .filter(i => i.j >= 0 && i.j <= daysMax)
    .sort((a,b)=> (a.j-b.j) || a.start.localeCompare(b.start));
}
function buildTicker(){
  if (!els.ticker || !els.tickerItems) return;
  const top = keyDatesWithin(30).slice(0,3);
  if (!top.length){ els.ticker.style.display = "none"; return; }
  els.ticker.style.display = "";
  const line = top.map(i => `<span class="msg">${safeText(i.title)}<span class="meta">${fmtDateFR(i.start)} • J-${i.j}</span></span>`).join('<span class="sep">•</span>');
  els.tickerItems.innerHTML = `<div class="marquee"><div class="track">${line}<span class="sep">•</span>${line}</div></div>`;
}
function timelineBadges(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  const b = [];
  return b;
}

function isFranceEvent(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  return title.includes("championnat de france") || t.includes("france");
}


function renderTimeline() {
  const today = new Date(); today.setHours(0,0,0,0);
  const todayIso = today.toISOString().slice(0,10);
  els.pillToday.textContent = "Aujourd’hui : " + fmtDateFR(todayIso);

  const items = normalizeKeyDates();
  if (!items.length) {
    els.timeline.innerHTML = `<div class="muted">Aucune date clé.</div>`;
    return;
  }

  const byMonth = {};
  items.forEach(i => {
    const key = i.start.slice(0,7);
    byMonth[key] = byMonth[key] || [];
    byMonth[key].push(i);
  });

  let out = "";
  Object.keys(byMonth).sort().forEach(m => {
    const [y,mo]=m.split("-");
    const label = new Date(y,mo-1,1).toLocaleDateString("fr-FR",{month:"long",year:"numeric"});
    out += `<div class="vt-month"><h3>${label}</h3>`;
    byMonth[m].forEach(i => {
      const st = tlStatus(i, todayIso);
      const cls = st==="past"?"past":st==="today"?"today":"upcoming";
      const badges = timelineBadges(i);
      const isCD = badges.some(x=>x.cls==="cd");
      const isCDMail = isComiteDirecteur(i);
      const isFR = isFranceEvent(i);
      const j = daysUntil(i.start);
      out += `
        <div class="vt-card ${cls} ${vtTypeClass(i)} ${isFR?"france":""}">
          <div class="vt-title">${safeText(i.title)}</div>
          <div class="vt-meta">${fmtDateFR(i.start)}${i.end!==i.start?" → "+fmtDateFR(i.end):""}${i.lieu?" • "+safeText(i.lieu):""}${isFR?" • <span class=\"fr-label\">France</span>":""}</div>
          <div class="vt-chips">
            ${st==="today"?'<span class="vt-chip j">En cours</span>':""}
            ${j>0?`<span class="vt-chip j">J-${j}</span>`:""}
          </div>
          ${badges.length?`<div class="vt-badges">`+badges.map(x=>`<span class="vt-badge ${x.cls||""}">`+x.html+`</span>`).join("")+`</div>`:""}
        </div>`;
    });
    out += `</div>`;
  });

  els.timeline.innerHTML = out;
}

/* UI */
function wireUi() {
  els.tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      els.tabs.forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");

      const view = btn.dataset.view;
      Object.values(els.views).forEach(v => v.classList.remove("is-active"));
      els.views[view].classList.add("is-active");

      if (view === "calendar" && state.calendar) state.calendar.updateSize();
    });
  });

  ["input","change"].forEach(ev => {
    els.fSearch.addEventListener(ev, applyFilters);
    els.fDiscipline.addEventListener(ev, applyFilters);
    els.fEtat.addEventListener(ev, applyFilters);
  });

  els.btnToday.addEventListener("click", () => state.calendar && state.calendar.today());
  els.btnReset.addEventListener("click", resetFilters);
}

async function boot() {
  wireUi();

  try {
    const concoursText = await loadCsvUrl("concours.csv");
    state.rawEvents = rowsToConcoursEvents(concoursText);
  } catch (e) {
    console.error(e);
    els.upcoming.innerHTML = `<div class="muted"><b>Impossible de charger concours.csv</b><br>Ouvrez via un serveur web.</div>`;
    state.rawEvents = [];
  }

  try {
    const keyText = await loadCsvUrl("dates_cles.csv");
    state.keyDates = rowsToKeyDates(keyText);
  } catch (e) {
    console.error(e);
    state.keyDates = [];
  }

  buildFilters(state.rawEvents);
  applyFilters();

  initCalendar();
  state.calendar.addEventSource(state.filteredEvents);

  renderTimeline();
  buildTicker();
}

boot();

function isComiteDirecteur(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  return t.includes("comité directeur") || title.includes("comité directeur");
}
