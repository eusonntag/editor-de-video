"""Personagens de IA salvos para reutilizar nos vídeos (imagem aprovada + descrição + voz + gestos).

Cada personagem fica em config/personagens/<slug>/:
  personagem.json  {"nome", "descricao", "aparencia", "roupa", "cenario", "jeito_de_falar", "gestos" (inglês, vai
                    como motion_prompt), "expressividade" (low|medium|high), "voz": {"provedor", "voice_id", "nome"},
                    "look_padrao", "looks": {"<look>": {"imagem", "heygen_look", "prompt", "proporcao", "criado_em"}}}
  <look>.jpg       imagem aprovada de cada look (roupa/cenário)
As opções geradas antes da aprovação ficam em videos/.trabalho/personagens/<slug>/ (galeria.jpg + opcoes.json).

  saldo                                                       saldo da carteira da API da HeyGen
  listar [--json]                                             personagens salvos (+ galeria.jpg com todos)
  mostrar <slug>
  opcoes <slug> --prompt "... {variacao} ..." --variacoes a b c [--base <slug>[:look]] [--proporcao 16:9]
  salvar <slug> (--opcao N | --arquivo img) [--look principal] [--dados dados.json]
  editar <slug> --dados dados.json                            muda só os campos do arquivo
  apagar <slug> [--look nome] --confirmar
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402
import heygen as H  # noqa: E402

PERSONAGENS = C.CONFIG / "personagens"
RASCUNHOS = C.TRABALHO / "personagens"
CAMPOS = ("nome", "descricao", "aparencia", "roupa", "cenario", "jeito_de_falar", "gestos", "expressividade", "voz")


def slug(texto: str) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "personagem"


def pasta(s: str) -> Path:
    return PERSONAGENS / slug(s)


def ler(s: str) -> dict:
    p = pasta(s) / "personagem.json"
    if not p.exists():
        raise SystemExit(f"✗ não existe o personagem \"{s}\" (veja os salvos com: personagens listar)")
    return C.ler_json(p)


def gravar(s: str, dados: dict) -> None:
    C.gravar_json(pasta(s) / "personagem.json", dados)


def todos() -> list[tuple[str, dict]]:
    if not PERSONAGENS.exists():
        return []
    return [(p.name, C.ler_json(p / "personagem.json")) for p in sorted(PERSONAGENS.iterdir())
            if (p / "personagem.json").exists()]


def folha(itens: list[tuple[str, Path]], destino: Path) -> Path:
    """Grade com rótulo numerado sobre cada imagem (para aprovar na conversa)."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    tw, th, faixa, m = 640, 360, 44, 14
    cols = min(3, len(itens))
    linhas = (len(itens) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw + (cols + 1) * m, linhas * (th + faixa) + (linhas + 1) * m), (10, 10, 10))
    try:
        fonte = ImageFont.truetype(str(C.FONTES / "Inter-700.ttf"), 24)
    except OSError:
        fonte = ImageFont.load_default()
    d = ImageDraw.Draw(img)
    for i, (rotulo, arq) in enumerate(itens):
        x, y = m + (i % cols) * (tw + m), m + (i // cols) * (th + faixa + m)
        d.rectangle([x, y, x + tw, y + faixa - 6], fill=(196, 255, 94))
        d.text((x + 12, y + 7), rotulo, fill=(0, 0, 0), font=fonte)
        with Image.open(arq) as im:
            img.paste(ImageOps.pad(im.convert("RGB"), (tw, th), color=(24, 24, 26)), (x, y + faixa))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, quality=88)
    return destino


def look_base(ref: str) -> str:
    s, _, look = ref.partition(":")
    dados = ler(s)
    info = (dados.get("looks") or {}).get(look or dados.get("look_padrao") or "principal") or {}
    if not info.get("heygen_look"):
        raise SystemExit(f"✗ o personagem \"{s}\" não tem esse visual registrado na HeyGen")
    return info["heygen_look"]


