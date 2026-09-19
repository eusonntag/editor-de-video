# Etapa comum: checagem e escolha do vídeo (comandos avulsos)

1. Detecte `{PY}`. Se não existir `.venv` na raiz: oriente `/configurar-editor-video` e encerre.
2. Se o aluno já disse qual vídeo (nome ou "o último"), use-o. Se mandou um arquivo pelo chat, copie para `videos/Para Editar/`.
3. Senão, `{PY} editor.py videos --json` e pergunte, destacando primeiro os que servem para este comando (ex.: para legendar, os que já têm corte). Os 🟢 já editados ficam escondidos atrás da última opção (só aparece se houver algum):
   ```
   Em qual vídeo?

   1. 🟡 aula 3 (corte feito)
   2. Visualizar também os vídeos já editados (1)

   Digite o número:
   ```
   Escolhendo a última opção, repita a lista com todos (🟢 no fim: `🟢 teste → teste_editado.mp4`). Comandos que só fazem sentido em vídeo pronto (ex.: `/video-ajustar`) listam os 🟢 direto.
   Se houver um só vídeo compatível, confirme em vez de perguntar: `Vou usar o vídeo "aula 3". 1. Isso / 2. Outro`.
4. Leia o estado (`{PY} editor.py estado <id> --json`) para saber o que já foi feito, as escolhas (formatos, estilos) e o `nome_final`.
5. Pré-requisito faltando (ex.: legendar sem corte): explique e ofereça fazer antes:
   ```
   Este vídeo ainda não foi cortado. A legenda precisa do corte pronto.

   1. Fazer o corte agora e depois a legenda
   2. Cancelar

   Digite o número:
   ```
