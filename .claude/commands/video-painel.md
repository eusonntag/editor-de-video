---
name: editor-video:video-painel
description: Abre o painel visual de edição no navegador (estilo CapCut) - linha do tempo com o que foi cortado, zooms, cards de motion e legenda, player sincronizado, transcrição clicável para manter ou cortar frases, edição dos textos dos cards e correção de palavras. Os ajustes voltam para o Claude pelo /video-ajustar. Use para "abrir o painel", "ver a linha do tempo", "revisar no painel", "ver o que foi cortado". "/video-painel fechar" encerra o painel.
allowed-tools: Read, Bash
model: sonnet
---

# Painel visual de edição

## Passo 0. Verificar

1. Detecte `{PY}`. Sem `.venv`: oriente `/configurar-editor-video` e encerre.
2. Se o aluno escreveu `/video-painel fechar` (ou "fechar o painel"): `{PY} editor.py painel --parar` → `✅ Concluído: painel fechado.` Encerre.
3. Se nenhum vídeo passou pelo corte ainda (`{PY} editor.py videos --json`: todos ⚪):
   ```
   O painel mostra os vídeos depois que eu começo a editar (corte, zooms, animações e legenda).
   Quer começar a editar um vídeo agora?

   1. Sim (/video-editar)
   2. Não

   Digite o número:
   ```

## Passo 1. Qual vídeo

Se este comando foi chamado por outro (portão "Revisar no painel"), use o vídeo atual e pule a pergunta. Se houver um vídeo em andamento:

```
1. Abrir o vídeo em andamento ({id})
2. Escolher outro vídeo
3. Visão geral de todos

Digite o número:
```

## Passo 2. Abrir

`🔍 Próximo passo: abrir o painel de edição. Tempo estimado: cerca de 5 segundos.`

`{PY} editor.py painel --video <id>` (ou sem `--video` para a visão geral). Ele reaproveita o painel se já estiver aberto.

`✅ Concluído: painel aberto. Endereço: http://localhost:8765/#/video/{id}`

## Passo 3. Como usar (até 5 linhas)

```
- A linha do tempo mostra o que foi cortado (riscado) e o que ficou.
- Clique numa frase riscada da transcrição para mantê-la (ou numa normal para cortar).
- Dá para editar os textos dos cards, ligar e desligar zooms e corrigir palavras da legenda.
- No fim, clique em "Aplicar alterações" e volte aqui digitando /video-ajustar.
```

Se este comando foi chamado por um portão de aprovação: `Quando terminar, volte aqui e me diga "voltei" (ou "apliquei").` e retome a etapa.

O painel fecha sozinho depois de 2 horas sem uso. Para fechar antes: `/video-painel fechar`.

## Se não abrir

- Porta ocupada: `{PY} editor.py painel --porta 8766 --video <id>`.
- O navegador não abriu sozinho: mostre o endereço para copiar.
