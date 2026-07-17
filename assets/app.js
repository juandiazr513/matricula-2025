/* Competencia por carrera — Matrícula SIES 2025
   github.com/juandiazr513/matricula-2025
   Toda la base vive en memoria; cualquier agregación se recalcula en cliente. */

const NUM = new Set(['mat_total','mat_muj','mat_hom','mat_nb','mat1_total','mat1_muj','mat1_hom',
  'mat1_nb','cod_inst','duracion','e15_19','e20_24','e25_29','e30_34','e35_39','e40_mas',
  'edad_prom','e_sin_info','tes_mun','tes_psub','tes_ppag','tes_cad','tes_slep','tes_total','tes_cob']);

let ROWS = [];

const state = {
  foco:'UNIVERSIDAD ANDRES BELLO',
  ambito:'region',
  universo:'Universidades',
  nivel:'Pregrado',
  metrica:'mat1_total',
  mJornada:true,
  mModalidad:false,
  orden:'foco',
  q:'',
  sel:null
};

/* ── parser CSV (RFC-4180: comillas y saltos embebidos) ─────────── */
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

/* ── formato ────────────────────────────────────────────────────── */
const fmt = n => n==null ? '—' : n.toLocaleString('es-CL');
const pct = n => n==null ? '—' : n.toFixed(1).replace('.',',')+'%';
const dec = n => n==null ? '—' : n.toFixed(1).replace('.',',');
const geoOf = r => state.ambito==='pais' ? 'PAÍS' : r[state.ambito];

/* ── construcción de mercados ───────────────────────────────────── */
function build(){
  const m = state.metrica;
  const base = ROWS.filter(r =>
    (state.universo==='__all' || r.tipo_inst===state.universo) &&
    (state.nivel==='__all'    || r.nivel_global===state.nivel) &&
    r[m] > 0
  );

  const mkts = new Map();
  for(const r of base){
    const parts=[r.area_generica, geoOf(r)];
    if(state.mJornada) parts.push(r.jornada);
    if(state.mModalidad) parts.push(r.modalidad);
    const k = parts.join('¦');
    let mk = mkts.get(k);
    if(!mk){ mk={key:k, carrera:r.area_generica, geo:geoOf(r), jornada:state.mJornada?r.jornada:null,
                 modalidad:state.mModalidad?r.modalidad:null, total:0, inst:new Map()}; mkts.set(k,mk); }
    mk.total += r[m];
    let it = mk.inst.get(r.institucion);
    if(!it){ it={nombre:r.institucion, val:0, mat:0, muj:0, sexo:0, edadW:0, edadN:0,
                 tesLow:0, tesTot:0, rows:[]}; mk.inst.set(r.institucion,it); }
    it.val += r[m];
    it.mat += r.mat_total;
    if(r.mat_muj!=null){ it.muj += r.mat_muj; it.sexo += r.mat_total; }
    if(r.edad_prom!=null){ it.edadW += r.edad_prom*r.mat_total; it.edadN += r.mat_total; }
    if(r.tes_total>0){ it.tesLow += (r.tes_mun||0)+(r.tes_psub||0)+(r.tes_slep||0); it.tesTot += r.tes_total; }
    it.rows.push(r);
  }

  const out=[];
  for(const mk of mkts.values()){
    const list=[...mk.inst.values()].sort((a,b)=>b.val-a.val);
    const foco = mk.inst.get(state.foco);
    if(!foco) continue;
    list.forEach((it,i)=>{ it.pos=i+1; it.share=it.val/mk.total*100; });
    mk.list=list;
    mk.foco=foco;
    mk.lider=list[0];
    mk.share=foco.val/mk.total*100;
    mk.gap=list[0].val-foco.val;
    mk.nInst=list.length;
    out.push(mk);
  }
  return out;
}

