"""Servidor local do painel visual (http://localhost:8765). Só biblioteca padrão.

Rotas
  GET  /                              painel/index.html (+ /app.js, /estilo.css, /fontes/*.ttf)
  GET  /api/ping                      vivo?
  POST /api/parar                     encerra o servidor
  GET  /api/videos                    lista de vídeos com status
  GET  /api/video/<id>                tudo que o painel desenha (estado, EDL, palavras, roteiro, zooms, ondas…)
  GET  /api/video/<id>/estado         só o estado (progresso ao vivo)
  POST /api/video/<id>/ajustes        grava videos/.trabalho/<id>/ajustes.json
  GET  /api/icones?q=termos           busca local de ícones
  GET  /api/icone?nome=x&estilo=y     SVG do ícone
  POST /api/abrir-pasta               abre videos/Editados no explorador de arquivos
  GET  /midia/<id>/bruto              vídeo original (com Range)
  GET  /midia/<id>/<caminho>          arquivo dentro de videos/.trabalho/<id>/ (com Range)
  GET  /final/<arquivo>               arquivo de videos/Editados (com Range)

Escuta só em 127.0.0.1. Fecha sozinho após 2 horas sem nenhuma requisição.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

PAINEL = C.RAIZ / "painel"
OCIOSO_MAX = 2 * 3600
ultimo_uso = time.time()
_cache_info: dict[str, tuple[float, dict]] = {}


def info_cache(p: Path) -> dict | None:
    try:
        m = p.stat().st_mtime
    except OSError:
        return None
    k = str(p)
    if k in _cache_info and _cache_info[k][0] == m:
        return _cache_info[k][1]
    try:
        i = C.info_video(p)
    except Exception:  # noqa: BLE001
        return None
    _cache_info[k] = (m, i)
    return i


def _tempo_nome(nome: str) -> float:
    import re

    m = re.findall(r"(\d+(?:[.,]\d+)?)", nome)
    return float(m[-1].replace(",", ".")) if m else 0.0


def url_midia(vid: str, rel: str) -> str:
    return f"/midia/{quote(vid)}/{quote(rel)}"


# ------------------------------------------------------------------ dados ----

def lista_videos() -> list[dict]:
    out = []
    ids = {b.stem: b for b in C.listar_brutos()}
    if C.TRABALHO.exists():
        for p in C.TRABALHO.iterdir():
            if p.is_dir() and not p.name.startswith("_") and p.name not in ids and (p / "estado.json").exists():
                ids[p.name] = None
    for vid, bruto in ids.items():
        emoji, desc = C.status_video(vid)
        e = C.ler_estado(vid)
        info = info_cache(bruto) if bruto else None
        grupo = "prontos" if emoji == "🟢" else ("andamento" if emoji == "🟡" else "novos")
        miniatura = None
        for f in ("horizontal", "vertical", "react"):
            if (C.TRABALHO / vid / f / "verificacao.jpg").exists():
                miniatura = url_midia(vid, f"{f}/verificacao.jpg")
                break
        out.append({"id": vid, "status": emoji, "grupo": grupo, "descricao": desc,
                    "duracao": round(info["duracao"], 1) if info else None,
                    "orientacao": C.orientacao(info) if info else None,
                    "nome_final": e.get("nome_final"), "etapa_atual": e.get("etapa_atual"),
                    "atualizado": e.get("atualizado"), "miniatura": miniatura})
    return sorted(out, key=lambda v: v.get("atualizado") or "", reverse=True)


def _palavras_origem(t: Path, vid: str) -> list[dict]:
    arq = t / "edit" / "transcripts" / f"{vid}.json"
    if not arq.exists():
        return []
    dados = json.loads(arq.read_text(encoding="utf-8"))
    return [{"t": w["text"], "s": round(w["start"], 3), "e": round(w["end"], 3)}
            for w in dados.get("words", []) if w.get("type", "word") == "word" and w.get("start") is not None]


def _cortes_editado(t: Path, edl: dict | None) -> list[float]:
    din = C.ler_json(t / "dinamica.json")
    if din and din.get("cortes") is not None:
        return din["cortes"]
    if not edl:
        return []
    try:
        from palavras_timeline import duracoes_reais

        reais = duracoes_reais(t / "edit", len(edl["ranges"]))
    except Exception:  # noqa: BLE001
        reais = None
    cortes, acc = [], 0.0
    for i, r in enumerate(edl["ranges"][:-1]):
        acc += reais[i] if reais else float(r["end"]) - float(r["start"])
        cortes.append(round(acc, 3))
    return cortes


_preparando: set[str] = set()


def preparar_midia(vid: str, t: Path, bruto: Path | None) -> bool:
    """Gera (uma vez, em segundo plano) a onda e a cópia leve do original. True = ainda preparando."""
    if not bruto:
        return False
    precisa = [(t / "onda_original.json", "onda"), (t / "painel_original.mp4", "proxy")]
    if (t / "cortado.mp4").exists():
        precisa.append((t / "onda_cortado.json", "onda_c"))
    faltam = [(p, k) for p, k in precisa if not p.exists()]
    if not faltam:
        return False
    if vid not in _preparando:
        _preparando.add(vid)

        def trabalho():
            try:
                for p, k in faltam:
                    if k == "onda":
                        C.gerar_onda(bruto, p)
                    elif k == "onda_c":
                        C.gerar_onda(t / "cortado.mp4", p)
                    else:
                        C.gerar_proxy(bruto, p)
            except (Exception, SystemExit):  # noqa: BLE001
                pass
            finally:
                _preparando.discard(vid)

        threading.Thread(target=trabalho, daemon=True).start()
    return True


def dados_video(vid: str) -> dict:
    t = C.TRABALHO / vid
    e = C.ler_estado(vid)
    try:
        bruto = C.achar_bruto(vid)
    except SystemExit:
        bruto = None
    preparando = preparar_midia(vid, t, bruto)
    edl = C.ler_json(t / "edit" / "edl.json")
    ib = info_cache(bruto) if bruto else None
    cortado = t / "cortado.mp4"
    ic = info_cache(cortado) if cortado.exists() else None
    formatos = {}
    for f in C.FORMATOS:
        pf = t / f
        if not pf.exists():
            continue
        arquivos = {n: url_midia(vid, f"{f}/{n}.mp4") for n in ("base", "animado", "final") if (pf / f"{n}.mp4").exists()}
        imagens = {n: url_midia(vid, f"{f}/{n}.jpg") for n in ("conferencia", "verificacao", "galeria-legendas")
                   if (pf / f"{n}.jpg").exists()}
        pm = t / "motion" / f
        for n in ("previa", "galeria-estilos", "galeria-icones"):
            if (pm / f"{n}.jpg").exists():
                imagens[n] = url_midia(vid, f"motion/{f}/{n}.jpg")
        montagem = C.ler_json(pm / "montagem.json")
        snaps = sorted((pm / "snapshots").glob("*.png"), key=lambda s: _tempo_nome(s.name)) if (pm / "snapshots").exists() else []
        formatos[f] = {"layout": C.ler_json(pf / "layout.json"), "arquivos": arquivos, "imagens": imagens,
                       "montagem": montagem,
                       "snapshots": [url_midia(vid, f"motion/{f}/snapshots/{s.name}") for s in snaps],
                       "feito": {et: bool(C.etapa_feita(vid, et, f)) for et in ("layout", "motion", "legenda", "final")}}
    resumo = None
    if edl and bruto and (t / "edit" / "transcripts" / f"{vid}.json").exists():
        try:
            import editor  # noqa: PLC0415

            resumo = editor.resumo_corte(vid)
        except (Exception, SystemExit):  # noqa: BLE001
            resumo = None
    finais = {}
    for f, arq in (e.get("arquivos_finais") or {}).items():
        p = Path(arq)
        if p.exists():
            finais[f] = {"caminho": str(p), "nome": p.name, "mb": round(p.stat().st_size / 1e6, 1),
                         "url": f"/final/{quote(p.name)}",
                         "srt": str(p.with_suffix(".srt")) if p.with_suffix(".srt").exists() else None}
    return {
        "id": vid, "estado": e, "status": C.status_video(vid),
        "raiz": str(C.RAIZ), "pasta_editados": str(C.EDITADOS),
        "preparando": preparando,
        "bruto": {"url": url_midia(vid, "painel_original.mp4") if (t / "painel_original.mp4").exists() else None,
                  "duracao": ib["duracao"] if ib else None,
                  "largura": ib["largura"] if ib else None, "altura": ib["altura"] if ib else None} if bruto else None,
        "cortado": {"url": url_midia(vid, "cortado.mp4"), "duracao": ic["duracao"]} if ic else None,
        "rascunho": url_midia(vid, "rascunho.mp4") if (t / "rascunho.mp4").exists() else None,
        "edl": [{"s": float(r["start"]), "e": float(r["end"])} for r in edl["ranges"]] if edl else None,
        "palavras_origem": _palavras_origem(t, vid),
        "palavras": C.ler_json(t / "palavras.json", []),
        "correcoes": C.ler_json(t / "edit" / "correcoes.json", {}),
        "cortes_editado": _cortes_editado(t, edl),
        "resumo": resumo,
        "dinamica": C.ler_json(t / "dinamica.json"),
        "desfoque": C.ler_json(t / "desfoque.json", {"regioes": []}),
        "roteiro": C.ler_json(t / "motion" / "roteiro.json"),
        "onda_original": C.ler_json(t / "onda_original.json"),
        "onda_cortado": C.ler_json(t / "onda_cortado.json"),
        "formatos": formatos, "finais": finais,
        "estilos_motion": [{"id": p.stem, **{k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                                             if k in ("nome", "descricao")}}
                           for p in sorted((C.RAIZ / "motion" / "estilos").glob("*.json"),
                                           key=lambda p: ["escuro", "claro", "pop", "editorial", "cinema"].index(p.stem)
                                           if p.stem in ("escuro", "claro", "pop", "editorial", "cinema") else 9)],
        "ajustes_pendentes": C.ler_json(t / "ajustes.json"),
    }


# ----------------------------------------------------------------- servidor ----

class Handler(BaseHTTPRequestHandler):
    server_version = "EditorPainel/1.0"

    def log_message(self, fmt, *args):  # silencioso
        pass

    def _json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, status, msg):
        self._json({"erro": msg}, status)

    def _arquivo(self, p: Path, cache: bool = False):
        if not p.exists() or not p.is_file():
            return self._erro(404, "arquivo não encontrado")
        tamanho = p.stat().st_size
        tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix == ".js":
            tipo = "text/javascript; charset=utf-8"
        elif p.suffix in (".css", ".html"):
            tipo += "; charset=utf-8"
        faixa = self.headers.get("Range")
        inicio, fim = 0, tamanho - 1
        if faixa and faixa.startswith("bytes="):
            a, _, b = faixa[6:].split(",")[0].partition("-")
            try:
                if a:
                    inicio = int(a)
                    fim = int(b) if b else tamanho - 1
                else:  # sufixo: últimos N bytes
                    inicio = max(0, tamanho - int(b))
            except ValueError:
                return self._erro(416, "faixa inválida")
            fim = min(fim, tamanho - 1)
            if inicio > fim:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{tamanho}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        else:
            self.send_response(200)
        n = fim - inicio + 1
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(n))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(inicio)
            restante = n
            try:
                while restante > 0:
                    bloco = f.read(min(1 << 20, restante))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    restante -= len(bloco)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass  # o player trocou de posição no meio do envio

    @staticmethod
    def _dentro(base: Path, p: Path) -> bool:
        try:
            p.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        global ultimo_uso
        ultimo_uso = time.time()
        url = urlparse(self.path)
        partes = [unquote(x) for x in url.path.strip("/").split("/") if x]
        try:
            if not partes:
                return self._arquivo(PAINEL / "index.html")
            if partes[0] in ("app.js", "estilo.css"):
                return self._arquivo(PAINEL / partes[0])
            if partes[0] == "fontes" and len(partes) == 2:
                return self._arquivo(C.FONTES / Path(partes[1]).name, cache=True)
            if partes[0] == "api":
                return self._api_get(partes[1:], parse_qs(url.query))
            if partes[0] == "midia" and len(partes) >= 3:
                vid = partes[1]
                if partes[2] == "bruto":
                    return self._arquivo(C.achar_bruto(vid))
                base = C.TRABALHO / vid
                p = base.joinpath(*partes[2:])
                if not self._dentro(base, p):
                    return self._erro(403, "fora da pasta do vídeo")
                return self._arquivo(p)
            if partes[0] == "final" and len(partes) == 2:
                p = C.EDITADOS / partes[1]
                if not self._dentro(C.EDITADOS, p):
                    return self._erro(403, "fora da pasta Editados")
                return self._arquivo(p)
            return self._erro(404, "rota desconhecida")
        except SystemExit as e:
            return self._erro(404, str(e))

    def _api_get(self, partes, q):
        if partes == ["ping"]:
            return self._json({"ok": True})
        if partes == ["videos"]:
            return self._json(lista_videos())
        if len(partes) == 2 and partes[0] == "video":
            return self._json(dados_video(partes[1]))
        if len(partes) == 3 and partes[0] == "video" and partes[2] == "estado":
            e = C.ler_estado(partes[1])
            return self._json({"estado": e, "status": C.status_video(partes[1])})
        if partes == ["icones"]:
            from icones import buscar

            termos = (q.get("q") or [""])[0]
            return self._json([n for n, _ in buscar(termos, 12)] if termos.strip() else [])
        if partes == ["icone"]:
            from icones import svg

            try:
                corpo = svg((q.get("nome") or [""])[0], (q.get("estilo") or ["linha"])[0]).encode("utf-8")
            except SystemExit:
                return self._erro(404, "ícone não encontrado")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return None
        return self._erro(404, "rota desconhecida")

    def do_POST(self):
        global ultimo_uso
        ultimo_uso = time.time()
        partes = [unquote(x) for x in urlparse(self.path).path.strip("/").split("/") if x]
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b""
        if partes == ["api", "parar"]:
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        if partes == ["api", "abrir-pasta"]:
            abrir_pasta(C.EDITADOS)
            return self._json({"ok": True})
        if len(partes) == 4 and partes[:2] == ["api", "video"] and partes[3] == "ajustes":
            vid = partes[2]
            try:
                dados = json.loads(corpo.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._erro(400, "JSON inválido")
            dados["video"] = vid
            dados["criado"] = time.strftime("%Y-%m-%d %H:%M:%S")
            C.gravar_json(C.TRABALHO / vid / "ajustes.json", dados)
            return self._json({"ok": True, "arquivo": str(C.TRABALHO / vid / "ajustes.json")})
        return self._erro(404, "rota desconhecida")


def abrir_pasta(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


def vigia(servidor: ThreadingHTTPServer) -> None:
    while True:
        time.sleep(60)
        if time.time() - ultimo_uso > OCIOSO_MAX:
            servidor.shutdown()
            return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8765)
    a = ap.parse_args()
    sys.path.insert(0, str(C.RAIZ))  # para importar editor.resumo_corte
    mimetypes.add_type("video/mp4", ".mp4")
    mimetypes.add_type("image/jpeg", ".jpg")
    mimetypes.add_type("font/ttf", ".ttf")
    servidor = ThreadingHTTPServer(("127.0.0.1", a.porta), Handler)
    servidor.daemon_threads = True
    threading.Thread(target=vigia, args=(servidor,), daemon=True).start()
    print(f"painel em http://localhost:{a.porta}", flush=True)
    try:
        servidor.serve_forever()
    finally:
        (C.TRABALHO / "painel.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
