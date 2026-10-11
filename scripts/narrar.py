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
  sobre <id> --modo inteiro|trechos|trocar --voz V [--texto-arquivo f | --trechos-arquivo j] [--inicio s]
        [--audio-original mudo|baixo|manter] [--velocidade v] [--so-custo]   narração num vídeo existente
  remover <id>                            desfaz a narração sobre o vídeo

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
    if status == "ivc_not_permitted" or (isinstance(det, dict) and det.get("code") == "subscription_required"):
        return "esta voz (clonada) não está liberada no plano atual da ElevenLabs: escolha outra voz ou mude o plano"
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

def decodificar(mp3: bytes, sr: int = SR):
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
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
    elif est["id"] == "cinema":  # quase preto: os pontos e o texto branco brilham sozinhos
        topo, base = _rgb("#0b0b0d"), _rgb("#050506")
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


# ------------------------------------------- narração sobre um vídeo existente ----
# Os três modos mexem no cortado.mp4 (ou no bruto, se o vídeo não tem corte) e guardam o original em
# cortado_sem_narracao.mp4 / palavras_sem_narracao.json (+ dinamica/desfoque), para refazer ou remover.
#   inteiro: uma narração começando em --inicio (vídeo sem fala: tela, produto, imagens)
#   trechos: falas em pontos escolhidos (--trechos-arquivo [{"em": s, "texto": "...", "pausar": false}])
#            pausar = congela a imagem enquanto a narração fala (empurra o resto do vídeo)
#   trocar:  a voz de IA fala o mesmo texto do vídeo, frase a frase, no ritmo da fala original

SR_V = 48000
GANHO_ORIGINAL = {"mudo": 0.0, "baixo": 0.15, "manter": 1.0}
EXTRAS = ("palavras", "dinamica", "desfoque", "motion/roteiro")  # guardados como <nome>_sem_narracao.json


def ler_audio(video: Path, dur: float, sr: int = SR_V):
    import numpy as np

    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).copy() if r.returncode == 0 else np.zeros(0, np.float32)
    n = int(round(dur * sr))
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def esticar(x, fator: float, sr: int = SR_V):
    """Muda a duração sem mudar o tom (atempo). fator > 1 acelera."""
    import numpy as np

    if abs(fator - 1) < 0.01 or not len(x):
        return x
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
                        "-filter:a", f"atempo={fator:.4f}", "-f", "f32le", "-"],
                       input=x.astype(np.float32).tobytes(), capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy() if r.returncode == 0 else x


def base_sobre(t: Path, vid: str) -> tuple[Path, list[dict], bool]:
    """(vídeo base, palavras base, base é o bruto). Na 1ª narração guarda o corte original."""
    extra = C.ler_json(t / "narracao_extra.json", {}) or {}
    if extra.get("base_bruto"):
        return C.achar_bruto(vid), [], True
    orig = t / "cortado_sem_narracao.mp4"
    if not orig.exists():
        if not (t / "cortado.mp4").exists():
            return C.achar_bruto(vid), [], True
        shutil.copy2(t / "cortado.mp4", orig)
        for nome in EXTRAS:
            if (t / f"{nome}.json").exists():
                shutil.copy2(t / f"{nome}.json", t / f"{nome}_sem_narracao.json")
    return orig, C.ler_json(t / "palavras_sem_narracao.json", []) or [], False


def _norm(p: str) -> str:
    import unicodedata

    p = unicodedata.normalize("NFD", p.lower())
    return "".join(ch for ch in p if ch.isalnum())


def frases_de(palavras: list[dict], pausa: float = 0.45, max_palavras: int = 28) -> list[list[int]]:
    out: list[list[int]] = []
    for i, w in enumerate(palavras):
        if out:
            ant = palavras[out[-1][-1]]
            if (w["start"] - ant["end"] <= pausa and not ant["text"].endswith((".", "!", "?"))
                    and len(out[-1]) < max_palavras):
                out[-1].append(i)
                continue
        out.append([i])
    return out


