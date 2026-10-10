---
name: editor-video:video-narrar
description: Cria um vídeo só de animações, sem precisar gravar a câmera - o aluno manda o texto (ou só o assunto e o Claude escreve o roteiro), escolhe uma voz de IA ouvindo amostras (ElevenLabs, créditos pré-pagos) ou manda o próprio áudio, e recebe o vídeo com cards de motion sincronizados com a narração, fundo no estilo da marca e legenda, em 9:16 e/ou 16:9, mais o áudio da narração separado. Use para "narrar", "narração", "voz de IA", "locução", "vídeo sem aparecer", "vídeo só com animação", "texto para áudio".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Vídeo narrado (só animações)

1. **Configuração**: detecte `{PY}`. Sem `.venv` na raiz: oriente `/configurar-editor-video` e encerre.
2. **Retomar?** `{PY} editor.py videos --json`: se houver um vídeo 🟡 com `estado.origem` igual a `narracao` ou `audio`, ofereça `1. Continuar "{id}" / 2. Fazer um novo` e retome da primeira etapa não feita.
3. **Anúncio**: `🔍 Próximo passo: criar o seu vídeo narrado ({N} passos). Tempo estimado: {soma de tempo-estimado.md: narração + fundo + motion + legenda, pela duração estimada do texto}.` Faça o anúncio depois do passo 3 da etapa (quando já se sabe o tamanho do texto).
4. **Etapa**: `.claude/etapas/narrar.md`.
