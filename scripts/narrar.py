"""Narração por voz de IA (ElevenLabs) e vídeos só de animações.

Um vídeo narrado não tem câmera: o "bruto" é um fundo liso na cor do estilo com o áudio da
narração, gravado em videos/.trabalho/<id>/<id>.mp4 (narracao.json marca a pasta). Depois disso
ele segue o caminho normal: motion → legenda → finalizar.

  vozes [--json]                          vozes da conta (padrão, clonadas, adicionadas)
  biblioteca [--json]                     vozes brasileiras da biblioteca pública
  adicionar <public_user_id> <voice_id> --nome X   adiciona uma voz da biblioteca à conta
  amostras --vozes id,id --texto-arquivo f --saida pasta
  custo --texto-arquivo f [--modelo X]    caracteres, minutos e créditos estimados
  gerar <id> --texto-arquivo f --voz V [--formato horizontal|vertical] [--modelo X] [--velocidade 1.0] [--refazer]
  audio <id> --audio arquivo [--formato F]  usa um áudio gravado pelo aluno (depois: transcrever e cortar)
  layout <trabalho> <formato> [--estilo X] [--fundo imagem]   fundo + áudio do cortado.mp4 → base.mp4

Chave: ELEVENLABS_API_KEY no .env, com as permissões "Text to Speech" e "Voices" (leitura).
Modelo: NARRACAO_MODELO no .env (padrão eleven_multilingual_v2; eleven_flash_v2_5 custa metade).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

API = "https://api.elevenlabs.io"
MODELO_PADRAO = "eleven_multilingual_v2"
CREDITO_POR_CARACTERE = {"eleven_flash_v2_5": 0.5, "eleven_v4_turbo": 0.5}
CARACTERES_POR_MINUTO = 900  # fala em português, ritmo de vídeo
INICIO_SILENCIO, FIM_SILENCIO = 0.4, 1.2
TAMANHO_PEDACO = 2000
SR = 44100
ESTILOS = C.RAIZ / "motion" / "estilos"


class ErroNarracao(SystemExit):
    pass


# ---------------------------------------------------------------------- API ----

def chave() -> str:
    k = C.ler_env("ELEVENLABS_API_KEY")
    if not k:
        raise ErroNarracao("✗ falta a chave da ElevenLabs (ELEVENLABS_API_KEY no .env)")
    return k


def modelo_padrao() -> str:
    return C.ler_env("NARRACAO_MODELO") or MODELO_PADRAO


def _erro_api(r) -> str:
    try:
        det = r.json().get("detail")
    except ValueError:
        det = None
    status = det.get("status", "") if isinstance(det, dict) else ""
    msg = det.get("message", "") if isinstance(det, dict) else (str(det) if det else r.text[:300])
    if r.status_code == 401 and ("missing_permissions" in status or "permission" in msg.lower()):
        return "a chave não tem permissão para isso: crie uma chave com \"Text to Speech\" e \"Voices\" liberados"
    if r.status_code == 401:
        return "chave recusada: confira se copiou inteira"
    if status == "quota_exceeded" or r.status_code == 402:
        return "o saldo da ElevenLabs acabou: adicione créditos em https://elevenlabs.io/app/subscription"
    if r.status_code == 429:
        return "muitos pedidos ao mesmo tempo; tente de novo em alguns segundos"
    if status == "voice_not_found":
        return "voz não encontrada na conta"
    return f"a ElevenLabs respondeu {r.status_code}: {msg}"


def pedir(metodo: str, caminho: str, **kw):
    import requests

    try:
        r = requests.request(metodo, API + caminho, headers={"xi-api-key": chave()}, timeout=kw.pop("timeout", 120), **kw)
    except requests.RequestException:
        raise ErroNarracao("✗ sem conexão com a ElevenLabs (internet caiu ou o serviço está fora do ar)")
    if r.status_code >= 400:
        raise ErroNarracao("✗ " + _erro_api(r))
    return r.json()


def falar(texto: str, voz: str, modelo: str, velocidade: float = 1.0,
          antes: str = "", depois: str = "") -> tuple[bytes, dict]:
    """Áudio mp3 e alinhamento por caractere (texto original, sem normalizar)."""
    corpo = {"text": texto, "model_id": modelo,
             "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0,
                                "use_speaker_boost": True, "speed": velocidade}}
    if antes:
        corpo["previous_text"] = antes[-400:]
    if depois:
        corpo["next_text"] = depois[:400]
    d = pedir("POST", f"/v1/text-to-speech/{voz}/with-timestamps?output_format=mp3_44100_128", json=corpo, timeout=300)
    return base64.b64decode(d["audio_base64"]), (d.get("alignment") or d.get("normalized_alignment") or {})


# -------------------------------------------------------------------- texto ----

def ler_texto(arq: Path) -> str:
    t = arq.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    if not t:
        raise ErroNarracao("✗ o texto da narração está vazio")
    return t


def pedacos(texto: str, limite: int = TAMANHO_PEDACO) -> list[str]:
    """Divide nos parágrafos e, se preciso, nas frases, sem passar do limite."""
    out: list[str] = []
    for par in [p.strip() for p in texto.split("\n\n") if p.strip()]:
        frases = re.split(r"(?<=[.!?…])\s+", par.replace("\n", " "))
        atual = ""
        for f in frases:
            if atual and len(atual) + 1 + len(f) > limite:
                out.append(atual)
                atual = f
            else:
                atual = f"{atual} {f}".strip()
        if atual:
            out.append(atual)
    # junta parágrafos curtos para gastar menos pedidos e manter a entonação contínua
    juntos: list[str] = []
    for p in out:
        if juntos and len(juntos[-1]) + 2 + len(p) <= limite:
            juntos[-1] += "\n\n" + p
        else:
            juntos.append(p)
    return juntos


def palavras_do_alinhamento(al: dict, deslocamento: float) -> list[dict]:
    chars = al.get("characters") or []
    ini = al.get("character_start_times_seconds") or []
    fim = al.get("character_end_times_seconds") or []
    out, atual = [], None
    for c, a, b in zip(chars, ini, fim):
        if c.isspace():
            if atual:
                out.append(atual)
                atual = None
            continue
        if atual is None:
            atual = {"text": c, "start": a, "end": b}
        else:
            atual["text"] += c
            atual["end"] = b
    if atual:
        out.append(atual)
    for w in out:
        w["end"] = round(max(w["end"], w["start"] + 0.05) + deslocamento, 3)
        w["start"] = round(w["start"] + deslocamento, 3)
    # sobra de pontuação solta ("—", "-") vira parte da palavra anterior
    limpas: list[dict] = []
    for w in out:
        if limpas and not re.search(r"\w", w["text"]):
            limpas[-1]["text"] += w["text"] if w["text"] not in "-–—" else ""
            limpas[-1]["end"] = max(limpas[-1]["end"], w["end"])
        else:
            limpas.append(w)
    return limpas


# -------------------------------------------------------------------- áudio ----

def decodificar(mp3: bytes):
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       input=mp3, capture_output=True)
    if r.returncode:
        raise ErroNarracao("✗ não consegui ler o áudio recebido da ElevenLabs")
    return np.frombuffer(r.stdout, dtype=np.float32)


def duracao_audio(arq: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


# -------------------------------------------------------------------- fundo ----

def _rgb(hex_cor: str) -> tuple[int, int, int]:
    h = hex_cor.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb) -> float:
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255


def estilo_atual(trab: Path, estilo: str | None) -> dict:
    roteiro = C.ler_json(trab / "motion" / "roteiro.json", {}) or {}
    marca = C.ler_marca()
    nome = estilo or roteiro.get("estilo") or (marca.get("motion") or {}).get("estilo") or "escuro"
    arq = ESTILOS / f"{nome}.json"
    est = json.loads((arq if arq.exists() else ESTILOS / "escuro.json").read_text(encoding="utf-8"))
    cores = marca.get("cores") or {}
    if cores.get("destaque"):
        est["vars"]["--destaque"] = cores["destaque"]
    if cores.get("secundaria"):
        est["vars"]["--destaque-2"] = cores["secundaria"]
    return est


def gerar_fundo(W: int, H: int, est: dict, destino: Path) -> None:
    """Gradiente suave + dois brilhos difusos nas cores do estilo. Escuro se o texto dos cards é claro."""
    import numpy as np
    from PIL import Image

    texto = _rgb(est["vars"]["--texto"])
    escuro = _lum(texto) > 0.5
    if est["id"] == "pop":
        topo, base = _rgb("#2a1157"), _rgb("#140829")
    elif escuro:
        topo, base = _rgb("#15171d"), _rgb("#0b0c10")
    elif est["id"] == "editorial":
        topo, base = _rgb("#f3ede2"), _rgb("#e6dccb")
    else:
        topo, base = _rgb("#f5f6f8"), _rgb("#e3e7ee")
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img = np.array(topo, np.float32) * (1 - y) + np.array(base, np.float32) * y
    img = np.broadcast_to(img, (H, W, 3)).copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    raio = max(W, H) * 0.55
    for cor, (cx, cy), forca in ((est["vars"]["--destaque"], (0.12, 0.10), 0.16 if escuro else 0.12),
                                 (est["vars"]["--destaque-2"], (0.92, 0.88), 0.10 if escuro else 0.08)):
        d2 = ((xx - cx * W) ** 2 + (yy - cy * H) ** 2) / (raio ** 2)
        a = (np.exp(-d2 * 2.2) * forca)[..., None]
        img = img * (1 - a) + np.array(_rgb(cor), np.float32) * a
    # um pouco de granulado esconde o degradê em faixas depois da compressão
    rng = np.random.default_rng(7)
    img += rng.normal(0, 1.6, img.shape).astype(np.float32)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(destino)


def fundo_imagem(arq: Path, W: int, H: int, destino: Path) -> None:
    from PIL import Image, ImageOps

    with Image.open(arq) as im:
        ImageOps.fit(im.convert("RGB"), (W, H), Image.LANCZOS).save(destino)


def tamanho(formato: str) -> tuple[int, int]:
    return (1080, 1920) if formato == "vertical" else (1920, 1080)


def montar_video(fundo: Path, audio: Path, destino: Path, dur: float, fps: int = 30) -> None:
    tmp = destino.with_suffix(".tmp.mp4")
    C.rodar(["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(fundo), "-i", str(audio),
             "-map", "0:v", "-map", "1:a", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
             "-tune", "stillimage", "-crf", "18", "-g", str(fps), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(tmp)])
    tmp.replace(destino)


def pasta_nova(vid: str, refazer: bool = False) -> Path:
    vid = C.limpar_nome(vid)
    if not vid:
        raise ErroNarracao("✗ nome inválido para o vídeo")
    t = C.TRABALHO / vid
    if refazer and (t / "narracao.json").exists():
        # tudo nesta pasta foi gerado a partir do texto (não há bruto do aluno): pode recomeçar
        roteiro = C.ler_json(t / "motion" / "roteiro.json")
        shutil.rmtree(t)
        if roteiro:
            C.gravar_json(t / "motion" / "roteiro-anterior.json", roteiro)
    elif any(b.stem == vid for b in C.listar_brutos()):
        raise ErroNarracao(f"✗ já existe um vídeo chamado \"{vid}\"; escolha outro nome")
    t.mkdir(parents=True, exist_ok=True)
    return t


def preparar_origem(t: Path, formato: str, audio: Path, dur: float) -> Path:
    """Fundo + áudio → <id>.mp4 (o "bruto" do vídeo narrado, que nunca sai da pasta de trabalho)."""
    W, H = tamanho(formato)
    est = estilo_atual(t, None)
    gerar_fundo(W, H, est, t / f"fundo_{formato}.png")
    origem = t / f"{t.name}.mp4"
    montar_video(t / f"fundo_{formato}.png", audio, origem, dur)
    return origem


# ------------------------------------------------------------------ comandos ----

def resumir_voz(v: dict) -> dict:
    lab = v.get("labels") or {}
    langs = v.get("verified_languages") or []
    pt = any((l.get("language") or "").startswith("pt") for l in langs) or (lab.get("language") or "").startswith("pt")
    sotaque = next((l.get("accent") or l.get("locale") for l in langs if (l.get("language") or "").startswith("pt")), None)
    return {"id": v["voice_id"], "nome": v.get("name"), "tipo": v.get("category"),
            "genero": lab.get("gender"), "idade": lab.get("age"), "sotaque": sotaque or lab.get("accent"),
            "descricao": lab.get("descriptive") or lab.get("description") or v.get("description"),
            "portugues": pt, "amostra": v.get("preview_url")}


def cmd_vozes(a) -> None:
    vozes, token = [], None
    while True:
        q = "/v2/voices?page_size=100" + (f"&next_page_token={token}" if token else "")
        d = pedir("GET", q)
        vozes += [resumir_voz(v) for v in d.get("voices", [])]
        token = d.get("next_page_token")
        if not d.get("has_more") or not token:
            break
    ordem = {"cloned": 0, "professional": 0, "generated": 1, "premade": 3}
    vozes.sort(key=lambda v: (ordem.get(v["tipo"], 2), not v["portugues"], v["nome"] or ""))
    if a.json:
        print(json.dumps(vozes, indent=1, ensure_ascii=False))
        return
    for v in vozes:
        print(f"{v['id']}  {v['nome']:<24} {v['tipo'] or '':<12} {v['genero'] or '':<7} pt={'sim' if v['portugues'] else 'não'}")


def cmd_biblioteca(a) -> None:
    d = pedir("GET", "/v1/shared-voices?page_size=30&language=pt&locale=pt-BR&sort=trending")
    vozes = [{"id": v["voice_id"], "dono": v.get("public_owner_id"), "nome": v.get("name"),
              "genero": v.get("gender"), "idade": v.get("age"), "sotaque": v.get("accent") or v.get("locale"),
              "descricao": v.get("descriptive") or v.get("description"), "uso": v.get("use_case"),
              "amostra": v.get("preview_url")} for v in d.get("voices", [])]
    if a.json:
        print(json.dumps(vozes, indent=1, ensure_ascii=False))
        return
    for v in vozes:
        print(f"{v['dono']} {v['id']}  {v['nome']:<28} {v['genero'] or '':<7} {v['uso'] or ''}")


def cmd_adicionar(a) -> None:
    d = pedir("POST", f"/v1/voices/add/{a.dono}/{a.voz}", json={"new_name": a.nome})
    print(json.dumps({"ok": True, "id": d.get("voice_id"), "nome": a.nome}, ensure_ascii=False))


def trecho_amostra(texto: str, alvo: int = 220) -> str:
    frases = re.split(r"(?<=[.!?…])\s+", texto.replace("\n", " ").strip())
    out = ""
    for f in frases:
        if out and len(out) + len(f) > alvo:
            break
        out = f"{out} {f}".strip()
    return out[: alvo + 120]


def cmd_amostras(a) -> None:
    texto = trecho_amostra(ler_texto(Path(a.texto_arquivo)))
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    modelo = a.modelo or modelo_padrao()
    nomes = {}
    try:
        nomes = {v["id"]: v["nome"] for v in json.loads(a.nomes)} if a.nomes else {}
    except (ValueError, KeyError, TypeError):
        pass
    feitos = []
    for n, voz in enumerate(a.vozes.split(","), 1):
        mp3, _ = falar(texto, voz, modelo, a.velocidade)
        nome = C.limpar_nome(nomes.get(voz) or voz)
        arq = saida / f"voz-{n}-{nome}.mp3"
        arq.write_bytes(mp3)
        feitos.append({"n": n, "voz": voz, "arquivo": str(arq)})
    print(json.dumps({"texto": texto, "caracteres": len(texto) * len(feitos), "amostras": feitos},
                     indent=1, ensure_ascii=False))


def estimar(texto: str, modelo: str) -> dict:
    n = len(texto)
    return {"caracteres": n, "minutos": round(n / CARACTERES_POR_MINUTO, 1), "modelo": modelo,
            "creditos": int(round(n * CREDITO_POR_CARACTERE.get(modelo, 1.0)))}


def saldo() -> dict | None:
    try:
        d = pedir("GET", "/v1/user/subscription", timeout=20)
    except SystemExit:
        return None
    usados, limite = d.get("character_count"), d.get("character_limit")
    if usados is None or limite is None:
        return None
    return {"restantes_no_plano": max(0, limite - usados), "plano": d.get("tier")}


def cmd_custo(a) -> None:
    modelo = a.modelo or modelo_padrao()
    out = estimar(ler_texto(Path(a.texto_arquivo)), modelo)
    s = saldo() if not a.offline else None
    if s:
        out["saldo"] = s
    print(json.dumps(out, indent=1, ensure_ascii=False))


def gravar_palavras(t: Path, palavras: list[dict], motor: str) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from transcrever import para_scribe

    vid = t.name
    (t / "edit" / "transcripts").mkdir(parents=True, exist_ok=True)
    C.gravar_json(t / "edit" / "transcripts" / f"{vid}.json",
                  para_scribe(palavras, {"language_code": "Portuguese", "engine": motor}))
    C.gravar_json(t / "palavras.json", [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in palavras])


def cmd_gerar(a) -> None:
    import numpy as np
    import soundfile as sf

    texto = ler_texto(Path(a.texto_arquivo))
    modelo = a.modelo or modelo_padrao()
    t = pasta_nova(a.id, a.refazer)
    partes = pedacos(texto)
    audio = [np.zeros(int(SR * INICIO_SILENCIO), np.float32)]
    pos = INICIO_SILENCIO
    palavras: list[dict] = []
    for i, p in enumerate(partes):
        print(f"⏳ Passo {i + 1}/{len(partes) + 1}: gravar a narração (parte {i + 1} de {len(partes)}).", flush=True)
        mp3, al = falar(p, a.voz, modelo, a.velocidade,
                        antes=partes[i - 1] if i else "", depois=partes[i + 1] if i + 1 < len(partes) else "")
        x = decodificar(mp3)
        palavras += palavras_do_alinhamento(al, pos)
        audio.append(x)
        pos += len(x) / SR
    audio.append(np.zeros(int(SR * FIM_SILENCIO), np.float32))
    wav = t / "narracao.wav"
    sf.write(wav, np.concatenate(audio), SR, subtype="PCM_16")
    dur = duracao_audio(wav)

    print(f"⏳ Passo {len(partes) + 1}/{len(partes) + 1}: montar o vídeo com o fundo.", flush=True)
    origem = preparar_origem(t, a.formato, wav, dur)
    C.copiar(origem, t / "cortado.mp4")
    gravar_palavras(t, palavras, f"elevenlabs-tts/{modelo}")
    (t / "roteiro-narracao.txt").write_text(texto + "\n", encoding="utf-8")
    C.gravar_json(t / "narracao.json", {"tipo": "ia", "voz": a.voz, "voz_nome": a.voz_nome, "modelo": modelo,
                                        "velocidade": a.velocidade, "formato": a.formato,
                                        **estimar(texto, modelo), "duracao": round(dur, 2)})
    C.gerar_onda(origem, t / "onda_original.json")
    e = C.ler_estado(t.name)
    e.setdefault("escolhas", {}).update({"formatos": [a.formato], "pacote": "narrado"})
    e["origem"] = "narracao"
    C.salvar_estado(t.name, e)
    C.marcar_etapa(t.name, "transcricao", motor=f"elevenlabs-tts/{modelo}")
    C.marcar_etapa(t.name, "corte", narrado=True)
    print(json.dumps({"id": t.name, "duracao": round(dur, 2), "palavras": len(palavras), "pedacos": len(partes),
                      "caracteres": len(texto), "audio": str(wav)}, ensure_ascii=False))


def cmd_audio(a) -> None:
    arq = Path(a.audio)
    if not arq.exists():
        raise ErroNarracao(f"✗ áudio não encontrado: {arq}")
    t = pasta_nova(a.id, a.refazer)
    wav = t / "narracao.wav"
    C.rodar(["ffmpeg", "-y", "-i", str(arq), "-vn", "-ac", "1", "-ar", str(SR), str(wav)])
    dur = duracao_audio(wav)
    preparar_origem(t, a.formato, wav, dur)
    C.gravar_json(t / "narracao.json", {"tipo": "audio", "arquivo": str(arq), "formato": a.formato,
                                        "duracao": round(dur, 2)})
    e = C.ler_estado(t.name)
    e.setdefault("escolhas", {}).update({"formatos": [a.formato], "pacote": "narrado"})
    e["origem"] = "audio"
    C.salvar_estado(t.name, e)
    print(json.dumps({"id": t.name, "duracao": round(dur, 2)}, ensure_ascii=False))


def cmd_layout(a) -> None:
    """Fundo do formato + áudio do cortado.mp4 (narração já cortada, se foi o caso)."""
    t = Path(a.trabalho).resolve()
    cortado = t / "cortado.mp4"
    if not cortado.exists():
        raise ErroNarracao("✗ falta o cortado.mp4")
    W, H = tamanho(a.formato)
    pasta = t / a.formato
    pasta.mkdir(exist_ok=True)
    fundo = t / f"fundo_{a.formato}.png"
    est = estilo_atual(t, a.estilo)
    if a.fundo:
        fundo_imagem(Path(a.fundo), W, H, fundo)
    else:
        gerar_fundo(W, H, est, fundo)
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.wav"
        C.rodar(["ffmpeg", "-y", "-i", str(cortado), "-vn", "-ac", "2", "-ar", "48000", str(audio)])
        montar_video(fundo, audio, pasta / "base.mp4", C.info_video(cortado)["duracao"])
    leg = ({"alinhamento": "baixo", "margem_v": 1920 - 1480} if a.formato == "vertical"
           else {"alinhamento": "baixo", "margem_v": int(H * 0.08)})
    layout = {"formato": a.formato, "largura": W, "altura": H, "areas": {"voce": [0, 0, W, H]}, "costura": None,
              "rosto": None, "legenda": leg, "zooms": 0, "desfoques": 0, "sem_rosto": True,
              "centralizado": True, "fundo": {"estilo": est["id"], "imagem": str(a.fundo) if a.fundo else None}}
    C.gravar_json(pasta / "layout.json", layout)
    print(f"layout {a.formato} (narrado): {W}x{H}, fundo {'imagem' if a.fundo else est['id']} → {pasta / 'base.mp4'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Narração por IA e vídeos só de animações")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("vozes"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("biblioteca"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("adicionar"); p.add_argument("dono"); p.add_argument("voz"); p.add_argument("--nome", required=True)
    p = sub.add_parser("amostras"); p.add_argument("--vozes", required=True); p.add_argument("--texto-arquivo", required=True)
    p.add_argument("--saida", required=True); p.add_argument("--modelo"); p.add_argument("--velocidade", type=float, default=1.0)
    p.add_argument("--nomes", help='JSON [{"id": ..., "nome": ...}] para nomear os arquivos')
    p = sub.add_parser("custo"); p.add_argument("--texto-arquivo", required=True); p.add_argument("--modelo")
    p.add_argument("--offline", action="store_true")
    p = sub.add_parser("gerar"); p.add_argument("id"); p.add_argument("--texto-arquivo", required=True)
    p.add_argument("--voz", required=True); p.add_argument("--voz-nome"); p.add_argument("--modelo")
    p.add_argument("--formato", choices=["horizontal", "vertical"], default="vertical")
    p.add_argument("--velocidade", type=float, default=1.0)
    p.add_argument("--refazer", action="store_true", help="apaga a narração anterior deste id (voz/texto novos)")
    p = sub.add_parser("audio"); p.add_argument("id"); p.add_argument("--audio", required=True)
    p.add_argument("--refazer", action="store_true")
    p.add_argument("--formato", choices=["horizontal", "vertical"], default="vertical")
    p = sub.add_parser("layout"); p.add_argument("trabalho"); p.add_argument("formato", choices=["horizontal", "vertical"])
    p.add_argument("--estilo"); p.add_argument("--fundo")
    a = ap.parse_args()
    if getattr(a, "velocidade", None) is not None and not 0.7 <= a.velocidade <= 1.2:
        ap.error("--velocidade vai de 0.7 a 1.2")
    {"vozes": cmd_vozes, "biblioteca": cmd_biblioteca, "adicionar": cmd_adicionar, "amostras": cmd_amostras,
     "custo": cmd_custo, "gerar": cmd_gerar, "audio": cmd_audio, "layout": cmd_layout}[a.cmd](a)


if __name__ == "__main__":
    main()
