---
name: editor-video:video-verticalizar
description: Cria a versão vertical 9:16 (Reels, TikTok, Shorts) de um vídeo horizontal já cortado - recorte centralizado no rosto (acompanha se a pessoa se mexer), zooms suaves, cards reposicionados na faixa de cima e legenda abaixo do queixo, longe da interface do app. Use para "versão vertical", "fazer para Reels", "TikTok", "Shorts", "9:16", "em pé".
allowed-tools: Read, Write, Edit, Bash, Glob
model: sonnet
---

# Versão vertical (Reels, TikTok, Shorts)

1. **Vídeo**: `.claude/etapas/escolher-video.md` (precisa do corte). Se o bruto já é vertical, avise que ele já está em 9:16 e ofereça `/video-editar`.
2. **Anúncio**: `🔍 Próximo passo: criar a versão vertical ({N} passos). Tempo estimado: {layout 1× D + motion 4× D se houver + legenda}.`
3. **Recorte**: `.claude/etapas/video-editar/verticalizar.md`.
4. **Motion**: se o horizontal tem motion (`motion/roteiro.json` e etapa motion feita), reaproveite o mesmo roteiro: `{PY} editor.py motion <id> montar --formato vertical` + `previa` → mostre a prévia vertical para aprovar (os cards ficam compactos na faixa de cima) → `render`. Se não tem, pergunte `Quer animações na versão vertical? 1. Sim / 2. Não` (sim → `.claude/etapas/video-editar/motion.md`).
5. **Legenda**: se o horizontal tem legenda, use o mesmo estilo em silêncio (`{PY} editor.py legendar <id> --formato vertical`); confira o quadro de verificação. Senão pergunte se quer (sim → `legendar.md`).
6. **Salvar**: `{PY} editor.py estado <id> --escolha` com `formatos` incluindo `vertical` e siga `.claude/etapas/video-editar/finalizar.md` só para o vertical (`--formatos vertical`). Com `nome_final`, sai como `<nome>_editado_vertical.mp4`.