def cmd_opcoes(a) -> None:
    from PIL import Image

    base = look_base(a.base) if a.base else None
    destino = RASCUNHOS / slug(a.slug)
    C.apagar_pasta(destino)
    destino.mkdir(parents=True, exist_ok=True)
    pedidos = []
    for i, var in enumerate(a.variacoes or [""], 1):
        prompt = a.prompt.replace("{variacao}", var).strip()
        pedidos.append({"n": i, "prompt": prompt,
                        "heygen_look": H.criar_look(f"{a.slug} opção {i}", prompt, a.proporcao, base)})
        print(f"⏳ opção {i}/{len(a.variacoes or [''])} pedida", flush=True)
    feitas = []
    for p in pedidos:
        d = H.esperar_look(p["heygen_look"])
        if d.get("status") != "completed" or not d.get("preview_image_url"):
            print(f"✗ opção {p['n']} não saiu (status: {d.get('status')})", flush=True)
            continue
        arq = destino / f"opcao-{p['n']}.jpg"
        H.baixar(d["preview_image_url"], arq)
        with Image.open(arq) as im:  # a HeyGen manda WEBP
            im.convert("RGB").save(arq, "JPEG", quality=92)
        feitas.append({**p, "imagem": arq.name, "proporcao": a.proporcao,
                       "motores": d.get("supported_api_engines")})
    if not feitas:
        raise SystemExit("✗ nenhuma opção saiu: tente de novo ou mude a descrição")
    C.gravar_json(destino / "opcoes.json", {"base": a.base, "opcoes": feitas})
    galeria = folha([(f"{o['n']}", destino / o["imagem"]) for o in feitas], destino / "galeria.jpg")
    print(json.dumps({"galeria": str(galeria), "opcoes": [o["n"] for o in feitas]}, ensure_ascii=False))


def registrar_foto(dados: dict, s: str, look: str, arquivo: Path) -> str:
    """Foto própria vira um visual registrado na HeyGen (cobrado), no mesmo grupo dos outros visuais do personagem."""
    hl, grupo = H.criar_look_foto(f"{dados.get('nome') or s} {look}", arquivo, dados.get("heygen_grupo"))
    d = H.esperar_look(hl)
    if d.get("status") != "completed":
        raise SystemExit(f"✗ a HeyGen não terminou de preparar a foto (status: {d.get('status')})")
    dados["heygen_grupo"] = grupo or d.get("group_id")
    return hl


def cmd_registrar(a) -> None:
    s = slug(a.slug)
    dados = ler(s)
    info = (dados.get("looks") or {}).get(slug(a.look))
    if not info:
        raise SystemExit(f"✗ o personagem não tem o visual \"{a.look}\"")
    if info.get("heygen_look"):
        print(json.dumps({"look": slug(a.look), "mensagem": "já estava registrado"}, ensure_ascii=False))
        return
    info["heygen_look"] = registrar_foto(dados, s, slug(a.look), pasta(s) / info["imagem"])
    gravar(s, dados)
    print(json.dumps({"look": slug(a.look), "heygen_look": info["heygen_look"], "saldo_usd": H.saldo()}, ensure_ascii=False))


def cmd_salvar(a) -> None:
    from PIL import Image

    s = slug(a.slug)
    atual = C.ler_json(pasta(s) / "personagem.json", {}) or {}
    look = slug(a.look) if a.look else (atual.get("look_padrao") or "principal")
    info = {"criado_em": time.strftime("%Y-%m-%d")}
    if a.opcao:
        rasc = C.ler_json(RASCUNHOS / s / "opcoes.json") or {}
        o = next((x for x in rasc.get("opcoes") or [] if x["n"] == a.opcao), None)
        if not o:
            raise SystemExit(f"✗ não há a opção {a.opcao} (gere as opções de novo)")
        origem = RASCUNHOS / s / o["imagem"]
        info.update({k: o.get(k) for k in ("heygen_look", "prompt", "proporcao")})
    else:
        origem = Path(a.arquivo)
        if not origem.exists():
            raise SystemExit(f"✗ não achei a imagem {origem}")
    destino = pasta(s) / f"{look}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(origem) as im:
        im.convert("RGB").save(destino, "JPEG", quality=95)
        info["proporcao"] = info.get("proporcao") or ("16:9" if im.width > im.height else "9:16")
    info["imagem"] = destino.name
    if a.arquivo and not a.sem_heygen:
        info["heygen_look"] = registrar_foto(atual, a.slug, look, destino)
    elif a.arquivo:
        info["heygen_look"] = None
    elif info.get("heygen_look") and not atual.get("heygen_grupo"):
        atual["heygen_grupo"] = H.esperar_look(info["heygen_look"]).get("group_id")
    dados = {**atual, **(C.ler_json(Path(a.dados)) if a.dados else {})}
    dados.setdefault("nome", a.slug)
    dados.setdefault("looks", {})[look] = info
    dados.setdefault("look_padrao", look)
    gravar(s, dados)
    print(json.dumps({"personagem": s, "look": look, "pasta": str(pasta(s))}, ensure_ascii=False))


