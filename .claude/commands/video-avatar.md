---
name: editor-video:video-avatar
description: Cria um vídeo com um personagem de IA falando para a câmera (HeyGen Avatar IV), sem gravar nada - escolhe o personagem salvo, escreve o roteiro a partir de um tema, de um texto ou da transcrição de um vídeo de referência (reescrito com outras palavras), divide em blocos, escolhe a voz, mostra o custo, gera um bloco de amostra, gera o resto, junta e manda para a edição normal (corte, zoom, cards, legenda, Reels). Use para "vídeo com personagem", "vídeo com avatar", "apresentador de IA", "influencer de IA", "vídeo com o Marcos", "gerar vídeo sem gravar".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Vídeo com personagem de IA

Uma pergunta por vez, opções numeradas. Aprovação antes de cada coisa que gasta saldo. Referência dos comandos: `docs/pipeline.md` (seção Vídeo com personagem).

## 0. Preparar

1. Detecte `{PY}`. Sem `.venv` na raiz: oriente `/configurar-editor-video` e encerre.
2. **Retomar?** Procure pastas `videos/.trabalho/*/avatar/roteiro.json` cujo vídeo ainda não está em `videos/Para Editar/`. Se houver, ofereça `1. Continuar "{id}" / 2. Fazer outro` e retome do primeiro passo não feito (roteiro aprovado → blocos → voz → geração).
3. Chave e saldo: `{PY} editor.py chave testar heygen` e `{PY} editor.py personagens saldo` (mesmas mensagens do `/video-personagens`).
4. Personagem: `{PY} editor.py personagens listar --json`. Nenhum: oriente `/video-personagens` e encerre. Um só: use e diga em uma linha. Vários: mande a galeria e pergunte qual. Mais de um visual: pergunte qual (`1. Principal / 2. Cozinha …`).

## 1. Assunto

```
Do que vai ser o vídeo?

1. Tenho a transcrição de um vídeo de referência
2. Tenho um tema (eu escrevo o roteiro)
3. Já tenho o texto pronto, palavra por palavra

Digite o número:
```
Depois peça o material (texto colado ou arquivo). No 1 e no 2, pergunte também, uma por vez: o nome do canal (`ex.: "Caixa a Dois"`) e se há um produto, app ou link para divulgar no vídeo (`ex.: "o app Caixa a Dois", ou 1 para nenhum`). Guarde as respostas para os próximos vídeos do mesmo personagem em `config/personagens/<slug>/personagem.json` → `canal` (`{"nome", "produto", "publico"}`) com `personagens editar`; da próxima vez, confirme em uma linha em vez de perguntar.

## 2. Roteiro (opções 1 e 2)

Escreva o roteiro e mostre para aprovar. Regras:
- Reescreva tudo com as suas palavras; nunca copie frases da transcrição de referência. Tire patrocínios, cupons, cotações, datas e qualquer coisa que envelheça o vídeo.
- Gancho de até 25 segundos com uma cena reconhecível do público, que planta uma promessa cumprida só no meio do vídeo.
- Logo depois, o personagem se apresenta **como personagem de IA** (obrigatório, sempre no início).
- Conteúdo em passos práticos que o público consiga aplicar.
- Chamada curta e natural para o produto (se houver) no ponto em que ele resolve o problema que acabou de ser explicado.
- Final com uma pergunta fácil para os comentários; indique um vídeo anterior do canal quando fizer sentido.
- Histórias como exemplos ilustrativos, nunca como experiências reais do personagem. Sem afirmações médicas, diagnósticos ou promessas de ganho; sem humilhar quem está em dificuldade.
- Fala no jeito do personagem (`jeito_de_falar`), português do Brasil informal ("pra", "tá"), frases curtas, sem travessão e sem emoji. Escreva números, siglas e nomes estrangeiros como se falam.
- Tamanho: pergunte antes se não estiver claro (`1. Curto, até 1 minuto (Reels) / 2. Médio, 3 a 5 minutos / 3. Longo, 8 a 10 minutos`). Conte cerca de 900 caracteres por minuto de fala.
- Junto, sugira 3 títulos e uma ideia de thumbnail com texto curto.
Ajustes: mude só o que foi pedido.

## 3. Blocos

Divida o roteiro aprovado em blocos de 30 a 60 segundos (cerca de 450 a 900 caracteres), sempre cortando no fim de uma frase e, de preferência, na troca de assunto (gancho, apresentação, cada passo, chamada, final). Para cada bloco, se o assunto pedir, escreva em inglês uma orientação curta de gestos coerente com o trecho (ex.: `"leans slightly forward, counts on fingers"`); sem orientação, vale a do personagem. Respeite a continuidade: personagem sentado, sem objetos novos, câmera parada. Mostre a lista numerada (número, duração estimada e a primeira frase de cada bloco) e peça `1. Tudo certo / 2. Quero ajustar algo`.

Escreva também as **notas de edição**: em quais falas entram textos na tela (números, divisões, nome do produto e link), onde vale um zoom leve e ideias de imagens de apoio. Elas não aparecem para o aluno agora; a etapa de animações usa depois.

