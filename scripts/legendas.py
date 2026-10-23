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
          --opcoes '{"escala": 1.2, "contorno": "grosso"}'  (chaves em OPCOES; a marca vale como padrão)
  galeria: python -X utf8 scripts/legendas.py palavras.json --video base.mp4 --galeria galeria.jpg [--em 4.2]
           [--variar estilo|fonte|tamanho|cor|contorno|destaque|leitura|palavras|maiusculas|posicao|atual]
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

# nome amigável → família do TTF em assets/fontes (a versão mais pesada, que lê melhor em vídeo)
FONTES_LEGENDA = {
    "montserrat": ("Montserrat", "Montserrat Black"),
    "poppins": ("Poppins", "Poppins Black"),
    "inter": ("Inter", "Inter Black"),
    "space-grotesk": ("Space Grotesk", "Space Grotesk"),
    "playfair": ("Playfair Display", "Playfair Display Black"),
}

# opções que o aluno pode configurar (config/marca.json → legenda, ou estado.json → legenda_opcoes)
OPCOES = {
    "fonte": "montserrat | poppins | inter | space-grotesk | playfair",
    "cor": "cor da palavra falada (#hex)",
    "destaque": "true/false: pinta a palavra falada",
    "cor_texto": "cor das letras (#hex, padrão branco)",
    "cor_contorno": "cor do contorno (#hex, padrão preto)",
    "contorno": "sem | fino | normal | grosso | brilho (contorno esfumado)",
    "sombra": "auto | forte (sombra projetada escura)",
    "fundo": "nenhum | tarja | translucido | sombreado (faixa escura suave atrás)",
    "destaque_tipo": "cor | caixa (caixa colorida atrás da palavra) | maior (palavra cresce)",
    "cor_caixa": "cor da tarja (#hex)",
    "escala": "tamanho relativo (1 = padrão; 0.8 pequena, 1.2 grande)",
    "tamanho": "tamanho da letra em px (vence a escala)",
    "max_palavras": "palavras na tela por vez",
    "maiusculas": "true/false",
    "animacao": "pop | nenhuma",
    "posicao": "baixo | centro",
    "subir": "fração da altura para subir a legenda (0.05 = 5%)",
    "margem_v": "px da base da legenda até a borda de baixo",
    "centro_y": "centro da legenda em px (react)",
}


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


def fonte_familia(fonte: str | None) -> str | None:
    if not fonte:
        return None
    chave = fonte.strip().lower().replace(" ", "-")
    for k, (nome, familia) in FONTES_LEGENDA.items():
        if chave in (k, nome.lower().replace(" ", "-")):
            return familia
    return fonte