def falas_trocar(pal: list[dict], voz: str, modelo: str, velocidade: float, avisos: list[str]) -> list[dict]:
    """Fala o mesmo texto com a voz de IA; cada frase é esticada/encolhida para caber no tempo da original."""
    import difflib

    pal = [w for w in pal if re.search(r"\w", w["text"])]
    if not pal:
        raise ErroNarracao("✗ este vídeo não tem fala transcrita para trocar a voz")
    frases = frases_de(pal)
    blocos: list[list[list[int]]] = [[]]
    for f in frases:
        tam = sum(len(pal[i]["text"]) + 1 for fr in blocos[-1] for i in fr)
        if blocos[-1] and tam + sum(len(pal[i]["text"]) + 1 for i in f) > TAMANHO_PEDACO:
            blocos.append([])
        blocos[-1].append(f)
    textos = [" ".join(pal[i]["text"] for fr in b for i in fr) for b in blocos]
    falas, cursor = [], 0.0
    for n, (bloco, texto) in enumerate(zip(blocos, textos)):
        print(f"⏳ Passo {n + 1}/{len(blocos) + 1}: gravar a voz nova (parte {n + 1} de {len(blocos)}).", flush=True)
        mp3, al = falar(texto, voz, modelo, velocidade, antes=textos[n - 1] if n else "",
                        depois=textos[n + 1] if n + 1 < len(textos) else "")
        audio = decodificar(mp3, SR_V)
        ws = palavras_do_alinhamento(al, 0.0)
        idx = [i for fr in bloco for i in fr]
        # palavra original ↔ palavra falada pela IA (normalmente 1 para 1)
        par: dict[int, int] = {}
        if len(ws) == len(idx):
            par = {i: k for k, i in enumerate(idx)}
        else:
            sm = difflib.SequenceMatcher(a=[_norm(pal[i]["text"]) for i in idx], b=[_norm(w["text"]) for w in ws],
                                         autojunk=False)
            for m in sm.get_matching_blocks():
                for d in range(m.size):
                    par[idx[m.a + d]] = m.b + d
            avisos.append(f"parte {n + 1}: a voz leu {len(ws)} palavras para {len(idx)} do texto; o sincronismo pode variar")
        for fr in bloco:
            casadas = [i for i in fr if i in par]
            if not casadas:
                continue
            ts, te = ws[par[casadas[0]]]["start"], ws[par[casadas[-1]]]["end"]
            os_, oe = pal[fr[0]]["start"], pal[fr[-1]]["end"]
            a0, a1 = max(0.0, ts - 0.04), te + 0.10
            trecho = audio[int(a0 * SR_V): int(a1 * SR_V)]
            fator = min(1.3, max(0.8, (te - ts) / max(oe - os_, 0.2)))
            if fator in (0.8, 1.3):
                avisos.append(f"frase em {os_:.1f}s: a voz nova ficou {'mais longa' if fator == 1.3 else 'mais curta'} que a original")
            esticado = esticar(trecho, fator)
            pos = max(os_ - 0.04, cursor)
            cursor = pos + len(esticado) / SR_V
            falas.append({"pos": pos, "pausar": False, "audio": esticado,
                          "palavras": [{"text": pal[i]["text"], "start": (ws[par[i]]["start"] - a0) / fator,
                                        "end": (ws[par[i]]["end"] - a0) / fator} for i in casadas]})
    return falas


