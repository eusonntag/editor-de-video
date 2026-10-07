/* Painel do Editor de Vídeo: sem framework e sem build.
   Lê tudo de /api/video/<id> e grava os pedidos em /api/video/<id>/ajustes (lidos pelo /video-ajustar). */
"use strict";

const S = {
  videos: [], dados: null, id: null, aba: "cortes",
  visao: "editado", formato: null, pps: 0, pendentes: [], atualizado: null, motionFormato: null,
  modoSel: "frase", busca: { q: "", ach: [], n: 1, idx: 0 }, sel: null, desenhando: false, ancora: null,
};
try { S.modoSel = localStorage.getItem("painel-modo-selecao") === "palavra" ? "palavra" : "frase"; } catch { /* sem armazenamento */ }
const ABAS = [["cortes", "Cortes"], ["motion", "Motion"], ["legendas", "Legendas"], ["exportar", "Exportar"]];
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
  S._R = null;
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
    case "zoom_tempo": return `Zoom ${fmt(p.antes)}: agora de ${fmt(p.inicio, true)} a ${fmt(p.fim, true)}`;
    case "zoom_novo": return `Novo zoom de ${fmt(p.inicio, true)} a ${fmt(p.fim, true)}`;
    case "card_tempo": return `${p.card}: agora de ${fmt(p.inicio, true)} a ${fmt(p.fim, true)}`;
    case "desfoque_novo": return `Desfocar área de ${fmt(p.inicio, true)} a ${fmt(p.fim, true)}${p.rotulo ? " (" + p.rotulo + ")" : ""}`;
    case "desfoque_tempo": return `Desfoque ${fmt(p.antes)}: agora de ${fmt(p.inicio, true)} a ${fmt(p.fim, true)}`;
    case "desfoque_ativo": return `Desfoque ${fmt(p.inicio)} ${p.ativo ? "ligado" : "desligado"}`;
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
  if (p[0] === "video" && p[1]) return { id: p[1], aba: ABAS.some((a) => a[0] === p[2]) ? p[2] : "cortes" };
  return { id: null, aba: "inicio" };
}
async function irPara() {
  const r = lerRota();
  const mudouVideo = r.id !== S.id;
  S.id = r.id; S.aba = r.aba;
  if (S.id && (mudouVideo || !S.dados)) {
    S.busca = { q: "", ach: [], n: 1, idx: 0 }; S.sel = null; S.desenhando = false; S.ancora = null;
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
    S._R = null;
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
    const f = { cortes: paginaCortes, motion: paginaMotion, legendas: paginaLegendas, exportar: paginaExportar }[aba[0]];
    pg.innerHTML = f();
    const pos = { cortes: montarCortes, motion: montarMotion, legendas: montarLegendas, exportar: montarExportar }[aba[0]];
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
function blocoEstatisticas() {
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
  return `<div class="section-h" id="estatisticas"><span>Estatísticas deste vídeo</span><span>${esc(D.status.join(" "))}${e.nome_final ? ` · ${esc(e.nome_final)}` : ""}</span></div>
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
const norm = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const arred = (x) => Math.round(x * 100) / 100;
const NOME_K = { z: "Zoom", zn: "Zoom novo", c: "Card", d: "Desfoque", dn: "Desfoque novo" };
function originalLike() { return S.visao === "original" || S.visao === "previa"; }

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

/* Cortes do vídeo com as alterações pendentes aplicadas (usado na "Prévia") */
function edlVirtual() {
  if (S._R) return S._R;
  let R = (S.dados.edl || []).map((r) => ({ s: r.s, e: r.e }));
  for (const p of S.pendentes) {
    if (p.tipo === "cortar_trecho") {
      const n = [];
      for (const r of R) {
        if (p.fim <= r.s || p.inicio >= r.e) { n.push(r); continue; }
        if (p.inicio > r.s) n.push({ s: r.s, e: p.inicio });
        if (p.fim < r.e) n.push({ s: p.fim, e: r.e });
      }
      R = n;
    } else if (p.tipo === "manter_trecho") R.push({ s: Math.max(0, p.inicio - 0.04), e: p.fim + 0.04 });
  }
  R.sort((a, b) => a.s - b.s);
  const m = [];
  for (const r of R) { const u = m[m.length - 1]; if (u && r.s <= u.e + 0.001) u.e = Math.max(u.e, r.e); else m.push({ ...r }); }
  S._R = m.filter((r) => r.e - r.s > 0.03);
  return S._R;
}
function tempoEditadoVirtual(t) {
  let acc = 0;
  for (const r of edlVirtual()) { if (t < r.s) return acc; if (t <= r.e) return acc + t - r.s; acc += r.e - r.s; }
  return acc;
}
function duracaoVirtual() { return edlVirtual().reduce((a, r) => a + r.e - r.s, 0); }
function pularCortes(v) {
  const R = edlVirtual(), t = v.currentTime;
  if (!R.length || R.some((r) => t >= r.s - 0.02 && t < r.e)) return false;
  const prox = R.find((r) => r.s > t);
  if (prox) { v.currentTime = prox.s; return true; }
  v.pause(); v.currentTime = Math.max(0, R[R.length - 1].e - 0.05);
  return true;
}

function frasesOrigem() {
  const D = S.dados;
  if (S._frD === D) return S._fr;
  const R = D.edl || [], W = D.palavras_origem || [];
  W.forEach((w, g) => { w.g = g; });
  const mantida = (w) => { const m = (w.s + w.e) / 2; return R.some((r) => m >= r.s && m <= r.e); };
  const fr = [];
  for (const w of W) {
    const k = mantida(w);
    w.k = k;
    const ult = fr[fr.length - 1];
    if (ult && ult.k === k && w.s - ult.e <= 0.6 && !/[.!?]$/.test(ult.w[ult.w.length - 1].t)) { ult.w.push(w); ult.e = w.e; }
    else fr.push({ k, w: [w], s: w.s, e: w.e });
  }
  S._fr = fr.map((f, i) => ({ ...f, i, texto: f.w.map((x) => x.t).join(" ") }));
  S._frD = D;
  return S._fr;
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
  for (const [f, x] of Object.entries(D.finais || {})) opcoes.push(["final-" + f, x.url, NOME_FORMATO[f] + " · salvo"]);
  return opcoes;
}

function paginaCortes() {
  const D = S.dados;
  if (!D.edl) return placeholder("Ainda não há cortes", "O painel mostra a linha do tempo depois do corte. Digite /video-editar no Claude.") + blocoEstatisticas();
  if (S.visao === "editado" && !fonteEditado().length) S.visao = "original";
  if (S.visao === "previa" && !(D.bruto && D.bruto.url)) S.visao = fonteEditado().length ? "editado" : "original";
  const fontes = fonteEditado();
  if (!fontes.find((f) => f[0] === S.formato)) S.formato = fontes[0] && fontes[0][0];
  const e = D.estado;
  const legendaTl = { original: "vídeo original, com o que foi cortado", previa: "prévia: o original pulando o que está cortado, já com as suas marcações", editado: "vídeo editado" }[S.visao];
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">01</span>Cortes e linha do tempo</h1>
      <p class="page-sub">Riscado é o que foi cortado. Escolha selecionar por <b>frases</b> ou por <b>palavras</b> e clique (ou arraste, nas palavras) para manter ou cortar. Dois cliques numa palavra corrigem a grafia. Use <b>Prévia</b> para assistir com as suas marcações antes de aplicar.</p></div></div>
    ${e.etapa_atual ? `<div class="callout">O Claude está trabalhando neste vídeo agora: ${esc(e.etapa_atual.texto)} (passo ${e.etapa_atual.passo} de ${e.etapa_atual.total})</div>` : ""}
    <div class="editor-top">
      <div class="player">
        <div class="vwrap"><video id="player" preload="metadata" playsinline controls></video><div class="sobre" id="sobre"></div></div>
        <div class="player-bar">
          <div class="seg" id="seg-visao">
            <button data-v="original" class="${S.visao === "original" ? "on" : ""}">Original</button>
            <button data-v="editado" class="${S.visao === "editado" ? "on" : ""}" ${fontes.length ? "" : "disabled"}>Editado</button>
            <button data-v="previa" class="${S.visao === "previa" ? "on" : ""}" ${D.bruto && D.bruto.url ? "" : "disabled"} title="Toca o vídeo pulando o que está marcado para cortar, com as suas alterações ainda não aplicadas">Prévia</button>
          </div>
          ${S.visao === "editado" && fontes.length > 1 ? `<div class="seg" id="seg-formato">${fontes.map(([f, , n]) => `<button data-f="${f}" class="${S.formato === f ? "on" : ""}">${n}</button>`).join("")}</div>` : ""}
          ${D.cortado ? `<button class="btn" id="bt-desfocar" title="Marcar uma área da tela para ficar desfocada (e-mail, nomes, dados)">${S.desenhando ? "Cancelar desenho" : "Desfocar área"}</button>` : ""}
          <div class="tempo" id="tempo"><b>0:00</b> / 0:00</div>
        </div>
      </div>
      <div>
        <div class="busca-bar">
          <input type="search" id="busca" placeholder="buscar palavra ou frase" value="${esc(S.busca.q)}">
          <span class="chip" id="busca-n"></span>
          <button class="btn" id="busca-ant" title="Resultado anterior">‹</button><button class="btn" id="busca-prox" title="Próximo resultado (Enter)">›</button>
        </div>
        <div class="busca-bar">
          <span class="card-label" style="margin:0">Selecionar por</span>
          <div class="seg" id="seg-sel"><button data-m="frase" class="${S.modoSel === "frase" ? "on" : ""}">Frases</button><button data-m="palavra" class="${S.modoSel === "palavra" ? "on" : ""}">Palavras</button></div>
        </div>
        <div class="transcricao modo-${S.modoSel}" id="transcricao"></div>
      </div>
    </div>
    <div class="timeline">
      <div class="tl-head"><span class="chip ${S.visao === "editado" ? "active" : S.visao === "previa" ? "ochre" : "rust"}"><span class="dot"></span>${legendaTl}</span>
        <label class="chip">zoom <input type="range" id="tl-zoom" min="0" max="100" value="${S.ppsSlider || 0}"></label></div>
      <div class="tl-sel" id="tl-sel"></div>
      <div class="tl-body"><div class="tl-labels" id="tl-labels"></div><div class="tl-scroll" id="tl-scroll"><div class="tl-inner" id="tl-inner"></div></div></div>
    </div>
    ${blocoEstatisticas()}`;
}
function montarCortes() {
  const D = S.dados;
  if (!D.edl) return;
  const v = $("#player");
  const fontes = fonteEditado();
  const fonte = originalLike() ? D.bruto && D.bruto.url : (fontes.find((f) => f[0] === S.formato) || [])[1];
  v.src = fonte || "";
  v.onerror = () => aviso("Não consegui tocar este arquivo aqui no painel. Tente a opção <b>Prévia</b> ou <b>Original</b>.", 9000);
  if (!fonte && originalLike()) v.poster = "", aviso("Preparando uma cópia leve do vídeo original para tocar aqui. Leva alguns segundos.");
  const dur = originalLike() ? (D.bruto && D.bruto.duracao) : (D.cortado && D.cortado.duracao) || 0;
  document.querySelectorAll("#seg-visao button").forEach((b) => (b.onclick = () => { S.visao = b.dataset.v; S.desenhando = false; desenhar(); }));
  document.querySelectorAll("#seg-formato button").forEach((b) => (b.onclick = () => { S.formato = b.dataset.f; S.desenhando = false; desenhar(); }));
  montarBusca();
  desenharTranscricao();
  desenharTimeline(dur);
  executarBusca(false);
  desenharBarraSel();
  montarSobre();
  const agulha = () => {
    const t = v.currentTime || 0;
    if (S.visao === "previa" && pularCortes(v)) return;
    $("#tempo").innerHTML = S.visao === "previa"
      ? `<b>${fmt(tempoEditadoVirtual(t), true)}</b> / ${fmt(duracaoVirtual())} <span style="color:var(--text-faint)">prévia</span>`
      : `<b>${fmt(t, true)}</b> / ${fmt(dur)}`;
    const a = $("#agulha");
    if (a) {
      a.style.left = t * S.pps + "px";
      const sc = $("#tl-scroll");
      if (!v.paused && (t * S.pps > sc.scrollLeft + sc.clientWidth - 40 || t * S.pps < sc.scrollLeft)) sc.scrollLeft = t * S.pps - 60;
    }
    marcarFraseTocando(t);
    atualizarDesfoques(t);
    desenharBarraSel();
  };
  v.ontimeupdate = agulha;
  v.onseeked = agulha;
  v.onloadedmetadata = agulha;
  const loop = () => { if (!v.paused) { agulha(); requestAnimationFrame(loop); } };
  v.onplay = () => requestAnimationFrame(loop);
  $("#tl-zoom").oninput = (e) => { S.ppsSlider = +e.target.value; desenharTimeline(dur); agulha(); };
  $("#tl-scroll").onclick = (e) => {
    if (e.target.closest(".bloco.edit")) return;
    const r = $("#tl-inner").getBoundingClientRect();
    v.currentTime = Math.max(0, (e.clientX - r.left) / S.pps);
  };
  const bd = $("#bt-desfocar");
  if (bd) bd.onclick = () => {
    if (S.desenhando) { S.desenhando = false; bd.textContent = "Desfocar área"; montarSobre(); return; }
    const trocar = !(S.visao === "editado" && S.formato === "cortado");
    S.visao = "editado"; S.formato = "cortado"; S.desenhando = true;
    aviso("Arraste sobre a imagem para marcar o que deve ficar desfocado. Ele dura 5 s a partir do ponto atual; depois ajuste as bordas na linha do tempo.", 9000);
    if (trocar) desenhar(); else { bd.textContent = "Cancelar desenho"; v.pause(); montarSobre(); }
  };
  agulha();
}
function marcarFraseTocando(t) {
  const to = originalLike() ? t : mapa().paraOriginal(t);
  const f = frasesOrigem().find((f) => to >= f.s - 0.05 && to <= f.e + 0.05);
  const atual = document.querySelector(".frase.tocando");
  if (atual && f && +atual.dataset.i === f.i) return;
  if (atual) atual.classList.remove("tocando");
  if (f) { const el = document.querySelector(`.frase[data-i="${f.i}"]`); if (el) el.classList.add("tocando"); }
}

/* ---------------- busca na transcrição ---------------- */
function montarBusca() {
  const inp = $("#busca");
  inp.oninput = () => { S.busca.q = inp.value; S.busca.idx = 0; executarBusca(true); };
  inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); irBusca(e.shiftKey ? -1 : 1); } };
  $("#busca-ant").onclick = () => irBusca(-1);
  $("#busca-prox").onclick = () => irBusca(1);
  document.querySelectorAll("#seg-sel button").forEach((b) => (b.onclick = () => {
    S.modoSel = b.dataset.m;
    try { localStorage.setItem("painel-modo-selecao", S.modoSel); } catch { /* sem armazenamento */ }
    document.querySelectorAll("#seg-sel button").forEach((x) => x.classList.toggle("on", x === b));
    $("#transcricao").className = "transcricao modo-" + S.modoSel;
  }));
}
function executarBusca(rolar) {
  const W = S.dados.palavras_origem || [];
  if (S._nwD !== S.dados) { S._nw = W.map((w) => norm(w.t)); S._nwD = S.dados; }
  const q = norm(S.busca.q), toks = q.split(" ").filter(Boolean);
  const ach = [];
  if (q.length >= 2) {
    for (let i = 0; i + toks.length <= W.length; i++) {
      let ok = true;
      for (let k = 0; k < toks.length; k++) if (!S._nw[i + k] || !S._nw[i + k].includes(toks[k])) { ok = false; break; }
      if (ok) ach.push(i);
    }
  }
  S.busca.ach = ach; S.busca.n = Math.max(1, toks.length);
  if (S.busca.idx >= ach.length) S.busca.idx = 0;
  pintarBusca(rolar);
  desenharTimeline(null);
}
function pintarBusca(rolar) {
  document.querySelectorAll(".palavra.achada").forEach((x) => x.classList.remove("achada", "achada-atual"));
  const { ach, n, idx, q } = S.busca;
  let alvo = null;
  ach.forEach((g, k) => {
    for (let j = 0; j < n; j++) {
      const el = document.querySelector(`.palavra[data-g="${g + j}"]`);
      if (!el) continue;
      el.classList.add("achada");
      if (k === idx) { el.classList.add("achada-atual"); if (!alvo) alvo = el; }
    }
  });
  const c = $("#busca-n");
  if (c) c.textContent = ach.length ? `${idx + 1} de ${ach.length}` : norm(q).length >= 2 ? "nenhum resultado" : "";
  const box = $("#transcricao");
  if (rolar && alvo && box) box.scrollTop = Math.max(0, alvo.offsetTop - box.clientHeight / 2);
}
function irBusca(delta) {
  const b = S.busca;
  if (!b.ach.length) return;
  b.idx = (b.idx + delta + b.ach.length) % b.ach.length;
  pintarBusca(true);
  irParaOriginal(S.dados.palavras_origem[b.ach[b.idx]].s);
}

