/* Evolución 2015-2025 — Matrícula SIES
   github.com/juandiazr513/matricula-2025

   La serie viene agregada por etl/prep_serie.py: 102.641 filas, ~1 MB con gzip. Toda la
   agregación se recalcula en cliente, igual que en la vista de competencia. */

const NUM = new Set(['anio','mat_total','mat1_total','carreras']);
const SISTEMA = '__sistema';

let ROWS = [];
let ANIOS = [];

const state = {
  foco:'UNIVERSIDAD ANDRES BELLO',
  corte:'modalidad',
  nivel:'Pregrado',
  universo:'__all',
  modalidad:'__all',
  metrica:'mat_total',
  escala:'abs',
  anio0:2019,
  anio1:2025
};

/* Paleta contenida: la del sitio primero, después neutros diferenciables.
   Nunca más de 10 categorías simultáneas en los cortes disponibles. */
const COLORES = ['#1f3fa8','#a9550b','#3f7d8c','#6b4a9e','#2f7d4f',
                 '#b03a5b','#7a6a3a','#4a4f57','#5c6bc0','#96a0ad'];

/* ── parser CSV ─────────────────────────────────────────────────── */
function parseCSV(text){
  if(text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  const rows=[]; let row=[], f='', q=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(q){
      if(c === '"'){ if(text[i+1] === '"'){ f+='"'; i++; } else q=false; }
      else f+=c;
    } else if(c === '"') q=true;
    else if(c === ','){ row.push(f); f=''; }
    else if(c === '\n'){ row.push(f); rows.push(row); row=[]; f=''; }
    else if(c !== '\r') f+=c;
  }
  if(f !== '' || row.length){ row.push(f); rows.push(row); }
  const head=rows.shift();
  return rows.filter(r=>r.length===head.length).map(r=>{
    const o={};
    for(let j=0;j<head.length;j++){
      const k=head[j], v=r[j];
      o[k] = NUM.has(k) ? (v==='' ? null : +v) : v;
    }
    return o;
  });
}

const fmt = n => n==null ? '—' : Math.round(n).toLocaleString('es-CL');
const pct = n => n==null ? '—' : n.toFixed(1).replace('.',',')+'%';
const sig = n => (n>0?'+':'') + fmt(n);

/* ── filtro base ────────────────────────────────────────────────── */
function base(){
  const m = state.metrica;
  return ROWS.filter(r =>
    (state.nivel==='__all'     || r.nivel_global===state.nivel) &&
    (state.universo==='__all'  || r.tipo_inst===state.universo) &&
    (state.modalidad==='__all' || r.modalidad===state.modalidad) &&
    r[m]!=null && r[m]>0
  );
}

/* ── serie por corte ────────────────────────────────────────────── */
function serie(){
  const m = state.metrica;
  let d = base();
  if(state.foco!==SISTEMA) d = d.filter(r=>r.institucion===state.foco);

  const cats = new Map();     // categoría -> Map(anio -> valor)
  for(const r of d){
    const k = r[state.corte];
    if(!cats.has(k)) cats.set(k, new Map());
    const s = cats.get(k);
    s.set(r.anio, (s.get(r.anio)||0) + r[m]);
  }
  let out = [...cats.entries()].map(([nombre, s]) => ({
    nombre,
    valores: ANIOS.map(a => s.get(a) || 0),
  }));
  out.sort((a,b)=> b.valores[b.valores.length-1] - a.valores[a.valores.length-1]);
  if(out.length > 10){                         // agrupa la cola para no ensuciar el gráfico
    const resto = out.slice(9);
    out = out.slice(0,9);
    out.push({nombre:`Otras (${resto.length})`,
              valores: ANIOS.map((_,i)=>resto.reduce((s,r)=>s+r.valores[i],0))});
  }
  return out;
}

function transformar(ss){
  if(state.escala==='idx'){
    return ss.map(s=>({...s, valores: s.valores.map(v => s.valores[0] ? v/s.valores[0]*100 : null)}));
  }
  if(state.escala==='pct'){
    const tot = ANIOS.map((_,i)=>ss.reduce((a,s)=>a+s.valores[i],0));
    return ss.map(s=>({...s, valores: s.valores.map((v,i)=> tot[i] ? v/tot[i]*100 : null)}));
  }
  return ss;
}