def falas_trechos(trechos: list[dict], voz: str, modelo: str, velocidade: float) -> list[dict]:
    falas = []
    textos = [tr["texto"].strip() for tr in trechos]
    for n, (tr, texto) in enumerate(zip(trechos, textos)):
        print(f"⏳ Passo {n + 1}/{len(trechos) + 1}: gravar a narração (trecho {n + 1} de {len(trechos)}).", flush=True)
        audio, palavras = [], []
        pos = 0.0
        partes = pedacos(texto)
        for k, p in enumerate(partes):
            mp3, al = falar(p, voz, modelo, velocidade, antes=partes[k - 1] if k else (textos[n - 1] if n else ""),
                            depois=partes[k + 1] if k + 1 < len(partes) else "")
            x = decodificar(mp3, SR_V)
            palavras += palavras_do_alinhamento(al, pos)
            audio.append(x)
            pos += len(x) / SR_V
        import numpy as np

        falas.append({"pos": float(tr["em"]), "pausar": bool(tr.get("pausar")), "audio": np.concatenate(audio),
                      "palavras": palavras, "texto": texto})
    return falas


def _deslocar(eventos: list[dict], mapear) -> list[dict]:
    out = []
    for ev in eventos:
        ev = dict(ev)
        for k in ("inicio", "fim"):
            if k in ev:
                ev[k] = round(mapear(ev[k]), 3)
        out.append(ev)
    return out


