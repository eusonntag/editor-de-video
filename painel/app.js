/* Painel do Editor de Vídeo: sem framework e sem build.
   Lê tudo de /api/video/<id> e grava os pedidos em /api/video/<id>/ajustes (lidos pelo /video-ajustar). */
"use strict";

const S = {
  videos: [], dados: null, id: null, aba: "visao",
  visao: "editado", formato: null, pps: 0, pendentes: [], atualizado: null, motionFormato: null,
};
const ABAS = [["visao", "Visão geral"], ["cortes", "Cortes"], ["motion", "Motion"], ["legendas", "Legendas"], ["exportar", "Exportar"]];
const NOME_ETAPA = { transcricao: "Transcrição", corte: "Corte", layout: "Formato e zoom", motion: "Motion", legenda: "Legenda", final: "Finalização" };
const NOME_FORMATO = { horizontal: "Horizontal", vertical: "Vertical", react: "React" };
const NOME_ESTILO_EDICAO = { natural: "natural", dinamica: "dinâmica", acelerada: "acelerada" };
const TIPO_CARD = { apresentacao: "Apresentação", titulo: "Título", lista: "Lista", numero: "Número", destaque: "Destaque", passos: "Passos", palavra: "Palavra", "chamada-final": "Chamada final", personalizado: "Personalizado" };
const ESTILOS_LEGENDA = [["dinamica", "Dinâmica", "poucas palavras, a falada em destaque"], ["classica", "Clássica", "frase inteira, discreta"], ["caixa", "Caixa", "palavras numa tarja"], ["palavra", "Palavra", "uma por vez, grande"]];

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function fmt(t, dec = false) {
  if (t == null || isNaN(t)) return "–";
  t = Math.max(0, t);
  const m = Math.floor(t / 60), s = t - m * 60;
  return dec ? `${m}:${s.toFixed(1).padStart(4, "0")}` : `${m}:${String(Math.floor(s)).padStart(2, "0")}`;
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).erro || r.statusText);
  return r.json();
}
function aviso(txt, ms = 6000) {
  const a = $("#aviso");
  a.innerHTML = txt; a.hidden = false;
  clearTimeout(aviso.t); aviso.t = setTimeout(() => (a.hidden = true), ms);
}