def gerar_ass(palavras: list[dict], largura: int, altura: int, estilo: str = "dinamica",
              fonte: str | None = None, cor: str | None = None, posicao: str | None = "baixo",
              tamanho: int | None = None, max_palavras: int | None = None,
              margem_v: int | None = None, centro_y: int | None = None,
              cor_caixa: str | None = None, escala: float | None = None, maiusculas: bool | None = None,
              destaque: bool | None = None, cor_texto: str | None = None, cor_contorno: str | None = None,
              contorno: str | None = None, fundo: str | None = None, animacao: str | None = None,
              subir: float | None = None, sombra: str | None = None, destaque_tipo: str | None = None) -> str:
    cfg = ESTILOS[estilo]
    retrato = altura > largura
    fonte = fonte_familia(fonte) or cfg["fonte"]
    cor = cor or COR_PADRAO
    if tamanho is None:
        tamanho = int(altura * (0.042 if retrato else 0.062) * cfg["escala"] * float(escala or 1))
    max_chars = cfg["max_chars"]
    if max_palavras and max_palavras > cfg["max_palavras"]:
        max_chars = max(max_chars, 6 * max_palavras + 4)
    max_palavras = max_palavras or cfg["max_palavras"]
    maiusculas = cfg["maiusculas"] if maiusculas is None else bool(maiusculas)
    com_destaque = cfg["destaque"] if destaque is None else bool(destaque)
    fundo = fundo or ("tarja" if cfg["caixa"] else "nenhum")
    dtipo = destaque_tipo or "cor"
    if dtipo == "caixa" and fundo in ("tarja", "translucido"):
        fundo = "nenhum"  # a caixa da palavra já é o fundo; tarja por cima a esconderia
    pop_ligado = (animacao or ("nenhuma" if estilo == "classica" else "pop")) == "pop"
    if margem_v is None:
        margem_v = int(altura * (0.26 if retrato else 0.08))
    if subir:
        margem_v += int(altura * float(subir))
    alinhamento = 5 if posicao == "centro" else 2
    grosso = estilo in ("dinamica", "palavra")
    espessura = contorno or ("normal" if grosso else "fino")
    contorno = {"sem": 0, "fino": max(2, tamanho // 18), "normal": max(3, tamanho // 12),
                "grosso": max(4, tamanho // 8), "brilho": max(6, tamanho // 5)}.get(espessura, max(2, tamanho // 18))
    negrito = -1

    branco = "&H00FFFFFF"
    destaque_ass = cor_ass(cor)
    texto_cor = cor_ass(cor_texto) if cor_texto else branco
    contorno_cor = cor_ass(cor_contorno) if cor_contorno else "&H00000000"
    sombra_cor = "&H80000000"
    prefixo = ""
    if sombra == "forte":
        sombra, sombra_cor = max(3, tamanho // 13), "&H20000000"  # sombra projetada, quase opaca
    else:
        sombra = 0 if grosso else 1
        if espessura == "sem":
            sombra = max(2, tamanho // 22)  # sem contorno: sombra suave para ler em fundo claro
    if espessura == "brilho":
        # contorno largo e esfumado: um "halo" escuro que separa a letra de qualquer fundo
        if not cor_contorno:
            contorno_cor = "&H00000000"
        prefixo = f"{{\\blur{max(4, tamanho // 7)}}}"
    borda_estilo = 1
    if fundo == "tarja":
        # tarja sólida: fundo na cor da caixa (branco por padrão), texto escuro ou claro conforme o fundo
        cor_fundo = cor_caixa or "#FFFFFF"
        borda_estilo, contorno, sombra = 3, max(8, tamanho // 5), 0
        contorno_cor = cor_ass(cor_fundo)
        if not cor_texto:
            texto_cor = "&H00141414" if luminancia(cor_fundo) > 0.55 else branco
        if cor.lower() == cor_fundo.lower():
            destaque_ass = "&H00141414"
    elif fundo == "translucido":
        # tarja escura semitransparente (estilo streaming), uma caixa só por linha (sem faixas entre as palavras)
        borda_estilo, contorno, sombra = 4, 0, max(8, tamanho // 5)
        sombra_cor = cor_ass(cor_caixa or "#000000", "60")
    margem_h = int(largura * 0.08)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,{fonte},{tamanho},{texto_cor},{texto_cor},{contorno_cor},{sombra_cor},{negrito},0,0,0,100,100,0,0,{borda_estilo},{contorno},{sombra},{alinhamento},{margem_h},{margem_h},{margem_v},1
Style: Caixa,{fonte},{tamanho},&HFF000000,&HFF000000,{destaque_ass},&HFF000000,{negrito},0,0,0,100,100,0,0,3,{max(6, tamanho // 7)},0,{alinhamento},{margem_h},{margem_h},{margem_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pos = f"{{\\an5\\pos({largura // 2},{centro_y})}}" if centro_y is not None else ""
    # palavra em destaque na caixa: letra escura ou clara conforme a cor da caixa
    texto_na_caixa = "&H00141414" if luminancia(cor) > 0.55 else branco
    volta_borda = f"{{\\bord{contorno}\\shad{sombra}}}"

    def linhas(textos: list[str], hi: int | None, pop: str) -> list[tuple[int, str, str]]:
        """(camada, estilo, texto): o texto vai na camada 2; no destaque em caixa, a caixa da palavra na 1."""
        if hi is None:
            return [(2, "Leg", f"{pos}{prefixo}{pop}{' '.join(textos)}")]
        if dtipo == "caixa":
            partes = [f"{{\\bord0\\shad0\\c{texto_na_caixa}}}{t}{volta_borda}{{\\c{texto_cor}}}" if j == hi else t
                      for j, t in enumerate(textos)]
            caixa = [f"{{\\3a&H00&}}{t}{{\\3a&HFF&}}" if j == hi else t for j, t in enumerate(textos)]
            return [(1, "Caixa", f"{pos}{pop}{{\\3a&HFF&}}{' '.join(caixa)}"),
                    (2, "Leg", f"{pos}{prefixo}{pop}{' '.join(partes)}")]
        if dtipo == "maior":
            partes = [f"{{\\fscx122\\fscy122\\c{destaque_ass}}}{t}{{\\fscx100\\fscy100\\c{texto_cor}}}" if j == hi
                      else t for j, t in enumerate(textos)]
            return [(2, "Leg", f"{pos}{prefixo}{' '.join(partes)}")]
        partes = [f"{{\\c{destaque_ass}}}{t}{{\\c{texto_cor}}}" if j == hi else t for j, t in enumerate(textos)]
        return [(2, "Leg", f"{pos}{prefixo}{pop}{' '.join(partes)}")]

    def eventos_de(s: float, e: float, textos: list[str], hi: int | None, pop: str) -> list[str]:
        return [f"Dialogue: {camada},{ts(s)},{ts(e)},{est},,0,0,0,,{texto}"
                for camada, est, texto in linhas(textos, hi, pop)]

    blocos = agrupar(palavras, max_palavras, max_chars, pausa=0.45)
    eventos: list[str] = []
    trechos: list[list[float]] = []  # quando há legenda na tela (para o fundo sombreado)
    for bi, bloco in enumerate(blocos):
        inicio = bloco[0]["start"]
        fim = bloco[-1]["end"] + 0.25
        if bi + 1 < len(blocos):
            prox = blocos[bi + 1][0]["start"]
            fim = prox if prox - bloco[-1]["end"] < 0.5 else min(fim, prox)
        if trechos and inicio - trechos[-1][1] < 0.3:
            trechos[-1][1] = fim
        else:
            trechos.append([inicio, fim])
        textos = [limpar(w["text"]) for w in bloco]
        if maiusculas:
            textos = [t.upper().rstrip(",;:") for t in textos]
        if estilo == "palavra" and max_palavras == 1:
            pop = "{\\fscx125\\fscy125\\t(0,110,\\fscx100\\fscy100)}" if pop_ligado else ""
            hi = 0 if com_destaque else None
            eventos += eventos_de(inicio, fim, [textos[0].rstrip(".!?")], hi, pop)
        elif com_destaque:
            for wi, w in enumerate(bloco):
                s = inicio if wi == 0 else w["start"]
                e = bloco[wi + 1]["start"] if wi + 1 < len(bloco) else fim
                if e <= s:
                    continue
                pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 and pop_ligado else ""
                eventos += eventos_de(s, e, textos, wi, pop)
        else:
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if pop_ligado else ""
            eventos += eventos_de(inicio, fim, textos, None, pop)
    if fundo == "sombreado":
        # faixa escura bem esfumada atrás da legenda: lê em qualquer fundo, sem "caixa" aparente
        if centro_y is not None:
            meio = centro_y
        elif alinhamento == 5:
            meio = altura // 2
        else:
            meio = altura - margem_v - int(tamanho * 0.6)
        alt = int(tamanho * 3.4)
        topo = max(0, meio - alt // 2)
        faixa = (f"{{\\an7\\pos(0,{topo})\\p1\\bord0\\shad0\\blur{max(20, tamanho // 2)}\\c&H000000&\\1a&H58&"
                 f"\\fad(150,150)}}m 0 0 l {largura} 0 {largura} {alt} 0 {alt}{{\\p0}}")
        eventos = [f"Dialogue: 0,{ts(a)},{ts(b)},Leg,,0,0,0,,{faixa}" for a, b in trechos] + eventos
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


VARIACOES = ("estilo", "fonte", "tamanho", "cor", "contorno", "destaque", "leitura", "palavras", "maiusculas",
             "posicao", "atual")
# opções que dependem do estilo: na comparação de estilos cada um aparece do seu jeito
DO_ESTILO = ("fonte", "max_palavras", "maiusculas", "fundo", "destaque", "contorno", "animacao", "sombra",
             "destaque_tipo")


def variantes(tipo: str, estilo: str, opcoes: dict, marca: dict) -> list[tuple[str, str, dict]]:
    """(rótulo, estilo, opções) de cada quadro da galeria."""
    if tipo == "estilo":
        base = {k: v for k, v in opcoes.items() if k not in DO_ESTILO}
        return [(c["nome"], e, base) for e, c in ESTILOS.items()]
    if tipo == "fonte":
        return [(nome, estilo, {**opcoes, "fonte": k}) for k, (nome, _) in FONTES_LEGENDA.items()]
    if tipo == "tamanho":
        return [(nome, estilo, {**opcoes, "tamanho": None, "escala": e})
                for nome, e in (("Pequena", 0.8), ("Média (padrão)", 1.0), ("Grande", 1.2), ("Gigante", 1.45))]
    if tipo == "cor":
        cores = [("Amarelo", "#FFD400"), ("Verde-limão", "#C4FF5E"), ("Azul-claro", "#3DD9FF"),
                 ("Rosa", "#FF4FA3"), ("Laranja", "#FF8A00")]
        da_marca = ((marca.get("cores") or {}).get("destaque") or "").strip()
        if da_marca and da_marca.lower() not in (c.lower() for _, c in cores):
            cores[-1] = ("Cor da marca", da_marca)
        lista = [(n, estilo, {**opcoes, "cor": c, "destaque": True}) for n, c in cores]
        return lista + [("Sem destaque", estilo, {**opcoes, "destaque": False})]
    if tipo == "contorno":
        sem_fundo = {**opcoes, "fundo": "nenhum", "sombra": None}
        return [("Sem contorno", estilo, {**sem_fundo, "contorno": "sem"}),
                ("Contorno fino", estilo, {**sem_fundo, "contorno": "fino"}),
                ("Contorno normal", estilo, {**sem_fundo, "contorno": "normal"}),
                ("Contorno grosso", estilo, {**sem_fundo, "contorno": "grosso"}),
                ("Grosso com sombra", estilo, {**sem_fundo, "contorno": "grosso", "sombra": "forte"}),
                ("Brilho escuro", estilo, {**sem_fundo, "contorno": "brilho"}),
                ("Fundo escurecido", estilo, {**sem_fundo, "contorno": opcoes.get("contorno"), "fundo": "sombreado"}),
                ("Tarja escura", estilo, {**opcoes, "fundo": "translucido", "cor_caixa": None, "sombra": None}),
                ("Tarja branca", estilo, {**opcoes, "fundo": "tarja", "cor_caixa": None, "sombra": None})]
    if tipo == "destaque":
        com = {**opcoes, "destaque": True}
        return [("Palavra colorida", estilo, {**com, "destaque_tipo": "cor"}),
                ("Caixa colorida na palavra", estilo, {**com, "destaque_tipo": "caixa"}),
                ("Palavra maior", estilo, {**com, "destaque_tipo": "maior"}),
                ("Sem destaque", estilo, {**opcoes, "destaque": False})]
    if tipo == "leitura":
        # combinações que leem bem em vídeo colorido ou com muita coisa na tela
        limpo = {**opcoes, "fundo": "nenhum", "sombra": None, "cor_texto": None, "cor_contorno": None}
        cor = opcoes.get("cor") or COR_PADRAO
        escura = cor if luminancia(cor) < 0.45 else "#D4145A"  # destaque claro some no contorno branco
        return [("Contorno grosso e sombra", estilo, {**limpo, "contorno": "grosso", "sombra": "forte"}),
                ("Brilho escuro", estilo, {**limpo, "contorno": "brilho"}),
                ("Fundo escurecido", estilo, {**limpo, "contorno": "normal", "fundo": "sombreado"}),
                ("Tarja escura", estilo, {**limpo, "fundo": "translucido", "cor_caixa": None}),
                ("Caixa colorida na palavra", estilo, {**limpo, "contorno": "grosso", "destaque": True,
                                                       "destaque_tipo": "caixa"}),
                ("Letra preta, contorno branco", estilo, {**limpo, "contorno": "grosso", "cor_texto": "#141414",
                                                          "cor_contorno": "#FFFFFF", "cor": escura})]
    if tipo == "palavras":
        return [(n, estilo, {**opcoes, "max_palavras": q})
                for n, q in (("1 palavra", 1), ("2 palavras", 2), ("3 palavras", 3), ("Frase (até 7)", 7))]
    if tipo == "maiusculas":
        return [("MAIÚSCULAS", estilo, {**opcoes, "maiusculas": True}),
                ("Normal", estilo, {**opcoes, "maiusculas": False})]
    if tipo == "posicao":
        return [("Embaixo (automático)", estilo, {**opcoes, "posicao": "baixo", "subir": 0}),
                ("Um pouco mais alto", estilo, {**opcoes, "posicao": "baixo", "subir": 0.06}),
                ("Bem mais alto", estilo, {**opcoes, "posicao": "baixo", "subir": 0.14}),
                ("Meio da tela", estilo, {**opcoes, "posicao": "centro", "centro_y": None})]
    return [("Como vai ficar", estilo, opcoes)]


def galeria(palavras: list[dict], video: Path, destino: Path, em: float | None, tipo: str, estilo: str,
            opcoes: dict, marca: dict) -> None:
    """Uma imagem com as variações lado a lado, sobre o mesmo quadro do vídeo."""
    largura, altura = dimensoes(video)
    t = em if em is not None else momento_com_fala(palavras, video)
    lista = variantes(tipo, estilo, opcoes, marca)
    n = len(lista)
    colunas = 1 if n == 1 else (2 if n <= 4 else 3)
    linhas = -(-n // colunas)
    if largura >= altura:
        esc = {1: 1280, 2: 960, 3: 720}[colunas]
    else:
        esc = {1: 720, 2: 540, 3: 400}[colunas]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        quadro = tmp / "quadro.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        str(quadro)], check=True)
        rotulados = []
        for i, (rotulo, est, op) in enumerate(lista, start=1):
            ass = tmp / f"v{i}.ass"
            ass.write_text(gerar_ass(palavras, largura, altura, est, **op), encoding="utf-8-sig")
            saida = tmp / f"v{i}.png"
            vf = f"setpts=PTS+{t:.3f}/TB,{_filtro_ass(ass)}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(quadro), "-vf", vf, "-frames:v", "1",
                            str(saida)], check=True, cwd=str(tmp))
            texto = (rotulo if n == 1 else f"{i}. {rotulo}").replace(":", " ").replace("'", "")
            r = tmp / f"r{i}.png"
            rot = (f"scale={esc}:-2,drawtext=fontfile=Inter-900.ttf:text='{texto}':x=20:y=20:fontsize={max(18, esc // 20)}:"
                   "fontcolor=black:box=1:boxcolor=0xc4ff5e:boxborderw=12")
            res = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(saida), "-vf", rot, str(r)], cwd=FONTES)
            if res.returncode:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(saida), "-vf", f"scale={esc}:-2", str(r)],
                               check=True)
            rotulados.append(r)
        tw, th = dimensoes(rotulados[0])
        while len(rotulados) < colunas * linhas:  # completa a última linha com um quadro preto
            vazio = tmp / f"vazio{len(rotulados)}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={tw}x{th}",
                            "-frames:v", "1", str(vazio)], check=True)
            rotulados.append(vazio)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if len(rotulados) == 1:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(rotulados[0]), str(destino.resolve())], check=True)
        else:
            ent, filtro, fileiras = [], [], []
            for r in rotulados:
                ent += ["-i", str(r)]
            for li in range(linhas):
                idx = "".join(f"[{li * colunas + c}]" for c in range(colunas))
                filtro.append(f"{idx}hstack=inputs={colunas}[l{li}]" if colunas > 1 else f"{idx}null[l{li}]")
                fileiras.append(f"[l{li}]")
            if linhas > 1:
                filtro.append(f"{''.join(fileiras)}vstack=inputs={linhas}")
            else:
                filtro[-1] = filtro[-1].rsplit("[", 1)[0]
            subprocess.run(["ffmpeg", "-v", "error", "-y", *ent, "-filter_complex", ";".join(filtro),
                            str(destino.resolve())], check=True)
    print(f"galeria de legendas ({tipo}, {t:.1f}s) → {destino}")


def opcoes_da_marca(marca: dict) -> dict:
    leg = marca.get("legenda") or {}
    return {k: v for k, v in leg.items() if k in OPCOES and v not in ("", None)}


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
    ap.add_argument("--posicao", choices=["baixo", "centro"])
    ap.add_argument("--tamanho", type=int)
    ap.add_argument("--max-palavras", type=int)
    ap.add_argument("--margem-v", type=int,
                    help="Distância da base da legenda até a borda de baixo (px). Padrão: 26%% da altura no vertical, 8%% no horizontal")
    ap.add_argument("--centro-y", type=int, help="Centraliza a legenda nesta altura (px), ex.: emenda do react")
    ap.add_argument("--opcoes", help="JSON com opções (chaves de OPCOES); vence a marca, perde para as opções acima")
    ap.add_argument("--galeria", type=Path, help="Gera a imagem comparando variações")
    ap.add_argument("--variar", choices=VARIACOES, default="estilo", help="O que muda entre os quadros da galeria")
    ap.add_argument("--em", type=float, help="Instante do quadro da galeria (s)")
    args = ap.parse_args()

    palavras = json.loads(args.palavras.read_text(encoding="utf-8"))
    marca = ler_marca()
    opcoes = opcoes_da_marca(marca)
    if args.opcoes:
        opcoes.update({k: v for k, v in json.loads(args.opcoes).items() if k in OPCOES and v not in ("", None)})
    explicitas = {"fonte": args.fonte, "cor": args.cor, "cor_caixa": args.cor_caixa, "posicao": args.posicao,
                  "tamanho": args.tamanho, "max_palavras": args.max_palavras, "margem_v": args.margem_v,
                  "centro_y": args.centro_y}
    opcoes.update({k: v for k, v in explicitas.items() if v is not None})
    estilo = args.estilo or (marca.get("legenda") or {}).get("estilo") or "dinamica"

    if args.galeria:
        galeria(palavras, args.video, args.galeria, args.em, args.variar, estilo, opcoes, marca)
        return

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
