---
name: editor-video:video-cortar
description: Corta um vídeo de pessoa falando - tira silêncios, pausas longas, hesitações, frases erradas e repetidas (mantendo a última versão), com estilo de edição natural, dinâmica (zoom a cada corte e nas frases importantes) ou acelerada (ritmo de Reels). Correção de cor opcional quando a imagem estiver escura ou azulada. Use para "cortar o vídeo", "tirar as pausas", "tirar os erros", "limpar a gravação", "só cortar".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Cortar um vídeo

Siga o CLAUDE.md (uma pergunta por vez, 🔍/⏳/✅, caminho absoluto).

1. **Vídeo**: `.claude/etapas/escolher-video.md`. Se o vídeo já tem motion ou legenda e o aluno quer recortar: avise que o corte novo exige refazer as etapas seguintes (`1. Refazer o corte e depois as outras etapas / 2. Cancelar`).
2. **Estilo de edição** (pergunte só se não estiver no estado):
   ```
   Qual ritmo de edição?

   1. Natural: só os cortes, sem zoom
   2. Dinâmica: zoom a cada corte e nas frases importantes
   3. Acelerada: pausas mínimas e zooms frequentes, ritmo de Reels

   Digite o número:
   ```
   `{PY} editor.py estado <id> --escolha estilo_edicao=<estilo>`
3. **Anúncio**: `🔍 Próximo passo: cortar pausas e erros do vídeo (3 passos). Tempo estimado: {transcrição + rascunho + corte final}.`
4. **Transcrição**: `.claude/etapas/video-editar/transcrever.md`.
5. **Corte**: `.claude/etapas/video-editar/cortar.md`.
6. **Salvar**: o corte sozinho também vira um vídeo pronto. `{PY} editor.py layout <id> horizontal` (ou `vertical` se o bruto for em pé) e siga `.claude/etapas/video-editar/finalizar.md`.
7. **Próximo passo**:
   ```
   Quer continuar?
   - /video-legendar: colocar legenda
   - /video-motion: colocar animações
   - /video-verticalizar: versão para Reels/TikTok
   ```

Se o vídeo já tinha etapas depois do corte (motion, legenda, vertical), pergunte no fim: `Quer que eu refaça {etapas} com o corte novo? 1. Sim, tudo / 2. Não agora`. Sim → refaça na ordem layout → motion (mesmo roteiro, revise os tempos) → legenda → finalizar com o mesmo nome.
