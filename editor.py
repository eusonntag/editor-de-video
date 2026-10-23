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
  dinamica <id> [--estilo natural|dinamica|acelerada] [--listar] [--desligar N,N] [--previa]
  desfoque <id> [--listar] [--adicionar --inicio S --fim S --area X,Y,L,A [--rotulo T]] [--remover N] [--limpar] [--previa]
  ajustes-tempo <id>                    aplica do painel: tempo dos zooms/cards e desfoques (ajustes.json)
Formato, motion e legenda
  layout <id> horizontal|vertical|react [--sem-zoom] [opções do react]
                                        vídeo narrado: horizontal|vertical [--estilo X] [--fundo imagem]
  conferir-layout <id> <formato>
  baixar-referencia <url> [--nome arquivo]
  icones buscar "termos" | icones indexar
  imagens buscar <id> "termos em inglês" [--n 8] | imagens usar <id> <número> [--nome x] | imagens creditos <id>
  motion <id> montar|previa|galeria|render|validar --formato F [--estilo X] [--icones Y] [--tipo estilos|icones]
  legendar <id> --formato F [--estilo X] [--cor #hex] [--margem-v N] [--tamanho px]
  galeria-legendas <id> --formato F [--variar estilo|fonte|tamanho|cor|contorno|destaque|leitura|palavras|maiusculas|posicao|atual]
  legenda-config [--video <id>] [--definir k=v …] [--limpar k,k|tudo] [--json]
Entrega
  finalizar <id> --nome N [--formatos a,b] [--substituir | --nova-versao]
  verificar <id> --formato F
  painel [--video <id>] [--parar] [--sem-abrir]
  liberar-espaco [--confirmar]
  exemplo                               testa o editor com o vídeo de exemplo (sem custo)
Narração (vídeo só de animações, sem câmera)
  narrar vozes|biblioteca [--json]      vozes da conta / vozes brasileiras da biblioteca ElevenLabs
  narrar adicionar <dono> <voz> --nome X
  narrar amostras --vozes a,b --texto-arquivo f --saida pasta
  narrar custo --texto-arquivo f        caracteres, minutos e créditos
  narrar gerar <id> --texto-arquivo f --voz V [--formato vertical|horizontal] [--velocidade 1.0]
  narrar audio <id> --audio arquivo     áudio gravado pelo aluno (depois transcrever e cortar)
  narrar sobre <id> --modo inteiro|trechos|trocar --voz V …   narração num vídeo existente
  narrar remover <id>                   desfaz a narração sobre o vídeo
Fundo musical (entra no finalizar, por baixo da voz)
  musica amostras <id> --prompts "a" "b" [--duracao 15]   trechos para escolher o gênero (ElevenLabs Music)
  musica gerar <id> --prompt "..."      trilha instrumental do tamanho do vídeo
  musica usar <id> --arquivo f          música do aluno
  musica config <id> [--volume baixo|medio|alto] [--abaixar sim|nao] [--trilha arq] [--desligar]
  musica previa <id> --formato F        vídeo atual + música (musica/previa_F.mp4)
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


def _rascunho_com_zoom(t: Path) -> None:
    """O aluno aprova cortes e zooms juntos: aplica os zooms ativos no rascunho."""
    sem_zoom = t / "rascunho_sem_zoom.mp4"
    if not sem_zoom.exists():
        if not (t / "rascunho.mp4").exists():
            return
        (t / "rascunho.mp4").replace(sem_zoom)  # rascunho feito antes desta versão do editor
    rodar_script("layout.py", str(t), "horizontal", "--previa")


def cmd_cortar(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    edl = t / "edit" / "edl.json"
    exigir(edl, "cortes-base")
    render = C.TOOLS / "video-use" / "helpers" / "render.py"
    exigir(render, "instalação (video-use)")
    script = str(render.relative_to(C.RAIZ))
    pasta_trechos = t / "edit" / ("clips_draft" if a.rascunho else "clips_graded")
    try:
        C.apagar_pasta(pasta_trechos)  # trechos de um EDL antigo atrapalham a contagem
    except OSError:
        pass
    if a.rascunho:
        destino = t / "rascunho.mp4"
        C.rodar_script(script, str(edl), "-o", str(destino), "--draft", "--no-subtitles", quieto=True)
        rodar_script("palavras_timeline.py", str(edl))
        _zooms(vid, t)  # lê a duração do rascunho.mp4 novo
        destino.replace(t / "rascunho_sem_zoom.mp4")
        (t / "rosto_rascunho.json").unlink(missing_ok=True)
        _rascunho_com_zoom(t)
        print(f"✅ rascunho do corte (com os zooms): {destino}")
        return
    destino = t / "cortado.mp4"
    if (t / "narracao_extra.json").exists():
        # corte novo parte do bruto: a narração sobre o vídeo antigo deixa de valer (refazer depois)
        for arq in ("narracao_extra.json", "narracao.wav", "cortado_sem_narracao.mp4", "palavras_sem_narracao.json",
                    "dinamica_sem_narracao.json", "desfoque_sem_narracao.json", "motion/roteiro_sem_narracao.json"):
            (t / arq).unlink(missing_ok=True)
        print("aviso: a narração por IA deste vídeo foi removida pelo corte novo; refaça a narração")
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
    if a.previa:
        _rascunho_com_zoom(t)
        print(f"✅ rascunho atualizado com os zooms: {t / 'rascunho.mp4'}")


def _desfoques(vid: str) -> tuple[Path, dict]:
    arq = trab(vid) / "desfoque.json"
    return arq, C.ler_json(arq, {"regioes": []})


def _listar_desfoques(regs: list[dict]) -> None:
    if not regs:
        print("nenhum desfoque")
        return
    for i, r in enumerate(regs, 1):
        estado = "" if r.get("ativo", True) else " (desligado)"
        print(f"  {i}. {C.fmt_tempo(r['inicio'])}–{C.fmt_tempo(r['fim'])}  área x={r['x']:.2f} y={r['y']:.2f} "
              f"larg={r['w']:.2f} alt={r['h']:.2f}  {r.get('rotulo', '')}{estado}")


def cmd_desfoque(a) -> None:
    """Áreas da tela borradas (dados pessoais). Tempos na linha do tempo do vídeo CORTADO; área em frações 0 a 1."""
    vid = C.id_video(a.id)
    t = trab(vid)
    arq, d = _desfoques(vid)
    regs = d["regioes"]
    mudou = False
    if a.limpar:
        regs.clear()
        mudou = True
    if a.remover:
        for n in sorted({int(x) for x in a.remover.split(",") if x.strip()}, reverse=True):
            if 1 <= n <= len(regs):
                regs.pop(n - 1)
                mudou = True
    if a.adicionar:
        if a.inicio is None or a.fim is None or not a.area:
            raise SystemExit("✗ Para adicionar, informe --inicio, --fim e --area x,y,largura,altura (frações de 0 a 1)")
        try:
            x, y, w, h = (float(v) for v in a.area.split(","))
        except ValueError:
            raise SystemExit("✗ --area precisa de 4 números: x,y,largura,altura (ex.: 0.10,0.40,0.30,0.06)")
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1 and a.fim > a.inicio):
            raise SystemExit("✗ Área ou tempo inválidos (valores entre 0 e 1; fim maior que início)")
        regs.append({"inicio": round(a.inicio, 2), "fim": round(a.fim, 2), "x": round(x, 4), "y": round(y, 4),
                     "w": round(min(w, 1 - x), 4), "h": round(min(h, 1 - y), 4), "rotulo": a.rotulo or "", "ativo": True})
        mudou = True
    if mudou:
        regs.sort(key=lambda r: r["inicio"])
        C.gravar_json(arq, d)
        C.desmarcar_a_partir(vid, "layout")  # o desfoque entra no formato: refazer layout, motion, legenda e finalização
    if a.listar or mudou or not a.previa:
        _listar_desfoques(regs)
    if mudou:
        print("refaça o formato (layout) para o desfoque entrar no vídeo")
    if a.previa:
        _rascunho_com_zoom(t)
        print(f"✅ rascunho atualizado com o desfoque: {t / 'rascunho.mp4'}")


def cmd_ajustes_tempo(a) -> None:
    """Aplica do ajustes.json (painel) o que é só números: tempo de zooms e cards, desfoques."""
    vid = C.id_video(a.id)
    t = trab(vid)
    aj = C.ler_json(t / "ajustes.json")
    if not aj:
        raise SystemExit("✗ Não há ajustes do painel para este vídeo")
    itens = aj.get("itens", [])
    din_p, rot_p = t / "dinamica.json", t / "motion" / "roteiro.json"
    din, rot = C.ler_json(din_p), C.ler_json(rot_p)
    arq, d = _desfoques(vid)
    regs = d["regioes"]
    feitos, mexeu_din, mexeu_rot, mexeu_desf = [], False, False, False
    novos_desf = []
    for it in itens:
        tipo = it.get("tipo")
        if tipo == "zoom_tempo" and din and 0 <= it["indice"] < len(din["eventos"]):
            ev = din["eventos"][it["indice"]]
            ev["inicio"], ev["fim"] = round(it["inicio"], 2), round(it["fim"], 2)
            mexeu_din = True
        elif tipo == "zoom_novo" and din:
            din["eventos"].append({"tipo": it.get("tipo_zoom", "enfase"), "inicio": round(it["inicio"], 2),
                                   "fim": round(it["fim"], 2), "intensidade": it.get("intensidade", 1.12), "ativo": True})
            mexeu_din = True
        elif tipo == "card_tempo" and rot:
            for c in rot["cards"]:
                if c["id"] == it["card"]:
                    c["inicio"], c["fim"] = round(it["inicio"], 2), round(it["fim"], 2)
                    mexeu_rot = True
        elif tipo == "desfoque_tempo" and 0 <= it["indice"] < len(regs):
            regs[it["indice"]]["inicio"], regs[it["indice"]]["fim"] = round(it["inicio"], 2), round(it["fim"], 2)
            mexeu_desf = True
        elif tipo == "desfoque_ativo" and 0 <= it["indice"] < len(regs):
            regs[it["indice"]]["ativo"] = bool(it["ativo"])
            mexeu_desf = True
        elif tipo == "desfoque_novo":
            x, y, w, h = it["area"]
            novos_desf.append({"inicio": round(it["inicio"], 2), "fim": round(it["fim"], 2), "x": round(x, 4),
                               "y": round(y, 4), "w": round(w, 4), "h": round(h, 4),
                               "rotulo": it.get("rotulo", ""), "ativo": True})
            mexeu_desf = True
        else:
            continue
        feitos.append(tipo)
    regs.extend(novos_desf)
    if mexeu_din:
        din["eventos"].sort(key=lambda e: e["inicio"])
        C.gravar_json(din_p, din)
    if mexeu_rot:
        C.gravar_json(rot_p, rot)
    if mexeu_desf:
        regs.sort(key=lambda r: r["inicio"])
        C.gravar_json(arq, d)
    if mexeu_din or mexeu_desf:
        C.desmarcar_a_partir(vid, "layout")
    elif mexeu_rot:
        C.desmarcar_a_partir(vid, "motion")
    print(f"aplicados: {len(feitos)} ({', '.join(sorted(set(feitos))) or 'nenhum'})")
    print("refazer: " + ("layout → motion → legenda → finalizar" if (mexeu_din or mexeu_desf)
                         else "motion → legenda → finalizar" if mexeu_rot else "nada"))
    resto = sorted({i.get("tipo", "?") for i in itens} - set(feitos))
    print("fazer à mão: " + ", ".join(resto) if resto else "todos aplicados")


# ------------------------------------------------------ formato / motion / legenda ----

def cmd_layout(a, extras: list[str]) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    exigir(t / "cortado.mp4", "corte")
    if C.narrado(vid):
        if a.formato == "react":
            raise SystemExit("✗ vídeo narrado não tem câmera: use horizontal ou vertical")
        rodar_script("narrar.py", "layout", str(t), a.formato, *extras)
    else:
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
    if a.capitulo:
        args += ["--capitulo", str(a.capitulo)]
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
    args += _opcoes_legenda_video(opcoes)
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


def _opcoes_legenda_video(opcoes: dict) -> list[str]:
    """Opções da legenda guardadas no vídeo (vencem as da marca). margem_v é por formato: vai à parte."""
    extras = {k: v for k, v in opcoes.items() if k != "margem_v" and v not in ("", None)}
    return ["--opcoes", json.dumps(extras, ensure_ascii=False)] if extras else []


def cmd_galeria_legendas(a) -> None:
    vid = C.id_video(a.id)
    t = trab(vid)
    entrada, args = parametros_legenda(vid, a.formato)
    esc = C.ler_estado(vid).get("escolhas") or {}
    opcoes = esc.get("legenda_opcoes") or {}
    args += _opcoes_legenda_video(opcoes)
    margem = (opcoes.get("margem_v") or {}).get(a.formato)
    if margem and "--centro-y" not in args:
        if "--margem-v" in args:
            i = args.index("--margem-v")
            del args[i:i + 2]
        args += ["--margem-v", str(margem)]
    if esc.get("legenda_estilo"):
        args += ["--estilo", esc["legenda_estilo"]]
    variar = a.variar or "estilo"
    nome = "galeria-legendas.jpg" if variar == "estilo" else f"galeria-legendas-{variar}.jpg"
    destino = t / a.formato / nome
    rodar_script("legendas.py", str(t / "palavras.json"), "--video", str(entrada), "--galeria", str(destino),
                 "--variar", variar, *args)


def _valor_legenda(chave: str, bruto: str):
    """Converte e confere um valor do legenda-config (o aluno nunca vê isto; mensagens curtas)."""
    import legendas as L

    try:
        v = json.loads(bruto)
    except json.JSONDecodeError:
        v = bruto
    escolhas = {"estilo": list(L.ESTILOS), "fonte": list(L.FONTES_LEGENDA), "contorno": ["sem", "fino", "normal", "grosso", "brilho"],
                "fundo": ["nenhum", "tarja", "translucido", "sombreado"], "animacao": ["pop", "nenhuma"],
                "posicao": ["baixo", "centro"], "sombra": ["auto", "forte"], "destaque_tipo": ["cor", "caixa", "maior"]}
    if v is None:
        return None
    if chave in escolhas:
        v = str(v).lower()
        if chave == "fonte":
            v = next((k for k, (nome, _) in L.FONTES_LEGENDA.items() if v in (k, nome.lower())), v)
        if v not in escolhas[chave]:
            raise SystemExit(f"✗ {chave}: use {', '.join(escolhas[chave])}")
    elif chave.startswith("cor"):
        v = str(v)
        if not (v.startswith("#") and len(v) == 7):
            raise SystemExit(f"✗ {chave}: use o código da cor, ex.: #FFD400")
    elif chave in ("destaque", "maiusculas"):
        if not isinstance(v, bool):
            raise SystemExit(f"✗ {chave}: use true ou false")
    elif chave in ("escala", "subir"):
        v = float(v)
    elif chave in ("tamanho", "max_palavras"):
        v = int(v)
    return v


def cmd_legenda_config(a) -> None:
    """Opções da legenda: padrão de todos os vídeos (config/marca.json) ou só de um vídeo (estado.json)."""
    import legendas as L

    chaves = ["estilo", *[k for k in L.OPCOES if k not in ("margem_v", "centro_y")]]
    marca_p = C.CONFIG / "marca.json"
    marca = C.ler_json(marca_p, {})
    global_ = dict(marca.get("legenda") or {})
    vid = C.id_video(a.video) if a.video else None
    e = C.ler_estado(vid) if vid else {}
    esc = e.setdefault("escolhas", {}) if vid else {}
    do_video = dict(esc.get("legenda_opcoes") or {})
    if vid and esc.get("legenda_estilo"):
        do_video["estilo"] = esc["legenda_estilo"]

    alvo = do_video if vid else global_
    if a.limpar:
        for k in (chaves if a.limpar == "tudo" else a.limpar.split(",")):
            alvo.pop(k.strip(), None)
    for par in a.definir or []:
        k, _, bruto = par.partition("=")
        k = k.strip()
        if k not in chaves:
            raise SystemExit(f"✗ opção desconhecida: {k}. Opções: {', '.join(chaves)}")
        v = _valor_legenda(k, bruto)
        if v is None:
            alvo.pop(k, None)
        else:
            alvo[k] = v
    if a.definir or a.limpar:
        if vid:
            estilo = do_video.pop("estilo", None)
            if estilo:
                esc["legenda_estilo"] = estilo
            else:
                esc.pop("legenda_estilo", None)
            esc["legenda_opcoes"] = do_video
            C.salvar_estado(vid, e)
        else:
            marca["legenda"] = {k: v for k, v in global_.items() if v not in ("", None)}
            C.gravar_json(marca_p, marca)

    efetivo = {k: v for k, v in global_.items() if v not in ("", None)}
    efetivo.update({k: v for k, v in do_video.items() if k != "margem_v" and v not in ("", None)})
    res = {"padrao_todos": {k: v for k, v in global_.items() if v not in ("", None)},
           "so_este_video": do_video if vid else None, "efetivo": efetivo, "opcoes": {"estilo": "dinamica | classica | caixa | palavra", **L.OPCOES}}
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return
    print("Legenda (" + (f"vídeo {vid}" if vid else "padrão de todos os vídeos") + "):")
    for k in chaves:
        if k in efetivo:
            origem = "este vídeo" if vid and k in do_video else "padrão"
            print(f"  {k} = {efetivo[k]}  ({origem})")
    if not efetivo:
        print("  (tudo no padrão do estilo)")


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
        if (C.ler_json(t / "musica" / "musica.json", {}) or {}).get("ativo"):
            destino.parent.mkdir(parents=True, exist_ok=True)
            rodar_script("musica.py", "mixar", str(origem), str(destino), "--trab", str(t))
        else:
            C.copiar(origem, destino)
        srt = t / f / "legendas.srt"
        if srt.exists() and C.etapa_feita(vid, "legenda", f):
            shutil.copy2(srt, destino.with_suffix(".srt"))
        v = verificar_arquivo(destino, ref)
        relatorio.append(v)
        finais[f] = str(destino)
        C.marcar_etapa(vid, "final", f, arquivo=str(destino))
    narr, mp3 = C.narrado(vid), None
    if (t / "narracao.wav").exists() and ((narr and narr.get("tipo") == "ia") or (t / "narracao_extra.json").exists()):
        mp3 = C.EDITADOS / f"{nome}_narracao.mp3"
        C.rodar(["ffmpeg", "-y", "-i", str(t / "narracao.wav"), "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)])
    caps = exportar_capitulos(t, nome, ref)
    caps.update(exportar_creditos(t, nome))
    e = C.ler_estado(vid)
    e["nome_final"] = nome
    e.setdefault("arquivos_finais", {}).update(finais)
    if mp3:
        e["narracao_mp3"] = str(mp3)
    C.salvar_estado(vid, e)
    print(json.dumps({"nome": nome, "arquivos": finais, **({"narracao": str(mp3)} if mp3 else {}), **caps,
                      "verificacao": relatorio}, indent=1, ensure_ascii=False))


def exportar_creditos(t: Path, nome: str) -> dict:
    """Imagens do Wikimedia Commons usadas nos cards ativos → <nome>_creditos.txt (para a descrição do vídeo).
    CC BY e CC BY-SA exigem o crédito; domínio público entra também, por cortesia."""
    sys.path.insert(0, str(C.RAIZ / "scripts"))
    from imagens import credito_texto, ler_creditos

    creditos = ler_creditos(t)
    if not creditos:
        return {}
    usadas: list[str] = []

    def achar(v) -> None:
        if isinstance(v, dict):
            if isinstance(v.get("imagem"), str):
                usadas.append(Path(v["imagem"]).name)
            for x in v.values():
                achar(x)
        elif isinstance(v, list):
            for x in v:
                achar(x)

    roteiro = C.ler_json(t / "motion" / "roteiro.json") or {}
    for card in roteiro.get("cards", []):
        if card.get("ativo", True):
            achar(card.get("campos") or {})
    linhas = [f"- {Path(creditos[a]['titulo']).stem}: {credito_texto(creditos[a])} ({creditos[a].get('pagina', '')})"
              for a in dict.fromkeys(usadas) if a in creditos]
    if not linhas:
        return {}
    arq = C.EDITADOS / f"{nome}_creditos.txt"
    arq.write_text("Imagens:\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    return {"creditos": str(arq)}


def exportar_capitulos(t: Path, nome: str, dur: float | None) -> dict:
    """capitulos.json → <nome>_capitulos.txt, no formato da descrição do YouTube ("0:00 Título").
    O YouTube só mostra os capítulos com 3 ou mais, o primeiro em 0:00 e todos com pelo menos 10 s."""
    caps = C.ler_json(t / "capitulos.json") or []
    if not caps:
        return {}
    longo = (dur or caps[-1]["inicio"]) >= 3600

    def tempo(s: float) -> str:
        s = int(s)
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if longo else f"{s // 60}:{s % 60:02d}"

    fins = [c["inicio"] for c in caps[1:]] + [dur or caps[-1]["inicio"] + 10]
    problemas = []
    if len(caps) < 3:
        problemas.append("o YouTube pede pelo menos 3 capítulos")
    if caps[0]["inicio"] > 0:
        problemas.append("o primeiro capítulo precisa começar em 0:00")
    curtos = [c["titulo"] for c, f in zip(caps, fins) if f - c["inicio"] < 10]
    if curtos:
        problemas.append("capítulo com menos de 10 segundos: " + ", ".join(curtos))
    arq = C.EDITADOS / f"{nome}_capitulos.txt"
    arq.write_text("\n".join(f"{tempo(c['inicio'])} {c['titulo']}" for c in caps) + "\n", encoding="utf-8")
    return {"capitulos": str(arq), **({"capitulos_avisos": problemas} if problemas else {})}


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
        cmd = [sys.executable, "-X", "utf8", str(C.RAIZ / "scripts" / "painel_servidor.py"), "--porta", str(porta)]
        saida = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            # sai do "job" do programa que chamou: sem isso o painel fecha junto com ele e o vídeo para de tocar
            base_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            try:
                p = subprocess.Popen(cmd, creationflags=base_flags | 0x01000000, **saida)  # CREATE_BREAKAWAY_FROM_JOB
            except OSError:
                p = subprocess.Popen(cmd, creationflags=base_flags, **saida)
        else:
            p = subprocess.Popen(cmd, start_new_session=True, **saida)
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
        C.apagar_pasta(p)
    print(f"✅ {round(total / 1e6, 1)} MB liberados ({len(alvos)} vídeos prontos). Os vídeos em Editados e os brutos não foram tocados.")


CHAVES = {"groq": "GROQ_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY", "heygen": "HEYGEN_API_KEY"}


def testar_chave(servico: str, valor: str) -> tuple[bool, str]:
    import requests

    try:
        if servico == "groq":
            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {valor}"}, timeout=20)
        elif servico == "heygen":
            r = requests.get("https://api.heygen.com/v3/users/me", headers={"x-api-key": valor}, timeout=20)
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


def cmd_narrar(a, extras: list[str]) -> None:
    """Repassa para scripts/narrar.py (vozes, amostras, custo, gerar, audio)."""
    rodar_script("narrar.py", a.acao, *extras)


def cmd_musica(a, extras: list[str]) -> None:
    """Repassa para scripts/musica.py com a pasta de trabalho do vídeo."""
    vid = C.id_video(a.id)
    t = trab(vid)
    exigir(t / "cortado.mp4", "corte")
    rodar_script("musica.py", a.acao, str(t), *extras)


def cmd_personagens(a, extras: list[str]) -> None:
    """Repassa para scripts/personagens.py (saldo, listar, mostrar, opcoes, salvar, editar, apagar)."""
    rodar_script("personagens.py", a.acao, *extras)


def cmd_avatar(a, extras: list[str]) -> None:
    """Repassa para scripts/avatar.py (vozes, amostras, custo, gerar, juntar)."""
    rodar_script("avatar.py", a.acao, *extras)


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
    if argv[0] == "imagens":
        rodar_script("imagens.py", *argv[1:])
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
    p.add_argument("--previa", action="store_true", help="refaz o rascunho do corte com os zooms atuais")
    p = sub.add_parser("desfoque"); p.add_argument("id"); p.add_argument("--listar", action="store_true")
    p.add_argument("--adicionar", action="store_true"); p.add_argument("--inicio", type=float); p.add_argument("--fim", type=float)
    p.add_argument("--area", help="x,y,largura,altura em frações de 0 a 1 do quadro"); p.add_argument("--rotulo")
    p.add_argument("--remover", help="números da lista, separados por vírgula"); p.add_argument("--limpar", action="store_true")
    p.add_argument("--previa", action="store_true", help="refaz o rascunho do corte com os desfoques atuais")
    p = sub.add_parser("ajustes-tempo"); p.add_argument("id")
    p = sub.add_parser("layout"); p.add_argument("id"); p.add_argument("formato", choices=["horizontal", "vertical", "react"]); p.add_argument("--sem-zoom", action="store_true")
    p = sub.add_parser("conferir-layout"); p.add_argument("id"); p.add_argument("formato", choices=["horizontal", "vertical", "react"])
    p = sub.add_parser("baixar-referencia"); p.add_argument("url"); p.add_argument("--nome")
    p = sub.add_parser("motion"); p.add_argument("id"); p.add_argument("acao", choices=["montar", "previa", "galeria", "render", "validar"])
    p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"]); p.add_argument("--estilo")
    p.add_argument("--icones"); p.add_argument("--tipo", choices=["estilos", "icones"]); p.add_argument("--capitulo", type=int)
    p = sub.add_parser("legendar"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p.add_argument("--estilo", choices=["dinamica", "classica", "caixa", "palavra"]); p.add_argument("--cor"); p.add_argument("--margem-v", type=int)
    p.add_argument("--tamanho", type=int, help="tamanho da letra em px (padrão: 4,2%% da altura no vertical, 6,2%% no horizontal)")
    p = sub.add_parser("galeria-legendas"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p.add_argument("--variar", choices=["estilo", "fonte", "tamanho", "cor", "contorno", "destaque", "leitura", "palavras",
                                       "maiusculas", "posicao", "atual"])
    p = sub.add_parser("legenda-config"); p.add_argument("--video"); p.add_argument("--definir", nargs="*")
    p.add_argument("--limpar", help="opções separadas por vírgula, ou 'tudo'"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("finalizar"); p.add_argument("id"); p.add_argument("--nome", required=True); p.add_argument("--formatos")
    g = p.add_mutually_exclusive_group(); g.add_argument("--substituir", action="store_true"); g.add_argument("--nova-versao", action="store_true")
    p = sub.add_parser("verificar"); p.add_argument("id"); p.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    p = sub.add_parser("painel"); p.add_argument("--video"); p.add_argument("--parar", action="store_true")
    p.add_argument("--sem-abrir", action="store_true"); p.add_argument("--porta", type=int, default=8765)
    p = sub.add_parser("liberar-espaco"); p.add_argument("--confirmar", action="store_true")
    sub.add_parser("exemplo")
    p = sub.add_parser("narrar"); p.add_argument("acao", choices=["vozes", "biblioteca", "adicionar", "amostras", "custo", "gerar", "audio", "sobre", "remover"])
    p = sub.add_parser("musica"); p.add_argument("acao", choices=["amostras", "gerar", "usar", "config", "previa"]); p.add_argument("id")
    p = sub.add_parser("personagens"); p.add_argument("acao", choices=["saldo", "listar", "mostrar", "opcoes", "salvar", "registrar", "editar", "apagar"])
    p = sub.add_parser("avatar"); p.add_argument("acao", choices=["vozes", "amostras", "custo", "gerar", "juntar"])
    p = sub.add_parser("chave"); p.add_argument("acao", choices=["gravar", "testar", "motor"])
    p.add_argument("servico", nargs="?", choices=["groq", "elevenlabs", "heygen", "whisper", "scribe"]); p.add_argument("valor", nargs="?")

    a, extras = ap.parse_known_args(argv)
    if extras and a.cmd not in ("layout", "narrar", "musica", "personagens", "avatar"):
        ap.error("argumentos não reconhecidos: " + " ".join(extras))
    funcoes = {
        "videos": cmd_videos, "estado": cmd_estado, "nome": cmd_nome, "transcrever": cmd_transcrever,
        "custo": cmd_custo, "texto": cmd_texto, "cortes-base": cmd_cortes_base, "palavras": cmd_palavras,
        "cortar": cmd_cortar, "corte-resumo": cmd_corte_resumo, "analisar-imagem": cmd_analisar_imagem,
        "cor": cmd_cor, "dinamica": cmd_dinamica, "desfoque": cmd_desfoque, "ajustes-tempo": cmd_ajustes_tempo,
        "conferir-layout": cmd_conferir_layout,
        "baixar-referencia": cmd_baixar_referencia, "motion": cmd_motion, "legendar": cmd_legendar,
        "galeria-legendas": cmd_galeria_legendas, "legenda-config": cmd_legenda_config, "finalizar": cmd_finalizar, "verificar": cmd_verificar,
        "painel": cmd_painel, "liberar-espaco": cmd_liberar_espaco, "exemplo": cmd_exemplo, "chave": cmd_chave,
    }
    if a.cmd == "layout":
        cmd_layout(a, extras)
    elif a.cmd == "narrar":
        cmd_narrar(a, extras)
    elif a.cmd == "musica":
        cmd_musica(a, extras)
    elif a.cmd == "personagens":
        cmd_personagens(a, extras)
    elif a.cmd == "avatar":
        cmd_avatar(a, extras)
    else:
        funcoes[a.cmd](a)


if __name__ == "__main__":
    main()