## 4. Formato

`1. Horizontal 16:9 (YouTube) / 2. Vertical 9:16 (Reels, TikTok)`. Se o visual do personagem foi criado na outra proporção, avise em uma frase que a HeyGen vai recortar a imagem e sugira criar um visual na proporção certa pelo `/video-personagens` (custa US$ 1).

## 5. Voz

Se o personagem já tem `voz`, confirme em uma linha (`Voz: Rafael (ElevenLabs)`) e siga. Senão:
```
Qual voz o Marcos vai ter?

1. Voz da própria HeyGen (mais simples, sem outro custo)
2. Voz da ElevenLabs (a mesma voz em todos os vídeos, mais natural; gasta créditos da ElevenLabs também)

Digite o número:
```
- HeyGen: `{PY} editor.py avatar vozes --json` → escolha 3 a 4 vozes em português do gênero do personagem, prefira as de descrição calma/natural → `{PY} editor.py avatar amostras --vozes id1,id2,id3 --saida videos/.trabalho/<id>/avatar/vozes` → mande cada áudio com `SendUserFile` (legenda com número e nome) e pergunte qual. Avise que a amostra é a da HeyGen (pode não ser o mesmo texto).
- ElevenLabs: siga o passo 5 de `.claude/etapas/narrar.md`, com a primeira fala do roteiro como amostra.
- Depois pergunte o ritmo (`1. Normal / 2. Um pouco mais devagar / 3. Um pouco mais rápido` → velocidade 1.0, 0.92, 1.08). Salve a voz no personagem (`personagens editar` com `{"voz": {...}}`) para os próximos vídeos.

## 6. Nome e custo

1. Nome do vídeo: `Qual o nome do vídeo? (ex.: "dividir-as-contas-do-casal")`. Será o id: confira que não existe em `videos/Para Editar/` nem em `videos/.trabalho/`.
2. Escreva `videos/.trabalho/<id>/avatar/roteiro.json` (formato no topo de `scripts/avatar.py`): `personagem`, `look`, `proporcao`, `voz`, `velocidade`, `titulos`, `thumbnail`, `notas_edicao`, `blocos` (`n`, `texto`, `gestos` opcional). Guarde também o roteiro inteiro em `roteiro.md` na mesma pasta.
3. `{PY} editor.py avatar custo <id>` e mostre:
   ```
   Vídeo: 4 min 30 s em 6 blocos, com o Marcos
   Custo estimado: US$ 10,80 (cerca de US$ 2,40 por minuto). Saldo: US$ 20,00
   Primeiro gero só o bloco 1 (cerca de US$ 2) para você conferir o rosto, a voz e os gestos.

   1. Pode gerar o bloco 1
   2. Quero ajustar algo

   Digite o número:
   ```
   Saldo menor que o custo: avise e diga quanto falta (a carteira da API recarrega em app.heygen.com, área da API). Com voz da ElevenLabs, mostre também os caracteres que vão sair dos créditos de lá.

## 7. Bloco de amostra

`🔍 Próximo passo: gerar o bloco 1 do vídeo (1 passo). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py avatar gerar <id> --blocos 1`. Confira o vídeo (extraia 3 quadros com o ffmpeg e abra com Read: rosto, roupa e cenário iguais à imagem do personagem, boca acompanhando, nenhum objeto novo). Mande com `SendUserFile` (`display: "render"`, legenda "Bloco 1 com o Marcos") e pergunte:
```
1. Ficou bom, pode gerar o resto
2. Mudar a voz ou o ritmo
3. Mudar os gestos (mais calmo, mais animado)
4. Mudar o texto do bloco
```
Mudança: ajuste o `roteiro.json` (voz, `gestos` do bloco ou do personagem, texto) e refaça só o bloco 1 (`--blocos 1 --refazer`; cada refação é cobrada; diga o valor antes).

## 8. Resto dos blocos

Mostre o custo do que falta e peça o OK. `🔍 Próximo passo: gerar os outros {N} blocos ({N} passos). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py avatar gerar <id>`. Falhas: refaça só o bloco que falhou. Confira um quadro de cada bloco (Read) procurando rosto diferente, objeto novo ou corte estranho; se achar, mostre o bloco e ofereça refazer.

## 9. Juntar e editar

`⏳ Passo 1/1: juntar os blocos numa gravação só.` → `{PY} editor.py avatar juntar <id>` → o vídeo vai para `videos/Para Editar/<id>.mp4`. Mande com `SendUserFile` e diga o custo total.

`✅ Concluído: gravação do Marcos pronta ({duração}, US$ {custo}). Caminho: {caminho absoluto}`

Em seguida, pergunte se quer editar agora: `1. Editar agora (cortes, zoom, cards, legenda e versão para Reels) (recomendado) / 2. Depois`. Editar: siga `/video-editar` com esse vídeo já escolhido (sem perguntar de novo qual vídeo); no corte, use o estilo dinâmico (a fala da IA não tem erros para cortar; o corte só tira os silêncios entre blocos). Os títulos e a ideia de thumbnail ficam em `roteiro.md`: mostre de novo na entrega final.
