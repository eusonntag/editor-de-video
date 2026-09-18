"""Transcreve um vídeo com timestamps por palavra, no formato Scribe do video-use.

Motores:
  groq    -> Whisper large-v3 na API do Groq (padrão; rápido e barato, ~US$0,11/hora de áudio).
             Chave GROQ_API_KEY no .env da raiz do projeto ou no ambiente.
  whisper -> faster-whisper local (gratuito, roda na CPU, ~1x a duração do vídeo)
  scribe  -> ElevenLabs Scribe via tools/video-use/helpers/transcribe.py
             Chave ELEVENLABS_API_KEY no .env da raiz do projeto.
  auto    -> TRANSCRICAO_MOTOR do .env (groq|whisper|scribe); sem preferência: groq se houver
             GROQ_API_KEY, senão whisper local

Saída: <edit-dir>/transcripts/<nome_do_video>.json  (cache: não refaz se já existir)

Uso:
  python -X utf8 scripts/transcrever.py "videos/Para Editar/video.mp4" --edit-dir videos/.trabalho/video/edit
  python -X utf8 scripts/transcrever.py video.mp4 --edit-dir ... --motor whisper --modelo medium
  python -X utf8 scripts/transcrever.py video.mp4 --edit-dir ... --motor groq --modelo whisper-large-v3-turbo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VIDEO_USE = RAIZ / "tools" / "video-use"

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_LIMITE_MB = 24.0          # plano gratuito aceita 25 MB por requisição
GROQ_PEDACO_S = 20 * 60        # tamanho alvo de cada pedaço quando precisa dividir

# Prompt que empurra o Whisper a transcrever de forma literal (sem "limpar" a fala),
# o que é essencial para detectar repetições e frases refeitas.
PROMPT_LITERAL = (
    "Transcrição literal em português do Brasil, mantendo hesitações e repetições: "
    "é..., hã, hum, tipo, né, então, então, eu fui, eu fui no mercado."
)


# ---------------------------------------------------------------- chaves ----

def ler_env(arquivo: Path, chave: str) -> str:
    if arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith(f"{chave}="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def chave_groq() -> str:
    return ler_env(RAIZ / ".env", "GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")


def chave_elevenlabs() -> str:
    return ler_env(RAIZ / ".env", "ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")


def motor_preferido() -> str:
    motor = ler_env(RAIZ / ".env", "TRANSCRICAO_MOTOR").lower()
    if motor in {"groq", "whisper", "scribe"}:
        return motor
    return "groq" if chave_groq() else "whisper"


# ----------------------------------------------------------------- áudio ----

def extrair_audio(video: Path, destino: Path, formato: str) -> None:
    if formato == "wav":
        codec = ["-c:a", "pcm_s16le"]
    else:  # mp3 mono 16 kHz 48 kbps: ~0,36 MB/min, suficiente para reconhecimento de fala
        codec = ["-c:a", "libmp3lame", "-b:a", "48k"]
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", *codec, str(destino)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def duracao(arquivo: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(arquivo)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def silencios_do_audio(wav: Path, min_dur: float = 0.25) -> list[tuple[float, float]]:
    """Silêncios reais do áudio (wav 16-bit mono), por energia com limiar adaptativo:
    fica a 25% do caminho entre o ruído de fundo (percentil 10) e a fala (percentil 95),
    então funciona tanto em estúdio quanto com ruído ambiente."""
    import wave

    import numpy as np

    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    hop, win = int(sr * 0.01), int(sr * 0.03)
    if len(x) < win:
        return []
    cs = np.concatenate([[0.0], np.cumsum(x * x)])
    ini = np.arange(0, len(x) - win + 1, hop)
    db = 10 * np.log10((cs[ini + win] - cs[ini]) / win + 1e-12)
    pico = np.percentile(db, 95)
    chao = max(np.percentile(db, 10), pico - 60)
    baixo = db < chao + 0.25 * (pico - chao)

    silencios: list[tuple[float, float]] = []
    i, n = 0, len(baixo)
    while i < n:
        if baixo[i]:
            j = i
            while j < n and baixo[j]:
                j += 1
            s, e = (i * hop + win / 2) / sr, ((j - 1) * hop + win / 2) / sr
            if e - s >= min_dur:
                silencios.append((s + 0.03, e - 0.03))  # margem para não comer o fim das palavras
            i = j
        else:
            i += 1
    return silencios


def ajustar_pelo_audio(palavras: list[dict], silencios: list[tuple[float, float]]) -> int:
    """Corrige timestamps que atravessam silêncios reais (comum no Whisper, principalmente
    via API): recorta a parte da palavra que cai em silêncio e reposiciona palavras que
    ficaram "dentro" da palavra anterior para depois da pausa. Retorna quantas mudaram."""
    ajustadas = 0
    for w in palavras:
        pedacos = [(w["start"], w["end"])]
        for s, e in silencios:
            if e <= w["start"] or s >= w["end"]:
                continue
            novo = []
            for a, b in pedacos:
                if e <= a or s >= b:
                    novo.append((a, b))
                    continue
                if a < s:
                    novo.append((a, s))
                if e < b:
                    novo.append((e, b))
            pedacos = novo
        pedacos = [p for p in pedacos if p[1] - p[0] >= 0.02]
        if pedacos:
            a, b = max(pedacos, key=lambda p: p[1] - p[0])
        else:  # palavra inteira dentro de um silêncio: vai para o início da fala seguinte
            fim_sil = next((e for s, e in silencios if s <= w["start"] < e), w["start"])
            a, b = fim_sil, fim_sil + min(w["end"] - w["start"], 0.25)
        if abs(a - w["start"]) > 0.01 or abs(b - w["end"]) > 0.01:
            ajustadas += 1
        w["start"], w["end"] = a, b

    for i in range(1, len(palavras)):
        ant, w = palavras[i - 1], palavras[i]
        if w["start"] >= ant["end"] - 0.03:
            continue
        ajustadas += 1
        if w["end"] <= ant["end"] + 0.03:
            # engolida pela anterior: na verdade vem depois do próximo silêncio
            inicio_fala = next((e for s, e in silencios if s >= ant["end"] - 0.05), None)
            prox = palavras[i + 1] if i + 1 < len(palavras) else None
            if inicio_fala is not None and (prox is None or inicio_fala < prox["end"]):
                dur = min(0.25, max(0.05, w["end"] - w["start"]))
                w["start"] = inicio_fala
                w["end"] = inicio_fala + dur
                if prox is not None and prox["start"] < w["end"]:
                    meio = (inicio_fala + prox["end"]) / 2
                    w["end"] = meio
                    prox["start"] = meio
                continue
        w["start"] = ant["end"]
        w["end"] = max(w["end"], w["start"] + 0.02)
    return ajustadas


def pontos_de_corte(audio: Path, total: float, alvo: float) -> list[float]:
    """Escolhe pontos para dividir o áudio perto de cada múltiplo de `alvo`, sempre no meio
    de um silêncio, para nunca partir uma palavra ao meio."""
    proc = subprocess.run(
        ["ffmpeg", "-i", str(audio), "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"],
        capture_output=True, text=True)
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    meios = [(a + b) / 2 for a, b in zip(inicios, fins)]
    cortes: list[float] = []
    marca = alvo
    while marca < total - 30:
        candidatos = [m for m in meios if abs(m - marca) < alvo * 0.25 and (not cortes or m > cortes[-1] + alvo * 0.5)]
        cortes.append(min(candidatos, key=lambda m: abs(m - marca)) if candidatos else marca)
        marca = cortes[-1] + alvo
    return cortes


# ------------------------------------------------------------------ groq ----

def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", t)


def pontuar(palavras: list[dict], segmentos: list[dict]) -> list[dict]:
    """O Whisper às vezes devolve as palavras sem pontuação/maiúsculas; o texto do segmento
    tem. Alinha as duas sequências e copia a grafia do segmento para cada palavra."""
    tokens: list[str] = []
    for s in segmentos:
        tokens += s.get("text", "").split()
    j = 0
    for w in palavras:
        alvo = normalizar(w["text"])
        for k in range(j, min(j + 4, len(tokens))):  # tolera pequenas divergências
            if normalizar(tokens[k]) == alvo and alvo:
                w["text"] = tokens[k]
                j = k + 1
                break
    return palavras


def chamar_groq(audio: Path, chave: str, modelo: str, idioma: str) -> dict:
    import requests

    for tentativa in range(5):
        with open(audio, "rb") as f:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {chave}"},
                files={"file": (audio.name, f, "audio/mpeg")},
                data=[
                    ("model", modelo),
                    ("language", idioma),
                    ("prompt", PROMPT_LITERAL),
                    ("response_format", "verbose_json"),
                    ("temperature", "0"),
                    ("timestamp_granularities[]", "word"),
                    ("timestamp_granularities[]", "segment"),
                ],
                timeout=600,
            )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429 or resp.status_code >= 500:
            espera = float(resp.headers.get("retry-after", 10 * (tentativa + 1)))
            print(f"    Groq {resp.status_code}, tentando de novo em {espera:.0f}s", flush=True)
            time.sleep(espera)
            continue
        if resp.status_code == 401:
            sys.exit("Groq recusou a chave (401). Confira GROQ_API_KEY no arquivo .env da raiz do projeto.")
        raise RuntimeError(f"Groq respondeu {resp.status_code}: {resp.text[:500]}")
    raise RuntimeError("Groq continuou indisponível após 5 tentativas")


def transcrever_groq(video: Path, modelo: str, idioma: str) -> tuple[list[dict], dict]:
    chave = chave_groq()
    if not chave:
        sys.exit("GROQ_API_KEY não encontrada no .env da raiz do projeto nem no ambiente.")
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.mp3"
        extrair_audio(video, audio, "mp3")
        total = duracao(audio)
        tamanho = audio.stat().st_size / (1024 * 1024)

        pedacos: list[tuple[Path, float]] = [(audio, 0.0)]
        if tamanho > GROQ_LIMITE_MB:
            cortes = pontos_de_corte(audio, total, GROQ_PEDACO_S)
            limites = [0.0, *cortes, total]
            pedacos = []
            for i in range(len(limites) - 1):
                p = Path(tmp) / f"pedaco_{i:02d}.mp3"
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", f"{limites[i]:.3f}", "-to", f"{limites[i + 1]:.3f}",
                     "-i", str(audio), "-c:a", "libmp3lame", "-b:a", "48k", str(p)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pedacos.append((p, limites[i]))
            print(f"  áudio de {tamanho:.1f} MB dividido em {len(pedacos)} pedaços nos silêncios", flush=True)

        palavras: list[dict] = []
        idioma_detectado = idioma
        for n, (arq, offset) in enumerate(pedacos, start=1):
            print(f"  enviando ao Groq ({modelo}) pedaço {n}/{len(pedacos)}", flush=True)
            r = chamar_groq(arq, chave, modelo, idioma)
            idioma_detectado = r.get("language", idioma_detectado)
            segs = r.get("segments") or []
            ws = [{"text": (w.get("word") or "").strip(), "start": float(w["start"]) + offset,
                   "end": float(w["end"]) + offset} for w in (r.get("words") or [])]
            ws = [w for w in ws if w["text"]]
            palavras += pontuar(ws, segs)
            for s in segs:
                print(f"    [{s['start'] + offset:7.2f}-{s['end'] + offset:7.2f}] {s['text'].strip()}", flush=True)

    print(f"  {len(palavras)} palavras em {time.time() - t0:.0f}s")
    return palavras, {"language_code": idioma_detectado, "engine": f"groq/{modelo}"}


# --------------------------------------------------------- whisper local ----

def transcrever_whisper(video: Path, modelo: str, idioma: str) -> tuple[list[dict], dict]:
    from faster_whisper import WhisperModel

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extrair_audio(video, wav, "wav")
        print(f"  whisper local: modelo '{modelo}' (a primeira execução baixa o modelo)", flush=True)
        model = WhisperModel(modelo, device="cpu", compute_type="int8")
        segmentos, info = model.transcribe(
            str(wav),
            language=idioma,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=PROMPT_LITERAL,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 200},
            beam_size=5,
        )
        palavras: list[dict] = []
        for seg in segmentos:
            for w in seg.words or []:
                texto = w.word.strip()
                if texto:
                    palavras.append({"text": texto, "start": w.start, "end": w.end})
            print(f"    [{seg.start:7.2f}-{seg.end:7.2f}] {seg.text.strip()}", flush=True)
    print(f"  {len(palavras)} palavras em {time.time() - t0:.0f}s")
    return palavras, {"language_code": info.language, "engine": f"faster-whisper/{modelo}"}


# ------------------------------------------------------- formato Scribe ----

def para_scribe(palavras: list[dict], meta: dict) -> dict:
    """Formato que o video-use entende: entradas 'word' intercaladas com 'spacing'."""
    words: list[dict] = []
    for i, w in enumerate(palavras):
        ini, fim = round(w["start"], 3), round(max(w["end"], w["start"]), 3)
        if i > 0 and ini > words[-1]["end"]:
            words.append({"text": " ", "start": words[-1]["end"], "end": ini,
                          "type": "spacing", "speaker_id": "speaker_0"})
        words.append({"text": w["text"], "start": ini, "end": fim,
                      "type": "word", "speaker_id": "speaker_0"})
    return {**meta, "text": " ".join(w["text"] for w in palavras), "words": words}


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcrição por palavra (formato Scribe)")
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("--motor", choices=["auto", "groq", "whisper", "scribe"], default="auto")
    ap.add_argument("--modelo", default=None,
                    help="groq: whisper-large-v3 (padrão) ou whisper-large-v3-turbo; "
                         "whisper local: small, medium (padrão), large-v3")
    ap.add_argument("--idioma", default="pt", help="Código ISO-639-1 do idioma (padrão: pt)")
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"vídeo não encontrado: {video}")
    edit_dir = args.edit_dir.resolve()
    (edit_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    saida = edit_dir / "transcripts" / f"{video.stem}.json"
    if saida.exists():
        print(f"cache: {saida.name} já existe, não vou retranscrever")
        return

    motor = args.motor
    if motor == "auto":
        motor = motor_preferido()
    print(f"transcrevendo {video.name} com {motor}")

    if motor == "scribe":
        cmd = [sys.executable, "-X", "utf8", str(VIDEO_USE / "helpers" / "transcribe.py"),
               str(video), "--edit-dir", str(edit_dir), "--num-speakers", "1",
               "--language", "por" if args.idioma == "pt" else args.idioma]
        env = {**os.environ, "ELEVENLABS_API_KEY": chave_elevenlabs()}
        subprocess.run(cmd, check=True, cwd=str(VIDEO_USE), env=env)
        return
    if motor == "groq":
        palavras, meta = transcrever_groq(video, args.modelo or "whisper-large-v3", args.idioma)
    else:
        palavras, meta = transcrever_whisper(video, args.modelo or "medium", args.idioma)

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "analise.wav"
        extrair_audio(video, wav, "wav")
        silencios = silencios_do_audio(wav)
    n = ajustar_pelo_audio(palavras, silencios)
    print(f"  ajuste pelo áudio: {len(silencios)} silêncios reais, {n} palavras corrigidas")
    meta["ajuste_audio"] = {"silencios": len(silencios), "palavras_corrigidas": n}

    saida.write_text(json.dumps(para_scribe(palavras, meta), indent=2, ensure_ascii=False),
                     encoding="utf-8")
    print(f"  salvo: {saida}")


if __name__ == "__main__":
    main()