/* ── orden y filtro ─────────────────────────────────────────────── */
function arrange(mkts){
  let a = mkts;
  if(state.q){
    const q=state.q.toLowerCase();
    a = a.filter(m => m.carrera.toLowerCase().includes(q) || m.geo.toLowerCase().includes(q));
  }
  const by={
    foco:(x,y)=>y.foco.val-x.foco.val,
    share:(x,y)=>y.share-x.share,
    mkt:(x,y)=>y.total-x.total,
    gap:(x,y)=>y.gap-x.gap
  }[state.orden];
  return [...a].sort(by);
}

/* ── render: resumen ────────────────────────────────────────────── */
function renderSummary(mkts){
  const focoVal = mkts.reduce((s,m)=>s+m.foco.val,0);
  const mktVal  = mkts.reduce((s,m)=>s+m.total,0);
  const lidera  = mkts.filter(m=>m.foco.pos===1).length;
  const marginal= mkts.filter(m=>m.share<10 && m.nInst>1).length;
  const solo    = mkts.filter(m=>m.nInst===1).length;
  const label   = state.metrica==='mat1_total' ? 'primer año' : 'matrícula total';

  document.getElementById('summary').innerHTML = `
    <div class="stat"><b>${fmt(mkts.length)}</b><span>mercados</span></div>
    <div class="stat stat--foco"><b>${fmt(focoVal)}</b><span>${label} · foco</span></div>
    <div class="stat"><b>${fmt(mktVal)}</b><span>${label} · mercado</span></div>
    <div class="stat stat--foco"><b>${pct(focoVal/mktVal*100)}</b><span>participación</span></div>
    <div class="stat"><b>${fmt(lidera)}</b><span>donde lidera</span></div>
    <div class="stat"><b>${fmt(marginal)}</b><span>bajo 10%</span></div>
    <div class="stat"><b>${fmt(solo)}</b><span>sin competencia</span></div>`;
}

/* ── render: strips ─────────────────────────────────────────────── */
function renderStrips(mkts){
  const host=document.getElementById('strips');
  if(!mkts.length){
    host.innerHTML=`<p class="empty">Ningún mercado calza con estos filtros. La institución en foco no dicta programas de este nivel, o la búsqueda no encuentra la carrera.</p>`;
    return;
  }
  host.innerHTML = mkts.map(m=>{
    const segs = m.list.map(it=>{
      const w=(it.val/m.total*100).toFixed(3);
      const cls = it.nombre===state.foco ? 'seg--foco' : (it.pos===1 ? 'seg--leader' : 'seg--other');
      return `<i class="seg ${cls}" style="flex:0 0 ${w}%" title="${it.nombre}: ${fmt(it.val)} (${pct(it.share)})"></i>`;
    }).join('');
    const geo = [m.geo, m.jornada, m.modalidad].filter(Boolean).join(' · ');
    return `<button class="strip" role="listitem" data-k="${encodeURIComponent(m.key)}"
              aria-current="${state.sel===m.key}">
      <span class="strip-top">
        <span class="strip-name">${m.carrera}<span class="strip-geo">${geo} · ${m.nInst} inst.</span></span>
        <span class="strip-share">${pct(m.share)}<small>${m.foco.pos}º de ${m.nInst}</small></span>
      </span>
      <span class="bar">${segs}</span>
    </button>`;
  }).join('');

  host.querySelectorAll('.strip').forEach(b=>{
    b.onclick=()=>{ state.sel=decodeURIComponent(b.dataset.k); render(); };
  });
}