/* ── gráfico de líneas en SVG ───────────────────────────────────── */
function chart(ss){
  const W=980, H=420, ml=64, mr=182, mt=16, mb=34;
  const iw=W-ml-mr, ih=H-mt-mb;
  const todos = ss.flatMap(s=>s.valores).filter(v=>v!=null);
  if(!todos.length) return '<p class="empty">Sin datos con estos filtros.</p>';

  const vmax = Math.max(...todos), vmin = state.escala==='abs' ? 0 : Math.min(...todos, 0);
  const pad = (vmax-vmin)*0.06 || 1;
  const y0 = state.escala==='abs' ? 0 : vmin-pad, y1 = vmax+pad;
  const X = i => ml + (iw * i / (ANIOS.length-1));
  const Y = v => mt + ih - (ih * (v-y0)/(y1-y0));

  const ticks=[]; const paso = (y1-y0)/5;
  for(let i=0;i<=5;i++) ticks.push(y0 + paso*i);
  const et = v => state.escala==='abs'
      ? (v>=1000 ? Math.round(v/1000)+'k' : Math.round(v))
      : (state.escala==='pct' ? v.toFixed(0)+'%' : v.toFixed(0));

  const grid = ticks.map(t=>`
    <line x1="${ml}" y1="${Y(t).toFixed(1)}" x2="${ml+iw}" y2="${Y(t).toFixed(1)}"
          stroke="var(--line-soft)" stroke-width="1"/>
    <text x="${ml-9}" y="${(Y(t)+3.5).toFixed(1)}" text-anchor="end" class="ax">${et(t)}</text>`).join('');

  const ejeX = ANIOS.map((a,i)=> (i%2===0 || i===ANIOS.length-1)
    ? `<text x="${X(i).toFixed(1)}" y="${H-12}" text-anchor="middle" class="ax">${a}</text>` : '').join('');

  // marca visual de la pandemia: no explica nada, solo ubica al lector
  const iPan = ANIOS.indexOf(2020);
  const pandemia = iPan >= 0 ? `
    <line x1="${X(iPan).toFixed(1)}" y1="${mt}" x2="${X(iPan).toFixed(1)}" y2="${mt+ih}"
          stroke="var(--muted)" stroke-width="1" stroke-dasharray="3 3" opacity=".55"/>
    <text x="${(X(iPan)+4).toFixed(1)}" y="${mt+11}" class="ax">2020</text>` : '';

  const lineas = ss.map((s,k)=>{
    const c = COLORES[k % COLORES.length];
    const d = s.valores.map((v,i)=> v==null ? null : `${i===0?'M':'L'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`)
                       .filter(Boolean).join(' ');
    const pts = s.valores.map((v,i)=> v==null ? '' :
      `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="2.4" fill="${c}"><title>${s.nombre} · ${ANIOS[i]}: ${state.escala==='abs'?fmt(v):pct(v)}</title></circle>`).join('');
    return `<path d="${d}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/>${pts}`;
  }).join('');

  const leyenda = ss.map((s,k)=>{
    const c = COLORES[k % COLORES.length];
    const ult = s.valores[s.valores.length-1];
    return `<g transform="translate(${ml+iw+14},${mt+8+k*20})">
      <rect width="9" height="9" y="-7" fill="${c}"/>
      <text x="15" y="0" class="lg">${s.nombre.length>20 ? s.nombre.slice(0,19)+'…' : s.nombre}</text>
      <text x="15" y="11" class="lg lg--v">${state.escala==='abs'?fmt(ult):pct(ult)}</text>
    </g>`;
  }).join('');

  return `<svg viewBox="0 0 ${W} ${H}" class="svg" role="img"
    aria-label="Serie anual desglosada por ${state.corte}">${grid}${pandemia}${ejeX}${lineas}${leyenda}</svg>`;
}

/* ── tabla ──────────────────────────────────────────────────────── */
function tabla(ss){
  const head = ANIOS.map(a=>`<th>${a}</th>`).join('');
  const filas = ss.map((s,k)=>{
    const v0=s.valores[0], v1=s.valores[s.valores.length-1];
    const g = v0 ? (v1/v0-1)*100 : null;
    const celdas = s.valores.map(v=>`<td class="num">${state.escala==='abs'?fmt(v):pct(v)}</td>`).join('');
    return `<tr>
      <td><span class="dot" style="background:${COLORES[k%COLORES.length]}"></span>${s.nombre}</td>
      ${celdas}
      <td class="num ${g>0?'up':(g<0?'down':'')}">${g==null?'—':(g>0?'+':'')+g.toFixed(0)+'%'}</td>
    </tr>`;
  }).join('');
  return `<table class="serie">
    <thead><tr><th>${state.corte.replace('_',' ')}</th>${head}<th>${ANIOS[0]}→${ANIOS[ANIOS.length-1]}</th></tr></thead>
    <tbody>${filas}</tbody></table>`;
}

