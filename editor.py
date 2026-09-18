#!/usr/bin/env python3
"""Editor de vídeo: ponto de entrada único (Windows e Mac).

Rode com qualquer Python 3.10+ (python3 ou py -3). Ele se re-executa dentro do .venv do
projeto com UTF-8. Os comandos do Claude (/video-editar etc.) chamam só este arquivo.

  <id> = nome do vídeo em videos/Para Editar sem a extensão (ex.: "minha gravação")

Instalação
  diagnostico [--json]                  checa tudo (✓/✗) e diz como resolver
  instalar [--sistema [--sim]] [--local]
Vídeos e estado
  videos [--json]                       brutos com status (⚪ novo, 🟡 em andamento, 🟢 editado)
  estado <id> [--json] [--escolha chave=valor ...]
  nome <id> [--sugerir] [--limpar "texto"] [--verificar "nome" --formatos horizontal,vertical]
Corte
  transcrever <id> [--motor groq|whisper|scribe] [--modelo X]
  custo <id>                            estimativa de custo e tempo da transcrição
  texto <id>                            transcrição em frases com tempo
  cortes-base <id> [--estilo natural|dinamica|acelerada] [--pausa 0.35]
  palavras <id> [--ver INICIO FIM]
  cortar <id> [--rascunho]
  corte-resumo <id> [--json]            antes → depois e o que foi removido
  analisar-imagem <id> [--comparar]     cor/exposição; sugere correção
  cor <id> (--filtro "..." | --remover)
  dinamica <id> [--estilo natural|dinamica|acelerada] [--listar] [--desligar N,N]
Formato, motion e legenda
  layout <id> horizontal|vertical|react [--sem-zoom] [opções do react]
  conferir-layout <id> <formato>
  baixar-referencia <url> [--nome arquivo]
  icones buscar "termos" | icones indexar
  motion <id> montar|previa|galeria|render|validar --formato F [--estilo X] [--icones Y] [--tipo estilos|icones]
  legendar <id> --formato F [--estilo X] [--cor #hex] [--margem-v N] [--tamanho px]
  galeria-legendas <id> --formato F
Entrega
  finalizar <id> --nome N [--formatos a,b] [--substituir | --nova-versao]
  verificar <id> --formato F
  painel [--video <id>] [--parar] [--sem-abrir]
  liberar-espaco [--confirmar]
  exemplo                               testa o editor com o vídeo de exemplo (sem custo)
Chaves (.env)
  chave gravar groq|elevenlabs <valor>  testa e só grava se funcionar (mostra mascarada)
  chave testar groq|elevenlabs
  chave motor groq|whisper|scribe       motor padrão da transcrição
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV_PY = RAIZ / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SEM_VENV = {"diagnostico", "instalar", "ajuda", "-h", "--help"}


def _completar_path() -> None:
    """Programas instalados agora pelo winget/Homebrew só entram no PATH de terminais novos."""
    extras = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        extras = [Path(la) / "Microsoft" / "WinGet" / "Links", Path(r"C:\Program Files\nodejs"),
                  Path(r"C:\Program Files\Git\cmd")]
        pacotes = Path(la) / "Microsoft" / "WinGet" / "Packages"
        if pacotes.exists():
            extras += [p.parent for p in pacotes.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe")]
    else:
        extras = [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    atual = os.environ.get("PATH", "").split(os.pathsep)
    novos = [str(p) for p in extras if p.exists() and str(p) not in atual]
    if novos:
        os.environ["PATH"] = os.pathsep.join(atual + novos)
    if os.name != "nt":
        # ffmpeg-full (com legendas) do Homebrew fica em opt/ e precisa vir antes do ffmpeg simples
        for p in (Path("/opt/homebrew/opt/ffmpeg-full/bin"), Path("/usr/local/opt/ffmpeg-full/bin")):
            if p.exists() and str(p) not in atual:
                os.environ["PATH"] = str(p) + os.pathsep + os.environ["PATH"]


def _reexecutar() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ajuda"
    no_venv = Path(sys.prefix).resolve() == (RAIZ / ".venv").resolve()
    if cmd in SEM_VENV:
        if not sys.flags.utf8_mode:
            sys.exit(subprocess.call([sys.executable, "-X", "utf8", __file__, *sys.argv[1:]]))
        return
    if not VENV_PY.exists():
        print("✗ O editor ainda não foi instalado neste computador. Rode /configurar-editor-video.")
        sys.exit(2)
    if not no_venv or not sys.flags.utf8_mode:
        sys.exit(subprocess.call([str(VENV_PY), "-X", "utf8", __file__, *sys.argv[1:]]))


if __name__ == "__main__":
    _completar_path()
    _reexecutar()

sys.path.insert(0, str(RAIZ / "scripts"))

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402

import comum as C  # noqa: E402

CUSTO_HORA = {"groq": ("whisper-large-v3", 0.111), "groq-turbo": ("whisper-large-v3-turbo", 0.04)}


# ------------------------------------------------------------------ auxiliares ----

def trab(vid: str) -> Path:
    return C.pasta(vid)


def exigir(caminho: Path, etapa: str) -> None:
    if not caminho.exists():
        raise SystemExit(f"✗ Falta a etapa anterior ({etapa}). Arquivo esperado: {caminho}")


gerar_onda = C.gerar_onda


def rodar_script(nome: str, *args) -> None:
    C.rodar_script(f"scripts/{nome}", *args)


def carregar_palavras_origem(vid: str) -> list[dict]:
    t = trab(vid) / "edit" / "transcripts" / f"{vid}.json"
    exigir(t, "transcrição")
    dados = json.loads(t.read_text(encoding="utf-8"))
    return [w for w in dados.get("words", []) if w.get("type", "word") == "word" and w.get("start") is not None]


def frases(palavras: list[dict], pausa: float = 0.6) -> list[list[dict]]:
    out: list[list[dict]] = []
    for w in palavras:
        if out and w["start"] - out[-1][-1]["end"] <= pausa and not out[-1][-1]["text"].endswith((".", "!", "?")):
            out[-1].append(w)
        else:
            out.append([w])
    return out


# --------------------------------------------------------------------- vídeos ----

def cmd_videos(a) -> None:
    lista = []
    for b in C.listar_brutos():
        try:
            info = C.info_video(b)
        except Exception:  # noqa: BLE001
            info = {"duracao": 0, "largura": 0, "altura": 0}
        emoji, desc = C.status_video(b.stem)
        est = C.ler_estado(b.stem)
        lista.append({"id": b.stem, "arquivo": str(b), "duracao": round(info["duracao"], 1),
                      "tempo": C.fmt_tempo(info["duracao"]), "resolucao": f"{info['largura']}x{info['altura']}",
                      "orientacao": C.orientacao(info) if info["largura"] else "?", "status": emoji, "descricao": desc,
                      "nome_final": est.get("nome_final")})
    if a.json:
        print(json.dumps(lista, indent=1, ensure_ascii=False))
        return
    if not lista:
        print(f"Nenhum vídeo em {C.PARA_EDITAR}")
        return
    for n, v in enumerate(lista, start=1):
        print(f"{n}. {v['status']} {v['id']}  ({v['tempo']}, {v['orientacao']} {v['resolucao']})  {v['descricao']}")


def cmd_estado(a) -> None:
    vid = C.id_video(a.id)
    e = C.ler_estado(vid)
    for par in a.escolha or []:
        chave, _, valor = par.partition("=")
        try:
            valor = json.loads(valor)
        except json.JSONDecodeError:
            pass
        e.setdefault("escolhas", {})[chave] = valor
    if a.escolha:
        C.salvar_estado(vid, e)
    if a.json or a.escolha:
        print(json.dumps(e, indent=1, ensure_ascii=False))
        return
    print(f"{vid}: {' '.join(C.status_video(vid))}")
    for etapa in C.ETAPAS:
        reg = (e.get("etapas") or {}).get(etapa)
        if not reg:
            continue
        if etapa in C.POR_FORMATO:
            print(f"  ✓ {C.NOME_ETAPA[etapa]}: {', '.join(reg)}")
        else:
            print(f"  ✓ {C.NOME_ETAPA[etapa]}")
    if e.get("escolhas"):
        print("  escolhas: " + ", ".join(f"{k}={v}" for k, v in e["escolhas"].items()))


def sugerir_nome(vid: str) -> str:
    import re
    import unicodedata

    try:
        pal = carregar_palavras_origem(vid)
    except SystemExit:
        return C.limpar_nome(vid)
    fr = [" ".join(w["text"] for w in f) for f in frases(pal)]
    saudacoes = ("oi", "olá", "ola", "fala", "e aí", "e ai", "bom dia", "boa tarde", "boa noite", "tudo bem")
    candidatas = [f for f in fr if len(f.split()) >= 4 and not f.lower().startswith(saudacoes)] or fr or [vid]
    texto = candidatas[0]
    palavras = [re.sub(r"[^\w-]", "", p) for p in texto.split()]
    vazias = {"eu", "que", "e", "o", "a", "os", "as", "de", "do", "da", "um", "uma", "é", "pra", "para", "né",
              "então", "aqui", "hoje", "vou", "vamos", "esse", "essa", "isso", "me", "meu", "minha", "tá", "com", "no", "na"}
    chave = [p.lower() for p in palavras if p and p.lower() not in vazias][:5]
    nome = "-".join(chave) or vid
    nome = unicodedata.normalize("NFC", nome)
    return C.limpar_nome(nome)


def cmd_nome(a) -> None:
    if a.limpar is not None:
        print(C.limpar_nome(a.limpar))
        return
    vid = C.id_video(a.id)
    if a.verificar is not None:
        nome = C.limpar_nome(a.verificar)
        formatos = (a.formatos or "horizontal").split(",")
        existentes = [str(C.caminho_final(nome, f)) for f in formatos if C.caminho_final(nome, f).exists()]
        print(json.dumps({"nome": nome, "existe": bool(existentes), "arquivos": existentes,
                          "alternativa": C.proxima_versao_livre(nome, formatos[0]).name if existentes else None},
                         ensure_ascii=False))
        return
    est = C.ler_estado(vid)
    print(est.get("nome_final") or sugerir_nome(vid))


# ------------------------------------------------------------------- corte ----

def cmd_transcrever(a) -> None:
    vid = C.id_video(a.id)
    bruto = C.achar_bruto(vid)
    t = trab(vid)
    args = [str(bruto), "--edit-dir", str(t / "edit")]
    if a.motor:
        args += ["--motor", a.motor]
    if a.modelo:
        args += ["--modelo", a.modelo]
    rodar_script("transcrever.py", *args)
    gerar_onda(bruto, t / "onda_original.json")
    if not (t / "painel_original.mp4").exists():
        C.gerar_proxy(bruto, t / "painel_original.mp4")
    dados = json.loads((t / "edit" / "transcripts" / f"{vid}.json").read_text(encoding="utf-8"))
    C.marcar_etapa(vid, "transcricao", motor=dados.get("engine", a.motor or "auto"))
    print(f"✅ transcrição pronta: {len([w for w in dados['words'] if w.get('type') == 'word'])} palavras")


def cmd_custo(a) -> None:
    vid = C.id_video(a.id)
    dur = C.info_video(C.achar_bruto(vid))["duracao"]
    motor = C.ler_env("TRANSCRICAO_MOTOR") or ("groq" if C.ler_env("GROQ_API_KEY") else "whisper")
    horas = dur / 3600
    res = {"duracao": C.fmt_tempo(dur), "motor": motor}
    if motor == "groq":
        res["custo"] = (f"grátis no plano gratuito do Groq (até 2 h de áudio por hora e 8 h por dia); "
                        f"no pago, cerca de US$ {max(0.01, horas * 0.111):.2f}".replace(".", ","))
        res["tempo"] = "cerca de 5 a 20 segundos" if dur < 600 else "cerca de 1 minuto"
    elif motor == "whisper":
        res["custo"] = "grátis (roda no seu computador)"
        res["tempo"] = f"cerca de {C.fmt_tempo(dur * 1.1)} (1x a duração do vídeo)"
    else:
        res["custo"] = f"cobrado pela ElevenLabs por minuto de áudio ({dur / 60:.1f} min)"
        res["tempo"] = "cerca de 20 a 60 segundos"
    print(json.dumps(res, ensure_ascii=False))


def cmd_texto(a) -> None:
    vid = C.id_video(a.id)
    for f in frases(carregar_palavras_origem(vid)):
        print(f"[{C.fmt_tempo(f[0]['start'])}] {' '.join(w['text'] for w in f)}")


def cmd_cortes_base(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    exigir(t / "edit" / "transcripts" / f"{vid}.json", "transcrição")
    pausa = a.pausa or (0.2 if a.estilo == "acelerada" else 0.35)
    rodar_script("edl_base.py", str(C.achar_bruto(vid)), "--edit-dir", str(t / "edit"), "--pausa", str(pausa))
    if a.estilo:
        e = C.ler_estado(vid)
        e.setdefault("escolhas", {})["estilo_edicao"] = a.estilo
        C.salvar_estado(vid, e)
    print(f"revisão: {t / 'edit' / 'revisao.md'}")


def cmd_palavras(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    args = [str(t / "edit" / "edl.json")]
    if a.ver:
        args += ["--ver", str(a.ver[0]), str(a.ver[1])]
    rodar_script("palavras_timeline.py", *args)


def _zooms(vid: str, t: Path) -> None:
    """Gera os zooms do estilo escolhido, a menos que os atuais já sejam deste mesmo corte."""
    estilo = (C.ler_estado(vid).get("escolhas") or {}).get("estilo_edicao") or "natural"
    arq = t / "dinamica.json"
    if arq.exists():
        import dinamica

        atual = json.loads(arq.read_text(encoding="utf-8"))
        if atual.get("edl_hash") == dinamica.hash_edl(t) and atual.get("estilo") == estilo:
            return
    rodar_script("dinamica.py", str(t), "--estilo", estilo)


def cmd_cortar(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    edl = t / "edit" / "edl.json"
    exigir(edl, "cortes-base")
    render = C.TOOLS / "video-use" / "helpers" / "render.py"
    exigir(render, "instalação (video-use)")
    script = str(render.relative_to(C.RAIZ))
    pasta_trechos = t / "edit" / ("clips_draft" if a.rascunho else "clips_graded")
    shutil.rmtree(pasta_trechos, ignore_errors=True)  # trechos de um EDL antigo atrapalham a contagem
    if a.rascunho:
        destino = t / "rascunho.mp4"
        C.rodar_script(script, str(edl), "-o", str(destino), "--draft", "--no-subtitles", quieto=True)
        rodar_script("palavras_timeline.py", str(edl))
        _zooms(vid, t)
        print(f"✅ rascunho do corte: {destino}")
        return
    destino = t / "cortado.mp4"
    C.rodar_script(script, str(edl), "-o", str(destino), "--no-subtitles", quieto=True)
    rodar_script("palavras_timeline.py", str(edl))
    gerar_onda(destino, t / "onda_cortado.json")
    C.desmarcar_a_partir(vid, "corte")
    C.marcar_etapa(vid, "corte")
    (t / "rosto.json").unlink(missing_ok=True)
    _zooms(vid, t)
    resumo = resumo_corte(vid)
    print(f"✅ corte pronto: {C.fmt_tempo(resumo['original'])} → {C.fmt_tempo(resumo['final'])}. Arquivo: {destino}")


def resumo_corte(vid: str) -> dict:
    """Compara a transcrição com o EDL: o que saiu e por quê (pausa ou frase)."""
    t = trab(vid)
    edl = json.loads((t / "edit" / "edl.json").read_text(encoding="utf-8"))
    pal = carregar_palavras_origem(vid)
    ranges = sorted(((float(r["start"]), float(r["end"])) for r in edl["ranges"]))
    dur_orig = C.info_video(C.achar_bruto(vid))["duracao"]
    dur_final = sum(b - a for a, b in ranges)
    if (t / "cortado.mp4").exists():
        dur_final = C.info_video(t / "cortado.mp4")["duracao"]

    def mantida(w):
        m = (w["start"] + w["end"]) / 2
        return any(a <= m <= b for a, b in ranges)

    removidas, atual = [], []
    for w in pal:
        if mantida(w):
            if atual:
                removidas.append(atual)
                atual = []
        else:
            atual.append(w)
    if atual:
        removidas.append(atual)
    frases_rem = [{"inicio": round(f[0]["start"], 2), "fim": round(f[-1]["end"], 2),
                   "texto": " ".join(w["text"] for w in f)} for f in removidas]
    pausas = []
    ant = 0.0
    for a, b in ranges:
        if a - ant > 0.5:
            pausas.append({"inicio": round(ant, 2), "fim": round(a, 2), "duracao": round(a - ant, 2)})
        ant = b
    if dur_orig - ant > 0.5:
        pausas.append({"inicio": round(ant, 2), "fim": round(dur_orig, 2), "duracao": round(dur_orig - ant, 2)})
    return {"original": round(dur_orig, 2), "final": round(dur_final, 2), "trechos": len(ranges),
            "frases_removidas": frases_rem, "pausas_longas": pausas,
            "silencio_removido": round(dur_orig - dur_final - sum(f["fim"] - f["inicio"] for f in frases_rem), 1)}


def cmd_corte_resumo(a) -> None:
    vid = C.id_video(a.id)
    r = resumo_corte(vid)
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return
    print(f"{C.fmt_tempo(r['original'])} → {C.fmt_tempo(r['final'])} ({r['trechos']} trechos)")
    print(f"silêncios removidos: cerca de {max(0, r['silencio_removido']):.0f} s")
    for f in r["frases_removidas"]:
        print(f"  ✂ [{C.fmt_tempo(f['inicio'])}] \"{f['texto']}\"")


def cmd_analisar_imagem(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    args = [str(C.achar_bruto(vid)), "--rosto", str(t / "rosto_original.json")]
    if a.filtro:
        args += ["--filtro", a.filtro]
    if a.comparar:
        args += ["--comparar", str(t / "cor-comparacao.jpg")]
    rodar_script("analisar_imagem.py", *args)


def cmd_cor(a) -> None:
    vid = C.id_video(a.id)
    edl_p = trab(vid) / "edit" / "edl.json"
    exigir(edl_p, "cortes-base")
    edl = json.loads(edl_p.read_text(encoding="utf-8"))
    edl["grade"] = "none" if a.remover else a.filtro
    edl_p.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    print("correção de cor " + ("removida" if a.remover else "gravada") + ": refaça o corte (editor.py cortar)")


def cmd_dinamica(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    arq = t / "dinamica.json"
    if a.estilo:
        exigir(t / "palavras.json", "corte")
        rodar_script("dinamica.py", str(t), "--estilo", a.estilo)
        e = C.ler_estado(vid)
        e.setdefault("escolhas", {})["estilo_edicao"] = a.estilo
        C.salvar_estado(vid, e)
    if a.desligar:
        d = json.loads(arq.read_text(encoding="utf-8"))
        ativos = [ev for ev in d["eventos"] if ev.get("ativo", True)]
        for n in (int(x) for x in a.desligar.split(",") if x.strip()):
            if 1 <= n <= len(ativos):
                ativos[n - 1]["ativo"] = False
        arq.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.listar or a.desligar or a.estilo:
        rodar_script("dinamica.py", str(t), "--listar")


# ------------------------------------------------------ formato / motion / legenda ----

def cmd_layout(a, extras: list[str]) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    exigir(t / "cortado.mp4", "corte")
    args = [str(t), a.formato, *extras]
    if a.sem_zoom:
        args.append("--sem-zoom")
    rodar_script("layout.py", *args)
    C.desmarcar_a_partir(vid, "layout", a.formato)
    lay = json.loads((t / a.formato / "layout.json").read_text(encoding="utf-8"))
    C.marcar_etapa(vid, "layout", a.formato, zooms=lay.get("zooms", 0))
    e = C.ler_estado(vid)
    formatos = e.setdefault("escolhas", {}).setdefault("formatos", [])
    if a.formato not in formatos:
        formatos.append(a.formato)
    C.salvar_estado(vid, e)


def folha_quadros(video: Path, tempos: list[float], destino: Path, altura: int = 540) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ent = []
        for i, tt in enumerate(tempos):
            p = Path(tmp) / f"q{i}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale=-2:{altura}", str(p)], check=True)
            ent += ["-i", str(p)]
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ent, "-filter_complex", f"hstack=inputs={len(tempos)}",
                        str(destino)], check=True)


def cmd_conferir_layout(a) -> None:
    vid = C.id_video(a.id)
    base = trab(vid) / a.formato / "base.mp4"
    exigir(base, f"layout {a.formato}")
    d = C.info_video(base)["duracao"]
    destino = trab(vid) / a.formato / "conferencia.jpg"
    folha_quadros(base, [d * 0.15, d * 0.5, d * 0.85], destino)
    print(f"conferência: {destino}")


def cmd_baixar_referencia(a) -> None:
    C.REFERENCIAS.mkdir(parents=True, exist_ok=True)
    ok = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True).returncode == 0
    if not ok:
        print("⏳ instalando o yt-dlp (só na primeira vez)…", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"], check=True)
    nome = C.limpar_nome(a.nome) if a.nome else "%(title).60s"
    saida = str(C.REFERENCIAS / f"{nome}.%(ext)s")
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                        "--merge-output-format", "mp4", "--no-playlist", "-o", saida, "--print", "after_move:filepath",
                        a.url], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit("✗ não consegui baixar: " + (r.stderr or "")[-500:])
    caminho = [linha for linha in r.stdout.splitlines() if linha.strip()][-1]
    print(f"✅ referência baixada: {caminho}")


def cmd_icones(a, extras: list[str]) -> None:
    rodar_script("icones.py", *extras)


def cmd_motion(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    args = [a.acao, str(t), "--formato", a.formato]
    if a.estilo:
        args += ["--estilo", a.estilo]
    if a.icones:
        args += ["--icones", a.icones]
    if a.tipo:
        args += ["--tipo", a.tipo]
    if a.acao in ("montar", "previa", "galeria", "render"):
        exigir(t / a.formato / "layout.json", f"layout {a.formato}")
    rodar_script("motion.py", *args)
    if a.acao == "render":
        C.desmarcar_a_partir(vid, "motion", a.formato)
        C.marcar_etapa(vid, "motion", a.formato)


def parametros_legenda(vid: str, formato: str) -> tuple[Path, list[str]]:
    t = trab(vid)
    lay_p = t / formato / "layout.json"
    exigir(lay_p, f"layout {formato}")
    lay = json.loads(lay_p.read_text(encoding="utf-8"))
    entrada = t / formato / "animado.mp4"
    if not (C.etapa_feita(vid, "motion", formato) and entrada.exists()):
        entrada = t / formato / "base.mp4"
    args = []
    leg = lay.get("legenda") or {}
    if leg.get("centro_y"):
        args += ["--centro-y", str(leg["centro_y"])]
    elif leg.get("margem_v"):
        args += ["--margem-v", str(leg["margem_v"])]
    return entrada, args


def cmd_legendar(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    entrada, args = parametros_legenda(vid, a.formato)
    e = C.ler_estado(vid)
    esc = e.setdefault("escolhas", {})
    # ajustes pedidos ficam guardados: refazer a legenda depois mantém cor, tamanho e posição
    opcoes = esc.setdefault("legenda_opcoes", {})
    if a.cor:
        opcoes["cor"] = a.cor
    if a.tamanho:
        opcoes["tamanho"] = a.tamanho
    if a.margem_v:
        opcoes.setdefault("margem_v", {})[a.formato] = a.margem_v
    estilo = a.estilo or esc.get("legenda_estilo")
    if estilo:
        esc["legenda_estilo"] = estilo
        args += ["--estilo", estilo]
    if opcoes.get("cor"):
        args += ["--cor", opcoes["cor"]]
    if opcoes.get("tamanho"):
        args += ["--tamanho", str(opcoes["tamanho"])]
    margem = (opcoes.get("margem_v") or {}).get(a.formato)
    if margem and "--centro-y" not in args:
        if "--margem-v" in args:
            i = args.index("--margem-v")
            del args[i:i + 2]
        args += ["--margem-v", str(margem)]
    C.salvar_estado(vid, e)
    destino = t / a.formato / "final.mp4"
    rodar_script("legendas.py", str(t / "palavras.json"), "--video", str(entrada), "--saida-ass",
                 str(t / a.formato / "legendas.ass"), "--queimar", str(destino), *args)
    C.marcar_etapa(vid, "legenda", a.formato, estilo=estilo or "dinamica")
    print(f"✅ legenda pronta: {destino}")


def cmd_galeria_legendas(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    entrada, args = parametros_legenda(vid, a.formato)
    destino = t / a.formato / "galeria-legendas.jpg"
    rodar_script("legendas.py", str(t / "palavras.json"), "--video", str(entrada), "--galeria", str(destino), *args)


# ------------------------------------------------------------------- entrega ----

def verificar_arquivo(video: Path, referencia: float | None) -> dict:
    info = C.info_video(video)
    res = {"arquivo": str(video), "duracao": round(info["duracao"], 2), "resolucao": f"{info['largura']}x{info['altura']}",
           "fps": round(info["fps"], 2), "audio": info["tem_audio"], "ok": info["tem_audio"]}
    if referencia:
        res["diferenca_duracao"] = round(info["duracao"] - referencia, 2)
        res["ok"] = res["ok"] and abs(res["diferenca_duracao"]) < 0.5
    return res


def cmd_verificar(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    video = C.arquivo_atual(vid, a.formato)
    ref = C.info_video(t / "cortado.mp4")["duracao"] if (t / "cortado.mp4").exists() else None
    res = verificar_arquivo(video, ref)
    d = res["duracao"]
    destino = t / a.formato / "verificacao.jpg"
    folha_quadros(video, [min(1.0, d * 0.05), d * 0.5, max(0, d - 1.0)], destino, 360)
    res["quadros"] = str(destino)
    print(json.dumps(res, indent=1, ensure_ascii=False))


def cmd_finalizar(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    e = C.ler_estado(vid)
    nome = C.limpar_nome(a.nome)
    formatos = a.formatos.split(",") if a.formatos else (e.get("escolhas", {}).get("formatos") or ["horizontal"])
    existentes = [f for f in formatos if C.caminho_final(nome, f).exists()]
    if existentes and not (a.substituir or a.nova_versao):
        print(json.dumps({"existe": [str(C.caminho_final(nome, f)) for f in existentes]}, ensure_ascii=False))
        sys.exit(3)
    ref = C.info_video(t / "cortado.mp4")["duracao"] if (t / "cortado.mp4").exists() else None
    finais, relatorio = {}, []
    for f in formatos:
        origem = C.arquivo_atual(vid, f)
        if origem.name == "cortado.mp4" and f != "horizontal":
            raise SystemExit(f"✗ o formato {f} ainda não foi montado (layout)")
        destino = C.proxima_versao_livre(nome, f) if (a.nova_versao and C.caminho_final(nome, f).exists()) \
            else C.caminho_final(nome, f)
        C.copiar(origem, destino)
        srt = t / f / "legendas.srt"
        if srt.exists() and C.etapa_feita(vid, "legenda", f):
            shutil.copy2(srt, destino.with_suffix(".srt"))
        v = verificar_arquivo(destino, ref)
        relatorio.append(v)
        finais[f] = str(destino)
        C.marcar_etapa(vid, "final", f, arquivo=str(destino))
    e = C.ler_estado(vid)
    e["nome_final"] = nome
    e.setdefault("arquivos_finais", {}).update(finais)
    C.salvar_estado(vid, e)
    print(json.dumps({"nome": nome, "arquivos": finais, "verificacao": relatorio}, indent=1, ensure_ascii=False))


def cmd_painel(a) -> None:
    import time
    import urllib.request
    import webbrowser

    porta = a.porta
    base = f"http://127.0.0.1:{porta}"
    pid_arq = C.TRABALHO / "painel.pid"

    def vivo() -> bool:
        try:
            with urllib.request.urlopen(base + "/api/ping", timeout=1.5) as r:
                return r.status == 200
        except OSError:
            return False

    if a.parar:
        if vivo():
            try:
                urllib.request.urlopen(urllib.request.Request(base + "/api/parar", method="POST"), timeout=2)
            except OSError:
                pass
        pid_arq.unlink(missing_ok=True)
        print("painel fechado")
        return
    if not vivo():
        C.TRABALHO.mkdir(parents=True, exist_ok=True)
        log = open(C.TRABALHO / "painel.log", "w", encoding="utf-8")
        flags = {}
        if os.name == "nt":
            flags["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            flags["start_new_session"] = True
        p = subprocess.Popen([sys.executable, "-X", "utf8", str(C.RAIZ / "scripts" / "painel_servidor.py"),
                              "--porta", str(porta)], stdout=log, stderr=log, stdin=subprocess.DEVNULL, **flags)
        pid_arq.write_text(str(p.pid), encoding="utf-8")
        for _ in range(40):
            if vivo():
                break
            time.sleep(0.25)
        else:
            raise SystemExit(f"✗ o painel não abriu; veja {C.TRABALHO / 'painel.log'}")
    url = f"http://localhost:{porta}/" + (f"#/video/{C.id_video(a.video)}" if a.video else "")
    if not a.sem_abrir:
        webbrowser.open(url)
    print(f"painel: {url}")


def tamanho_pasta(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def cmd_liberar_espaco(a) -> None:
    alvos = []
    for pasta in sorted(C.TRABALHO.iterdir()) if C.TRABALHO.exists() else []:
        if not pasta.is_dir():
            continue
        e = C.ler_estado(pasta.name)
        finais = [Path(f) for f in (e.get("arquivos_finais") or {}).values()]
        if finais and all(f.exists() for f in finais):
            alvos.append((pasta, tamanho_pasta(pasta)))
    total = sum(s for _, s in alvos)
    if not a.confirmar:
        print(json.dumps({"pastas": [{"video": p.name, "mb": round(s / 1e6, 1)} for p, s in alvos],
                          "total_mb": round(total / 1e6, 1)}, ensure_ascii=False))
        return
    for p, _ in alvos:
        if p.resolve().parent != C.TRABALHO.resolve():
            continue  # segurança: só apaga dentro de videos/.trabalho
        shutil.rmtree(p)
    print(f"✅ {round(total / 1e6, 1)} MB liberados ({len(alvos)} vídeos prontos). Os vídeos em Editados e os brutos não foram tocados.")


CHAVES = {"groq": "GROQ_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}


def testar_chave(servico: str, valor: str) -> tuple[bool, str]:
    import requests

    try:
        if servico == "groq":
            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {valor}"}, timeout=20)
        else:
            r = requests.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": valor}, timeout=20)
    except requests.RequestException:
        return False, "sem conexão com a internet (ou o serviço está fora do ar)"
    if r.status_code == 200:
        return True, "chave válida"
    if servico == "elevenlabs" and r.status_code == 401 and "missing_permissions" in r.text:
        return True, "chave válida (com permissões limitadas, suficiente para transcrever)"
    if r.status_code in (401, 403):
        return False, "chave recusada: confira se copiou inteira, sem espaços"
    if r.status_code == 429:
        return True, "chave válida (limite de uso atingido agora; volta em alguns minutos)"
    return False, f"o serviço respondeu {r.status_code}"


def cmd_chave(a) -> None:
    if a.acao == "motor":
        C.gravar_env("TRANSCRICAO_MOTOR", a.valor)
        print(f"motor de transcrição: {a.valor}")
        return
    nome_env = CHAVES[a.servico]
    if a.acao == "gravar":
        valor = (a.valor or sys.stdin.readline()).strip().strip('"').strip("'")
        ok, msg = testar_chave(a.servico, valor)
        if not ok:
            print(json.dumps({"ok": False, "mensagem": msg}, ensure_ascii=False))
            sys.exit(1)
        C.gravar_env(nome_env, valor)
        print(json.dumps({"ok": True, "mensagem": msg, "chave": C.mascarar(valor)}, ensure_ascii=False))
        return
    valor = C.ler_env(nome_env)
    if not valor:
        print(json.dumps({"ok": False, "mensagem": "chave não configurada"}, ensure_ascii=False))
        sys.exit(1)
    ok, msg = testar_chave(a.servico, valor)
    print(json.dumps({"ok": ok, "mensagem": msg, "chave": C.mascarar(valor)}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


def cmd_exemplo(a) -> None:
    rodar_script("exemplo.py")


# ------------------------------------------------------------------------ main ----

def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("ajuda", "-h", "--help"):
        print(__doc__)
        return
    if argv[0] in ("diagnostico", "instalar"):
        import instalacao

        sys.exit(instalacao.main(argv))
    if argv[0] == "icones":
        rodar_script("icones.py", *argv[1:])
        return

    ap = argparse.ArgumentParser(prog="editor.py", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("videos"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("estado"); p.add_argument("id"); p.add_argument("--json", action="store_true"); p.add_argument("--escolha", nargs="*")
    p = sub.add_parser("nome"); p.add_argument("id"); p.add_argument("--sugerir", action="store_true")
    p.add_argument("--limpar"); p.add_argument("--verificar"); p.add_argument("--formatos")
    p = sub.add_parser("transcrever"); p.add_argument("id"); p.add_argument("--motor", choices=["groq", "whisper", "scribe"]); p.add_argument("--modelo")
    p = sub.add_parser("custo"); p.add_argument("id")
    p = sub.add_parser("texto"); p.add_argument("id")
    p = sub.add_parser("cortes-base"); p.add_argument("id"); p.add_argument("--estilo", choices=["natural", "dinamica", "acelerada"]); p.add_argument("--pausa", type=float)
    p = sub.add_parser("palavras"); p.add_argument("id"); p.add_argument("--ver", nargs=2, type=float)
    p = sub.add_parser("cortar"); p.add_argument("id"); p.add_argument("--rascunho", action="store_true")
    p = sub.add_parser("corte-resumo"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("analisar-imagem"); p.add_argument("id"); p.add_argument("--comparar", action="store_true"); p.add_argument("--filtro")
    p = sub.add_parser("cor"); p.add_argument("id"); g = p.add_mutually_exclusive_group(required=True); g.add_argument("--filtro"); g.add_argument("--remover", action="store_true")
    p = sub.add_parser("dinamica"); p.add_argument("id"); p.add_argument("--estilo", choices=["natural", "dinamica", "acelerada"])
    p.add_argument("--listar", action="store_true"); p.add_argument("--desligar")
    p = sub.add_parser("layout"); p.add_argument("id"); p.add_argument("formato", choices=["horizontal", "vertical", "react"]); p.add_argument("--sem-zoom", action="store_true")
    p = sub.add_parser("conferir-layout"); p.add_argument("id"); p.add_argument("formato", choices=["horizontal", "vertical", "react"])
    p = sub.add_parser("baixar-referencia"); p.add_argument("url"); p.add_argument("--nome")
    p = sub.add_parser("motion"); p.add_argument("id"); p.add_argument("acao", choices=["montar", "previa", "galeria", "render", "validar"])
    p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"]); p.add_argument("--estilo")
    p.add_argument("--icones"); p.add_argument("--tipo", choices=["estilos", "icones"])
    p = sub.add_parser("legendar"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p.add_argument("--estilo", choices=["dinamica", "classica", "caixa", "palavra"]); p.add_argument("--cor"); p.add_argument("--margem-v", type=int)
    p.add_argument("--tamanho", type=int, help="tamanho da letra em px (padrão: 4,2%% da altura no vertical, 6,2%% no horizontal)")
    p = sub.add_parser("galeria-legendas"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p = sub.add_parser("finalizar"); p.add_argument("id"); p.add_argument("--nome", required=True); p.add_argument("--formatos")
    g = p.add_mutually_exclusive_group(); g.add_argument("--substituir", action="store_true"); g.add_argument("--nova-versao", action="store_true")
    p = sub.add_parser("verificar"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p = sub.add_parser("painel"); p.add_argument("--video"); p.add_argument("--parar", action="store_true")
    p.add_argument("--sem-abrir", action="store_true"); p.add_argument("--porta", type=int, default=8765)
    p = sub.add_parser("liberar-espaco"); p.add_argument("--confirmar", action="store_true")
    sub.add_parser("exemplo")
    p = sub.add_parser("chave"); p.add_argument("acao", choices=["gravar", "testar", "motor"])
    p.add_argument("servico", nargs="?", choices=["groq", "elevenlabs", "whisper", "scribe"]); p.add_argument("valor", nargs="?")

    a, extras = ap.parse_known_args(argv)
    if extras and a.cmd != "layout":
        ap.error("argumentos não reconhecidos: " + " ".join(extras))
    funcoes = {
        "videos": cmd_videos, "estado": cmd_estado, "nome": cmd_nome, "transcrever": cmd_transcrever,
        "custo": cmd_custo, "texto": cmd_texto, "cortes-base": cmd_cortes_base, "palavras": cmd_palavras,
        "cortar": cmd_cortar, "corte-resumo": cmd_corte_resumo, "analisar-imagem": cmd_analisar_imagem,
        "cor": cmd_cor, "dinamica": cmd_dinamica, "conferir-layout": cmd_conferir_layout,
        "baixar-referencia": cmd_baixar_referencia, "motion": cmd_motion, "legendar": cmd_legendar,
        "galeria-legendas": cmd_galeria_legendas, "finalizar": cmd_finalizar, "verificar": cmd_verificar,
        "painel": cmd_painel, "liberar-espaco": cmd_liberar_espaco, "exemplo": cmd_exemplo, "chave": cmd_chave,
    }
    if a.cmd == "layout":
        cmd_layout(a, extras)
    else:
        funcoes[a.cmd](a)


if __name__ == "__main__":
    main()
