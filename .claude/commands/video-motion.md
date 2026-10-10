---
name: editor-video:video-motion
description: Adiciona ou refaz as animações (motion graphics) de um vídeo já cortado - cards com títulos, listas com checks, números animados, passo a passo, frases em destaque, palavra-chave e chamada final, sincronizados com a fala, com ícones e no estilo da marca. Mostra a prévia antes de renderizar. Também cria um vídeo só de animações, sem câmera, com narração por voz de IA ou o áudio do aluno. Use para "colocar animação", "motion", "cards", "refazer as animações", "trocar o estilo dos cards", "mais cards", "vídeo só com animação".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Adicionar ou refazer as animações

1. **Vídeo**: pergunte primeiro (pule se o aluno já disse qual vídeo ou já pediu um vídeo sem câmera):
   ```
   O que você quer animar?

   1. Um vídeo que eu gravei (colocar os cards por cima)
   2. Criar um vídeo só de animações, sem gravar: com narração por voz de IA ou com o meu áudio

   Digite o número:
   ```
   2 → siga `.claude/etapas/narrar.md` e encerre aqui (ela já inclui motion, legenda e entrega).
   1 → `.claude/etapas/escolher-video.md` (precisa do corte). Vídeo narrado (`estado.origem` = `narracao` ou `audio`): as regras de vídeo narrado do `motion.md` valem.
2. **Formatos**: `escolhas.formatos` do estado; se nenhum layout existe, monte o horizontal (ou vertical para bruto em pé) em silêncio. Mais de um formato: `1. Todos / 2. Só o {formato}`.
3. **Já existe roteiro?** (`videos/.trabalho/<id>/motion/roteiro.json`)
   ```
   Este vídeo já tem {N} cards. O que você quer?

   1. Ajustar os cards atuais (textos, quantidade, estilo)
   2. Fazer do zero

   Digite o número:
   ```
   1 → mostre a lista atual dos cards e pergunte o que mudar; ajuste o roteiro e vá para a prévia (passo 3 de `motion.md`).
4. **Anúncio**: `🔍 Próximo passo: criar as animações ({N} passos). Tempo estimado: {montar + prévia + 4× D por formato}.`
5. **Etapa**: `.claude/etapas/video-editar/motion.md`.
6. **Legenda por cima**: se o vídeo tinha legenda nesse formato, ela precisa ser refeita por cima das animações novas: `{PY} editor.py legendar <id> --formato <f>` (mesmo estilo, sem perguntar).
7. **Salvar**: `.claude/etapas/video-editar/finalizar.md`.
