"""Imagens reais com licença livre, do Wikimedia Commons (sem chave de API).

  buscar <id> "termos em inglês" [--n 8]   busca, baixa miniaturas e monta a folha para escolher
                                           (motion/imagens/_busca/galeria.jpg + busca.json)
  usar <id> <número> [--nome x]            baixa a imagem escolhida (até 1600 px) para motion/imagens/<nome>.jpg
                                           e guarda o crédito em motion/imagens/creditos.json
  creditos <id> [--json]                   créditos das imagens do vídeo

Só entram licenças que deixam usar em vídeo (domínio público, CC0, CC BY, CC BY-SA). CC BY e CC BY-SA
exigem crédito: os cards de imagem mostram sozinhos e o finalizar grava <nome>_creditos.txt.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
# a Wikimedia pede um User-Agent que identifique o programa
CABECALHO = {"User-Agent": "EditorDeVideoIA/1.0 (editor de vídeo educacional; imagens com licença livre)"}
LICENCA_OK = re.compile(r"^(public domain|pd\b|cc0|cc[ -]by(-sa)?\b)", re.I)
LADO_MINIATURA, LADO_GRANDE = 480, 1600


def pasta_imagens(trab: Path) -> Path:
    return trab / "motion" / "imagens"


def _get(params: dict) -> dict:
    import requests

    try:
        r = requests.get(API, params={**params, "format": "json", "formatversion": 2}, headers=CABECALHO, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as ex:
        raise SystemExit(f"✗ não consegui falar com o Wikimedia Commons (internet?): {ex}")


def _baixar(url: str, destino: Path) -> None:
    import requests
    from PIL import Image

    try:
        r = requests.get(url, headers=CABECALHO, timeout=60)
        r.raise_for_status()
    except requests.RequestException as ex:
        raise SystemExit(f"✗ não consegui baixar a imagem: {ex}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_bytes(r.content)
    with Image.open(tmp) as im:  # sempre JPEG RGB (PNG com transparência ganha fundo escuro)
        im = im.convert("RGBA")
        fundo = Image.new("RGBA", im.size, (12, 12, 14, 255))
        fundo.alpha_composite(im)
        fundo.convert("RGB").save(destino, quality=90)
    tmp.unlink()


def _texto(meta: dict, chave: str) -> str:
    v = (meta.get(chave) or {}).get("value") or ""
    v = re.sub(r"<[^>]+>", "", str(v))
    return re.sub(r"\s+", " ", html.unescape(v)).strip()


def credito_texto(cr: dict) -> str:
    """"Autor, CC BY-SA 4.0, via Wikimedia Commons" (domínio público: "Domínio público, via Wikimedia Commons")."""
    lic = cr.get("licenca") or ""
    if re.match(r"^(public domain|pd\b|cc0)", lic, re.I):
        lic = "Domínio público" if not lic.lower().startswith("cc0") else "CC0"
    autor = cr.get("autor") or ""
    partes = [p for p in (autor if autor and autor.lower() != "unknown" else "", lic) if p]
    return ", ".join(partes) + ", via Wikimedia Commons"


def rotulo_licenca(lic: str) -> str:
    """Como a licença aparece na folha de escolha."""
    if re.match(r"^(public domain|pd)", lic, re.I):
        return "Domínio público"
    if lic.lower().startswith("cc0"):
        return "CC0 (livre)"
    return f"{lic[:22]} (pede crédito)"


def ler_creditos(trab: Path) -> dict:
    return C.ler_json(pasta_imagens(trab) / "creditos.json") or {}


def buscar(trab: Path, termos: str, n: int) -> list[dict]:
    d = _get({"action": "query", "generator": "search", "gsrsearch": f"{termos} filetype:bitmap",
              "gsrnamespace": 6, "gsrlimit": min(50, n * 4), "prop": "imageinfo",
              "iiprop": "url|extmetadata|size|mime", "iiurlwidth": LADO_MINIATURA})
    paginas = sorted((d.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    achadas = []
    for p in paginas:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = _texto(meta, "LicenseShortName")
        if not LICENCA_OK.match(lic) or info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        if min(info.get("width", 0), info.get("height", 0)) < 500:  # pequena demais para vídeo
            continue
        achadas.append({"n": len(achadas) + 1, "titulo": p["title"].removeprefix("File:"),
                        "autor": _texto(meta, "Artist")[:120], "licenca": lic,
                        "licenca_url": _texto(meta, "LicenseUrl"), "pagina": info.get("descriptionurl"),
                        "miniatura": info.get("thumburl"), "largura": info.get("width"), "altura": info.get("height")})
        if len(achadas) >= n:
            break
    pasta = pasta_imagens(trab) / "_busca"
    if pasta.exists():
        C.apagar_pasta(pasta)
    for a in achadas:
        _baixar(a["miniatura"], pasta / f"{a['n']:02d}.jpg")
    if achadas:
        folha(pasta, achadas)
    C.gravar_json(pasta / "busca.json", {"termos": termos, "imagens": achadas})
    return achadas


def folha(pasta: Path, achadas: list[dict]) -> Path:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    tw, th, faixa, m = 420, 300, 40, 12
    cols = min(4, len(achadas))
    linhas = (len(achadas) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw + (cols + 1) * m, linhas * (th + faixa) + (linhas + 1) * m), (10, 10, 10))
    try:
        fonte = ImageFont.truetype(str(C.FONTES / "Inter-700.ttf"), 20)
    except OSError:
        fonte = ImageFont.load_default()
    d = ImageDraw.Draw(img)
    for i, a in enumerate(achadas):
        x, y = m + (i % cols) * (tw + m), m + (i // cols) * (th + faixa + m)
        d.rectangle([x, y, x + tw, y + faixa - 6], fill=(196, 255, 94))
        d.text((x + 10, y + 7), f"{a['n']}. {rotulo_licenca(a['licenca'])}", fill=(0, 0, 0), font=fonte)
        with Image.open(pasta / f"{a['n']:02d}.jpg") as im:
            img.paste(ImageOps.pad(im.convert("RGB"), (tw, th), color=(24, 24, 26)), (x, y + faixa))
    destino = pasta / "galeria.jpg"
    img.save(destino, quality=88)
    return destino


def usar(trab: Path, n: int, nome: str | None) -> dict:
    busca = C.ler_json(pasta_imagens(trab) / "_busca" / "busca.json") or {}
    a = next((x for x in busca.get("imagens") or [] if x["n"] == n), None)
    if not a:
        raise SystemExit(f"✗ não há a imagem {n} na última busca (rode o buscar de novo)")
    d = _get({"action": "query", "titles": "File:" + a["titulo"], "prop": "imageinfo", "iiprop": "url",
              "iiurlwidth": LADO_GRANDE})
    info = (((d.get("query") or {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
    url = info.get("thumburl") or info.get("url")
    nome = C.limpar_nome(nome or Path(a["titulo"]).stem)[:60] or f"imagem-{n}"
    destino = pasta_imagens(trab) / f"{nome}.jpg"
    _baixar(url, destino)
    creditos = ler_creditos(trab)
    creditos[destino.name] = {k: a.get(k) for k in ("titulo", "autor", "licenca", "licenca_url", "pagina")}
    C.gravar_json(pasta_imagens(trab) / "creditos.json", creditos)
    return {"arquivo": str(destino), "caminho_no_roteiro": f"motion/imagens/{destino.name}",
            "credito": credito_texto(creditos[destino.name])}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("buscar"); p.add_argument("id"); p.add_argument("termos"); p.add_argument("--n", type=int, default=8)
    p = sub.add_parser("usar"); p.add_argument("id"); p.add_argument("numero", type=int); p.add_argument("--nome")
    p = sub.add_parser("creditos"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    trab = C.TRABALHO / C.id_video(a.id)
    if a.acao == "buscar":
        achadas = buscar(trab, a.termos, a.n)
        if not achadas:
            print(json.dumps({"imagens": [], "aviso": "nenhuma imagem com licença livre; tente outros termos (em inglês)"},
                             ensure_ascii=False))
            return
        print(json.dumps({"galeria": str(pasta_imagens(trab) / "_busca" / "galeria.jpg"),
                          "imagens": [{k: x[k] for k in ("n", "titulo", "autor", "licenca", "pagina")} for x in achadas]},
                         indent=1, ensure_ascii=False))
    elif a.acao == "usar":
        print(json.dumps(usar(trab, a.numero, a.nome), indent=1, ensure_ascii=False))
    else:
        cr = ler_creditos(trab)
        if a.json:
            print(json.dumps(cr, indent=1, ensure_ascii=False))
        else:
            for arq, x in cr.items():
                print(f"{arq}: {credito_texto(x)}")


if __name__ == "__main__":
    main()
