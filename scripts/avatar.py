"""Vídeo com personagem de IA falando (HeyGen Avatar IV), gerado por blocos e juntado numa gravação só.

O resultado vai para videos/Para Editar/<id>.mp4 e segue o editor normal (transcrição, corte, zoom, motion, legenda).
Trabalho em videos/.trabalho/<id>/avatar/:
  roteiro.json  {"personagem": slug, "look": nome|null, "proporcao": "16:9|9:16",
                 "voz": {"provedor": "heygen|elevenlabs", "voice_id", "nome"}, "velocidade": 1.0,
                 "titulos": [...], "thumbnail": "...", "notas_edicao": [...],
                 "blocos": [{"n": 1, "texto": "...", "gestos": "opcional, inglês"}]}
  blocos.json   {"<n>": {"video_id", "texto", "arquivo", "duracao", "custo"}}   (o que já foi gerado)
  bloco-NN.mp4  cada bloco pronto

  vozes [--idioma Portuguese] [--json]                     vozes da HeyGen (+ prévia de cada uma)
  amostras --vozes id1,id2 --saida pasta                   baixa as prévias das vozes da HeyGen
  custo <id>                                               duração e custo estimados + saldo
  gerar <id> [--blocos 1,3] [--refazer]                    gera os blocos que faltam (ou os indicados)
  juntar <id>                                              junta os blocos → videos/Para Editar/<id>.mp4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402
import heygen as H  # noqa: E402
import personagens as P  # noqa: E402

CARACTERES_POR_SEGUNDO = 15  # fala em português, ritmo de vídeo (900 por minuto, como na narração)


def pasta(vid: str) -> Path:
    p = C.TRABALHO / vid / "avatar"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ler_roteiro(vid: str) -> dict:
    r = C.ler_json(pasta(vid) / "roteiro.json")
    if not r or not r.get("blocos"):
        raise SystemExit(f"✗ falta o roteiro em {pasta(vid) / 'roteiro.json'}")
    return r


def feitos(vid: str) -> dict:
    return C.ler_json(pasta(vid) / "blocos.json", {}) or {}


def estimar_segundos(texto: str) -> float:
    return len(texto) / CARACTERES_POR_SEGUNDO


def cmd_vozes(a) -> None:
    lista = [{"voice_id": v["voice_id"], "nome": v.get("name"), "genero": v.get("gender"),
              "idioma": v.get("language"), "previa": v.get("preview_audio_url")} for v in H.vozes(a.idioma)]
    if a.json:
        print(json.dumps(lista, ensure_ascii=False, indent=1))
        return
    for i, v in enumerate(lista, 1):
        print(f"{i}. {v['nome']} ({v['genero']}, {v['idioma']}) {v['voice_id']}")


def cmd_amostras(a) -> None:
    ids = a.vozes.split(",")
    todas = {v["voice_id"]: v for v in H.vozes(a.idioma)}
    saida = Path(a.saida)
    feitas = []
    for i, vid in enumerate(ids, 1):
        v = todas.get(vid)
        if not v or not v.get("preview_audio_url"):
            print(f"✗ voz {vid} sem prévia", flush=True)
            continue
        ext = Path(v["preview_audio_url"].split("?")[0]).suffix or ".mp3"
        arq = saida / f"{i}-{P.slug(v.get('name') or vid)}{ext}"
        H.baixar(v["preview_audio_url"], arq)
        feitas.append({"n": i, "voice_id": vid, "nome": v.get("name"), "arquivo": str(arq)})
    print(json.dumps(feitas, ensure_ascii=False, indent=1))


def cmd_custo(a) -> None:
    r = ler_roteiro(a.id)
    ja = feitos(a.id)
    faltam = [b for b in r["blocos"] if str(b["n"]) not in ja]
    seg = sum(estimar_segundos(b["texto"]) for b in faltam)
    out = {"blocos": len(r["blocos"]), "faltam": len(faltam), "segundos": round(seg),
           "custo_usd": round(seg / 60 * H.CUSTO_MINUTO, 2), "preco_minuto_usd": H.CUSTO_MINUTO,
           "saldo_usd": H.saldo()}
    if r.get("voz", {}).get("provedor") == "elevenlabs":
        out["caracteres_elevenlabs"] = sum(len(b["texto"]) for b in faltam)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def corpo_bloco(vid: str, r: dict, pers: dict, bloco: dict) -> dict:
    look_nome = r.get("look") or pers.get("look_padrao")
    look = (pers.get("looks") or {}).get(look_nome) or {}
    if not look.get("heygen_look"):
        raise SystemExit(f"✗ o visual \"{look_nome}\" do personagem não está registrado na HeyGen")
    corpo = {"type": "avatar", "avatar_id": look["heygen_look"], "title": f"{vid} bloco {bloco['n']}",
             "aspect_ratio": r.get("proporcao") or look.get("proporcao") or "16:9", "resolution": "1080p",
             "expressiveness": pers.get("expressividade") or "low"}
    gestos = bloco.get("gestos") or pers.get("gestos")
    if gestos:
        corpo["motion_prompt"] = gestos
    voz = r.get("voz") or pers.get("voz") or {}
    if not voz.get("voice_id"):
        raise SystemExit("✗ falta escolher a voz (roteiro.voz ou a voz do personagem)")
    if voz.get("provedor") == "elevenlabs":
        import narrar as N

        mp3, _ = N.falar(bloco["texto"], voz["voice_id"], N.modelo_padrao(), r.get("velocidade") or 1.0)
        arq = pasta(vid) / f"bloco-{bloco['n']:02d}.mp3"
        arq.write_bytes(mp3)
        corpo["audio_asset_id"] = H.enviar_asset(arq)
    else:
        corpo.update({"script": bloco["texto"], "voice_id": voz["voice_id"],
                      "voice_settings": {"speed": r.get("velocidade") or 1.0}})
    return corpo


def cmd_gerar(a) -> None:
    r = ler_roteiro(a.id)
    pers = P.ler(r["personagem"])
    ja = feitos(a.id)
    pedidos = {int(x) for x in a.blocos.split(",")} if a.blocos else None
    alvo = [b for b in r["blocos"] if (pedidos is None or b["n"] in pedidos)
            and (a.refazer or str(b["n"]) not in ja or ja[str(b["n"])].get("texto") != b["texto"])]
    if not alvo:
        print(json.dumps({"gerados": [], "mensagem": "todos os blocos já estão prontos"}, ensure_ascii=False))
        return
    enviados = []
    for i, b in enumerate(alvo, 1):
        corpo = corpo_bloco(a.id, r, pers, b)
        # mesma combinação (texto + voz + visual + tentativa) não cobra duas vezes se o pedido se repetir
        tentativa = (ja.get(str(b["n"])) or {}).get("tentativa", 0) + (1 if a.refazer else 0)
        assinatura = hashlib.sha1(json.dumps([corpo.get("script"), corpo.get("audio_asset_id"),
                                              corpo["avatar_id"], corpo.get("voice_id"), tentativa]).encode()).hexdigest()
        enviados.append((b, H.criar_video(corpo, f"{a.id}-{b['n']}-{assinatura}"), tentativa))
        print(f"⏳ bloco {b['n']} pedido ({i}/{len(alvo)})", flush=True)
    gerados, falhas = [], []
    for b, video_id, tentativa in enviados:
        d = H.esperar_video(video_id)
        if d.get("status") != "completed" or not d.get("video_url"):
            falhas.append({"n": b["n"], "motivo": d.get("failure_message") or d.get("status")})
            continue
        arq = pasta(a.id) / f"bloco-{b['n']:02d}.mp4"
        H.baixar(d["video_url"], arq)
        dur = float(d.get("duration") or C.info_video(arq)["duracao"])
        ja[str(b["n"])] = {"video_id": video_id, "texto": b["texto"], "arquivo": arq.name, "duracao": round(dur, 2),
                           "custo": round(dur / 60 * H.CUSTO_MINUTO, 2), "tentativa": tentativa}
        C.gravar_json(pasta(a.id) / "blocos.json", ja)
        gerados.append({"n": b["n"], "arquivo": str(arq), "duracao": round(dur, 1)})
    print(json.dumps({"gerados": gerados, "falhas": falhas, "saldo_usd": H.saldo()}, ensure_ascii=False, indent=1))
    if falhas and not gerados:
        raise SystemExit(1)


def cmd_juntar(a) -> None:
    r = ler_roteiro(a.id)
    ja = feitos(a.id)
    faltam = [b["n"] for b in r["blocos"] if str(b["n"]) not in ja or ja[str(b["n"])].get("texto") != b["texto"]]
    if faltam:
        raise SystemExit(f"✗ ainda faltam os blocos {', '.join(map(str, faltam))}")
    arqs = [pasta(a.id) / ja[str(b["n"])]["arquivo"] for b in r["blocos"]]
    info = C.info_video(arqs[0])
    w, h, fps = info["largura"], info["altura"], info["fps_int"]
    entradas, filtros = [], []
    for i, arq in enumerate(arqs):
        entradas += ["-i", str(arq)]
        filtros.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-1:-1,"
                       f"fps={fps},setsar=1[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
    pares = "".join(f"[v{i}][a{i}]" for i in range(len(arqs)))
    filtro = ";".join(filtros) + f";{pares}concat=n={len(arqs)}:v=1:a=1[v][a]"
    destino = C.PARA_EDITAR / f"{a.id}.mp4"
    tmp = pasta(a.id) / "juntado.tmp.mp4"
    C.rodar(["ffmpeg", "-y", *entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)])
    C.PARA_EDITAR.mkdir(parents=True, exist_ok=True)
    tmp.replace(destino)
    dur = C.info_video(destino)["duracao"]
    print(json.dumps({"video": str(destino), "duracao": round(dur, 1),
                      "custo_total_usd": round(sum(x.get("custo", 0) for x in ja.values()), 2)}, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("vozes"); p.add_argument("--idioma", default="Portuguese"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("amostras"); p.add_argument("--vozes", required=True); p.add_argument("--saida", required=True)
    p.add_argument("--idioma", default="Portuguese")
    p = sub.add_parser("custo"); p.add_argument("id")
    p = sub.add_parser("gerar"); p.add_argument("id"); p.add_argument("--blocos"); p.add_argument("--refazer", action="store_true")
    p = sub.add_parser("juntar"); p.add_argument("id")
    a = ap.parse_args()
    {"vozes": cmd_vozes, "amostras": cmd_amostras, "custo": cmd_custo, "gerar": cmd_gerar, "juntar": cmd_juntar}[a.acao](a)


if __name__ == "__main__":
    main()
