// Helpers
function safeText(s){
  return String(s ?? "").replace(/[&<>"']/g, (m)=>({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[m]));
}
function parseFRDate(d){
  // "DD/MM/YYYY" or "YYYY-MM-DD"
  const s = String(d||"").trim();
  if(!s) return null;
  if(/^\d{4}-\d{2}-\d{2}$/.test(s)){
    const [y,m,dd]=s.split("-").map(Number);
    return new Date(y, m-1, dd);
  }
  const m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(m){
    const dd=Number(m[1]), mo=Number(m[2]), y=Number(m[3]);
    return new Date(y, mo-1, dd);
  }
  const dt = new Date(s);
  return isNaN(dt) ? null : dt;
}
function fmtDateFR(d){
  const dt = (d instanceof Date) ? d : parseFRDate(d);
  if(!dt) return "";
  return dt.toLocaleDateString("fr-FR", { weekday:"short", day:"2-digit", month:"short", year:"numeric" });
}
function isoDate(d){
  const dt = (d instanceof Date) ? d : parseFRDate(d);
  if(!dt) return null;
  const y=dt.getFullYear();
  const m=String(dt.getMonth()+1).padStart(2,"0");
  const dd=String(dt.getDate()).padStart(2,"0");
  return `${y}-${m}-${dd}`;
}
function daysBetween(a,b){
  const A = new Date(a.getFullYear(),a.getMonth(),a.getDate());
  const B = new Date(b.getFullYear(),b.getMonth(),b.getDate());
  return Math.round((B-A)/(1000*60*60*24));
}
async function loadCSV(url){
  const res = await fetch(url, {cache:"no-store"});
  if(!res.ok) throw new Error("Impossible de charger "+url);
  const txt = await res.text();
  // simple ; CSV parser
  const lines = txt.replace(/\r/g,"").split("\n").filter(l=>l.trim().length);
  const headers = lines[0].split(";").map(h=>h.trim());
  const rows = [];
  for(let i=1;i<lines.length;i++){
    const parts = lines[i].split(";");
    const row = {};
    for(let j=0;j<headers.length;j++){
      row[headers[j]] = (parts[j] ?? "").trim();
    }
    rows.push(row);
  }
  return rows;
}

// Views
const tabs = [...document.querySelectorAll(".tab")];
tabs.forEach(btn=>{
  btn.addEventListener("click", ()=>{
    tabs.forEach(b=>b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const v = btn.dataset.view;
    document.querySelectorAll(".view").forEach(s=>s.classList.remove("is-active"));
    document.querySelector(v==="concours" ? "#view-concours" : "#view-dates").classList.add("is-active");
  });
});

// State
let concoursRaw = [];
let concoursEvents = [];
let datesCles = [];
let cal = null;
let currentDiscipline = "Toutes";
let queryText = "";

// Load
init();

async function init(){
  // logo copy already in assets
  await Promise.all([loadConcours(), loadDatesCles()]);
  initFilters();
  initCalendar();
  renderUpcoming();
  renderMarquee();
  renderTimeline();
}

async function loadConcours(){
  const rows = await loadCSV("concours.csv");
  // only validated
  concoursRaw = rows.filter(r => String(r["Etat"]||"").toLowerCase().includes("valid"));
  concoursEvents = concoursRaw.map(r=>{
    const start = parseFRDate(r["Date Début"]);
    const end = parseFRDate(r["Date Fin"]);
    const discRaw = (r["Discipline"]||"").trim();
    const disc = discRaw.toLowerCase().includes("extérieur") ? "TAE" : discRaw.replace("Tir à l'Arc Extérieur","TAE");
    const mandat = (r["Mandat"]||"").trim();
    return {
      title: (r["Nom de l'épreuve"]||"").trim() || "Concours",
      start: isoDate(start),
      end: end && isoDate(end) !== isoDate(start) ? isoDate(new Date(end.getFullYear(), end.getMonth(), end.getDate()+1)) : undefined, // FC exclusive end
      allDay: true,
      extendedProps: {
        discipline: disc,
        discipline_raw: discRaw,
        lieu: (r["Lieu"]||"").trim(),
        organisateur: (r["Organisateur"]||"").trim(),
        agrement: (r["Agrément"]||"").trim(),
        mandat: mandat && mandat !== ")" ? mandat : ""
      }
    };
  });
}

async function loadDatesCles(){
  const rows = await loadCSV("dates_cles.csv");
  datesCles = rows.map(r=>{
    const start = parseFRDate(r["date_debut"]);
    const end = parseFRDate(r["date_fin"]) || start;
    return {
      type: (r["type"]||"").trim(),
      title: (r["titre"]||"").trim(),
      start: start,
      end: end,
      lieu: (r["lieu"]||"").trim(),
      precision: (r["precision"]||"").trim(),
      importance: (r["importance"]||"").trim(),
      mandat: (r["mandat"]||r["Mandat"]||r["lien_mandat"]||r["url_mandat"]||"").trim()
    };
  }).filter(x=>x.start)
    .filter(x=>{
      const today = new Date(); today.setHours(0,0,0,0);
      const endD = new Date(x.end); endD.setHours(23,59,59,999);
      return endD >= today;
    });
}

function initFilters(){
  const sel = document.getElementById("discipline");
  const discSet = new Set(concoursEvents.map(e=>e.extendedProps.discipline).filter(Boolean));
  const discs = ["Toutes", ...Array.from(discSet).sort((a,b)=>a.localeCompare(b,"fr"))];
  sel.innerHTML = discs.map(d=>`<option value="${safeText(d)}">${safeText(d)}</option>`).join("");
  sel.value = "Toutes";

  document.getElementById("q").addEventListener("input", (e)=>{
    queryText = e.target.value.trim().toLowerCase();
    applyFilters();
  });
  sel.addEventListener("change", (e)=>{
    currentDiscipline = e.target.value;
    applyFilters();
  });

  document.getElementById("btn-reset").addEventListener("click", ()=>{
    queryText = "";
    currentDiscipline = "Toutes";
    document.getElementById("q").value = "";
    sel.value = "Toutes";
    applyFilters();
  });
  document.getElementById("btn-today").addEventListener("click", ()=>{
    cal?.today();
  });
}

function applyFilters(){
  const filtered = concoursEvents.filter(ev=>{
    const ep = ev.extendedProps || {};
    const discOk = (currentDiscipline==="Toutes") || (ep.discipline===currentDiscipline);
    const q = queryText;
    const qOk = !q || [
      ev.title, ep.lieu, ep.organisateur, ep.discipline, ep.agrement
    ].some(v=>String(v||"").toLowerCase().includes(q));
    return discOk && qOk;
  });
  cal?.removeAllEvents();
  cal?.addEventSource(filtered);
  renderUpcoming(filtered);
}

function initCalendar(){
  const el = document.getElementById("calendar");
  cal = new FullCalendar.Calendar(el, {
    locale: "fr",
    firstDay: 1,
    initialView: "dayGridMonth",
    height: "auto",
    headerToolbar: { left:"prev,next", center:"title", right: "dayGridMonth,listMonth" },
    buttonText: { listMonth:"Liste", dayGridMonth:"Mois" },
    displayEventTime: false,
    allDayText: "",
    eventContent: function(arg){
      const ep = arg.event.extendedProps || {};
      const disc = ep.discipline || "";
      const place = ep.lieu || "";
      const title = arg.event.title || "";
      const mandat = ep.mandat || "";

      // List view: title + disc/place + mandate icon
      if(String(arg.view.type||"").startsWith("list")){
        const wrap = document.createElement("div");
        wrap.className="list-line";
        const left = document.createElement("div");
        left.className="list-main";
        left.innerHTML = `<div class="list-title">${safeText(title)}</div>
          <div class="list-meta">${safeText(disc)}${(disc&&place)?' • ':''}${safeText(place)}</div>`;
        wrap.appendChild(left);
        if(mandat){
          const a = document.createElement("a");
          a.className="mandat-ico";
          a.href = mandat;
          a.target="_blank";
          a.rel="noopener";
          a.title="Ouvrir le mandat";
          a.textContent="📄";
          a.addEventListener("click",(e)=>e.stopPropagation());
          wrap.appendChild(a);
        }
        return { domNodes:[wrap] };
      }

      // Month view: compact + optional mandate
      if(mandat){
        const wrap = document.createElement("div");
        wrap.className="cal-ev";
        const t = document.createElement("span");
        t.className="cal-ev-title";
        t.textContent = title;
        wrap.appendChild(t);
        const a = document.createElement("a");
        a.className="cal-ev-mandat";
        a.href = mandat;
        a.target="_blank";
        a.rel="noopener";
        a.title="Ouvrir le mandat";
        a.textContent="📄";
        a.addEventListener("click",(e)=>e.stopPropagation());
        wrap.appendChild(a);
        return { domNodes:[wrap] };
      }
      return true;
    },
    eventClick: function(info){
      const ep = info.event.extendedProps || {};
      const d = document.getElementById("details");
      const start = info.event.start;
      // FullCalendar uses exclusive end for all-day multi-day; show readable range from stored start/end in raw props if possible
      const title = safeText(info.event.title || "");
      const disc = safeText(ep.discipline || "");
      const lieu = safeText(ep.lieu || "");
      const org = safeText(ep.organisateur || "");
      const mandat = (ep.mandat||"").trim();

      d.innerHTML = `
        <div class="up-title">${title}</div>
        <div class="up-meta">${disc}${(disc&&lieu)?' • ':''}${lieu}</div>
        <div class="up-meta">${fmtDateFR(start)}</div>
        ${org?`<div class="up-meta">Organisateur : ${org}</div>`:""}
        ${mandat?`<div style="margin-top:10px"><a class="btn" href="${safeText(mandat)}" target="_blank" rel="noopener">📄 Ouvrir le mandat</a></div>`:""}
      `;
    }
  });
  cal.render();
  cal.addEventSource(concoursEvents);
}

function renderUpcoming(source){
  const list = (source || concoursEvents).slice().sort((a,b)=>{
    return (a.start||"").localeCompare(b.start||"");
  });
  const now = new Date();
  const upcoming = list.filter(e=>{
    const st = parseFRDate(e.start);
    return st && st >= new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }).slice(0,8);

  const el = document.getElementById("upcoming");
  if(!upcoming.length){
    el.textContent = "Aucun concours à venir.";
    return;
  }
  el.innerHTML = upcoming.map(e=>{
    const ep = e.extendedProps||{};
    return `<div class="up-item">
      <div class="up-title">${safeText(e.title)}</div>
      <div class="up-meta">${fmtDateFR(e.start)} • ${safeText(ep.lieu||"")}</div>
      <div class="badge" style="display:inline-block;margin-top:6px">${safeText(ep.discipline||"")}</div>
    </div>`;
  }).join("");
}

function renderMarquee(){
  // Dates clés within 30 days from today (any type, but highlight high importance)
  const wrap = document.getElementById("marquee-wrap");
  const track = document.getElementById("marquee-track");
  const today = new Date();
  const items = datesCles
    .map(x=>({x, d: daysBetween(today, x.start)}))
    .filter(o=>o.d>=0 && o.d<=30)
    .sort((a,b)=>a.d-b.d)
    .slice(0,8);

  if(!items.length){ wrap.hidden = true; return; }
  wrap.hidden = false;

  const txt = items.map(o=>{
    return `<span class="marquee-item"><strong>${safeText(o.x.title)}</strong> ${fmtDateFR(o.x.start)} • J-${o.d}</span>`;
  });

  // duplicate for infinite scroll
  track.innerHTML = txt.concat(txt).join('<span aria-hidden="true"> • </span>');
}

// Dates clés view
function isFranceEvent(item){
  const title = (item.title||"").toLowerCase();
  return title.includes("championnat de france");
}
function isCodir(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  return t === "codir" || title.includes("comité directeur") || title.includes("comite directeur");
}
function isInstitutionnel(item){
  const t = (item.type||"").toLowerCase();
  return t === "institutionnel";
}
function isDeadline(item){
  const t = (item.type||"").toLowerCase();
  const title = (item.title||"").toLowerCase();
  return t === "deadline" || title.includes("date limite") || title.includes("deadline");
}

function renderTimeline(){
  const today = new Date();
  document.getElementById("today-pill").textContent = "Aujourd’hui : " + today.toLocaleDateString("fr-FR", { weekday:"short", day:"2-digit", month:"short", year:"numeric" });

  const items = [...datesCles].sort((a,b)=>a.start-b.start);
  const byMonth = new Map();
  for(const it of items){
    const key = it.start.getFullYear()+"-"+String(it.start.getMonth()+1).padStart(2,"0");
    if(!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key).push(it);
  }

  const months = Array.from(byMonth.keys()).sort();
  const tl = document.getElementById("timeline");
  if(!months.length){ tl.textContent="Aucune date clé."; return; }

  let out = "";
  for(const key of months){
    const [y,m] = key.split("-").map(Number);
    const monthName = new Date(y, m-1, 1).toLocaleDateString("fr-FR", { month:"long", year:"numeric" });
    out += `<div class="month-title">${safeText(monthName)}</div><div class="vt">`;
    for(const it of byMonth.get(key)){
      const d = daysBetween(today, it.start);
      const cls = [
        isFranceEvent(it) ? "france" : "",
        isDeadline(it) ? "deadline" : "",
        (isInstitutionnel(it) && !isCodir(it)) ? "inst" : "",
        isCodir(it) ? "codir" : ""
      ].filter(Boolean).join(" ");

      const range = (isoDate(it.end) && isoDate(it.end) !== isoDate(it.start))
        ? `${fmtDateFR(it.start)} → ${fmtDateFR(it.end)}`
        : `${fmtDateFR(it.start)}`;

      out += `<div class="vt-item">
        <div class="vt-dot"></div>
        <div class="vt-card ${cls}">
          <div class="vt-title">${safeText(it.title)}</div>
          <div class="vt-meta">${safeText(range)}${it.lieu?` • ${safeText(it.lieu)}`:""}</div>
          <div class="vt-badges">
            <span class="badge">J-${Math.max(0,d)}</span>
            ${it.type?`<span class="badge">${safeText(it.type)}</span>`:""}
          </div>
          ${isCodir(it)?`<a class="cd-mail" href="mailto:s-general@arc-paysdelaloire.fr" title="Contacter le secrétariat général"></a>`:""}
        </div>
      </div>`;
    }
    out += `</div>`;
  }
  tl.innerHTML = out;
}

function getMandatFromRow(row){
  return row.mandat || row.Mandat || row.mandat_url || row.url_mandat || row.lien_mandat || row.lien || "";
}