/* ── render: detalle ────────────────────────────────────────────── */
function renderDetail(mkts){
  const host=document.getElementById('detail');
  const m = mkts.find(x=>x.key===state.sel) || mkts[0];
  if(!m){ host.innerHTML=''; return; }
  state.sel=m.key;

  const max=m.list[0].val;
  const label = state.metrica==='mat1_total' ? '1er año' : 'matrícula';
  const rows = m.list.map(it=>{
    const cls=[it.nombre===state.foco?'is-foco':'', it.pos===1?'is-leader':''].join(' ');
    return `<tr class="${cls}">
      <td class="pos">${it.pos}</td>
      <td>${it.nombre}</td>
      <td class="num">${fmt(it.val)}</td>
      <td class="num">${pct(it.share)}</td>
      <td class="microbar"><i style="width:${(it.val/max*100).toFixed(1)}%"></i></td>
    </tr>`;
  }).join('');

  // perfil: foco vs resto del mercado
  const rest = m.list.filter(it=>it.nombre!==state.foco);
  const agg = list => {
    const a=list.reduce((s,it)=>({muj:s.muj+it.muj, sexo:s.sexo+it.sexo, ew:s.ew+it.edadW,
      en:s.en+it.edadN, tl:s.tl+it.tesLow, tt:s.tt+it.tesTot}),{muj:0,sexo:0,ew:0,en:0,tl:0,tt:0});
    return {
      muj: a.sexo? a.muj/a.sexo*100 : null,
      edad:a.en ? a.ew/a.en : null,
      tes: a.tt ? a.tl/a.tt*100 : null
    };
  };
  const F=agg([m.foco]), R=agg(rest);
  const tesOk = state.nivel==='Pregrado';
  const prow=(t,f,r,fn)=>`<div class="prow"><span>${t}</span><b>${fn(f)}</b><em>${rest.length?fn(r):'—'}</em></div>`;

  const geo=[m.geo, m.jornada, m.modalidad].filter(Boolean).join(' · ');
  host.innerHTML = `
    <h3>${m.carrera}</h3>
    <p class="detail-sub">${geo} · ${m.nInst} institución${m.nInst>1?'es':''} · ${fmt(m.total)} en ${label}</p>
    <table class="rank">
      <thead><tr><th></th><th>Institución</th><th>${label}</th><th>Part.</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="profile">
      <h4>Perfil de la matrícula</h4>
      <div class="phead"><span></span><i>foco</i><i>resto</i></div>
      ${prow('Mujeres', F.muj, R.muj, pct)}
      ${prow('Edad promedio', F.edad, R.edad, dec)}
      ${tesOk ? prow('Origen municipal, PS o SLEP', F.tes, R.tes, pct)
              : '<div class="prow"><span>Origen escolar</span><b>—</b><em>solo pregrado</em></div>'}
    </div>`;
}

/* ── ciclo ──────────────────────────────────────────────────────── */
function render(){
  const all = build();
  const view = arrange(all);
  renderSummary(all);
  renderStrips(view);
  renderDetail(view);
}

function bind(){
  const on=(id,prop,ev='change',get=e=>e.target.value)=>{
    document.getElementById(id).addEventListener(ev,e=>{ state[prop]=get(e); state.sel=null; render(); });
  };
  on('foco','foco'); on('ambito','ambito'); on('universo','universo');
  on('nivel','nivel'); on('metrica','metrica'); on('orden','orden');
  on('mJornada','mJornada','change',e=>e.target.checked);
  on('mModalidad','mModalidad','change',e=>e.target.checked);
  document.getElementById('buscar').addEventListener('input',e=>{ state.q=e.target.value.trim(); render(); });
}

function fillFoco(){
  const sel=document.getElementById('foco');
  const insts=[...new Set(ROWS.map(r=>r.institucion))].sort((a,b)=>a.localeCompare(b,'es'));
  sel.innerHTML = insts.map(i=>`<option${i===state.foco?' selected':''}>${i}</option>`).join('');
}

fetch('data/matricula2025.csv')
  .then(r=>{ if(!r.ok) throw new Error(r.status); return r.text(); })
  .then(t=>{
    ROWS=parseCSV(t);
    fillFoco(); bind(); render();
    document.getElementById('loading').classList.add('done');
  })
  .catch(e=>{
    document.getElementById('loading').innerHTML =
      `<span>No se pudo leer data/matricula2025.csv (${e.message}). Revisa que el archivo esté publicado en el repo.</span>`;
  });