/* ── resumen ────────────────────────────────────────────────────── */
function renderSummary(ss){
  const tot = ANIOS.map((_,i)=>ss.reduce((a,s)=>a+s.valores[i],0));
  const v0=tot[0], v1=tot[tot.length-1];
  const g = v0 ? (v1/v0-1)*100 : null;
  const pre = ANIOS.indexOf(2019), pan = ANIOS.indexOf(2020);
  const gPan = (pre>=0 && pan>=0 && tot[pre]) ? (tot[pan]/tot[pre]-1)*100 : null;
  const label = state.metrica==='mat1_total' ? 'primer año' : 'matrícula';
  const quien = state.foco===SISTEMA ? 'sistema' : 'foco';

  document.getElementById('summary').innerHTML = `
    <div class="stat"><b>${fmt(v0)}</b><span>${label} ${ANIOS[0]} · ${quien}</span></div>
    <div class="stat stat--foco"><b>${fmt(v1)}</b><span>${label} ${ANIOS[ANIOS.length-1]} · ${quien}</span></div>
    <div class="stat ${g>0?'stat--up':'stat--down'}"><b>${g==null?'—':(g>0?'+':'')+g.toFixed(0)+'%'}</b><span>${ANIOS[0]}–${ANIOS[ANIOS.length-1]}</span></div>
    <div class="stat"><b>${gPan==null?'—':(gPan>0?'+':'')+gPan.toFixed(1)+'%'}</b><span>2019 → 2020</span></div>
    <div class="stat"><b>${ss.length}</b><span>categorías</span></div>`;

  document.getElementById('aviso-mat1').innerHTML = state.metrica==='mat1_total'
    ? '<span class="warn-inline">Los Planes de Continuidad no reportan primer año: desaparecen de esta vista.</span>' : '';
}

/* ── shift-share ────────────────────────────────────────────────── */
/* El cálculo va separado del render para poder verificarlo contra pandas. */
function calcShift(){
  const m = state.metrica;
  const d = ROWS.filter(r =>
    (state.nivel==='__all'    || r.nivel_global===state.nivel) &&
    (state.universo==='__all' || r.tipo_inst===state.universo) &&
    (state.modalidad==='__all'|| r.modalidad===state.modalidad) &&
    (r.anio===state.anio0 || r.anio===state.anio1) &&
    r[m]!=null && r[m]>0);

  const M={}, V={};
  for(const r of d){
    const k = `${r.area_generica}¦${r.region}¦${r.jornada}`;
    const t = r.anio===state.anio0 ? 0 : 1;
    (M[k] = M[k] || [0,0])[t] += r[m];
    if(r.institucion===state.foco) (V[k] = V[k] || [0,0])[t] += r[m];
  }

  let efM=0, efS=0, inter=0, ent=0, sal=0, nCom=0, nNue=0, nAba=0;
  for(const k in V){
    const [v0,v1] = V[k], [m0,m1] = M[k];
    if(v0>0 && v1>0){
      nCom++;
      const s0=v0/m0, s1=v1/m1;
      efM   += s0*(m1-m0);
      efS   += m0*(s1-s0);
      inter += (m1-m0)*(s1-s0);
    } else if(v1>0){ nNue++; ent += v1; }
    else if(v0>0){ nAba++; sal += v0; }
  }

  const v0t = Object.values(V).reduce((a,x)=>a+x[0],0);
  const v1t = Object.values(V).reduce((a,x)=>a+x[1],0);
  const delta = v1t - v0t;

  return {efM, efS, inter, ent, sal:-sal, nCom, nNue, nAba, v0t, v1t, delta};
}

