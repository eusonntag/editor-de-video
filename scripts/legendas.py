"""Gera legendas .ass (estilizadas) a partir de palavras.json e, opcionalmente, queima no vídeo.

Estilos:
  dinamica  (padrão) -> 1–3 palavras, MAIÚSCULAS, contorno grosso, palavra falada destacada em cor
                        e leve "pop" na entrada. Reels/TikTok.
  classica           -> frases de até ~7 palavras, caixa normal, sem destaque. YouTube/aulas.
  caixa              -> 2–4 palavras em tarja (caixa sólida), palavra falada em cor. Estilo TikTok.
  palavra            -> uma palavra por vez, grande, com "pop". Ritmo acelerado.

As fontes vêm de assets/fontes (TTF livres), então o resultado é igual no Windows e no Mac.
A legenda é SEMPRE a última camada: rode isto depois do motion.

Uso:
  python -X utf8 scripts/legendas.py palavras.json --video base.mp4 --queimar final.mp4
  opções: --estilo dinamica|classica|caixa|palavra  --fonte "Montserrat Black"  --cor "#FFD400"
          --posicao baixo|centro  --margem-v 380  --centro-y 960  --tamanho 80  --max-palavras 3
  galeria: python -X utf8 scripts/legendas.py palavras.json --video base.mp4 --galeria galeria.jpg [--em 4.2]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import FONTES, ler_marca  # noqa: E402

PONTUACAO_QUEBRA = tuple(".,!?;:…")

ESTILOS = {
    "dinamica": {"nome": "Dinâmica", "fonte": "Montserrat Black", "max_palavras": 3, "max_chars": 18,
                 "maiusculas": True, "destaque": True, "caixa": False, "escala": 1.0},
    "classica": {"nome": "Clássica", "fonte": "Inter", "negrito": True, "max_palavras": 7, "max_chars": 38,
                 "maiusculas": False, "destaque": False, "caixa": False, "escala": 0.78},
    "caixa": {"nome": "Caixa", "fonte": "Poppins Black", "max_palavras": 4, "max_chars": 22,
              "maiusculas": False, "destaque": True, "caixa": True, "escala": 0.82},
    "palavra": {"nome": "Palavra", "fonte": "Montserrat Black", "max_palavras": 1, "max_chars": 14,
                "maiusculas": True, "destaque": False, "caixa": False, "escala": 1.35},
}
COR_PADRAO = "#FFD400"


def cor_ass(hex_cor: str, alfa: str = "00") -> str:
    h = hex_cor.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa}{b}{g}{r}".upper()


def luminancia(hex_cor: str) -> float:
    h = hex_cor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ts(seg: float) -> str:
    cs = int(round(max(0.0, seg) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def limpar(texto: str) -> str:
    return texto.replace("\\", "").replace("{", "").replace("}", "").strip()


def dimensoes(video: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


def agrupar(palavras: list[dict], max_palavras: int, max_chars: int, pausa: float) -> list[list[dict]]:
    blocos: list[list[dict]] = []
    atual: list[dict] = []
    for w in palavras:
        if atual:
            gap = w["start"] - atual[-1]["end"]
            chars = sum(len(x["text"]) + 1 for x in atual) + len(w["text"])
            if gap > pausa or len(atual) >= max_palavras or chars > max_chars:
                blocos.append(atual)
                atual = []
        atual.append(w)
        if w["text"].endswith(PONTUACAO_QUEBRA):
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return blocos


def gerar_ass(palavras: list[dict], largura: int, altura: int, estilo: str = "dinamica",
              fonte: str | None = None, cor: str | None = None, posicao: str = "baixo",
              tamanho: int | None = None, max_palavras: int | None = None,
              margem_v: int | None = None, centro_y: int | None = None,
              cor_caixa: str | None = None) -> str:
    cfg = ESTILOS[estilo]
    retrato = altura > largura
    fonte = fonte or cfg["fonte"]
    cor = cor or COR_PADRAO
    if tamanho is None:
        tamanho = int(altura * (0.042 if retrato else 0.062) * cfg["escala"])
    max_palavras = max_palavras or cfg["max_palavras"]
    if margem_v is None:
        margem_v = int(altura * (0.26 if retrato else 0.08))
    alinhamento = 2 if posicao == "baixo" else 5
    grosso = estilo in ("dinamica", "palavra")
    contorno = max(3, tamanho // 12) if grosso else max(2, tamanho // 18)
    negrito = -1

    branco = "&H00FFFFFF"
    destaque = cor_ass(cor)
    texto_cor, contorno_cor, sombra = branco, "&H00000000", (0 if grosso else 1)
    borda_estilo = 1
    if cfg["caixa"]:
        # tarja sólida: fundo na cor da caixa (branco por padrão), texto escuro ou claro conforme o fundo
        fundo = cor_caixa or "#FFFFFF"
        borda_estilo, contorno, sombra = 3, max(8, tamanho // 5), 0
        contorno_cor = cor_ass(fundo)
        texto_cor = "&H00141414" if luminancia(fundo) > 0.55 else branco
        if cor.lower() == fundo.lower():
            destaque = "&H00141414"
    margem_h = int(largura * 0.08)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,{fonte},{tamanho},{texto_cor},{texto_cor},{contorno_cor},&H80000000,{negrito},0,0,0,100,100,0,0,{borda_estilo},{contorno},{sombra},{alinhamento},{margem_h},{margem_h},{margem_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pos = f"{{\\an5\\pos({largura // 2},{centro_y})}}" if centro_y is not None else ""
    blocos = agrupar(palavras, max_palavras, cfg["max_chars"], pausa=0.45)
    eventos: list[str] = []
    for bi, bloco in enumerate(blocos):
        inicio = bloco[0]["start"]
        fim = bloco[-1]["end"] + 0.25
        if bi + 1 < len(blocos):
            prox = blocos[bi + 1][0]["start"]
            fim = prox if prox - bloco[-1]["end"] < 0.5 else min(fim, prox)
        textos = [limpar(w["text"]) for w in bloco]
        if cfg["maiusculas"]:
            textos = [t.upper().rstrip(",;:") for t in textos]
        if estilo == "palavra":
            pop = "{\\fscx125\\fscy125\\t(0,110,\\fscx100\\fscy100)}"
            eventos.append(f"Dialogue: 0,{ts(inicio)},{ts(fim)},Leg,,0,0,0,,{pos}{pop}{textos[0].rstrip('.!?')}")
        elif cfg["destaque"]:
            volta = texto_cor
            for wi, w in enumerate(bloco):
                s = inicio if wi == 0 else w["start"]
                e = bloco[wi + 1]["start"] if wi + 1 < len(bloco) else fim
                if e <= s:
                    continue
                partes = [f"{{\\c{destaque}}}{t}{{\\c{volta}}}" if j == wi else t for j, t in enumerate(textos)]
                pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                eventos.append(f"Dialogue: 0,{ts(s)},{ts(e)},Leg,,0,0,0,,{pos}{pop}{' '.join(partes)}")
        else:
            eventos.append(f"Dialogue: 0,{ts(inicio)},{ts(fim)},Leg,,0,0,0,,{pos}{' '.join(textos)}")
    return cab + "\n".join(eventos) + "\n"


def gerar_srt(palavras: list[dict]) -> str:
    def t(seg: float) -> str:
        ms = int(round(seg * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    linhas = []
    for i, b in enumerate(agrupar(palavras, 7, 42, pausa=0.6), start=1):
        linhas += [str(i), f"{t(b[0]['start'])} --> {t(b[-1]['end'])}",
                   " ".join(limpar(w["text"]) for w in b), ""]
    return "\n".join(linhas)


def _filtro_ass(ass: Path) -> str:
    """Filtro ass com as fontes do projeto. Caminho relativo (evita o escape de "C:" no Windows)."""
    try:
        rel = os.path.relpath(FONTES, ass.parent).replace("\\", "/")
        return f"ass={ass.name}:fontsdir={rel}"
    except ValueError:  # outra unidade de disco
        return f"ass={ass.name}:fontsdir='{FONTES.as_posix()}'"


def queimar(video: Path, ass: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(video.resolve()), "-vf", _filtro_ass(ass),
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", str(destino.resolve())]
    r = subprocess.run(cmd, cwd=str(ass.parent.resolve()), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode:
        raise SystemExit("falhou a legenda:\n" + r.stderr.decode("utf-8", "replace")[-1200:])
    print(f"legendas queimadas → {destino}")


def momento_com_fala(palavras: list[dict], video: Path | None = None) -> float:
    """Um instante no meio de uma frase com 3+ palavras e, se der, com os olhos abertos."""
    blocos = agrupar(palavras, 3, 18, pausa=0.45)
    bons = [b for b in blocos if len(b) >= 3] or blocos
    if not bons:
        return 1.0
    ordem = bons[len(bons) // 3:] + bons[:len(bons) // 3]
    candidatos = [(b[0]["start"] + b[-1]["end"]) / 2 for b in ordem[:8]]
    if video is None:
        return candidatos[0]
    from rosto import quadro_bom

    return quadro_bom(video, candidatos)


def galeria(palavras: list[dict], video: Path, destino: Path, em: float | None, opcoes: dict) -> None:
    """Uma imagem 2x2 com os 4 estilos sobre o mesmo quadro do vídeo."""
    largura, altura = dimensoes(video)
    t = em if em is not None else momento_com_fala(palavras, video)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        quadro = tmp / "quadro.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        str(quadro)], check=True)
        imgs = []
        for i, estilo in enumerate(ESTILOS, start=1):
            ass = tmp / f"{estilo}.ass"
            ass.write_text(gerar_ass(palavras, largura, altura, estilo, **opcoes), encoding="utf-8-sig")
            saida = tmp / f"{estilo}.png"
            vf = f"setpts=PTS+{t:.3f}/TB,{_filtro_ass(ass)}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(quadro), "-vf", vf, "-frames:v", "1",
                            str(saida)], check=True, cwd=str(tmp))
            imgs.append((saida, f"{i}. {ESTILOS[estilo]['nome']}"))
        # rótulo em cada imagem e montagem 2x2 reduzida
        esc = 960 if largura >= altura else 540
        rotulados = []
        for p, rotulo in imgs:
            r = tmp / f"r_{p.name}"
            rot = (f"scale={esc}:-2,drawtext=fontfile=Inter-900.ttf:text='{rotulo}':x=24:y=24:fontsize={esc // 18}:"
                   "fontcolor=black:box=1:boxcolor=0xc4ff5e:boxborderw=14")
            res = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf", rot, str(r)], cwd=FONTES)
            if res.returncode:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf", f"scale={esc}:-2", str(r)], check=True)
            rotulados.append(r)
        ent = []
        for r in rotulados:
            ent += ["-i", str(r)]
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ent, "-filter_complex",
                        "[0][1]hstack[a];[2][3]hstack[b];[a][b]vstack", str(destino.resolve())], check=True)
    print(f"galeria de legendas ({t:.1f}s) → {destino}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("palavras", type=Path)
    ap.add_argument("--video", type=Path, required=True, help="Vídeo onde a legenda vai (define resolução)")
    ap.add_argument("--queimar", type=Path, help="Se passado, gera o vídeo final com legenda embutida")
    ap.add_argument("--saida-ass", type=Path, help="Padrão: legendas.ass ao lado do vídeo")
    ap.add_argument("--estilo", choices=list(ESTILOS), default=None)
    ap.add_argument("--fonte")
    ap.add_argument("--cor", help="Cor de destaque da palavra falada")
    ap.add_argument("--cor-caixa", help="Cor da tarja no estilo caixa")
    ap.add_argument("--posicao", choices=["baixo", "centro"], default="baixo")
    ap.add_argument("--tamanho", type=int)
    ap.add_argument("--max-palavras", type=int)
    ap.add_argument("--margem-v", type=int,
                    help="Distância da base da legenda até a borda de baixo (px). Padrão: 26%% da altura no vertical, 8%% no horizontal")
    ap.add_argument("--centro-y", type=int, help="Centraliza a legenda nesta altura (px), ex.: emenda do react")
    ap.add_argument("--galeria", type=Path, help="Gera a imagem comparando os 4 estilos")
    ap.add_argument("--em", type=float, help="Instante do quadro da galeria (s)")
    args = ap.parse_args()

    palavras = json.loads(args.palavras.read_text(encoding="utf-8"))
    marca = ler_marca()
    leg_marca = marca.get("legenda", {})
    cor = args.cor or leg_marca.get("cor") or COR_PADRAO
    opcoes = {"fonte": args.fonte or leg_marca.get("fonte"), "cor": cor, "posicao": args.posicao,
              "tamanho": args.tamanho, "max_palavras": args.max_palavras, "margem_v": args.margem_v,
              "centro_y": args.centro_y, "cor_caixa": args.cor_caixa or leg_marca.get("cor_caixa")}
    if args.galeria:
        opcoes["fonte"] = args.fonte  # cada estilo com a própria fonte na comparação
        galeria(palavras, args.video, args.galeria, args.em, opcoes)
        return

    estilo = args.estilo or leg_marca.get("estilo") or "dinamica"
    largura, altura = dimensoes(args.video)
    ass_txt = gerar_ass(palavras, largura, altura, estilo, **opcoes)
    ass_path = args.saida_ass or args.video.with_name("legendas.ass")
    ass_path.write_text(ass_txt, encoding="utf-8-sig")
    # SRT simples também, útil para subir como legenda separada (YouTube etc.)
    ass_path.with_suffix(".srt").write_text(gerar_srt(palavras), encoding="utf-8")
    print(f"legendas .ass ({largura}x{altura}, estilo {estilo}) → {ass_path}")
    if args.queimar:
        queimar(args.video, ass_path, args.queimar)


if __name__ == "__main__":
    main()
