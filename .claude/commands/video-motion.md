---
name: editor-video:video-motion
description: Adiciona ou refaz as animações (motion graphics) de um vídeo já cortado - cards com títulos, listas com checks, números animados, passo a passo, frases em destaque, palavra-chave e chamada final, sincronizados com a fala, com ícones e no estilo da marca. Mostra a prévia antes de renderizar. Use para "colocar animação", "motion", "cards", "refazer as animações", "trocar o estilo dos cards", "mais cards".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
model: opus
---

# Adicionar ou refazer as animações

1. **Vídeo**: `.claude/etapas/escolher-video.md` (precisa do corte).
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
