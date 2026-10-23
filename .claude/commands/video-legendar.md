---
name: editor-video:video-legendar
description: Coloca ou troca a legenda de um vídeo já cortado, escolhendo o estilo numa galeria feita com um quadro do próprio vídeo (dinâmica, clássica, caixa, palavra), sem refazer o corte nem as animações. Também gera o arquivo .srt separado. Use para "legendar", "colocar legenda", "trocar a legenda", "legenda maior", "mudar a cor da legenda".
allowed-tools: Read, Write, Edit, Bash, Glob, SendUserFile
model: sonnet
---

# Colocar ou trocar a legenda

1. **Vídeo**: `.claude/etapas/escolher-video.md` (precisa do corte; sem corte, ofereça `/video-cortar` antes).
2. **Formatos**: use `escolhas.formatos` do estado. Se o vídeo tem mais de um formato montado, pergunte `1. Todos ({lista}) / 2. Só o {formato}`. Se nenhum layout foi feito, rode `{PY} editor.py layout <id> horizontal` (ou vertical para bruto em pé) em silêncio.
3. **Estilo**: se o aluno quer TROCAR a legenda, sempre mostre a galeria (ignore o padrão salvo). Siga `.claude/etapas/video-editar/legendar.md`.
   - Pedidos de ajuste direto não precisam de galeria: "mais para cima/baixo" → `--margem-v <px>` (maior = mais alto; o valor atual está em `<formato>/layout.json` → `legenda`); "cor verde" → `--cor "#22c55e"`; "maior/menor" → `--tamanho <px>` (padrão: 81 px no vertical, 67 px no horizontal; "um pouco maior" ≈ +15%). O editor guarda esses ajustes e reaplica quando a legenda for refeita.
   - Pedidos de legenda difícil de ler (vídeo colorido), sombra, brilho, fundo escurecido, caixa na palavra, fonte, contorno, tarja, palavras por vez, maiúsculas, posição no meio da tela ou animação: use o fluxo do `/configurar-legenda` só para este vídeo (`legenda-config --video <id>`), com a galeria da opção.
4. **Anúncio**: `🔍 Próximo passo: colocar a legenda ({N} formato(s)). Tempo estimado: {0,5× D + 5 s por formato}.`
5. **Salvar**: `.claude/etapas/video-editar/finalizar.md` (se já tem `nome_final`, substitui avisando).
6. **Próximo passo**: `/video-ajustar` para mais mudanças, `/video-painel` para ver a linha do tempo.
