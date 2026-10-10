---
name: editor-video:video-musica
description: Coloca, troca ou tira o fundo musical de um vídeo - música criada por IA no clima do vídeo (ElevenLabs Music, escolhendo entre amostras de 15 segundos) ou uma música do aluno, por baixo da voz, abaixando sozinha quando alguém fala, com prévia e ajuste de volume. Não refaz animações nem legenda. Use para "música", "fundo musical", "trilha", "colocar música", "trocar a música", "música mais baixa", "tirar a música".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Fundo musical

1. **Vídeo**: `.claude/etapas/escolher-video.md` (precisa do corte; destaque os já editados e os que estão em andamento).
2. **Pedido pontual** ("música mais baixa", "tira a música"): faça só aquilo com `{PY} editor.py musica config <id> …`, refaça a prévia (ou salve, se já entregue) e encerre.
3. **Etapa**: `.claude/etapas/musica.md`.
4. Termine sugerindo o próximo comando (`/video-ajustar`, `/video-verticalizar`, `/video-editar`).