function shiftShare(){
  if(state.foco===SISTEMA)
    return `<p class="empty">La descomposición compara una institución contra su mercado, así que
            necesita una institución concreta. Elige una en el control "Ver".</p>`;

  const {efM, efS, inter, ent, sal, nCom, nNue, nAba, v0t, v1t, delta} = calcShift();

  const partes = [
    ['Efecto mercado', efM, 'El mercado creció o se contrajo, y la institución fue con él sin cambiar su participación.'],
    ['Efecto participación', efS, 'Ganó o perdió participación dentro de los mercados donde ya estaba.'],
    ['Interacción', inter, 'Término cruzado. Se reporta aparte en vez de repartirlo, porque repartirlo es otra convención.'],
    ['Entradas a mercados nuevos', ent, `Abrió programas en ${nNue} mercados donde no estaba en ${state.anio0}.`],
    ['Salidas de mercados', sal, `Dejó de ofrecer en ${nAba} mercados donde estaba en ${state.anio0}.`],
  ];
  const esc = Math.max(...partes.map(p=>Math.abs(p[1])), Math.abs(delta)) || 1;

  const barras = partes.map(([n,v,exp])=>`
    <div class="sf">
      <div class="sf-n">${n}</div>
      <div class="sf-bar"><i class="${v>=0?'pos':'neg'}" style="width:${Math.abs(v)/esc*100}%"></i></div>
      <div class="sf-v ${v>=0?'up':'down'}">${sig(v)}</div>
      <p class="sf-x">${exp}</p>
    </div>`).join('');

  return `
    <div class="sf-top">
      <div class="stat"><b>${fmt(v0t)}</b><span>${state.anio0}</span></div>
      <div class="stat stat--foco"><b>${fmt(v1t)}</b><span>${state.anio1}</span></div>
      <div class="stat ${delta>=0?'stat--up':'stat--down'}"><b>${sig(delta)}</b><span>cambio total</span></div>
      <div class="stat"><b>${nCom}</b><span>mercados comunes</span></div>
      <div class="stat"><b>${nNue}</b><span>mercados nuevos</span></div>
      <div class="stat"><b>${nAba}</b><span>abandonados</span></div>
    </div>
    ${barras}
    <p class="sf-nota"><b>Cómo leerlo.</b> Las cinco partes suman el cambio total. Un "efecto
    participación" positivo puede ser una ganancia real o un competidor que cerró: el sistema pasó
    de 156 instituciones en 2015 a 122 en 2025 y esta descomposición no distingue las dos cosas.</p>`;
}

/* ── ciclo ──────────────────────────────────────────────────────── */
function render(){
  const ss = transformar(serie());
  renderSummary(serie());
  document.getElementById('titulo-serie').textContent =
    `Serie anual por ${state.corte.replace('_',' ')}`;
  document.getElementById('chart').innerHTML = chart(ss);
  document.getElementById('tabla').innerHTML = tabla(ss);
  document.getElementById('shift').innerHTML = shiftShare();
}

function bind(){
  const on=(id,prop,get=e=>e.target.value)=>
    document.getElementById(id).addEventListener('change',e=>{ state[prop]=get(e); render(); });
  ['foco','corte','nivel','universo','modalidad','metrica','escala'].forEach(k=>on(k,k));
  on('anio0','anio0',e=>+e.target.value);
  on('anio1','anio1',e=>+e.target.value);
}

fetch('data/serie_2015_2025.csv')
  .then(r=>{ if(!r.ok) throw new Error(r.status); return r.text(); })
  .then(t=>{
    ROWS = parseCSV(t);
    ANIOS = [...new Set(ROWS.map(r=>r.anio))].sort((a,b)=>a-b);

    const sel = document.getElementById('foco');
    const insts = [...new Set(ROWS.filter(r=>r.anio===ANIOS[ANIOS.length-1]).map(r=>r.institucion))]
                    .sort((a,b)=>a.localeCompare(b,'es'));
    sel.innerHTML = `<option value="${SISTEMA}">Sistema completo</option>` +
      insts.map(i=>`<option${i===state.foco?' selected':''}>${i}</option>`).join('');

    for(const id of ['anio0','anio1']){
      document.getElementById(id).innerHTML =
        ANIOS.map(a=>`<option${a===state[id]?' selected':''}>${a}</option>`).join('');
    }
    bind(); render();
    document.getElementById('loading').classList.add('done');
  })
  .catch(e=>{
    document.getElementById('loading').innerHTML =
      `<span>No se pudo leer data/serie_2015_2025.csv (${e.message}). Corre etl/prep_serie.py y publica el archivo.</span>`;
  });
