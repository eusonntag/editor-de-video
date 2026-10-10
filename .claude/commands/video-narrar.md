---
name: editor-video:video-narrar
description: Narração por voz de IA (ElevenLabs, créditos pré-pagos) ou com o áudio do aluno. Quatro usos - criar um vídeo novo só de animações, sem gravar a câmera (texto ou assunto → voz → cards + fundo + legenda, 9:16 e/ou 16:9); narrar um vídeo existente sem fala (gravação de tela, produto); colocar narração em trechos de um vídeo (com a imagem parando ou rodando por baixo); ou trocar a voz do aluno pela voz de IA no vídeo inteiro. Escolha da voz ouvindo amostras, custo antes de gerar, prévia e desfazer. Use para "narrar", "narração", "voz de IA", "locução", "vídeo sem aparecer", "vídeo só com animação", "texto para áudio", "narrar meu vídeo", "colocar uma voz", "trocar minha voz".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Narração por voz de IA

1. **Configuração**: detecte `{PY}`. Sem `.venv` na raiz: oriente `/configurar-editor-video` e encerre.
2. **Retomar?** `{PY} editor.py videos --json`: se houver um vídeo 🟡 com `estado.origem` igual a `narracao` ou `audio`, ou com `estado.narracao_extra`, ofereça `1. Continuar "{id}" / 2. Fazer outro` e retome da primeira etapa não feita.
3. **Anúncio**: `🔍 Próximo passo: {criar o seu vídeo narrado | narrar o seu vídeo} ({N} passos). Tempo estimado: {soma de tempo-estimado.md pela duração do texto ou do vídeo}.` Faça o anúncio quando já se sabe o tamanho do texto (antes de gerar).
4. **Etapa**: `.claude/etapas/narrar.md`.
