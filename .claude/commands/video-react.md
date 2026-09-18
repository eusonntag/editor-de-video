---
name: editor-video:video-react
description: Formato react - você e um vídeo de referência na mesma tela (referência em cima ou embaixo no vertical; lado a lado ou você no cantinho no horizontal), com escolha do trecho da referência e do áudio dela (mudo, baixo ou abaixando sozinho quando você fala), legenda na emenda. Use para "react", "reagir a um vídeo", "vídeo em cima e eu embaixo", "tela dividida", "dueto".
allowed-tools: Read, Write, Edit, Bash, Glob
model: opus
---

# Formato react

1. **Vídeo** (a sua fala): `.claude/etapas/escolher-video.md`. Precisa do corte; se não tiver, faça antes (`/video-cortar` embutido: transcrever + cortar).
2. **Anúncio**: `🔍 Próximo passo: montar o react ({N} passos). Tempo estimado: {react 2× D + legenda + motion se houver}.`
3. **Montagem**: `.claude/etapas/video-editar/react.md`.
4. **Motion** (opcional): `Quer animações na parte da referência? 1. Sim / 2. Não` → sim: `.claude/etapas/video-editar/motion.md` com `--formato react`.
5. **Legenda**: `.claude/etapas/video-editar/legendar.md` com `--formato react` (fica na emenda automaticamente).
6. **Salvar**: `.claude/etapas/video-editar/finalizar.md` com `--formatos react` → `<nome>_editado_react.mp4`.