/* ---------------- transcrição: selecionar frases ou palavras ---------------- */
const nucleoDe = (t) => t.replace(/[.,!?;:…"']/g, "");
function pendSobrepostos(s, e) {
  return S.pendentes.filter((p) => (p.tipo === "cortar_trecho" || p.tipo === "manter_trecho") && p.inicio < e - 0.001 && p.fim > s + 0.001);
}
function alternarFrase(i) {
  const f = frasesOrigem()[i];
  const ja = pendSobrepostos(f.s, f.e);
  if (ja.length) ja.forEach((p) => pend(null, p._chave));
  else pend({ tipo: f.k ? "cortar_trecho" : "manter_trecho", inicio: f.s, fim: f.e, texto: f.texto }, "trecho-" + f.s.toFixed(2));
  aposMarcar();
}
function alternarPalavras(a, b) {
  const W = S.dados.palavras_origem;
  const sel = W.slice(a, b + 1);
  if (!sel.length) return;
  frasesOrigem();
  const ja = pendSobrepostos(sel[0].s, sel[sel.length - 1].e);
  if (ja.length) ja.forEach((p) => pend(null, p._chave));
  else {
    let corrida = [];
    const fechar = () => {
      if (!corrida.length) return;
      pend({ tipo: corrida[0].k ? "cortar_trecho" : "manter_trecho", inicio: corrida[0].s, fim: corrida[corrida.length - 1].e,
             texto: corrida.map((w) => w.t).join(" ") }, "trecho-" + corrida[0].s.toFixed(2));
      corrida = [];
    };
    for (const w of sel) { if (corrida.length && corrida[0].k !== w.k) fechar(); corrida.push(w); }
    fechar();
  }
  aposMarcar();
}
function aposMarcar() { desenharTranscricao(); desenharTimeline(null); pintarBusca(false); }
function desenharTranscricao() {
  const fr = frasesOrigem();
  const corr = S.dados.correcoes || {};
  const box = $("#transcricao");
  if (!fr.length) { box.innerHTML = `<div class="dica">Sem transcrição.</div>`; return; }
  box.innerHTML = fr.map((f) => {
    const palavras = f.w.map((w) => {
      const nucleo = nucleoDe(w.t).toLowerCase();
      const pc = temPend("corr-" + nucleo);
      const certo = pc ? pc.certo : corr[nucleo];
      const pd = S.pendentes.filter((p) => (p.tipo === "cortar_trecho" || p.tipo === "manter_trecho") && (w.s + w.e) / 2 >= p.inicio - 0.001 && (w.s + w.e) / 2 <= p.fim + 0.001).pop();
      const cls = [f.k ? "" : "cortada", certo ? "corrigida" : "", pd ? (pd.tipo === "manter_trecho" ? "pend-manter" : "pend-cortar") : ""].join(" ");
      return `<span class="palavra ${cls}" data-g="${w.g}" title="${certo ? "vira: " + esc(certo) : ""}">${esc(w.t)}</span>`;
    }).join(" ");
    return `<span class="tempo-frase" data-s="${f.s}">${fmt(f.s)}</span><span class="frase" data-i="${f.i}">${palavras}</span> `;
  }).join("");
  box.querySelectorAll(".tempo-frase").forEach((el) => (el.onclick = () => irParaOriginal(+el.dataset.s)));
  const W = S.dados.palavras_origem;
  let baixo = null, timer = null;
  const fraseDe = (g) => fr.find((f) => f.w.some((w) => w.g === g));
  box.onmousedown = (ev) => { const p = ev.target.closest(".palavra"); baixo = p ? +p.dataset.g : null; };
  box.onmouseup = (ev) => {
    const p = ev.target.closest(".palavra");
    const ini = baixo; baixo = null;
    if (!p || ini == null || ev.detail > 1) return;
    const fim = +p.dataset.g;
    clearTimeout(timer);
    if (S.modoSel === "palavra") {
      if (ev.shiftKey && S.ancora != null) { alternarPalavras(Math.min(S.ancora, fim), Math.max(S.ancora, fim)); return; }
      if (fim !== ini) { alternarPalavras(Math.min(ini, fim), Math.max(ini, fim)); S.ancora = fim; return; }
      timer = setTimeout(() => { S.ancora = fim; alternarPalavras(fim, fim); }, 220);
    } else {
      const f = fraseDe(ini);
      if (!f || f !== fraseDe(fim)) return;
      timer = setTimeout(() => alternarFrase(f.i), 220);
    }
  };
  box.ondblclick = (ev) => {
    clearTimeout(timer);
    const sp = ev.target.closest(".palavra");
    if (!sp) return;
    const nucleo = nucleoDe(W[+sp.dataset.g].t);
    const certo = window.prompt(`Como "${nucleo}" deveria ser escrito? (vale para a legenda e para todas as vezes que aparece)`, nucleo);
    if (certo && certo.trim() && certo.trim() !== nucleo) {
      pend({ tipo: "corrigir_palavra", errado: nucleo.toLowerCase(), certo: certo.trim() }, "corr-" + nucleo.toLowerCase());
      desenharTranscricao(); pintarBusca(false);
    }
  };
}
function irParaOriginal(t) {
  const v = $("#player");
  if (originalLike()) v.currentTime = t;
  else { const te = mapa().paraEditado(t); if (te != null) v.currentTime = te; else { S.visao = "original"; desenhar(); setTimeout(() => ($("#player").currentTime = t), 300); } }
}

/* ---------------- itens da linha do tempo que dá para ajustar (zoom, card, desfoque) ---------------- */
function itensTL() {
  const D = S.dados, out = [];
  ((D.dinamica && D.dinamica.eventos) || []).forEach((ev, i) => {
    const pT = temPend("ztempo-" + i), pA = temPend("zoom-" + i);
    const nome = ev.tipo === "punch" ? "corte" : ev.tipo === "enfase" ? "ênfase" : "aproximação";
    out.push({ k: "z", id: String(i), inicio: pT ? pT.inicio : ev.inicio, fim: pT ? pT.fim : ev.fim, ativo: pA ? pA.ativo : ev.ativo !== false,
      nome: `${nome} ${Math.round((ev.intensidade - 1) * 100)}%`, orig: { inicio: ev.inicio, fim: ev.fim }, ev });
  });
  S.pendentes.filter((p) => p.tipo === "zoom_novo").forEach((p) => out.push({ k: "zn", id: p._chave, inicio: p.inicio, fim: p.fim, ativo: true,
    nome: `${p.tipo_zoom === "punch" ? "corte" : p.tipo_zoom === "aproximacao" ? "aproximação" : "ênfase"} ${Math.round((p.intensidade - 1) * 100)}% (novo)`, novo: true }));
  ((D.roteiro && D.roteiro.cards) || []).forEach((c) => {
    const pT = temPend("ctempo-" + c.id), pA = temPend("ativo-" + c.id);
    out.push({ k: "c", id: c.id, tipo: c.tipo, inicio: pT ? pT.inicio : c.inicio, fim: pT ? pT.fim : c.fim, ativo: pA ? pA.ativo : c.ativo !== false,
      nome: `${TIPO_CARD[c.tipo] || c.tipo}: ${tituloCard(c)}`, orig: { inicio: c.inicio, fim: c.fim } });
  });
  ((D.desfoque && D.desfoque.regioes) || []).forEach((r, i) => {
    const pT = temPend("dtempo-" + i), pA = temPend("dativo-" + i);
    out.push({ k: "d", id: String(i), inicio: pT ? pT.inicio : r.inicio, fim: pT ? pT.fim : r.fim, ativo: pA ? pA.ativo : r.ativo !== false,
      nome: "desfoque" + (r.rotulo ? ": " + r.rotulo : ""), orig: { inicio: r.inicio, fim: r.fim }, area: [r.x, r.y, r.w, r.h], rotulo: r.rotulo || "" });
  });
  S.pendentes.filter((p) => p.tipo === "desfoque_novo").forEach((p) => out.push({ k: "dn", id: p._chave, inicio: p.inicio, fim: p.fim, ativo: true,
    nome: "desfoque (novo)", novo: true, area: p.area, rotulo: p.rotulo || "" }));
  return out;
}
const achaItem = (k, id) => itensTL().find((x) => x.k === k && x.id === id);

function definirTempo(it, ini, fim) {
  ini = arred(Math.max(0, ini)); fim = arred(Math.min(S._dur || fim, fim));
  if (fim - ini < 0.2) return;
  const igual = it.orig && ini === arred(it.orig.inicio) && fim === arred(it.orig.fim);
  if (it.k === "z") igual ? pend(null, "ztempo-" + it.id) : pend({ tipo: "zoom_tempo", indice: +it.id, inicio: ini, fim, antes: arred(it.orig.inicio) }, "ztempo-" + it.id);
  else if (it.k === "c") igual ? pend(null, "ctempo-" + it.id) : pend({ tipo: "card_tempo", card: it.id, inicio: ini, fim, antes: arred(it.orig.inicio) }, "ctempo-" + it.id);
  else if (it.k === "d") igual ? pend(null, "dtempo-" + it.id) : pend({ tipo: "desfoque_tempo", indice: +it.id, inicio: ini, fim, antes: arred(it.orig.inicio) }, "dtempo-" + it.id);
  else { const p = temPend(it.id); if (p) { const { _chave, ...r } = p; pend({ ...r, inicio: ini, fim }, it.id); } }
  desenharTimeline(null); desenharBarraSel(true);
}
function alternarAtivo(it) {
  const novo = !it.ativo;
  if (it.k === "z") novo === (it.ev.ativo !== false) ? pend(null, "zoom-" + it.id) : pend({ tipo: "zoom", indice: +it.id, inicio: it.ev.inicio, ativo: novo }, "zoom-" + it.id);
  else if (it.k === "c") novo === (((S.dados.roteiro.cards.find((c) => c.id === it.id)) || {}).ativo !== false) ? pend(null, "ativo-" + it.id) : pend({ tipo: "card_ativo", card: it.id, ativo: novo }, "ativo-" + it.id);
  else if (it.k === "d") novo === (S.dados.desfoque.regioes[+it.id].ativo !== false) ? pend(null, "dativo-" + it.id) : pend({ tipo: "desfoque_ativo", indice: +it.id, ativo: novo, inicio: it.inicio }, "dativo-" + it.id);
  desenharTimeline(null); desenharBarraSel(true);
}
function dividirItem(it, t) {
  if (!(t > it.inicio + 0.2 && t < it.fim - 0.2)) return;
  const n = Date.now(), fimAntigo = it.fim;
  let novo = null;
  if (it.k === "z") novo = { tipo: "zoom_novo", tipo_zoom: it.ev.tipo, intensidade: it.ev.intensidade };
  else if (it.k === "zn") { const p = temPend(it.id); novo = { tipo: "zoom_novo", tipo_zoom: p.tipo_zoom, intensidade: p.intensidade }; }
  else if (it.k === "d" || it.k === "dn") novo = { tipo: "desfoque_novo", area: it.area, rotulo: it.rotulo };
  if (!novo) return;
  definirTempo(it, it.inicio, arred(t));
  pend({ ...novo, inicio: arred(t), fim: fimAntigo }, (novo.tipo === "zoom_novo" ? "zoomnovo-" : "desfnovo-") + n);
  desenharTimeline(null); desenharBarraSel(true);
}
function selecionar(k, id, ir) {
  S.sel = { k, id };
  const it = achaItem(k, id);
  if (ir && it) $("#player").currentTime = Math.max(0, it.inicio + 0.05);
  desenharTimeline(null); desenharBarraSel(true);
}
function desenharBarraSel(forcar) {
  const el = $("#tl-sel");
  if (!el) return;
  const it = S.sel && achaItem(S.sel.k, S.sel.id);
  if (S.sel && !it) S.sel = null;
  const v = $("#player"), t = v ? v.currentTime || 0 : 0;
  const dentro = !!it && t > it.inicio + 0.2 && t < it.fim - 0.2;
  const chave = it ? [it.k, it.id, it.inicio, it.fim, it.ativo, dentro].join("|") : "-";
  if (!forcar && el._chave === chave) return;
  el._chave = chave;
  if (!it) {
    el.innerHTML = originalLike() ? "" : `<span class="dica">Clique num item da linha do tempo (zoom, card ou desfoque) para encurtar, cortar ou desligar. Arraste as bordas para mudar a duração.</span>`;
    el.onclick = null;
    return;
  }
  const dica = dentro ? "" : "title=\"Leve o vídeo para dentro do item\" disabled";
  el.innerHTML = `<span class="chip active">${NOME_K[it.k]} · ${fmt(it.inicio, true)}–${fmt(it.fim, true)} (${(it.fim - it.inicio).toFixed(1)} s)</span>
    <span class="dica" style="margin:0">${esc(it.nome)}</span>
    ${it.novo ? "" : `<button class="btn" data-a="ativo">${it.ativo ? "Desligar" : "Ligar"}</button>`}
    <button class="btn" data-a="ini" ${dica}>Começar aqui</button>
    <button class="btn" data-a="fim" ${dica}>Terminar aqui</button>
    ${it.k === "c" ? "" : `<button class="btn" data-a="div" ${dica}>Dividir aqui</button>`}
    ${it.novo ? `<button class="btn" data-a="rem">Remover</button>` : ""}
    <button class="btn" data-a="x">Fechar</button>`;
  el.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    const a = b.dataset.a, tt = $("#player").currentTime || 0;
    if (a === "ativo") alternarAtivo(it);
    else if (a === "ini") definirTempo(it, tt, it.fim);
    else if (a === "fim") definirTempo(it, it.inicio, tt);
    else if (a === "div") dividirItem(it, tt);
    else if (a === "rem") { pend(null, it.id); S.sel = null; desenharTimeline(null); desenharBarraSel(true); }
    else if (a === "x") { S.sel = null; desenharTimeline(null); desenharBarraSel(true); }
  };
}
function iniciarArrasto(e) {
  const al = e.target.closest(".al");
  if (!al) return;
  const b = al.closest(".bloco.edit");
  const it = achaItem(b.dataset.k, b.dataset.id);
  if (!it) return;
  e.preventDefault(); e.stopPropagation();
  const esq = al.classList.contains("esq"), x0 = e.clientX;
  let ini = it.inicio, fim = it.fim;
  const mover = (ev) => {
    const dt = (ev.clientX - x0) / S.pps;
    if (esq) ini = Math.min(Math.max(0, it.inicio + dt), it.fim - 0.2); else fim = Math.max(Math.min(S._dur, it.fim + dt), it.inicio + 0.2);
    b.style.left = ini * S.pps + "px"; b.style.width = Math.max(6, (fim - ini) * S.pps) + "px";
  };
  const soltar = () => {
    document.removeEventListener("mousemove", mover); document.removeEventListener("mouseup", soltar);
    S.sel = { k: it.k, id: it.id };
    definirTempo(it, ini, fim);
  };
  document.addEventListener("mousemove", mover); document.addEventListener("mouseup", soltar);
}

/* ---------------- desfoque: desenhar a área sobre o vídeo ---------------- */
function retanguloVideo(v) {
  const w0 = v.clientWidth, h0 = v.clientHeight, ar = (v.videoWidth || 16) / (v.videoHeight || 9);
  let w = w0, h = h0;
  if (w / h > ar) w = h * ar; else h = w / ar;
  return { x: (w0 - w) / 2, y: (h0 - h) / 2, w, h };
}
function montarSobre() {
  const box = $("#sobre"), v = $("#player");
  if (!box) return;
  box.classList.toggle("desenhando", !!S.desenhando);
  box._h = null;
  atualizarDesfoques(v.currentTime || 0);
  let ini = null, ret = null;
  const limitar = (n) => Math.min(1, Math.max(0, n));
  const pos = (ev) => { const r = retanguloVideo(v), b = box.getBoundingClientRect(); return { x: limitar((ev.clientX - b.left - r.x) / r.w), y: limitar((ev.clientY - b.top - r.y) / r.h) }; };
  box.onmousedown = (ev) => {
    if (!S.desenhando || !v.videoWidth) return;
    ev.preventDefault();
    ini = pos(ev);
    ret = document.createElement("div"); ret.className = "ret-desenho"; box.appendChild(ret);
    const mover = (e2) => {
      const p = pos(e2), r = retanguloVideo(v);
      ret.style.left = r.x + Math.min(ini.x, p.x) * r.w + "px"; ret.style.top = r.y + Math.min(ini.y, p.y) * r.h + "px";
      ret.style.width = Math.abs(p.x - ini.x) * r.w + "px"; ret.style.height = Math.abs(p.y - ini.y) * r.h + "px";
    };
    const soltar = (e2) => {
      document.removeEventListener("mousemove", mover); document.removeEventListener("mouseup", soltar);
      const p = pos(e2);
      ret.remove();
      const x = Math.min(ini.x, p.x), y = Math.min(ini.y, p.y), w = Math.abs(p.x - ini.x), h = Math.abs(p.y - ini.y);
      if (w < 0.01 || h < 0.01) return;
      const dur = S._dur || (S.dados.cortado && S.dados.cortado.duracao) || 0;
      const t0 = arred(Math.min(v.currentTime || 0, Math.max(0, dur - 0.5))), t1 = arred(Math.min(dur, t0 + 5));
      const chave = "desfnovo-" + Date.now();
      pend({ tipo: "desfoque_novo", inicio: t0, fim: t1, area: [arred(x * 100) / 100, arred(y * 100) / 100, arred(w * 100) / 100, arred(h * 100) / 100], rotulo: "" }, chave);
      S.desenhando = false; S.sel = { k: "dn", id: chave };
      const bd = $("#bt-desfocar"); if (bd) bd.textContent = "Desfocar área";
      box.classList.remove("desenhando"); box._h = null;
      desenharTimeline(null); desenharBarraSel(true); atualizarDesfoques(v.currentTime || 0);
      aviso("Área marcada. Ela fica desfocada por 5 s; arraste as bordas na linha do tempo para ajustar. Depois clique em <b>Aplicar alterações</b>.", 9000);
    };
    document.addEventListener("mousemove", mover); document.addEventListener("mouseup", soltar);
  };
}
function atualizarDesfoques(t) {
  const box = $("#sobre"), v = $("#player");
  if (!box || !v) return;
  let h = "";
  if (S.visao === "editado" && S.formato === "cortado" && v.videoWidth) {
    const r = retanguloVideo(v);
    for (const it of itensTL()) {
      if ((it.k !== "d" && it.k !== "dn") || !it.ativo || t < it.inicio || t >= it.fim) continue;
      const [x, y, w, hh] = it.area;
      h += `<div class="desf-ao-vivo ${S.sel && S.sel.k === it.k && S.sel.id === it.id ? "sel" : ""}" style="left:${r.x + x * r.w}px;top:${r.y + y * r.h}px;width:${w * r.w}px;height:${hh * r.h}px"></div>`;
    }
  }
  if (box._h !== h) { box._h = h; box.querySelectorAll(".desf-ao-vivo").forEach((n) => n.remove()); box.insertAdjacentHTML("afterbegin", h); }
}

/* ---------------- linha do tempo ---------------- */
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
  const blocoEd = (it, cls) => `<div class="bloco edit ${cls}${it.ativo ? "" : " off"}${S.sel && S.sel.k === it.k && S.sel.id === it.id ? " sel" : ""}" data-k="${it.k}" data-id="${esc(it.id)}" style="left:${it.inicio * S.pps}px;width:${Math.max(6, (it.fim - it.inicio) * S.pps)}px" title="${esc(it.nome)}"><i class="al esq"></i>${esc(it.nome)}<i class="al dir"></i></div>`;
  // régua
  const passo = [1, 2, 5, 10, 15, 30, 60, 120, 300].find((p) => p * S.pps >= 70) || 600;
  let regua = "";
  for (let t = 0; t <= dur; t += passo) regua += `<div class="tick" style="left:${t * S.pps}px">${fmt(t)}</div>`;
  trilhas.push(["Tempo", "regua", regua]);
  // resultados da busca
  const Wo = D.palavras_origem || [];
  if (S.busca.ach.length) {
    const m = mapa();
    const b = S.busca.ach.map((g, k) => {
      const a = Wo[g], z = Wo[g + S.busca.n - 1] || a;
      const s = originalLike() ? a.s : m.paraEditado(a.s), e = originalLike() ? z.e : m.paraEditado(z.e);
      return s == null || e == null ? "" : bloco("busca" + (k === S.busca.idx ? " atual" : ""), s, Math.max(e, s + 0.15), a.t);
    }).join("");
    trilhas.push(["Busca", "", b]);
  }
  if (originalLike()) {
    const R = S.visao === "previa" ? edlVirtual() : D.edl;
    const pendM = S.pendentes.filter((p) => p.tipo === "manter_trecho");
    const cortado = (a, b) => {
      const dentro = Wo.filter((w) => { const m = (w.s + w.e) / 2; return m >= a - 0.02 && m <= b + 0.02; });
      const txt = dentro.length ? "✂ " + dentro.map((w) => w.t).join(" ") : `pausa ${(b - a).toFixed(1)}s`;
      const pm = S.visao !== "previa" && pendM.some((p) => p.inicio < b && p.fim > a);
      return bloco("cortado" + (pm ? " pendente-manter" : ""), a, b, txt);
    };
    let v = "", ant = 0;
    R.forEach((r) => {
      if (r.s - ant > 0.05) v += cortado(ant, r.s);
      v += bloco("mantido", r.s, r.e, "");
      ant = r.e;
    });
    if (dur - ant > 0.05) v += cortado(ant, dur);
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
    const itens = itensTL();
    const z = itens.filter((i) => i.k === "z" || i.k === "zn");
    if (z.length) trilhas.push(["Zoom", "", z.map((i) => blocoEd(i, "zoom")).join("")]);
    const lay = S.formato && D.formatos[S.formato] && D.formatos[S.formato].layout;
    if (lay && lay.referencia) {
      const r = lay.referencia;
      trilhas.push(["Referência", "", bloco("ref", 0, dur, `referência ${fmt(r.inicio)}–${fmt(r.fim)} · áudio ${r.audio}`)]);
    }
    const c = itens.filter((i) => i.k === "c");
    if (c.length) {
      const tipos = [...new Set(c.map((i) => i.tipo))];
      trilhas.push(["Motion", "", c.map((i) => blocoEd(i, `card-m t${tipos.indexOf(i.tipo) % 3}`)).join("")]);
    }
    const d = itens.filter((i) => i.k === "d" || i.k === "dn");
    if (d.length) trilhas.push(["Desfoque", "", d.map((i) => blocoEd(i, "desf")).join("")]);
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
  desenharOnda(originalLike() ? D.onda_original : D.onda_cortado);
  $("#tl-inner").onmousedown = iniciarArrasto;
  $("#tl-inner").onclick = (e) => {
    const b = e.target.closest(".bloco.edit");
    if (!b) return;
    e.stopPropagation();
    selecionar(b.dataset.k, b.dataset.id, true);
  };
  const v = $("#player");
  if (v) { const a = $("#agulha"); if (a) a.style.left = (v.currentTime || 0) * S.pps + "px"; }
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
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">02</span>Motion</h1>
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
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">03</span>Legendas</h1>
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
  return `<div class="page-head"><div><h1 class="page-title"><span class="accent">04</span>Exportar</h1>
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
