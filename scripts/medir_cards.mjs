// Mede a caixa real de cada card (depois das fontes e da animação de entrada) no Chrome do
// HyperFrames. Usado pelo motion.py para afastar cards do rosto e da legenda.
//
// Uso: node scripts/medir_cards.mjs <public/index.html> <largura> <altura> <tempos.json>
//   tempos.json = {"card-01": 3.2, ...}  (instante em que o card está completo)
// Saída (stdout): {"card-01": {"x":..,"y":..,"w":..,"h":..}, ...}

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import puppeteer from "puppeteer-core";

const [, , pagina, largura, altura, temposArq] = process.argv;
const raiz = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const hf = join(raiz, "node_modules", ".bin", process.platform === "win32" ? "hyperframes.cmd" : "hyperframes");
const chrome = execFileSync(hf, ["browser", "path"], { encoding: "utf8", shell: process.platform === "win32" })
  .trim().split(/\r?\n/).pop().trim();
const tempos = JSON.parse(readFileSync(temposArq, "utf8"));

const navegador = await puppeteer.launch({
  executablePath: chrome,
  headless: "shell",
  args: ["--allow-file-access-from-files", "--disable-web-security", "--autoplay-policy=no-user-gesture-required"],
});
try {
  const aba = await navegador.newPage();
  await aba.setViewport({ width: Number(largura), height: Number(altura) });
  await aba.goto(pathToFileURL(resolve(pagina)).href, { waitUntil: "load" });
  await aba.evaluate(() => document.fonts.ready);
  const caixas = await aba.evaluate((tempos) => {
    const tl = Object.values(window.__timelines || {})[0];
    const saida = {};
    for (const [id, t] of Object.entries(tempos)) {
      if (tl) tl.seek(t, false);
      const host = document.querySelector(`.card-host[data-card-id="${id}"]`);
      const alvo = host && (host.querySelector(".fit") || host.querySelector(".root"));
      if (!alvo) continue;
      host.style.visibility = "visible";
      host.style.opacity = "1";
      const r = alvo.getBoundingClientRect();
      saida[id] = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    }
    return saida;
  }, tempos);
  process.stdout.write(JSON.stringify(caixas));
} finally {
  await navegador.close();
}
