// -----------------------------
// Calendrier + Carte concours (CSV unique concours26.csv)
// - Charge concours26.csv et dates_cles.csv depuis le même dossier (ou data/ ou assets/)
// - Gère dates FR (DD/MM/YY et DD/MM/YYYY) + ISO
// - Filtre Discipline (colonne "Discipline") + Département + Recherche => calendrier + liste + carte
// - Points carte mêmes couleurs (adoucies) que les disciplines
// - Popup carte inclut Mandat (si dispo)
// -----------------------------

// Helpers
function safeText(s){
  return String(s ?? "").replace(/[&<>"']/g, (m)=>({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[m]));
}

function parseFRDate(d){
  const s = String(d||"").trim();
  if(!s) return null;

  // ISO YYYY-MM-DD
  if(/^\d{4}-\d{2}-\d{2}$/.test(s)){
    const [y,m,dd] = s.split("-").map(Number);
    const dt = new Date(y, m-1, dd);
    return isNaN(dt) ? null : dt;
  }

  // FR DD/MM/YY or DD/MM/YYYY
  const m = s.match(/^(\d{2})\/(\d{2})\/(\d{2}|\d{4})$/);
  if(m){
    const dd = Number(m[1]);
    const mo = Number(m[2]);
    let y = Number(m[3]);
    if(y < 100) y += 2000; // 25 -> 2025
    const dt = new Date(y, mo-1, dd);
    return isNaN(dt) ? null : dt;
  }

  // Fallback
  const dt = new Date(s);
  return isNaN(dt) ? null : dt;
}

function isoDate(d){
  const dt = (d instanceof Date) ? d : parseFRDate(d);
  if(!dt) return null;
  const y = dt.getFullYear();
  const m = String(dt.getMonth()+1).padStart(2,"0");
  const dd = String(dt.getDate()).padStart(2,"0");
  return `${y}-${m}-${dd}`;
}

function fmtDateFR(d){
  const dt = (d instanceof Date) ? d : parseFRDate(d);
  if(!dt) return "";
  return dt.toLocaleDateString("fr-FR", { weekday:"short", day:"2-digit", month:"short", year:"numeric" });
}

function daysBetween(a,b){
  const A = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  const B = new Date(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((B-A)/(1000*60*60*24));
}

function deptFromCodeStructure(code){
  const s = String(code||"").trim();
  if (s.length >= 14) return s.substring(12,14);
  const m = s.match(/\b(0\d|[1-9]\d)\b/);
  return m ? m[1] : "";
}

async function loadCSV(url){
  const res = await fetch(url, {cache:"no-store"});
  if(!res.ok) throw new Error(`HTTP ${res.status} - ${url}`);
  const txt = await res.text();
  const lines = txt.replace(/\r/g,"").split("\n").filter(l=>l.trim().length);
  if(!lines.length) return [];

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

async function loadCSVAny(paths){
  let lastErr = null;
  for(const p of paths){
    try{
      const rows = await loadCSV(p);
      // eslint-disable-next-line no-console
      console.log("CSV chargé :", p, rows.length, "lignes");
      return rows;
    }catch(e){
      lastErr = e;
      // eslint-disable-next-line no-console
      console.warn("Échec chargement CSV :", p, e?.message || e);
    }
  }
  throw lastErr || new Error("Impossible de charger le CSV");
}

// Discipline => clé couleur (palette adoucie)
function disciplineKey(discipline){
  const d = String(discipline||"").toLowerCase();
  if (d.includes("tournoi poussin") || d.includes("jeunes") || d.includes("jeune") || d.includes("poussin")) return "jeune";
  if (d.includes("rencontres clubs loisirs") || d.includes("loisirs") || d.includes("loisir")) return "loisir";
  if (d.includes("beursault")) return "beursault";
  if (d.includes("campagne")) return "campagne";
  if (d.includes("nature")) return "nature";
  if (d.includes("3d")) return "3d";
  if (d.includes("para") && (d.includes("18") || d.includes("à 18") || d.includes("a 18") || d.includes("18m") || d.includes("salle"))) return "para18m";
  if (d.includes("para") && (d.includes("extérieur") || d.includes("exterieur") || d.includes("ext") || d.includes("arc extérieur") || d.includes("arc exterieur"))) return "paraext";
  if (d.includes("arc extérieur") || d.includes("arc exterieur") || d.includes("extérieur") || d.includes("exterieur") || d.includes("tae")) return "tae";
  if (d.includes("18") || d.includes("18m") || d.includes("à 18") || d.includes("a 18") || d.includes("salle")) return "18m";
  return "";
}

const PALETTE = {
  tae:      { fill:"#e6e255", stroke:"#6b6b00", text:"#000000" },
  "18m":    { fill:"#d98c2b", stroke:"#6a3f09", text:"#111827" },
  paraext:  { fill:"#2f6bff", stroke:"#12306a", text:"#ffffff" },
  para18m:  { fill:"#1e3a8a", stroke:"#0b1a3f", text:"#ffffff" },
  "3d":     { fill:"#8b5a2b", stroke:"#3f2712", text:"#ffffff" },
  nature:   { fill:"#556b2f", stroke:"#24310f", text:"#ffffff" },
  campagne: { fill:"#000000", stroke:"#000000", text:"#ffd400", bi:["#000000","#ffd400"] },
  beursault:{ fill:"#000000", stroke:"#000000", text:"#ffffff", bi:["#000000","#ffffff"] },
  jeune:    { fill:"#7c3aed", stroke:"#3b1a7a", text:"#ffffff" },
  loisir:   { fill:"#e11dcc", stroke:"#6b0a5e", text:"#ffffff" },
};

function getMandatFromRow(row){
  // colonne Mandat si existante, sinon premier lien http trouvé
  let mandat = (row["Mandat"]||row["mandat"]||row["lien_mandat"]||row["url_mandat"]||"").trim();
  if(mandat && mandat !== ")") return mandat;
  for(const v of Object.values(row)){
    const s = String(v||"").trim();
    if(/^https?:\/\//i.test(s)) return s;
  }
  return "";
}

// ---------- UI Tabs ----------
const tabs = [...document.querySelectorAll(".tab")];
tabs.forEach(btn=>{
  btn.addEventListener("click", ()=>{
    tabs.forEach(b=>b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const v = btn.dataset.view;
    document.querySelectorAll(".view").forEach(s=>s.classList.remove("is-active"));
    document.querySelector(v==="concours" ? "#view-concours" : "#view-dates").classList.add("is-active");
    // Fix Leaflet sizing when switching tabs
    if(v==="concours" && nearby.map){
      setTimeout(()=>nearby.map.invalidateSize(), 50);
    }
  });
});

// ---------- State ----------
let concoursRaw = [];
let concoursEvents = [];      // FullCalendar events (upcoming only)
let concoursGeo = [];         // Geo list (upcoming only)
let datesCles = [];

let cal = null;

let currentDiscipline = "Toutes";
let currentDept = "Tous";
let queryText = "";

let allowedUids = null;       // Set of event ids allowed by filters

let nearby = {
  map: null,
  layer: null,
  user: null,
  radius: 50,
  markersById: new Map(),     // uid => marker
};

// ---------- Init ----------
init();

async function init(){
  try{
    await Promise.all([loadConcours(), loadDatesCles()]);
    loadConcoursGeo(); // derived from concoursRaw
  }catch(err){
    console.error("Erreur chargement données:", err);
    const up = document.getElementById("upcoming");
    if(up) up.textContent = "Impossible de charger les CSV. Vérifie que concours26.csv et dates_cles.csv sont bien dans le même dossier que index.html (ou dans /data).";
    const tl = document.getElementById("timeline");
    if(tl) tl.textContent = "Impossible de charger dates_cles.csv.";
    return;
  }

  initFilters();
  initCalendar();
  initNearby();
  initModal();

  applyFilters();      // renders upcoming + map + calendar
  renderMarquee();
  renderTimeline();
}

// ---------- Load concours ----------
async function loadConcours(){
  const rows = await loadCSVAny(["concours26.csv","./concours26.csv","data/concours26.csv","assets/concours26.csv"]);
  concoursRaw = rows;

  const today = new Date(); today.setHours(0,0,0,0);

  concoursEvents = rows.map(r=>{
    const title = (r["Titre compétition"]||r["Titre competition"]||r["Titre"]||"").trim() || "Concours";

    const startD = parseFRDate(r["Date debut"] || r["Date début"]);
    const endD = parseFRDate(r["Date fin"]);
    const endOrStart = endD || startD;

    const dept = (r["Departement"]||r["Département"]||"").trim() || deptFromCodeStructure(r["Code structure"]);
    const code_structure = (r["Code structure"]||"").trim();

    const disciplineBase = (r["Discipline"]||"").trim();           // <- IMPORTANT (filtre discipline)
    const spec = (r["Spécificité"]||r["Specificite"]||"").trim();
    const discLabel = [disciplineBase, spec].filter(Boolean).join(" • ") || disciplineBase || spec || "";

    const lieu = (r["Lieu"]||"").trim() || (r["Ville compétition"]||r["Ville competition"]||r["Ville"]||"").trim();
    const org = (r["Club organisateur"]||r["Organisateur"]||"").trim();
    const agre = (r["Agrément"]||r["Agrement"]||"").trim();
    const city = (r["Ville compétition"]||r["Ville competition"]||r["Ville"]||r["Ville;"]||r["Ville " ]||r["Ville"]||r["Ville"]||r["Ville"]||r["Ville"]||r["Ville"]||r["Ville"]||r["Ville"]||"").trim() || (r["Ville"]||"").trim();

    const mandat = getMandatFromRow(r);

    const uid = `${code_structure||dept||""}|${title}|${isoDate(startD)||""}|${isoDate(endOrStart)||""}|${disciplineBase}`;

    const key = disciplineKey(disciplineBase);

    const startISO = isoDate(startD);
    const endExclusive = (endOrStart && startD && isoDate(endOrStart) !== isoDate(startD))
      ? isoDate(new Date(endOrStart.getFullYear(), endOrStart.getMonth(), endOrStart.getDate()+1)) // FC end exclusive
      : undefined;

    return {
      id: uid,
      title,
      start: startISO,
      end: endExclusive,
      allDay: true,
      classNames: key ? [`ev-${key}`] : [],
      extendedProps: {
        uid,
        disciplineBase,
        disciplineLabel: discLabel,
        lieu,
        ville: city,
        organisateur: org,
        agrement: agre,
        mandat: mandat && mandat !== ")" ? mandat : "",
        code_structure,
        dept
      }
    };
  }).filter(e=>{
    // keep upcoming: end inclusive >= today
    const s = parseFRDate(e.start);
    const endEx = e.end ? parseFRDate(e.end) : s;
    const endInc = endEx ? new Date(endEx.getFullYear(), endEx.getMonth(), endEx.getDate()-1) : s;
    const d = endInc || s;
    if(!d) return true;
    d.setHours(0,0,0,0);
    return d >= today;
  });
}

// Derive geo list from concoursRaw (upcoming + coords)
function loadConcoursGeo(){
  const today = new Date(); today.setHours(0,0,0,0);

  const geo = [];
  for(const r of concoursRaw){
    const startD = parseFRDate(r["Date debut"] || r["Date début"]);
    const endD = parseFRDate(r["Date fin"]) || startD;
    const endInc = endD || startD;
    if(!endInc) continue;
    const endCheck = new Date(endInc.getFullYear(), endInc.getMonth(), endInc.getDate());
    if(endCheck < today) continue;

    const title = (r["Titre compétition"]||r["Titre competition"]||r["Titre"]||"").trim() || "Concours";
    const dept = (r["Departement"]||r["Département"]||"").trim() || deptFromCodeStructure(r["Code structure"]);
    const code_structure = (r["Code structure"]||"").trim();

    const disciplineBase = (r["Discipline"]||"").trim();
    const spec = (r["Spécificité"]||r["Specificite"]||"").trim();
    const discLabel = [disciplineBase, spec].filter(Boolean).join(" • ") || disciplineBase || spec || "";

    const city = (r["Ville compétition"]||r["Ville competition"]||r["Ville"]||"").trim() || (r["Ville"]||"").trim();
    const lieu = (r["Lieu"]||"").trim();

    // Coordinates: CSV columns swapped (Long contains lat, Lat contains lon)
    const rawLong = String(r["Long"]||"").trim().replace(",",".");
    const rawLat  = String(r["Lat"]||"").trim().replace(",",".");
    let a = Number(rawLong);
    let b = Number(rawLat);
    if(!isFinite(a) || !isFinite(b)) continue;

    // Heuristic swap: in France lat ~ 41..52, lon ~ -6..10
    let lat = a, lon = b;
    const latLooks = (x)=> x >= 41 && x <= 52;
    const lonLooks = (x)=> x >= -6 && x <= 10;
    if(latLooks(a) && lonLooks(b)){
      lat = a; lon = b;
    }else if(latLooks(b) && lonLooks(a)){
      lat = b; lon = a;
    }else{
      // last resort: assume Long=lat, Lat=lon (your file's current convention)
      lat = a; lon = b;
    }

    const mandat = getMandatFromRow(r);

    const uid = `${code_structure||dept||""}|${title}|${isoDate(startD)||""}|${isoDate(endInc)||""}|${disciplineBase}`;

    geo.push({
      id: uid,
      title,
      start: startD,
      end: endInc,
      dept,
      disciplineBase,
      disciplineLabel: discLabel,
      city,
      lieu,
      mandat,
      lat, lon
    });
  }
  concoursGeo = geo;
}

// ---------- Dates clés ----------
async function loadDatesCles(){
  const rows = await loadCSVAny(["dates_cles.csv","./dates_cles.csv","data/dates_cles.csv","assets/dates_cles.csv"]);
  datesCles = rows.map(r=>{
    const start = parseFRDate(r["date_debut"]);
    const end = parseFRDate(r["date_fin"]) || start;
    return {
      type: (r["type"]||"").trim(),
      title: (r["titre"]||"").trim(),
      start,
      end,
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

// ---------- Filters ----------
function initFilters(){
  const selDisc = document.getElementById("discipline");
  const selDept = document.getElementById("dept");

  // Discipline = colonne "Discipline" (base)
  const discSet = new Set(concoursEvents.map(e=>e.extendedProps.disciplineBase).filter(Boolean));
  const discs = ["Toutes", ...Array.from(discSet).sort((a,b)=>a.localeCompare(b,"fr"))];
  selDisc.innerHTML = discs.map(d=>`<option value="${safeText(d)}">${safeText(d)}</option>`).join("");
  selDisc.value = "Toutes";

  // Département
  const deptSet = new Set(concoursEvents.map(e=>e.extendedProps.dept).filter(Boolean));
  const depts = ["Tous", ...Array.from(deptSet).sort()];
  selDept.innerHTML = depts.map(d=>`<option value="${safeText(d)}">${safeText(d)}</option>`).join("");
  selDept.value = "Tous";

  document.getElementById("q").addEventListener("input", (e)=>{
    queryText = e.target.value.trim().toLowerCase();
    applyFilters();
  });

  selDisc.addEventListener("change", (e)=>{
    currentDiscipline = e.target.value;
    applyFilters();
  });

  selDept.addEventListener("change",(e)=>{
    currentDept = e.target.value;
    applyFilters();
  });

  document.getElementById("btn-reset").addEventListener("click", ()=>{
    queryText = "";
    currentDiscipline = "Toutes";
    currentDept = "Tous";
    document.getElementById("q").value = "";
    selDisc.value = "Toutes";
    selDept.value = "Tous";
    applyFilters();
  });

  document.getElementById("btn-today").addEventListener("click", ()=>{
    cal?.today();
  });
}

function applyFilters(){
  const filtered = concoursEvents.filter(ev=>{
    const ep = ev.extendedProps || {};
    const discOk = (currentDiscipline==="Toutes") || (ep.disciplineBase === currentDiscipline);
    const deptOk = (currentDept==="Tous") || (ep.dept === currentDept);

    const q = queryText;
    const qOk = !q || [
      ev.title, ep.lieu, ep.ville, ep.organisateur, ep.disciplineLabel, ep.disciplineBase, ep.agrement
    ].some(v=>String(v||"").toLowerCase().includes(q));

    return discOk && deptOk && qOk;
  });

  allowedUids = new Set(filtered.map(e=>e.id));

  if(cal){
    cal.removeAllEvents();
    cal.addEventSource(filtered);
  }

  renderUpcoming(filtered);
  updateNearby();
}

// ---------- Calendar ----------
function initCalendar(){
  const el = document.getElementById("calendar");
  if(!el || !window.FullCalendar){
    console.warn("FullCalendar non chargé");
    return;
  }

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
      const title = arg.event.title || "";
      const discLabel = ep.disciplineLabel || ep.disciplineBase || "";
      const place = ep.lieu || ep.ville || "";
      const mandat = ep.mandat || "";

      // List view
      if(String(arg.view.type||"").startsWith("list")){
        const wrap = document.createElement("div");
        wrap.className = "list-line";
        const left = document.createElement("div");
        left.className = "list-main";
        left.innerHTML = `<div class="list-title">${safeText(title)}</div>
          <div class="list-meta">${safeText(discLabel)}${(discLabel&&place)?' • ':''}${safeText(place)}</div>`;
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

      // Month view: title + optional mandate icon
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
      info.jsEvent.preventDefault();
      openEventModal(info.event);
    }
  });

  cal.render();
  cal.addEventSource(concoursEvents);
}

// ---------- Upcoming ----------
function renderUpcoming(source){
  const list = (source || concoursEvents).slice().sort((a,b)=> (a.start||"").localeCompare(b.start||""));
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const upcoming = list.filter(e=>{
    const st = parseFRDate(e.start);
    return st && st >= today;
  }).slice(0,8);

  const el = document.getElementById("upcoming");
  if(!el) return;

  if(!upcoming.length){
    el.textContent = "Aucun concours à venir.";
    return;
  }

  el.innerHTML = upcoming.map(e=>{
    const ep = e.extendedProps||{};
    const key = disciplineKey(ep.disciplineBase);
    const pal = PALETTE[key] || null;

    const badgeStyle = pal
      ? `background:${pal.fill}; color:${pal.text}; border-color:${pal.stroke};`
      : "";

    return `<div class="up-item">
      <div class="up-title">${safeText(e.title)}</div>
      <div class="up-meta">${fmtDateFR(e.start)} • ${safeText(ep.lieu||ep.ville||"")}</div>
      <div class="badge" style="display:inline-block;margin-top:6px;${badgeStyle}">${safeText(ep.disciplineBase||"")}</div>
    </div>`;
  }).join("");
}

// ---------- Marquee (dates clés J-30) ----------
function renderMarquee(){
  const wrap = document.getElementById("marquee-wrap");
  const track = document.getElementById("marquee-track");
  if(!wrap || !track) return;

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

  track.innerHTML = txt.concat(txt).join('<span aria-hidden="true"> • </span>');
}

// ---------- Dates clés timeline ----------
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
  const pill = document.getElementById("today-pill");
  if(pill){
    pill.textContent = "Aujourd’hui : " + today.toLocaleDateString("fr-FR", { weekday:"short", day:"2-digit", month:"short", year:"numeric" });
  }

  const items = [...datesCles].sort((a,b)=>a.start-b.start);
  const byMonth = new Map();
  for(const it of items){
    const key = it.start.getFullYear()+"-"+String(it.start.getMonth()+1).padStart(2,"0");
    if(!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key).push(it);
  }

  const months = Array.from(byMonth.keys()).sort();
  const tl = document.getElementById("timeline");
  if(!tl) return;

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

      const mandat = it.mandat ? `<a class="mandat-ico" href="${safeText(it.mandat)}" target="_blank" rel="noopener" title="Ouvrir le mandat">📄</a>` : "";

      out += `<div class="vt-item">
        <div class="vt-dot"></div>
        <div class="vt-card ${cls}">
          <div class="vt-title">${safeText(it.title)} ${mandat}</div>
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

// ---------- Nearby / Map ----------
function initNearby(){
  const mapEl = document.getElementById("nearby-map");
  const btn = document.getElementById("btn-locate");
  const slider = document.getElementById("radius");
  const val = document.getElementById("radius-val");
  const status = document.getElementById("nearby-status");
  if(!mapEl || !btn || !slider || !status) return;

  if(!window.L || !L.map){
    status.textContent = "Carte indisponible (Leaflet non chargé).";
    return;
  }
  if(!concoursGeo.length){
    status.textContent = "Carte indisponible : pas de concours avec coordonnées GPS.";
    mapEl.style.display = "none";
    return;
  }

  nearby.radius = parseInt(slider.value,10) || 50;
  val.textContent = nearby.radius + " km";

  nearby.map = L.map(mapEl, { zoomControl:true });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap"
  }).addTo(nearby.map);

  nearby.layer = L.layerGroup().addTo(nearby.map);

  // Centre par défaut : moyenne des concours
  const avg = concoursGeo.reduce((a,c)=>({lat:a.lat+c.lat, lon:a.lon+c.lon}), {lat:0,lon:0});
  const center = [avg.lat/concoursGeo.length, avg.lon/concoursGeo.length];
  nearby.map.setView(center, 8);

  btn.addEventListener("click", ()=>{
    if(!navigator.geolocation){
      status.textContent = "Géolocalisation non supportée par ce navigateur.";
      return;
    }
    status.textContent = "Localisation en cours…";
    navigator.geolocation.getCurrentPosition((pos)=>{
      nearby.user = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      status.textContent = "Localisé. Ajuste le rayon pour filtrer.";
      updateNearby();
    }, ()=>{
      status.textContent = "Impossible d'obtenir la localisation (autorisation refusée ?).";
    }, { enableHighAccuracy:true, timeout:10000, maximumAge:60000 });
  });

  slider.addEventListener("input", ()=>{
    nearby.radius = parseInt(slider.value,10) || 50;
    val.textContent = nearby.radius + " km";
    updateNearby();
  });

  updateNearby();
}

function haversineKm(aLat, aLon, bLat, bLon){
  const R = 6371;
  const toRad = (x)=> x*Math.PI/180;
  const dLat = toRad(bLat-aLat);
  const dLon = toRad(bLon-aLon);
  const s1 = Math.sin(dLat/2), s2 = Math.sin(dLon/2);
  const aa = s1*s1 + Math.cos(toRad(aLat))*Math.cos(toRad(bLat))*s2*s2;
  return 2*R*Math.asin(Math.min(1, Math.sqrt(aa)));
}

function makeMarker(lat, lon, key){
  const pal = PALETTE[key] || null;
  if(pal && pal.bi){
    // bicolore via divIcon
    const html = `<div style="
      width:16px;height:16px;border-radius:50%;
      border:2px solid rgba(15,23,42,.65);
      background: linear-gradient(90deg, ${pal.bi[0]} 0 50%, ${pal.bi[1]} 50% 100%);
      box-shadow: 0 6px 16px rgba(2,6,23,.18);
    "></div>`;
    const icon = L.divIcon({ className:"", html, iconSize:[16,16], iconAnchor:[8,8] });
    return L.marker([lat, lon], { icon });
  }
  // couleur simple via circleMarker (très fiable)
  const fill = pal ? pal.fill : "#111827";
  const stroke = pal ? pal.stroke : "#0b1220";
  return L.circleMarker([lat, lon], {
    radius: 7,
    color: stroke,
    weight: 2,
    fillColor: fill,
    fillOpacity: 0.95
  });
}

function updateNearby(){
  const status = document.getElementById("nearby-status");
  const itemsEl = document.getElementById("nearby-items");
  if(!status || !itemsEl) return;
  if(!nearby.map || !nearby.layer) return;

  nearby.layer.clearLayers();
  nearby.markersById.clear();
  itemsEl.innerHTML = "";

  // Appliquer filtres (dept/discipline/recherche) à la carte
  const visible = (allowedUids && allowedUids.size)
    ? concoursGeo.filter(c=>allowedUids.has(c.id))
    : concoursGeo.slice();

  // 1) Afficher tous les concours visibles sur la carte
  const boundsAll = L.latLngBounds([]);
  for(const c of visible){
    const key = disciplineKey(c.disciplineBase);
    const m = makeMarker(c.lat, c.lon, key).addTo(nearby.layer);
    nearby.markersById.set(c.id, m);

    const dates = (c.start?fmtDateFR(c.start):"") + (c.end && isoDate(c.end)!==isoDate(c.start)?(" → "+fmtDateFR(c.end)):"");
    const mandat = c.mandat ? `<br/><a href="${safeText(c.mandat)}" target="_blank" rel="noopener">📄 Mandat</a>` : "";

    m.bindPopup(
      `<b>${safeText(c.title)}</b><br/>${safeText(c.city||c.lieu||"")}` +
      (dates?("<br/>"+safeText(dates)):"") +
      `<br/>${safeText(c.disciplineLabel||c.disciplineBase||"")}` +
      mandat
    );

    boundsAll.extend([c.lat, c.lon]);
  }

  try{
    if(boundsAll.isValid()) nearby.map.fitBounds(boundsAll.pad(0.15));
  }catch(e){}

  // 2) Si pas localisé => juste info
  if(!nearby.user){
    status.textContent = "Concours filtrés affichés sur la carte. Clique sur “Me localiser” pour voir ceux dans ton rayon.";
    return;
  }

  // 3) Localisé => liste dans rayon (et toujours respect des filtres)
  const {lat, lon} = nearby.user;

  const me = L.circleMarker([lat, lon], { radius: 8, weight:2, fillOpacity:0.9 }).addTo(nearby.layer);
  me.bindPopup("Vous êtes ici");
  L.circle([lat, lon], { radius: nearby.radius*1000, weight:1, fillOpacity:0.06 }).addTo(nearby.layer);

  const within = visible.map(c=>{
    const km = haversineKm(lat, lon, c.lat, c.lon);
    return {...c, km};
  }).filter(c=>c.km <= nearby.radius).sort((a,b)=>a.km-b.km);

  if(!within.length){
    status.textContent = "Aucun concours dans un rayon de " + nearby.radius + " km (avec les filtres actuels).";
    return;
  }

  status.textContent = within.length + " concours dans " + nearby.radius + " km.";

  for(const c of within){
    const dates = (c.start?fmtDateFR(c.start):"") + (c.end && isoDate(c.end)!==isoDate(c.start)?(" → "+fmtDateFR(c.end)):"");
    const card = document.createElement("div");
    card.className = "nearby-card";

    const left = document.createElement("div");
    const meta = `${safeText(c.disciplineBase)}${(c.disciplineBase && c.city)?' • ':''}${safeText(c.city)}${dates?(' • '+safeText(dates)):""}`;
    left.innerHTML = `<div class="nearby-title">${safeText(c.title)}</div><div class="nearby-meta">${meta}</div>`;

    const right = document.createElement("div");
    right.className = "nearby-actions";

    const kmEl = document.createElement("div");
    kmEl.className = "nearby-km";
    kmEl.textContent = Math.round(c.km) + " km";
    right.appendChild(kmEl);

    if(c.mandat){
      const a = document.createElement("a");
      a.className = "nearby-mandat";
      a.href = c.mandat;
      a.target = "_blank";
      a.rel = "noopener";
      a.title = "Ouvrir le mandat";
      a.textContent = "📄";
      right.appendChild(a);
    }

    const g = document.createElement("a");
    g.className = "nearby-route";
    g.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(c.lat+","+c.lon)}`;
    g.target = "_blank";
    g.rel = "noopener";
    g.title = "Itinéraire";
    g.textContent = "🧭";
    right.appendChild(g);

    card.appendChild(left);
    card.appendChild(right);

    card.addEventListener("click", ()=>{
      nearby.map.setView([c.lat, c.lon], Math.max(nearby.map.getZoom(), 11));
      const mk = nearby.markersById.get(c.id);
      if(mk) mk.openPopup();
    });

    itemsEl.appendChild(card);
  }
}

// ---------- Modal ----------
function openEventModal(ev){
  const modal = document.getElementById("event-modal");
  if(!modal) return;

  const ep = ev.extendedProps || {};
  const titleEl = document.getElementById("modal-title");
  const metaEl = document.getElementById("modal-meta");
  const descEl = document.getElementById("modal-desc");
  const badgesEl = document.getElementById("modal-badges");
  const actionsEl = document.getElementById("modal-actions");

  const title = ev.title || "";
  const disc = ep.disciplineLabel || ep.disciplineBase || "";
  const lieu = ep.lieu || ep.ville || "";
  const org = ep.organisateur || "";
  const agre = ep.agrement || "";
  const dept = ep.dept || "";
  const mandat = (ep.mandat||"").trim();

  const start = ev.start ? fmtDateFR(ev.start) : "";
  const end = ev.end ? fmtDateFR(new Date(ev.end.getFullYear(), ev.end.getMonth(), ev.end.getDate()-1)) : "";
  const dates = start ? (end && end!==start ? `${start} → ${end}` : start) : "";

  titleEl.textContent = title;
  metaEl.innerHTML = `${safeText(disc)}${(disc&&lieu)?' • ':''}${safeText(lieu)}${dates?(' • '+safeText(dates)):""}`;
  descEl.textContent = org || agre ? `${org?("Organisateur : "+org+"\n"):""}${agre?("Agrément : "+agre):""}` : "";

  const key = disciplineKey(ep.disciplineBase);
  const badges = [];
  if(key) badges.push(`<span class="b">${safeText(key.toUpperCase())}</span>`);
  if(dept) badges.push(`<span class="b">Dpt ${safeText(dept)}</span>`);
  badgesEl.innerHTML = badges.join("");

  const acts = [];
  if(mandat) acts.push(`<a href="${safeText(mandat)}" target="_blank" rel="noopener">📄 Mandat</a>`);
  actionsEl.innerHTML = acts.join("");

  modal.setAttribute("aria-hidden","false");
  document.body.style.overflow="hidden";
}

function closeEventModal(){
  const modal = document.getElementById("event-modal");
  if(!modal) return;
  modal.setAttribute("aria-hidden","true");
  document.body.style.overflow="";
}

function initModal(){
  const modal = document.getElementById("event-modal");
  if(!modal) return;
  modal.addEventListener("click",(e)=>{
    const t = e.target;
    if(t && t.getAttribute && t.getAttribute("data-close")==="1") closeEventModal();
  });
  document.addEventListener("keydown",(e)=>{
    if(e.key==="Escape" && modal.getAttribute("aria-hidden")==="false") closeEventModal();
  });
}
