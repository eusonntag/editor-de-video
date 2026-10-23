"""Cliente da API da HeyGen (v3): saldo da carteira, personagens a partir de descrição e vídeos com Avatar IV.

A API usa uma carteira pré-paga própria (dólares), separada dos créditos do site.
Chave em HEYGEN_API_KEY no .env.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

API = "https://api.heygen.com"
CUSTO_IMAGEM = 1.0  # US$ por personagem gerado de descrição (medido em 23/10/2026)
CUSTO_MINUTO = 2.4  # US$ por minuto, Avatar IV com personagem, 1080p (medido em 23/10/2026: 13,4 s custaram US$ 0,52)


class ErroHeygen(SystemExit):
    pass


def chave() -> str:
    k = C.ler_env("HEYGEN_API_KEY")
    if not k:
        raise ErroHeygen("✗ falta a chave da HeyGen (HEYGEN_API_KEY no .env)")
    return k


def _erro_api(r) -> str:
    try:
        err = r.json().get("error") or {}
    except ValueError:
        err = {}
    codigo, msg = err.get("code", ""), err.get("message", "") or r.text[:300]
    if r.status_code == 402 or codigo == "insufficient_credit":
        return ("sem saldo na carteira da API da HeyGen: coloque créditos em app.heygen.com, na área da API "
                "(a partir de US$ 5); os créditos do site não valem para a API")
    if r.status_code in (401, 403):
        return "chave recusada: confira se copiou inteira"
    if r.status_code == 429:
        return "limite de pedidos atingido agora: tente de novo em alguns minutos"
    return f"a HeyGen respondeu {r.status_code}: {msg}"


def req(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    import requests

    try:
        r = requests.request(metodo, API + caminho, json=corpo, timeout=60,
                             headers={"x-api-key": chave(), "Content-Type": "application/json"})
    except requests.RequestException:
        raise ErroHeygen("✗ sem conexão com a HeyGen (internet caiu ou o serviço está fora do ar)")
    if r.status_code >= 400:
        raise ErroHeygen("✗ " + _erro_api(r))
    return r.json()


def saldo() -> float:
    d = req("GET", "/v3/users/me").get("data") or {}
    return float((d.get("wallet") or {}).get("remaining_balance") or 0)


def _id_look(d: dict) -> str | None:
    for k in ("look_id", "avatar_id", "id"):
        if d.get(k):
            return d[k]
    for k in ("avatar_item", "look", "avatar"):
        if isinstance(d.get(k), dict) and d[k].get("id"):
            return d[k]["id"]
    return None


def criar_look(nome: str, prompt: str, proporcao: str = "16:9", base: str | None = None) -> str:
    """Personagem a partir de descrição (até 1000 caracteres). Com `base` (id de um look), mantém a pessoa
    e muda roupa/cenário conforme o prompt."""
    corpo = {"type": "prompt", "name": nome, "prompt": prompt[:1000], "aspect_ratio": proporcao}
    if base:
        corpo["avatar_id"] = base
    d = req("POST", "/v3/avatars", corpo).get("data") or {}
    look = _id_look(d)
    if not look:
        raise ErroHeygen(f"✗ a HeyGen não devolveu o personagem: {str(d)[:300]}")
    return look


def esperar_look(look: str, limite: float = 600) -> dict:
    fim = time.time() + limite
    while True:
        d = req("GET", f"/v3/avatars/looks/{look}").get("data") or {}
        if d.get("status") != "processing" or time.time() > fim:
            return d
        time.sleep(5)


def vozes(idioma: str = "Portuguese", limite: int = 100) -> list[dict]:
    d = req("GET", f"/v3/voices?language={idioma}&limit={limite}")
    return d.get("data") or []


def enviar_asset(arquivo: Path) -> str:
    import requests

    try:
        with open(arquivo, "rb") as f:
            r = requests.post(API + "/v3/assets", headers={"x-api-key": chave()},
                              files={"file": (arquivo.name, f)}, timeout=300)
    except requests.RequestException:
        raise ErroHeygen("✗ sem conexão com a HeyGen ao enviar o áudio")
    if r.status_code >= 400:
        raise ErroHeygen("✗ " + _erro_api(r))
    d = r.json().get("data") or {}
    if not d.get("asset_id"):
        raise ErroHeygen(f"✗ a HeyGen não devolveu o arquivo enviado: {str(d)[:300]}")
    return d["asset_id"]


def criar_video(corpo: dict, chave_unica: str) -> str:
    """POST /v3/videos (Avatar IV por padrão). `chave_unica` evita cobrança dobrada se o pedido for repetido."""
    import requests

    try:
        r = requests.post(API + "/v3/videos", json=corpo, timeout=60,
                          headers={"x-api-key": chave(), "Content-Type": "application/json",
                                   "Idempotency-Key": chave_unica[:255]})
    except requests.RequestException:
        raise ErroHeygen("✗ sem conexão com a HeyGen (internet caiu ou o serviço está fora do ar)")
    if r.status_code >= 400:
        raise ErroHeygen("✗ " + _erro_api(r))
    d = r.json().get("data") or {}
    if not d.get("video_id"):
        raise ErroHeygen(f"✗ a HeyGen não aceitou o pedido do vídeo: {str(d)[:300]}")
    return d["video_id"]


def esperar_video(video_id: str, limite: float = 3600) -> dict:
    fim = time.time() + limite
    while True:
        d = req("GET", f"/v3/videos/{video_id}").get("data") or {}
        if d.get("status") in ("completed", "failed") or time.time() > fim:
            return d
        time.sleep(15)


def baixar(url: str, destino: Path) -> None:
    import requests

    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
    except requests.RequestException:
        raise ErroHeygen("✗ não consegui baixar a imagem da HeyGen (internet caiu?)")
    destino.write_bytes(r.content)