def cmd_editar(a) -> None:
    dados = ler(a.slug)
    novos = C.ler_json(Path(a.dados)) or {}
    dados.update({k: v for k, v in novos.items() if k in CAMPOS or k == "look_padrao"})
    gravar(a.slug, dados)
    print(json.dumps({k: dados.get(k) for k in CAMPOS}, ensure_ascii=False, indent=2))


def cmd_listar(a) -> None:
    lista = todos()
    saida = [{"slug": s, "nome": d.get("nome"), "descricao": d.get("descricao"),
              "looks": list((d.get("looks") or {}).keys()), "voz": (d.get("voz") or {}).get("nome")} for s, d in lista]
    if lista:
        itens = []
        for i, (s, d) in enumerate(lista, 1):
            img = pasta(s) / ((d.get("looks") or {}).get(d.get("look_padrao"), {}).get("imagem") or "")
            if img.is_file():
                itens.append((f"{i}. {d.get('nome', s)}", img))
        if itens:
            folha(itens, RASCUNHOS / "galeria-salvos.jpg")
    if a.json:
        print(json.dumps({"personagens": saida, "galeria": str(RASCUNHOS / "galeria-salvos.jpg") if lista else None},
                         ensure_ascii=False, indent=2))
        return
    if not saida:
        print("nenhum personagem salvo")
    for i, p in enumerate(saida, 1):
        print(f"{i}. {p['nome']} ({p['slug']}): {p['descricao'] or 'sem descrição'}; visuais: {', '.join(p['looks'])}")


def cmd_apagar(a) -> None:
    if not a.confirmar:
        raise SystemExit("✗ apagar precisa de --confirmar")
    s = slug(a.slug)
    dados = ler(s)
    if not a.look:
        C.apagar_pasta(pasta(s))
        print(f"personagem {s} apagado")
        return
    info = (dados.get("looks") or {}).pop(slug(a.look), None)
    if not info:
        raise SystemExit(f"✗ o personagem não tem o visual \"{a.look}\"")
    (pasta(s) / info["imagem"]).unlink(missing_ok=True)
    if dados.get("look_padrao") == slug(a.look):
        dados["look_padrao"] = next(iter(dados["looks"]), None)
    gravar(s, dados)
    print(f"visual {a.look} apagado")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="acao", required=True)
    sub.add_parser("saldo")
    p = sub.add_parser("listar"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("mostrar"); p.add_argument("slug")
    p = sub.add_parser("opcoes"); p.add_argument("slug"); p.add_argument("--prompt", required=True)
    p.add_argument("--variacoes", nargs="*"); p.add_argument("--base")
    p.add_argument("--proporcao", default="16:9", choices=["16:9", "9:16", "1:1", "4:5"])
    p = sub.add_parser("salvar"); p.add_argument("slug"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--opcao", type=int); g.add_argument("--arquivo"); p.add_argument("--look"); p.add_argument("--dados")
    p.add_argument("--sem-heygen", action="store_true", help="foto própria só fica salva, sem registrar na HeyGen")
    p = sub.add_parser("registrar"); p.add_argument("slug"); p.add_argument("--look", required=True)
    p = sub.add_parser("editar"); p.add_argument("slug"); p.add_argument("--dados", required=True)
    p = sub.add_parser("apagar"); p.add_argument("slug"); p.add_argument("--look"); p.add_argument("--confirmar", action="store_true")
    a = ap.parse_args()
    if a.acao == "saldo":
        print(json.dumps({"saldo_usd": H.saldo(), "custo_por_imagem_usd": H.CUSTO_IMAGEM}))
    elif a.acao == "mostrar":
        print(json.dumps(ler(a.slug), ensure_ascii=False, indent=2))
    else:
        {"listar": cmd_listar, "opcoes": cmd_opcoes, "salvar": cmd_salvar, "registrar": cmd_registrar, "editar": cmd_editar,
         "apagar": cmd_apagar}[a.acao](a)


if __name__ == "__main__":
    main()
