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
  if (d.includes("campagne")) return '<span class="ev-ico"><span class="ico-target-campagne"></span></span>';
  if (d.includes("nature")) return '<span class="ev-ico"><i class="ti ti-leaf"></i></span>';
  if (d.includes("3d")) return '<span class="ev-ico"><i class="ti ti-paw"></i></span>';
  if (d.includes("beursault")) return '<span class="ev-ico"><span class="ico-target-beursault"></span></span>';
  if (d.includes("tae") || d.includes("extérieur") || d.includes("exterieur")) return '<span class="ev-ico"><i class="ti ti-target"></i></span>';
  if (d.includes("loisir")) return '<span class="ev-ico"><i class="ti ti-mood-smile"></i></span>';
  return '';
}

function disciplineClass(disciplineRaw){
  const d = (disciplineRaw || "").toLowerCase();
  if (d.includes("campagne")) return "disc-campagne";
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
  state.calendar = new FullCalendar.Calendar(els.calendarEl, {
    locale: "fr",
    height: "auto",
    firstDay: 1,
    initialView: "dayGridMonth",
    headerToolbar: { left: "prev,next", center: "title", right: "dayGridMonth,listMonth" },
    eventClick: (info) => { info.jsEvent.preventDefault(); renderDetails(info.event); },
    eventDidMount: (info) => {
      const cls = disciplineClass(info.event.extendedProps?.discipline);
      if (cls) info.el.classList.add(cls);

      const icon = eventIconHtml(info.event.extendedProps?.discipline);
      if (icon) {
        const titleEl = info.el.querySelector(".fc-event-title");
        if (titleEl && !titleEl.dataset.iconified) {
          titleEl.innerHTML = icon + titleEl.innerHTML;
          titleEl.dataset.iconified = "1";
        }
      }
    },
    eventMouseEnter: (info) => {
      const p = info.event.extendedProps || {};
      const lieu = p.lieu ? safeText(p.lieu) : "Lieu non précisé";
      const disc = p.discipline ? safeText(p.discipline) : "Concours";
      showTooltip(info.jsEvent, `<span class="t">${safeText(info.event.title)}</span><span class="m">${lieu} • ${disc}</span>`);
    },
    eventMouseLeave: () => hideTooltip(),
    eventMouseMove: (info) => moveTooltip(info.jsEvent)
  });
  state.calendar.render();
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

function renderTimeline() {
  const today = new Date(); today.setHours(0,0,0,0);
  const todayIso = today.toISOString().slice(0,10);
  els.pillToday.textContent = "Aujourd’hui : " + fmtDateFR(todayIso);

  const items = normalizeKeyDates();
  if (!items.length) {
    els.nextImportant.innerHTML = `<div class="muted">Aucune donnée dans dates_cles.csv.</div>`;
    els.timeline.innerHTML = `<div class="muted">Ajoutez des lignes dans <b>dates_cles.csv</b> puis rechargez.</div>`;
    return;
  }

  // Progress bar (from first to last item)
  const minIso = items[0].start;
  const maxIso = items[items.length-1].end;
  const minD = new Date(minIso + "T00:00:00");
  const maxD = new Date(maxIso + "T00:00:00");
  const span = Math.max(1, (maxD - minD));
  const pos = Math.min(1, Math.max(0, (today - minD) / span));
  const fillEl = document.getElementById("tl-progress-fill");
  const nowEl = document.getElementById("tl-progress-now");
  const startEl = document.getElementById("tl-start");
  const endEl = document.getElementById("tl-end");
  if (fillEl) fillEl.style.width = (pos*100).toFixed(1) + "%";
  if (nowEl) nowEl.style.left = (pos*100).toFixed(1) + "%";
  if (startEl) startEl.textContent = fmtDateFR(minIso);
  if (endEl) endEl.textContent = fmtDateFR(maxIso);

  // Choose next event (today/upcoming, prioritize earliest, then importance)
  const impRank = (x) => x.importance === "haute" ? 0 : x.importance === "moyenne" ? 1 : 2;
  const upcoming = items
    .filter(i => tlStatus(i, todayIso) !== "past")
    .sort((a,b)=> {
      const sa = tlStatus(a, todayIso);
      const sb = tlStatus(b, todayIso);
      if (sa !== sb) return sa === "today" ? -1 : 1;
      if (a.start !== b.start) return a.start.localeCompare(b.start);
      return impRank(a)-impRank(b);
    });
  const next = upcoming[0];

  els.nextImportant.innerHTML = next ? `
    <div class="item">
      <strong>${safeText(next.title)}</strong>
      <div class="muted">${fmtDateFR(next.start)}${next.end!==next.start ? " → " + fmtDateFR(next.end) : ""}${next.approx ? " • " + safeText(next.approx) : ""}</div>
      ${next.lieu ? `<div class="muted" style="margin-top:6px">${safeText(next.lieu)}</div>` : ""}
      <div class="chips" style="margin-top:10px">
        ${tlStatus(next, todayIso)==="today" ? `<span class="chip j">En cours</span>` : ``}
        ${tlStatus(next, todayIso)!=="past" ? (()=>{
          const j = daysUntil(next.start);
          if (j>0) return `<span class="chip j">J-${j}</span>`;
          if (j===0) return `<span class="chip j">Aujourd’hui</span>`;
          return ``;
        })() : ``}
      </div>
    </div>
  ` : `<div class="muted">Aucun événement à venir.</div>`;

  // Group by month
  const groups = new Map();
  for (const i of items) {
    const k = monthKey(i.start);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(i);
  }

  let out = "";
  for (const [k, arr] of groups.entries()) {
    const label = monthLabel(k + "-01");
    out += `
      <div class="month">
        <div class="month-h">
          <span>${label}</span>
          <span class="count">${arr.length} événement${arr.length>1?"s":""}</span>
        </div>
        <div class="month-body">
          ${arr.map(i => {
            const st = tlStatus(i, todayIso);
            const cls = st === "past" ? "is-past" : st === "today" ? "is-today" : "is-upcoming";
            const nextCls = (next && next.title === i.title && next.start === i.start && st !== "past") ? " is-next-important" : "";
            const imp = safeText(i.importance || "moyenne");
            const j = daysUntil(i.start);
            const countdown = (st !== "past" && j>0 && j<=45) ? `<span class="chip j">J-${j}</span>` : (st==="today" ? `<span class="chip j">Aujourd’hui</span>` : ``);
            const statusChip = st==="today" ? `<span class="chip">En cours</span>` : ``;
            return `
              <div class="tl ${cls}${nextCls}" data-importance="${imp}">
                <div class="date">${fmtDateFR(i.start)}${i.end!==i.start ? " → " + fmtDateFR(i.end) : ""}${i.approx ? " • " + safeText(i.approx) : ""}</div>
                <div class="title">${safeText(i.title)}</div>
                ${i.lieu ? `<div class="meta">${safeText(i.lieu)}</div>` : ""}
                <div class="chips">
                  ${statusChip}
                  ${countdown}
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

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
}

boot();