/* ---------------- pendentes (guardados no navegador até aplicar) ---------------- */
function chavePend() { return "painel-ajustes-" + S.id; }
function carregarPend() {
  try { S.pendentes = JSON.parse(localStorage.getItem(chavePend()) || "[]"); } catch { S.pendentes = []; }
}
function salvarPend() {
  try { localStorage.setItem(chavePend(), JSON.stringify(S.pendentes)); } catch { /* sem armazenamento: fica só na memória */ }
  desenharPendentes();
}
function pend(item, chave) {
  const i = S.pendentes.findIndex((p) => p._chave === chave);
  if (i >= 0) S.pendentes.splice(i, 1);
  if (item) S.pendentes.push({ ...item, _chave: chave });
  salvarPend();
}
function temPend(chave) { return S.pendentes.find((p) => p._chave === chave); }
function descreverPend(p) {
  switch (p.tipo) {
    case "manter_trecho": return `Manter "${p.texto}"`;
    case "cortar_trecho": return `Cortar "${p.texto}"`;
    case "zoom": return `Zoom ${fmt(p.inicio)} ${p.ativo ? "ligado" : "desligado"}`;
    case "card_texto": return `${p.card}: ${p.campo} → "${p.valor}"`;
    case "card_ativo": return `${p.card} ${p.ativo ? "ligado" : "desligado"}`;
    case "card_icone": return `${p.card}: ícone ${p.icone}`;
    case "estilo_motion": return `Estilo dos cards: ${p.estilo}`;
    case "estilo_legenda": return `Estilo da legenda: ${p.estilo}`;
    case "corrigir_palavra": return `Corrigir "${p.errado}" → "${p.certo}"`;
    default: return p.tipo;
  }
}
function desenharPendentes() {
  const barra = $("#pendentes");
  if (!S.id || !S.pendentes.length) { barra.hidden = true; return; }
  barra.hidden = false;
  const itens = S.pendentes.map(descreverPend);
  $("#pendentes-lista").innerHTML = `<b>${itens.length} alteraç${itens.length > 1 ? "ões" : "ão"} pendente${itens.length > 1 ? "s" : ""}</b> · ` +
    esc(itens.slice(0, 4).join(" · ")) + (itens.length > 4 ? ` · e mais ${itens.length - 4}` : "");
}
function textoPedido() {
  return `No vídeo "${S.id}", aplicar:\n` + S.pendentes.map((p) => "- " + descreverPend(p)).join("\n");
}
$("#bt-descartar").onclick = () => { S.pendentes = []; salvarPend(); desenhar(); };
$("#bt-copiar").onclick = async () => {
  const t = textoPedido();
  try { await navigator.clipboard.writeText("/video-ajustar\n" + t); aviso("Pedido copiado. Cole no Claude."); }
  catch { window.prompt("Copie o pedido e cole no Claude:", t); }
};
$("#bt-aplicar").onclick = async () => {
  const itens = S.pendentes.map(({ _chave, ...r }) => r);
  try {
    await api(`/api/video/${encodeURIComponent(S.id)}/ajustes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ itens, texto: textoPedido() }) });
    S.pendentes = []; salvarPend();
    aviso("<b>Alterações enviadas.</b><br>Volte ao Claude e digite <b>/video-ajustar</b>.", 12000);
  } catch (e) { aviso("Não consegui salvar: " + esc(e.message) + ". Use “Copiar pedido”."); }
};

/* ---------------- rotas ---------------- */
function lerRota() {
  const p = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (p[0] === "video" && p[1]) return { id: p[1], aba: p[2] || "visao" };
  return { id: null, aba: "inicio" };
}
async function irPara() {
  const r = lerRota();
  const mudouVideo = r.id !== S.id;
  S.id = r.id; S.aba = r.aba;
  if (S.id && (mudouVideo || !S.dados)) {
    carregarPend();
    await carregarVideo();
  }
  if (!S.id) S.dados = null;
  desenhar();
}
window.addEventListener("hashchange", irPara);

async function carregarVideos() { try { S.videos = await api("/api/videos"); } catch { S.videos = []; } }
async function carregarVideo() {
  try {
    S.dados = await api(`/api/video/${encodeURIComponent(S.id)}`);
    S.atualizado = S.dados.estado.atualizado;
    const fs = Object.keys(S.dados.formatos);
    if (!S.formato || !fs.includes(S.formato)) S.formato = fs[0] || null;
    if (!S.motionFormato || !fs.includes(S.motionFormato)) S.motionFormato = fs.find((f) => S.dados.formatos[f].montagem) || fs[0] || null;
  } catch (e) { S.dados = null; aviso("Não consegui abrir o vídeo: " + esc(e.message)); }
}

/* ---------------- moldura ---------------- */
function desenhar() {
  desenharNav();
  const pg = $("#pagina");
  const cr = $("#crumbs");
  if (!S.id) {
    cr.innerHTML = `<span class="now">Seus vídeos</span>`;
    pg.innerHTML = paginaInicio();
  } else if (!S.dados) {
    cr.innerHTML = `Vídeos<span class="sep">/</span><span class="now">${esc(S.id)}</span>`;
    pg.innerHTML = `<div class="placeholder-box"><div class="ph-title">Vídeo não encontrado</div></div>`;
  } else {
    const aba = ABAS.find((a) => a[0] === S.aba) || ABAS[0];
    cr.innerHTML = `<a href="#/">Vídeos</a><span class="sep">/</span>${esc(S.id)}<span class="sep">/</span><span class="now">${aba[1]}</span>`;
    const f = { visao: paginaVisao, cortes: paginaCortes, motion: paginaMotion, legendas: paginaLegendas, exportar: paginaExportar }[aba[0]];
    pg.innerHTML = f();
    const pos = { cortes: montarCortes, motion: montarMotion, legendas: montarLegendas, exportar: montarExportar, visao: () => {} }[aba[0]];
    pos();
  }
  desenharPendentes();
  atualizarStatus(S.dados && S.dados.estado);
}

function desenharNav() {
  const grupos = [["andamento", "Em andamento"], ["novos", "Para editar"], ["prontos", "Prontos"]];
  let h = "";
  if (S.id && S.dados) {
    h += `<div class="nav-group"><div class="nav-group-title">Este vídeo</div>` +
      ABAS.map(([k, n], i) => `<a class="nav-item ${S.aba === k ? "active" : ""}" href="#/video/${encodeURIComponent(S.id)}/${k}"><span class="ix">0${i + 1}</span>${n}</a>`).join("") + `</div>`;
  }
  for (const [g, titulo] of grupos) {
    const vs = S.videos.filter((v) => v.grupo === g);
    if (!vs.length) continue;
    h += `<div class="nav-group"><div class="nav-group-title">${titulo}</div>` +
      vs.map((v) => `<a class="nav-item ${S.id === v.id ? "active" : ""}" href="#/video/${encodeURIComponent(v.id)}" title="${esc(v.id)}"><span class="sdot ${g}"></span><span class="nome">${esc(v.id)}</span></a>`).join("") + `</div>`;
  }
  $("#nav").innerHTML = h || `<div class="nav-group"><div class="nav-group-title">Sem vídeos ainda</div></div>`;
}

function atualizarStatus(estado) {
  const el = $("#status"), txt = $("#status-txt");
  const ea = estado && estado.etapa_atual;
  if (ea) { el.classList.add("trabalhando"); txt.textContent = `⏳ Passo ${ea.passo}/${ea.total}: ${ea.texto}`; }
  else { el.classList.remove("trabalhando"); txt.textContent = estado && estado.atualizado ? "atualizado " + estado.atualizado.slice(11, 16) : "conectado"; }
}

/* ---------------- início ---------------- */
function paginaInicio() {
  const vs = S.videos;
  if (!vs.length) {
    return `<div class="page-head"><div><h1 class="page-title">Seus vídeos</h1></div></div>
      <div class="placeholder-box"><div class="ph-title">Nenhum vídeo ainda</div>
      <div class="ph-sub">Coloque um vídeo na pasta videos/Para Editar e digite /video-editar no Claude</div></div>`;
  }
  const n = (g) => vs.filter((v) => v.grupo === g).length;
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">00</span>Seus vídeos</h1>
      <p class="page-sub">Tudo que passou pelo editor. Clique num vídeo para ver a linha do tempo, os cortes, os cards e a legenda.</p></div></div>
    <div class="grid grid-3" style="margin-bottom:var(--s-8)">
      <div class="card glow"><span class="card-label">Prontos</span><div class="metric">${n("prontos")}</div></div>
      <div class="card"><span class="card-label">Em andamento</span><div class="metric branco">${n("andamento")}</div></div>
      <div class="card"><span class="card-label">Para editar</span><div class="metric branco">${n("novos")}</div></div>
    </div>
    <div class="grid grid-3">${vs.map((v) => `
      <a class="card video-card" href="#/video/${encodeURIComponent(v.id)}">
        ${v.miniatura ? `<img src="${v.miniatura}" alt="">` : `<img alt="" style="visibility:hidden">`}
        <span class="chip ${v.grupo === "prontos" ? "active" : v.grupo === "andamento" ? "ochre" : ""}"><span class="dot"></span>${esc(v.descricao)}</span>
        <div class="card-title" style="margin-top:8px">${esc(v.id)}</div>
        <div class="card-body">${v.duracao ? fmt(v.duracao) : ""} ${v.orientacao ? "· " + v.orientacao : ""}</div>
      </a>`).join("")}</div>`;
}

/* ---------------- visão geral do vídeo ---------------- */
function paginaVisao() {
  const D = S.dados, e = D.estado, et = e.etapas || {};
  const cards = (D.roteiro && D.roteiro.cards || []).filter((c) => c.ativo !== false).length;
  const zooms = (D.dinamica && D.dinamica.eventos || []).filter((z) => z.ativo !== false).length;
  const linhas = [["transcricao", null], ["corte", null]];
  for (const f of Object.keys(D.formatos)) for (const x of ["layout", "motion", "legenda", "final"]) linhas.push([x, f]);
  const passos = linhas.map(([x, f], i) => {
    const feito = f ? (et[x] || {})[f] : et[x];
    return `<div class="step ${feito ? "feito" : ""}"><div class="step-num">${feito ? "✓" : String(i + 1).padStart(2, "0")}</div>
      <div class="step-title">${NOME_ETAPA[x]}${f ? ` <span class="chip">${NOME_FORMATO[f]}</span>` : ""}</div>
      <span class="chip ${feito ? "active" : ""}">${feito ? "feito " + (feito.feito || "").slice(11, 16) : "pendente"}</span></div>`;
  }).join("");
  const rem = D.resumo ? D.resumo.frases_removidas : [];
  const imgs = Object.entries(D.formatos).map(([f, x]) => x.imagens.verificacao || x.imagens.conferencia ? `
      <div><span class="card-label">${NOME_FORMATO[f]}</span><img class="previa" src="${x.imagens.verificacao || x.imagens.conferencia}?v=${Date.now()}"></div>` : "").join("");
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">01</span>${esc(D.id)}</h1>
      <p class="page-sub">${esc(D.status.join(" "))}</p></div>
      <div class="page-meta">${e.nome_final ? `nome final<br><strong>${esc(e.nome_final)}</strong>` : ""}</div></div>
    ${e.etapa_atual ? `<div class="callout">O Claude está trabalhando neste vídeo agora: ${esc(e.etapa_atual.texto)} (passo ${e.etapa_atual.passo} de ${e.etapa_atual.total})</div>` : ""}
    <div class="grid grid-4">
      <div class="card glow"><span class="card-label">Antes → depois</span><div class="metric">${fmt(D.bruto && D.bruto.duracao)} → ${fmt(D.cortado && D.cortado.duracao)}</div>
        <div class="metric-sub">${D.resumo ? Math.max(0, Math.round(D.resumo.silencio_removido)) + " s de pausas removidas" : ""}</div></div>
      <div class="card"><span class="card-label">Trechos</span><div class="metric branco">${D.edl ? D.edl.length : "–"}</div><div class="metric-sub">${rem.length} frases removidas</div></div>
      <div class="card"><span class="card-label">Cards de motion</span><div class="metric branco">${cards}</div></div>
      <div class="card"><span class="card-label">Zooms</span><div class="metric branco">${zooms}</div><div class="metric-sub">${D.dinamica ? "edição " + esc(NOME_ESTILO_EDICAO[D.dinamica.estilo] || D.dinamica.estilo) : "sem edição dinâmica"}</div></div>
    </div>
    <div class="section-h">Etapas</div><div class="steps">${passos}</div>
    ${rem.length ? `<div class="section-h">Frases removidas</div>${rem.map((f) => `<div class="callout" style="border-color:var(--rust)">${fmt(f.inicio)} · “${esc(f.texto)}”</div>`).join("")}` : ""}
    ${imgs ? `<div class="section-h">Como está ficando</div><div class="grid grid-2">${imgs}</div>` : ""}`;
}

/* ---------------- cortes: player + linha do tempo + transcrição ---------------- */
function mapa() {
  const D = S.dados, R = D.edl || [];
  const off = [0, ...(D.cortes_editado || [])];
  return {
    paraEditado(t) {
      for (let i = 0; i < R.length; i++) if (t >= R[i].s && t <= R[i].e) return t - R[i].s + (off[i] || 0);
      return null;
    },
    paraOriginal(te) {
      for (let i = R.length - 1; i >= 0; i--) if (te >= (off[i] || 0)) return te - (off[i] || 0) + R[i].s;
      return te;
    },
  };
}
function frasesOrigem() {
  const D = S.dados, R = D.edl || [], W = D.palavras_origem || [];
  const mantida = (w) => { const m = (w.s + w.e) / 2; return R.some((r) => m >= r.s && m <= r.e); };
  const fr = [];
  for (const w of W) {
    const k = mantida(w);
    const ult = fr[fr.length - 1];
    if (ult && ult.k === k && w.s - ult.e <= 0.6 && !/[.!?]$/.test(ult.w[ult.w.length - 1].t)) { ult.w.push(w); ult.e = w.e; }
    else fr.push({ k, w: [w], s: w.s, e: w.e });
  }
  return fr.map((f, i) => ({ ...f, i, texto: f.w.map((x) => x.t).join(" ") }));
}
function fonteEditado() {
  const D = S.dados;
  const opcoes = [];
  for (const [f, x] of Object.entries(D.formatos)) {
    const a = x.arquivos;
    const url = a.final || a.animado || a.base;
    if (url) opcoes.push([f, url, NOME_FORMATO[f] + (a.final ? "" : a.animado ? " (sem legenda)" : " (sem motion)")]);
  }
  if (D.cortado) opcoes.push(["cortado", D.cortado.url, "Só o corte"]);
  return opcoes;
}
function paginaCortes() {
  const D = S.dados;
  if (!D.edl) return placeholder("Ainda não há cortes", "O painel mostra a linha do tempo depois do corte. Digite /video-editar no Claude.");
  if (S.visao === "editado" && !fonteEditado().length) S.visao = "original";
  const fontes = fonteEditado();
  if (!fontes.find((f) => f[0] === S.formato)) S.formato = fontes[0] && fontes[0][0];
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">02</span>Cortes e linha do tempo</h1>
      <p class="page-sub">Riscado é o que foi cortado. Clique numa frase para manter ou cortar; dê dois cliques numa palavra para corrigir a grafia. Clique na linha do tempo para ir ao ponto do vídeo.</p></div></div>
    <div class="editor-top">
      <div class="player">
        <video id="player" preload="metadata" playsinline controls></video>
        <div class="player-bar">
          <div class="seg" id="seg-visao">
            <button data-v="original" class="${S.visao === "original" ? "on" : ""}">Original</button>
            <button data-v="editado" class="${S.visao === "editado" ? "on" : ""}" ${fontes.length ? "" : "disabled"}>Editado</button>
          </div>
          ${S.visao === "editado" && fontes.length > 1 ? `<div class="seg" id="seg-formato">${fontes.map(([f, , n]) => `<button data-f="${f}" class="${S.formato === f ? "on" : ""}">${n}</button>`).join("")}</div>` : ""}
          <div class="tempo" id="tempo"><b>0:00</b> / 0:00</div>
        </div>
      </div>
      <div><span class="card-label">Transcrição</span><div class="transcricao" id="transcricao"></div></div>
    </div>
    <div class="timeline">
      <div class="tl-head"><span class="chip ${S.visao === "editado" ? "active" : "rust"}"><span class="dot"></span>${S.visao === "editado" ? "vídeo editado" : "vídeo original, com o que foi cortado"}</span>
        <label class="chip">zoom <input type="range" id="tl-zoom" min="0" max="100" value="${S.ppsSlider || 0}"></label></div>
      <div class="tl-body"><div class="tl-labels" id="tl-labels"></div><div class="tl-scroll" id="tl-scroll"><div class="tl-inner" id="tl-inner"></div></div></div>
    </div>`;
}
function montarCortes() {
  const D = S.dados;
  if (!D.edl) return;
  const v = $("#player");
  const fontes = fonteEditado();
  const fonte = S.visao === "original" ? D.bruto && D.bruto.url : (fontes.find((f) => f[0] === S.formato) || [])[1];
  v.src = fonte || "";
  if (!fonte && S.visao === "original") v.poster = "", aviso("Preparando uma cópia leve do vídeo original para tocar aqui. Leva alguns segundos.");
  const dur = S.visao === "original" ? (D.bruto && D.bruto.duracao) : (D.cortado && D.cortado.duracao) || 0;
  document.querySelectorAll("#seg-visao button").forEach((b) => (b.onclick = () => { S.visao = b.dataset.v; desenhar(); }));
  document.querySelectorAll("#seg-formato button").forEach((b) => (b.onclick = () => { S.formato = b.dataset.f; desenhar(); }));
  desenharTranscricao();
  desenharTimeline(dur);
  const agulha = () => {
    const t = v.currentTime || 0;
    $("#tempo").innerHTML = `<b>${fmt(t, true)}</b> / ${fmt(dur)}`;
    const a = $("#agulha");
    if (a) {
      a.style.left = t * S.pps + "px";
      const sc = $("#tl-scroll");
      if (!v.paused && (t * S.pps > sc.scrollLeft + sc.clientWidth - 40 || t * S.pps < sc.scrollLeft)) sc.scrollLeft = t * S.pps - 60;
    }
    marcarFraseTocando(t);
  };
  v.ontimeupdate = agulha;
  v.onseeked = agulha;
  const loop = () => { if (!v.paused) { agulha(); requestAnimationFrame(loop); } };
  v.onplay = () => requestAnimationFrame(loop);
  $("#tl-zoom").oninput = (e) => { S.ppsSlider = +e.target.value; desenharTimeline(dur); agulha(); };
  $("#tl-scroll").onclick = (e) => {
    if (e.target.closest(".bloco.zoom") || e.target.closest(".bloco.card-m")) return;
    const r = $("#tl-inner").getBoundingClientRect();
    v.currentTime = Math.max(0, (e.clientX - r.left) / S.pps);
  };
  agulha();
}
function marcarFraseTocando(t) {
  const m = mapa();
  const to = S.visao === "original" ? t : m.paraOriginal(t);
  document.querySelectorAll(".frase.tocando").forEach((x) => x.classList.remove("tocando"));
  const f = frasesOrigem().find((f) => to >= f.s - 0.05 && to <= f.e + 0.05);
  if (f) { const el = document.querySelector(`.frase[data-i="${f.i}"]`); if (el) el.classList.add("tocando"); }
}
function desenharTranscricao() {
  const fr = frasesOrigem();
  const corr = S.dados.correcoes || {};
  const box = $("#transcricao");
  if (!fr.length) { box.innerHTML = `<div class="dica">Sem transcrição.</div>`; return; }
  box.innerHTML = fr.map((f) => {
    const chave = "trecho-" + f.s.toFixed(2);
    const p = temPend(chave);
    const cls = p ? (p.tipo === "manter_trecho" ? "pend-manter" : "pend-cortar") : (f.k ? "" : "cortada");
    const palavras = f.w.map((w, j) => {
      const nucleo = w.t.replace(/[.,!?;:…"']/g, "").toLowerCase();
      const pc = temPend("corr-" + nucleo);
      const certo = pc ? pc.certo : corr[nucleo];
      return `<span class="palavra ${certo ? "corrigida" : ""}" data-j="${j}" title="${certo ? "vira: " + esc(certo) : ""}">${esc(w.t)}</span>`;
    }).join(" ");
    return `<span class="tempo-frase" data-s="${f.s}">${fmt(f.s)}</span><span class="frase ${cls}" data-i="${f.i}">${palavras}</span> `;
  }).join("");
  box.querySelectorAll(".tempo-frase").forEach((el) => (el.onclick = () => irParaOriginal(+el.dataset.s)));
  box.querySelectorAll(".frase").forEach((el) => {
    el.onclick = (ev) => {
      if (ev.detail > 1) return;
      clearTimeout(el._t);
      el._t = setTimeout(() => {
        const f = fr[+el.dataset.i];
        const chave = "trecho-" + f.s.toFixed(2);
        if (temPend(chave)) pend(null, chave);
        else pend({ tipo: f.k ? "cortar_trecho" : "manter_trecho", inicio: f.s, fim: f.e, texto: f.texto }, chave);
        desenharTranscricao(); desenharTimeline(null);
      }, 220);
    };
    el.ondblclick = (ev) => {
      clearTimeout(el._t);
      const sp = ev.target.closest(".palavra");
      if (!sp) return;
      const w = fr[+el.dataset.i].w[+sp.dataset.j];
      const nucleo = w.t.replace(/[.,!?;:…"']/g, "");
      const certo = window.prompt(`Como "${nucleo}" deveria ser escrito? (vale para a legenda e para todas as vezes que aparece)`, nucleo);
      if (certo && certo.trim() && certo.trim() !== nucleo) {
        pend({ tipo: "corrigir_palavra", errado: nucleo.toLowerCase(), certo: certo.trim() }, "corr-" + nucleo.toLowerCase());
        desenharTranscricao();
      }
    };
  });
}
function irParaOriginal(t) {
  const v = $("#player");
  if (S.visao === "original") v.currentTime = t;
  else { const te = mapa().paraEditado(t); if (te != null) v.currentTime = te; else { S.visao = "original"; desenhar(); setTimeout(() => ($("#player").currentTime = t), 300); } }
}
function desenharTimeline(dur) {
  const D = S.dados;
  if (dur == null) dur = S._dur; else S._dur = dur;
  if (!dur) return;
  const sc = $("#tl-scroll");
  const largura = Math.max(sc.clientWidth - 2, 300);
  const base = largura / dur;
  S.pps = base * (1 + (S.ppsSlider || 0) / 100 * Math.max(0, 200 / base - 1));
  const W = dur * S.pps;
  const trilhas = [];
  const bloco = (cls, s, e, txt, extra = "") => `<div class="bloco ${cls}" style="left:${s * S.pps}px;width:${Math.max(2, (e - s) * S.pps)}px" title="${esc(txt)}" ${extra}>${esc(txt)}</div>`;
  // régua
  const passo = [1, 2, 5, 10, 15, 30, 60, 120, 300].find((p) => p * S.pps >= 70) || 600;
  let regua = "";
  for (let t = 0; t <= dur; t += passo) regua += `<div class="tick" style="left:${t * S.pps}px">${fmt(t)}</div>`;
  trilhas.push(["Tempo", "regua", regua]);
  if (S.visao === "original") {
    const R = D.edl, fr = frasesOrigem();
    let v = "", ant = 0;
    R.forEach((r) => {
      if (r.s - ant > 0.05) {
        const dentro = fr.filter((f) => !f.k && f.s >= ant - 0.05 && f.e <= r.s + 0.05);
        const txt = dentro.length ? "✂ " + dentro.map((f) => f.texto).join(" ") : `pausa ${(r.s - ant).toFixed(1)}s`;
        const pm = dentro.some((f) => temPend("trecho-" + f.s.toFixed(2)));
        v += bloco("cortado" + (pm ? " pendente-manter" : ""), ant, r.s, txt);
      }
      v += bloco("mantido", r.s, r.e, "");
      ant = r.e;
    });
    if (dur - ant > 0.05) v += bloco("cortado", ant, dur, `pausa ${(dur - ant).toFixed(1)}s`);
    trilhas.push(["Vídeo", "", v]);
    trilhas.push(["Áudio", "onda", `<canvas id="onda"></canvas>`]);
  } else {
    const cortes = D.cortes_editado || [];
    const lim = [0, ...cortes, dur];
    let v = "";
    for (let i = 0; i < lim.length - 1; i++) v += bloco("mantido", lim[i], lim[i + 1], `trecho ${i + 1}`);
    v += cortes.map((c) => `<div class="corte-marca" style="left:${c * S.pps}px"></div>`).join("");
    trilhas.push(["Vídeo", "", v]);
    trilhas.push(["Áudio", "onda", `<canvas id="onda"></canvas>`]);
    if (D.dinamica && D.dinamica.eventos.length) {
      const z = D.dinamica.eventos.map((ev, i) => {
        const p = temPend("zoom-" + i);
        const ativo = p ? p.ativo : ev.ativo !== false;
        const nome = ev.tipo === "punch" ? "corte" : ev.tipo === "enfase" ? "ênfase" : "aproximação";
        return bloco("zoom" + (ativo ? "" : " off"), ev.inicio, ev.fim, `${nome} ${Math.round((ev.intensidade - 1) * 100)}%`, `data-z="${i}"`);
      }).join("");
      trilhas.push(["Zoom", "", z]);
    }
    const lay = S.formato && D.formatos[S.formato] && D.formatos[S.formato].layout;
    if (lay && lay.referencia) {
      const r = lay.referencia;
      trilhas.push(["Referência", "", bloco("ref", 0, dur, `referência ${fmt(r.inicio)}–${fmt(r.fim)} · áudio ${r.audio}`)]);
    }
    if (D.roteiro && D.roteiro.cards) {
      const tipos = [...new Set(D.roteiro.cards.map((c) => c.tipo))];
      const m = D.roteiro.cards.map((c) => {
        const p = temPend("ativo-" + c.id);
        const ativo = p ? p.ativo : c.ativo !== false;
        return bloco(`card-m t${tipos.indexOf(c.tipo) % 3}` + (ativo ? "" : " off"), c.inicio, c.fim, `${TIPO_CARD[c.tipo] || c.tipo}: ${tituloCard(c)}`, `data-c="${esc(c.id)}"`);
      }).join("");
      trilhas.push(["Motion", "", m]);
    }
    if (D.palavras && D.palavras.length) {
      const fr = []; let at = null;
      for (const w of D.palavras) {
        if (at && (w.start - at.e > 0.45 || at.w.length >= 3 || /[.!?,]$/.test(at.w[at.w.length - 1]))) { fr.push(at); at = null; }
        if (!at) at = { s: w.start, e: w.end, w: [] };
        at.w.push(w.text); at.e = w.end;
      }
      if (at) fr.push(at);
      trilhas.push(["Legenda", "", fr.map((f) => bloco("leg", f.s, f.e, f.w.join(" "))).join("")]);
    }
  }
  $("#tl-labels").innerHTML = trilhas.map(([n, c]) => `<div class="tl-label ${c}">${n}</div>`).join("");
  $("#tl-inner").style.width = W + "px";
  $("#tl-inner").innerHTML = trilhas.map(([, c, h]) => `<div class="tl-track ${c}">${h}</div>`).join("") + `<div class="agulha" id="agulha"></div>`;
  desenharOnda(S.visao === "original" ? D.onda_original : D.onda_cortado);
  document.querySelectorAll(".bloco.zoom").forEach((b) => (b.onclick = (e) => {
    e.stopPropagation();
    const i = +b.dataset.z, ev = D.dinamica.eventos[i];
    const atual = temPend("zoom-" + i) ? temPend("zoom-" + i).ativo : ev.ativo !== false;
    const novo = !atual;
    if (novo === (ev.ativo !== false)) pend(null, "zoom-" + i);
    else pend({ tipo: "zoom", indice: i, inicio: ev.inicio, ativo: novo }, "zoom-" + i);
    desenharTimeline(null);
  }));
  document.querySelectorAll(".bloco.card-m").forEach((b) => (b.onclick = (e) => {
    e.stopPropagation();
    const c = D.roteiro.cards.find((x) => x.id === b.dataset.c);
    $("#player").currentTime = c.inicio + 0.3;
  }));
}
function desenharOnda(onda) {
  const cv = $("#onda");
  if (!cv || !onda) return;
  const w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
  cv.width = w * dpr; cv.height = h * dpr;
  const g = cv.getContext("2d");
  g.scale(dpr, dpr);
  g.fillStyle = "#9ec947";
  const n = onda.picos.length, pps = onda.pps;
  for (let x = 0; x < w; x++) {
    const i0 = Math.floor(x / S.pps * pps), i1 = Math.max(i0 + 1, Math.floor((x + 1) / S.pps * pps));
    let m = 0;
    for (let i = i0; i < i1 && i < n; i++) m = Math.max(m, onda.picos[i]);
    const a = Math.max(1, m / 100 * (h - 6));
    g.fillRect(x, (h - a) / 2, 1, a);
  }
}

/* ---------------- motion ---------------- */
function tituloCard(c) {
  const k = c.campos || {};
  return k.titulo || k.nome || k.frase || k.palavra || k.texto || k.rotulo || (k.valor != null ? String(k.valor) : "") || "";
}
function paginaMotion() {
  const D = S.dados;
  if (!D.roteiro || !D.roteiro.cards) return placeholder("Sem animações ainda", "Os cards aparecem aqui depois da etapa de motion. Digite /video-motion no Claude.");
  const fs = Object.keys(D.formatos).filter((f) => D.formatos[f].montagem);
  const f = S.motionFormato;
  const x = f && D.formatos[f];
  const estiloAtual = (temPend("estilo-motion") || {}).estilo || D.roteiro.estilo || "escuro";
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">03</span>Motion</h1>
      <p class="page-sub">Edite os textos, troque o ícone, ligue ou desligue cards e escolha o estilo. As mudanças viram um pedido para o Claude refazer as animações.</p></div>
      ${fs.length > 1 ? `<div class="seg" id="seg-mformato">${fs.map((k) => `<button data-f="${k}" class="${k === f ? "on" : ""}">${NOME_FORMATO[k]}</button>`).join("")}</div>` : ""}</div>
    <span class="card-label">Estilo</span>
    <div class="estilos">${D.estilos_motion.map((e) => `<button class="estilo-op ${e.id === estiloAtual ? "on" : ""}" data-e="${e.id}"><b>${esc(e.nome)}</b><span>${esc(e.descricao || "")}</span></button>`).join("")}</div>
    ${x && x.imagens["galeria-estilos"] ? `<img class="previa" style="margin-top:var(--s-5)" src="${x.imagens["galeria-estilos"]}">` : ""}
    <div class="section-h">Cards <span class="chip">${D.roteiro.cards.length} no roteiro · ícones ${esc(D.roteiro.icones || "")}</span></div>
    <div id="cards"></div>`;
}
function camposEditaveis(c) {
  const out = [], k = c.campos || {};
  const ignorar = new Set(["palavra", "falada", "em", "html", "css", "js", "casas", "de", "acao"]);
  for (const [n, v] of Object.entries(k)) {
    if (ignorar.has(n) && !(n === "palavra" && c.tipo === "palavra")) continue;
    if (typeof v === "string" || typeof v === "number") out.push([n, String(v)]);
    else if (Array.isArray(v)) v.forEach((it, i) => { if (it && typeof it === "object" && "texto" in it) out.push([`${n}.${i}.texto`, it.texto]); });
  }
  return out;
}
function montarMotion() {
  const D = S.dados;
  if (!D.roteiro || !D.roteiro.cards) return;
  document.querySelectorAll("#seg-mformato button").forEach((b) => (b.onclick = () => { S.motionFormato = b.dataset.f; desenhar(); }));
  document.querySelectorAll(".estilo-op").forEach((b) => (b.onclick = () => {
    if (b.dataset.e === D.roteiro.estilo) pend(null, "estilo-motion"); else pend({ tipo: "estilo_motion", estilo: b.dataset.e }, "estilo-motion");
    desenhar();
  }));
  const x = S.motionFormato && D.formatos[S.motionFormato];
  const ordem = x && x.montagem ? x.montagem.cards.map((c) => c.id) : [];
  const estiloIc = D.roteiro.icones || "duotone";
  const pesoIc = { linha: "linha", preenchido: "preenchido", duotone: "duotone" }[estiloIc] || "linha";
  $("#cards").innerHTML = D.roteiro.cards.map((c) => {
    const i = ordem.indexOf(c.id);
    const snap = i >= 0 && x.snapshots[i];
    const pA = temPend("ativo-" + c.id);
    const ativo = pA ? pA.ativo : c.ativo !== false;
    const pI = temPend("icone-" + c.id);
    const icone = pI ? pI.icone : c.icone;
    return `<div class="card-motion ${ativo ? "" : "off"}" data-c="${esc(c.id)}">
      <div>${snap ? `<img src="${snap}?v=${Date.now()}">` : `<div class="placeholder-box" style="padding:40px 0"><div class="ph-sub">sem prévia</div></div>`}
        <div class="chips-row" style="margin-top:8px"><span class="chip active"><span class="dot"></span>${esc(TIPO_CARD[c.tipo] || c.tipo)}</span><span class="chip">${fmt(c.inicio, true)}–${fmt(c.fim, true)}</span></div></div>
      <div>
        <div class="chips-row" style="justify-content:space-between;margin-bottom:12px"><b class="card-title">${esc(c.id)}</b>
          <button class="btn bt-ativo">${ativo ? "Desligar card" : "Ligar card"}</button></div>
        ${camposEditaveis(c).map(([n, v]) => {
          const p = temPend(`texto-${c.id}-${n}`);
          return `<div class="campo"><label>${esc(n.replace(/^\w+\.(\d+)\.texto$/, (m, d) => "item " + (+d + 1)))}</label><input type="text" data-campo="${esc(n)}" data-orig="${esc(v)}" value="${esc(p ? p.valor : v)}"></div>`;
        }).join("")}
        ${estiloIc === "emoji" ? `<div class="campo"><label>emoji</label><div>${esc(c.emoji || "–")}</div></div>` : estiloIc === "nenhum" ? "" : `
        <div class="campo"><label>ícone</label><div class="icone-atual">${icone ? `<img src="/api/icone?nome=${encodeURIComponent(icone)}&estilo=${pesoIc}">` : ""}<span class="chip">${esc(icone || "sem ícone")}</span></div>
          <input type="search" class="busca-icone" placeholder="buscar ícone (ex.: dinheiro, vídeo, cliente)" style="margin-top:8px"><div class="icone-res"></div></div>`}
      </div></div>`;
  }).join("");
  document.querySelectorAll(".card-motion").forEach((el) => {
    const id = el.dataset.c;
    const c = D.roteiro.cards.find((k) => k.id === id);
    el.querySelector(".bt-ativo").onclick = () => {
      const atual = temPend("ativo-" + id) ? temPend("ativo-" + id).ativo : c.ativo !== false;
      if (!atual === (c.ativo !== false)) pend(null, "ativo-" + id); else pend({ tipo: "card_ativo", card: id, ativo: !atual }, "ativo-" + id);
      montarMotion();
    };
    el.querySelectorAll("input[data-campo]").forEach((inp) => (inp.onchange = () => {
      const n = inp.dataset.campo, chave = `texto-${id}-${n}`;
      if (inp.value === inp.dataset.orig) pend(null, chave);
      else pend({ tipo: "card_texto", card: id, campo: n, valor: inp.value, antes: inp.dataset.orig }, chave);
    }));
    const busca = el.querySelector(".busca-icone");
    if (busca) busca.oninput = () => {
      clearTimeout(busca._t);
      busca._t = setTimeout(async () => {
        const nomes = busca.value.trim() ? await api("/api/icones?q=" + encodeURIComponent(busca.value)) : [];
        const peso = { linha: "linha", preenchido: "preenchido", duotone: "duotone" }[D.roteiro.icones] || "linha";
        const res = el.querySelector(".icone-res");
        res.innerHTML = nomes.map((n) => `<button data-n="${esc(n)}"><img src="/api/icone?nome=${encodeURIComponent(n)}&estilo=${peso}">${esc(n)}</button>`).join("");
        res.querySelectorAll("button").forEach((b) => (b.onclick = () => {
          if (b.dataset.n === c.icone) pend(null, "icone-" + id); else pend({ tipo: "card_icone", card: id, icone: b.dataset.n }, "icone-" + id);
          montarMotion();
        }));
      }, 250);
    };
  });
}

/* ---------------- legendas ---------------- */
function paginaLegendas() {
  const D = S.dados;
  if (!D.palavras || !D.palavras.length) return placeholder("Sem legenda ainda", "A legenda usa a transcrição do vídeo cortado. Faça o corte primeiro.");
  const atual = (temPend("estilo-legenda") || {}).estilo || (D.estado.escolhas || {}).legenda_estilo || "dinamica";
  const gal = Object.values(D.formatos).map((x) => x.imagens["galeria-legendas"]).find(Boolean);
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">04</span>Legendas</h1>
      <p class="page-sub">Escolha o estilo e corrija palavras que saíram erradas. A correção vale para todas as vezes que a palavra aparece.</p></div></div>
    <span class="card-label">Estilo</span>
    <div class="estilos">${ESTILOS_LEGENDA.map(([k, n, d]) => `<button class="estilo-op ${k === atual ? "on" : ""}" data-e="${k}"><b>${n}</b><span>${d}</span></button>`).join("")}</div>
    ${gal ? `<img class="previa" style="margin-top:var(--s-5)" src="${gal}?v=${Date.now()}">` : ""}
    <div class="section-h">Corrigir palavras <input type="search" id="filtro" placeholder="filtrar" style="max-width:220px"></div>
    <div class="terms" id="palavras"></div>`;
}
function montarLegendas() {
  const D = S.dados;
  if (!D.palavras || !D.palavras.length) return;
  document.querySelectorAll(".estilo-op").forEach((b) => (b.onclick = () => {
    const salvo = (D.estado.escolhas || {}).legenda_estilo || "dinamica";
    if (b.dataset.e === salvo) pend(null, "estilo-legenda"); else pend({ tipo: "estilo_legenda", estilo: b.dataset.e }, "estilo-legenda");
    desenhar();
  }));
  const desenharPalavras = () => {
    const f = ($("#filtro").value || "").toLowerCase();
    const vistos = new Map();
    for (const w of D.palavras) {
      const n = w.text.replace(/[.,!?;:…"']/g, "");
      if (!n || (f && !n.toLowerCase().includes(f))) continue;
      vistos.set(n.toLowerCase(), (vistos.get(n.toLowerCase()) || { n, q: 0 }));
      vistos.get(n.toLowerCase()).q++;
    }
    $("#palavras").innerHTML = [...vistos.values()].map(({ n, q }) => {
      const p = temPend("corr-" + n.toLowerCase());
      const corrigida = p ? p.certo : (D.correcoes || {})[n.toLowerCase()];
      return `<button class="term ${corrigida ? "on" : ""}" data-n="${esc(n)}" title="${q}×">${esc(corrigida ? `${n} → ${corrigida}` : n)}</button>`;
    }).join("");
    document.querySelectorAll("#palavras .term").forEach((b) => (b.onclick = () => {
      const n = b.dataset.n;
      const certo = window.prompt(`Como "${n}" deveria ser escrito?`, n);
      if (certo === null) return;
      if (!certo.trim() || certo.trim() === n) pend(null, "corr-" + n.toLowerCase());
      else pend({ tipo: "corrigir_palavra", errado: n.toLowerCase(), certo: certo.trim() }, "corr-" + n.toLowerCase());
      desenharPalavras();
    }));
  };
  $("#filtro").oninput = desenharPalavras;
  desenharPalavras();
}

/* ---------------- exportar ---------------- */
function paginaExportar() {
  const D = S.dados;
  const fs = Object.entries(D.finais || {});
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">05</span>Exportar</h1>
      <p class="page-sub">Os vídeos prontos ficam na pasta Editados, com o nome que você escolheu.</p></div>
      <button class="btn btn-claude" id="bt-pasta">Abrir a pasta</button></div>
    ${fs.length ? fs.map(([f, x]) => `<div class="card">
        <span class="card-label">${NOME_FORMATO[f] || f} · ${x.mb} MB</span>
        <div class="card-title">${esc(x.nome)}</div>
        <div class="caminho" style="margin:10px 0">${esc(x.caminho)}</div>
        ${x.srt ? `<div class="dica">Legenda separada (YouTube): ${esc(x.srt)}</div>` : ""}
        <a class="btn" href="${x.url}" target="_blank">Assistir</a></div>`).join("")
      : placeholder("Nada exportado ainda", "Quando o vídeo for finalizado, ele aparece aqui. Digite /video-editar no Claude para terminar.")}
    <div class="section-h">Pasta dos vídeos prontos</div><div class="caminho">${esc(D.pasta_editados)}</div>`;
}
function montarExportar() {
  const b = $("#bt-pasta");
  if (b) b.onclick = async () => { try { await api("/api/abrir-pasta", { method: "POST" }); } catch { aviso("Não consegui abrir a pasta."); } };
}

function placeholder(t, s) { return `<div class="placeholder-box"><div class="ph-title">${esc(t)}</div><div class="ph-sub">${esc(s)}</div></div>`; }

/* ---------------- progresso ao vivo ---------------- */
async function vigiar() {
  try {
    if (S.id && S.dados && S.dados.preparando) {
      await carregarVideo();
      if (!S.dados.preparando) desenhar();
    } else if (S.id && S.dados) {
      const r = await api(`/api/video/${encodeURIComponent(S.id)}/estado`);
      atualizarStatus(r.estado);
      if (r.estado.atualizado !== S.atualizado && !r.estado.etapa_atual) {
        const tempo = $("#player") && $("#player").currentTime;
        await carregarVideo(); await carregarVideos(); desenhar();
        if (tempo && $("#player")) $("#player").currentTime = tempo;
      }
    } else if (!S.id) {
      const antes = JSON.stringify(S.videos);
      await carregarVideos();
      if (JSON.stringify(S.videos) !== antes) desenhar();
    }
    $("#rodape").textContent = "localhost · online";
  } catch { $("#rodape").textContent = "painel desconectado"; }
  setTimeout(vigiar, 2500);
}
window.addEventListener("resize", () => { if (S.aba === "cortes" && S.dados) desenharTimeline(null); });

(async () => { await carregarVideos(); await irPara(); vigiar(); })();