def montar_sobre(t: Path, base: Path, pal_base: list[dict], falas: list[dict], ganho: float,
                 voz_inteira_trocada: bool, avisos: list[str], ganho_no_video_todo: bool = False) -> dict:
    import numpy as np
    import soundfile as sf

    info = C.info_video(base)
    dur = info["duracao"]
    falas.sort(key=lambda f: f["pos"])
    for f in falas:
        f["pos"] = min(max(0.0, f["pos"]), dur - 0.05 if f["pausar"] else dur)
        f["dur"] = len(f["audio"]) / SR_V

    # pausas: a imagem congela no ponto `pos` enquanto a narração fala
    pausas: list[tuple[float, float]] = []
    acumulado = 0.0
    for f in falas:
        if f["pausar"]:
            d = round(f["dur"] + 0.3, 3)
            f["novo"] = f["pos"] + acumulado + 0.15
            pausas.append((f["pos"], d))
            acumulado += d

    def mapear(x: float) -> float:
        return x + sum(d for p, d in pausas if p <= x + 1e-6)

    for f in falas:
        if not f["pausar"]:
            f["novo"] = mapear(f["pos"])
    novo_total = dur + acumulado
    fim_falas = max((f["novo"] + f["dur"] for f in falas), default=0.0)
    extensao = round(max(0.0, fim_falas + 0.6 - novo_total), 3)
    novo_total += extensao

    # áudio original com as pausas (silêncio) e o volume baixado onde a narração fala
    orig = ler_audio(base, dur)
    pedacos_a, ultimo = [], 0
    for p, d in pausas:
        corte = int(round(p * SR_V))
        pedacos_a += [orig[ultimo:corte], np.zeros(int(round(d * SR_V)), np.float32)]
        ultimo = corte
    pedacos_a += [orig[ultimo:], np.zeros(int(round(extensao * SR_V)), np.float32)]
    fundo = np.concatenate(pedacos_a)
    n_total = int(round(novo_total * SR_V))
    fundo = np.pad(fundo, (0, max(0, n_total - len(fundo))))[:n_total]
    env = np.ones(n_total, np.float32) * (0.0 if voz_inteira_trocada else ganho if ganho_no_video_todo else 1.0)
    if not voz_inteira_trocada and not ganho_no_video_todo and ganho < 1.0:
        rampa = int(0.2 * SR_V)
        for f in falas:
            a, b = int((f["novo"] - 0.1) * SR_V), int((f["novo"] + f["dur"] + 0.1) * SR_V)
            a, b = max(0, a), min(n_total, b)
            env[a:b] = np.minimum(env[a:b], ganho)
            for k in range(1, rampa):  # transição suave na entrada e na saída
                g = ganho + (1 - ganho) * k / rampa
                if a - k >= 0:
                    env[a - k] = min(env[a - k], g)
                if b - 1 + k < n_total:
                    env[b - 1 + k] = min(env[b - 1 + k], g)
    narr = np.zeros(n_total, np.float32)
    for f in falas:
        a = int(round(f["novo"] * SR_V))
        x = f["audio"][: max(0, n_total - a)]
        narr[a:a + len(x)] += x
    mix = fundo * env + narr
    pico = float(np.abs(mix).max() or 1.0)
    if pico > 0.98:
        mix *= 0.98 / pico

    # palavras: as originais que continuam audíveis + as da narração
    faixas = [(f["novo"] - 0.05, f["novo"] + f["dur"]) for f in falas]
    palavras = []
    if not voz_inteira_trocada and not (ganho_no_video_todo and ganho < 1.0):
        for w in pal_base:
            s, e = mapear(w["start"]), mapear(w["end"])
            dentro = any(s < b and a < e for a, b in faixas)
            if dentro and ganho >= 1.0:
                avisos.append(f"a narração em {s:.1f}s fala junto com a sua voz (áudio original mantido)")
            if dentro and ganho < 1.0:
                continue
            palavras.append({"text": w["text"], "start": round(s, 3), "end": round(e, 3)})
    for f in falas:
        palavras += [{"text": w["text"], "start": round(f["novo"] + w["start"], 3), "end": round(f["novo"] + w["end"], 3)}
                     for w in f["palavras"]]
    palavras.sort(key=lambda w: w["start"])
    avisos[:] = list(dict.fromkeys(avisos))[:12]

    # vídeo: trechos do original + imagem congelada nas pausas e no fim (se a narração passar do vídeo)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "mix.wav"
        sf.write(wav, mix, SR_V, subtype="PCM_16")
        sf.write(t / "narracao.wav", narr, SR_V, subtype="PCM_16")
        destino = t / "cortado.mp4"
        saida = t / "cortado.tmp.mp4"
        cortes = sorted({p for p, _ in pausas})
        if not cortes and not extensao and base.name == "cortado_sem_narracao.mp4":
            C.rodar(["ffmpeg", "-y", "-i", str(base), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                     "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(saida)])
        else:
            # imagem parada = foto do quadro naquele ponto, repetida pelo tempo da narração
            W, H, fps = info["largura"], info["altura"], info["fps_int"]
            paradas = [(p, sum(d for q, d in pausas if q == p)) for p in cortes]
            if extensao:
                paradas.append((dur, extensao))
            entradas, filtros, rotulos = [], [], []
            limites = [0.0] + cortes + [dur]
            norm = f"scale={W}:{H},setsar=1,fps={fps},format=yuv420p"
            for k in range(len(limites) - 1):
                a, b = limites[k], limites[k + 1]
                if b - a >= 0.04:
                    filtros.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,{norm}[s{k}]")
                    rotulos.append(f"[s{k}]")
                parada = next((d for q, d in paradas if abs(q - b) < 1e-6), 0)
                if parada:
                    foto = Path(tmp) / f"quadro{k}.png"
                    C.rodar(["ffmpeg", "-y", "-ss", f"{max(0.0, min(b, dur - 0.1)):.3f}", "-i", str(base),
                             "-frames:v", "1", str(foto)])
                    entradas += ["-loop", "1", "-framerate", str(fps), "-t", f"{parada:.3f}", "-i", str(foto)]
                    n = 2 + len(entradas) // 8 - 1
                    filtros.append(f"[{n}:v]{norm}[p{k}]")
                    rotulos.append(f"[p{k}]")
            filtros.append(f"{''.join(rotulos)}concat=n={len(rotulos)}:v=1:a=0[v]")
            C.rodar(["ffmpeg", "-y", "-i", str(base), "-i", str(wav), *entradas, "-filter_complex", ";".join(filtros),
                     "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                     "-g", str(fps), "-c:a", "aac", "-b:a", "192k", "-t", f"{novo_total:.3f}",
                     "-movflags", "+faststart", str(saida)])
        saida.replace(destino)

    C.gravar_json(t / "palavras.json", palavras)
    for nome in ("dinamica", "desfoque"):
        orig_j = C.ler_json(t / f"{nome}_sem_narracao.json")
        if orig_j:
            chave = "eventos" if nome == "dinamica" else "regioes"
            orig_j[chave] = _deslocar(orig_j.get(chave, []), mapear)
            if nome == "dinamica" and "duracao" in orig_j:
                orig_j["duracao"] = round(novo_total, 3)
            C.gravar_json(t / f"{nome}.json", orig_j)
    roteiro = C.ler_json(t / "motion" / "roteiro_sem_narracao.json")
    if roteiro:
        # cards (e os momentos já sincronizados com a fala) acompanham as pausas
        for card in roteiro.get("cards", []):
            card["inicio"], card["fim"] = round(mapear(card["inicio"]), 3), round(mapear(card["fim"]), 3)
            c = card.get("campos") or {}
            alvos = [c] + [it for lista in ("itens", "passos") for it in (c.get(lista) or []) if isinstance(it, dict)]
            for obj in alvos:
                if obj.get("em") is not None:
                    obj["em"] = round(mapear(obj["em"]), 3)
        C.gravar_json(t / "motion" / "roteiro.json", roteiro)
    return {"duracao_antes": round(dur, 2), "duracao": round(novo_total, 2), "pausas": len(pausas),
            "imagem_parada_no_fim": extensao, "palavras": len(palavras)}


def cmd_sobre(a) -> None:
    vid = C.id_video(a.id)
    t = C.pasta(vid)
    if C.narrado(vid):
        raise ErroNarracao("✗ este vídeo já é narrado (sem câmera): use gerar --refazer")
    modelo = a.modelo or modelo_padrao()
    base, pal_base, base_bruto = base_sobre(t, vid)
    if a.modo == "trocar":
        if base_bruto or not pal_base:
            raise ErroNarracao("✗ para trocar a voz, o vídeo precisa estar transcrito e cortado")
        texto = " ".join(w["text"] for w in pal_base if re.search(r"\w", w["text"]))
        trechos = []
    elif a.modo == "inteiro":
        texto = ler_texto(Path(a.texto_arquivo))
        trechos = [{"em": a.inicio, "texto": texto, "pausar": False}]
    else:
        trechos = json.loads(Path(a.trechos_arquivo).read_text(encoding="utf-8"))
        if not trechos or not all(tr.get("texto", "").strip() for tr in trechos):
            raise ErroNarracao("✗ cada trecho precisa de \"em\" (segundos) e \"texto\"")
        texto = "\n\n".join(tr["texto"].strip() for tr in trechos)
    (t / "narracao_texto.txt").write_text(texto + "\n", encoding="utf-8")
    if a.so_custo:
        out = {**estimar(texto, modelo), "texto_arquivo": str(t / "narracao_texto.txt"),
               "duracao_video": round(C.info_video(base)["duracao"], 2)}
        s = saldo()
        if s:
            out["saldo"] = s
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return

    avisos: list[str] = []
    if a.modo == "trocar":
        falas = falas_trocar(pal_base, a.voz, modelo, a.velocidade, avisos)
    else:
        falas = falas_trechos(trechos, a.voz, modelo, a.velocidade)
    print("⏳ Passo final: juntar a narração com o vídeo.", flush=True)
    ganho = 0.0 if a.modo == "trocar" else GANHO_ORIGINAL[a.audio_original]
    resumo = montar_sobre(t, base, pal_base, falas, ganho, a.modo == "trocar", avisos,
                          ganho_no_video_todo=a.modo == "inteiro")

    C.gravar_json(t / "narracao_extra.json", {
        "modo": a.modo, "voz": a.voz, "voz_nome": a.voz_nome, "modelo": modelo, "velocidade": a.velocidade,
        "audio_original": "mudo" if a.modo == "trocar" else a.audio_original, "base_bruto": base_bruto,
        "trechos": [{"em": tr["em"], "texto": tr["texto"], "pausar": bool(tr.get("pausar"))} for tr in trechos],
        **estimar(texto, modelo), **resumo})
    C.gerar_onda(t / "cortado.mp4", t / "onda_cortado.json")
    C.desmarcar_a_partir(vid, "layout")
    if base_bruto:
        C.marcar_etapa(vid, "transcricao", motor="sem fala (narração por IA)")
    C.marcar_etapa(vid, "corte", narracao=a.modo)
    e = C.ler_estado(vid)
    e["narracao_extra"] = a.modo
    C.salvar_estado(vid, e)
    print(json.dumps({"id": vid, "modo": a.modo, **resumo, "avisos": avisos}, indent=1, ensure_ascii=False))


def cmd_remover(a) -> None:
    """Desfaz a narração sobre o vídeo: volta o corte (ou o bruto) como era."""
    vid = C.id_video(a.id)
    t = C.pasta(vid)
    extra = C.ler_json(t / "narracao_extra.json")
    if not extra:
        raise ErroNarracao("✗ este vídeo não tem narração para remover")
    if extra.get("base_bruto"):
        for arq in ("cortado.mp4", "palavras.json", "onda_cortado.json"):
            (t / arq).unlink(missing_ok=True)
        C.desmarcar_a_partir(vid, "transcricao")
    else:
        (t / "cortado_sem_narracao.mp4").replace(t / "cortado.mp4")
        for nome in EXTRAS:
            if (t / f"{nome}_sem_narracao.json").exists():
                (t / f"{nome}_sem_narracao.json").replace(t / f"{nome}.json")
        C.gerar_onda(t / "cortado.mp4", t / "onda_cortado.json")
        C.desmarcar_a_partir(vid, "layout")
    for arq in ("narracao_extra.json", "narracao.wav", "narracao_texto.txt"):
        (t / arq).unlink(missing_ok=True)
    e = C.ler_estado(vid)
    e.pop("narracao_extra", None)
    C.salvar_estado(vid, e)
    print(json.dumps({"id": vid, "removida": extra.get("modo")}, ensure_ascii=False))


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
    p = sub.add_parser("sobre"); p.add_argument("id"); p.add_argument("--modo", choices=["inteiro", "trechos", "trocar"], required=True)
    p.add_argument("--voz"); p.add_argument("--voz-nome"); p.add_argument("--modelo")
    p.add_argument("--velocidade", type=float, default=1.0)
    p.add_argument("--texto-arquivo"); p.add_argument("--trechos-arquivo"); p.add_argument("--inicio", type=float, default=0.3)
    p.add_argument("--audio-original", choices=["mudo", "baixo", "manter"], default="baixo")
    p.add_argument("--so-custo", action="store_true", help="só mostra caracteres e créditos (não gasta nada)")
    p = sub.add_parser("remover"); p.add_argument("id")
    p = sub.add_parser("layout"); p.add_argument("trabalho"); p.add_argument("formato", choices=["horizontal", "vertical"])
    p.add_argument("--estilo"); p.add_argument("--fundo")
    a = ap.parse_args()
    if a.cmd == "sobre" and not a.so_custo and not a.voz:
        ap.error("falta --voz")
    if a.cmd == "sobre" and a.modo == "inteiro" and not a.texto_arquivo:
        ap.error("o modo inteiro precisa de --texto-arquivo")
    if a.cmd == "sobre" and a.modo == "trechos" and not a.trechos_arquivo:
        ap.error("o modo trechos precisa de --trechos-arquivo")
    if getattr(a, "velocidade", None) is not None and not 0.7 <= a.velocidade <= 1.2:
        ap.error("--velocidade vai de 0.7 a 1.2")
    {"vozes": cmd_vozes, "biblioteca": cmd_biblioteca, "adicionar": cmd_adicionar, "amostras": cmd_amostras,
     "custo": cmd_custo, "gerar": cmd_gerar, "audio": cmd_audio, "layout": cmd_layout,
     "sobre": cmd_sobre, "remover": cmd_remover}[a.cmd](a)


if __name__ == "__main__":
    main()
