# Etapa: corte (pausas, erros, repetições) + zooms + cor

Regras técnicas do corte: `docs/pipeline.md` → "Regras do corte". O estilo de edição está em `estado.json` → `escolhas.estilo_edicao` (natural, dinamica ou acelerada).

## 1. Base do corte

`⏳ Passo 1/3: encontrar pausas e frases repetidas.`

`{PY} editor.py cortes-base <id> --estilo <estilo>`

## 2. Decidir os cortes (você, em silêncio)

Leia `videos/.trabalho/<id>/edit/revisao.md` INTEIRO e edite `edit/edl.json`:
- Remova tentativas falhas e frases refeitas (mantenha SEMPRE a última versão), falsos começos, hesitações isoladas ("é…", "hã") e fala fora do conteúdo ("corta isso", "vou de novo", "deixa eu começar de novo").
- Os alertas ⚠ são pistas: confira cada um e procure repetições que o detector não pegou. Repetição intencional (ênfase: "muito, muito importante") fica.
- Corte parcial dentro de um trecho: use `{PY} editor.py palavras <id> --ver <ini> <fim>` e ajuste `start`/`end` entre palavras, com 30 a 200 ms de folga.
- Guarde para o resumo: cada frase removida e o motivo.

## 3. Cor (só se a análise indicou problema)

Se a análise da etapa de transcrição deu `precisa_corrigir: true` (e o aluno ainda não respondeu sobre cor neste vídeo):

```
Reparei que a imagem está {problemas em linguagem simples, ex.: "um pouco escura e azulada (a pele fica sem cor)"}.
Quer que eu corrija a cor?

1. Sim, me mostra o antes e depois
2. Não, deixa como está

Digite o número:
```
1 → `{PY} editor.py analisar-imagem <id> --comparar` → abra (Read) `cor-comparacao.jpg`, confira que o "depois" está melhor e que `estouro_novo` é `false`, e mostre o caminho: `Antes (em cima) e depois (embaixo): {caminho}. 1. Aplicar a correção / 2. Deixar sem correção`. Aplicar → `{PY} editor.py cor <id> --filtro "<sugestao>"`.

(A imagem de antes e depois também vai dentro da conversa.)

## 4. Rascunho para aprovar

`⏳ Passo 2/3: montar o rascunho do corte com os zooms.` → `{PY} editor.py cortar <id> --rascunho` (calcula os zooms do estilo e já aplica no rascunho: o aluno aprova cortes e zooms juntos).

Mostre o `rascunho.mp4` dentro da conversa (`SendUserFile`, regra "PRÉVIAS DENTRO DA CONVERSA" do CLAUDE.md) junto com o resumo abaixo.

Monte o resumo com `{PY} editor.py corte-resumo <id> --json` + suas anotações do passo 2, e (se o estilo não for natural) `{PY} editor.py dinamica <id> --listar`:

```
✂️ Corte pronto para você revisar
Antes: 4:12 → Depois: 3:21

Tirei:
- pausas e silêncios (38 s no total)
- "então hoje eu vou… hoje eu vou falar" (0:14): frase repetida, mantive a segunda
- "é…" (1:02): hesitação
- "corta essa parte" (2:40): fala fora do conteúdo

Zooms da edição dinâmica (12):
1. 0:03 zoom de ênfase em "três dicas"
2. 0:05 zoom de corte
…

Rascunho acima (qualidade baixa, só para conferir cortes e zooms).
Arquivo: {caminho absoluto do rascunho.mp4}

1. Aprovar
2. Manter algo que foi cortado
3. Cortar mais
4. Deixar as pausas mais naturais
5. Desligar algum zoom
6. Revisar no painel

Digite o número:
```

- 2 → `O que devo manter? (ex.: "a piada do começo", "a frase das 1:02")` → devolva ao EDL → refaça o passo 4.
- 3 → `O que mais cortar? (ex.: "a parte em que falo do curso", ou "pode apertar as pausas")` → ajuste (pausas: `cortes-base` com `--pausa 0.25` + repetir o passo 2) → passo 4.
- 4 → `cortes-base` com `--pausa 0.5` + repetir o passo 2 → passo 4.
- 5 → `Quais números? (ex.: 2, 5)` → `⏳ Passo 1/1: atualizar o rascunho sem esses zooms.` → `{PY} editor.py dinamica <id> --desligar 2,5 --previa` → mostre a lista nova e o rascunho atualizado e repita a pergunta.
- 6 → fluxo do `/video-painel`, depois volte a esta pergunta.

## 5. Corte final

`⏳ Passo 3/3: gerar o corte final em alta qualidade.` → `{PY} editor.py cortar <id>` (mantém os zooms aprovados).

`✅ Concluído: corte pronto ({antes} → {depois}).`

Anote no `project.md`: frases removidas, pausa usada, cor aplicada ou não, zooms desligados.
