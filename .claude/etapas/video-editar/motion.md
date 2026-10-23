# Etapa: motion (animações ligadas à fala)

Você decide o CONTEÚDO (roteiro de cards); o gerador cuida do visual. Referência: `docs/pipeline.md` → "Motion 2.0" e os manifestos em `motion/modelos/*/manifesto.json`.

Pré-requisito: layout do(s) formato(s) feito (`<formato>/layout.json`).

## 1. Estilo visual

Se `config/marca.json` tem `motion.estilo` e `motion.icones`: use e não pergunte (diga em uma linha: `Vou usar o seu estilo: {nome}, ícones {tipo}.`).

Senão:
1. `⏳ Passo 1/4: preparar a galeria de estilos.` → `{PY} editor.py motion <id> galeria --formato <formato principal> --tipo estilos` → abra e confira a imagem.
   ```
   Escolha o estilo das animações (veja os 5 no seu próprio vídeo):
   {caminho absoluto de galeria-estilos.jpg}

   1. Escuro elegante
   2. Claro minimalista
   3. Colorido pop
   4. Editorial
   5. Cinema (texto surgindo do desfoque, destaque em itálico; ótimo em vídeo narrado)

   Digite o número:
   ```
2. Estilo de ícone (sugira o padrão do estilo escolhido: escuro → duotone, claro → linha, pop → preenchido, editorial → linha, cinema → linha):
   ```
   E os ícones dos cards?

   1. Linha: traço fino, elegante
   2. Preenchido: sólido, forte
   3. Duotone: duas tonalidades com a sua cor (sugestão para este estilo)
   4. Emoji (a aparência muda um pouco entre Windows e Mac)
   5. Sem ícones
   6. Quero ver a comparação

   Digite o número:
   ```
   6 → `{PY} editor.py motion <id> galeria --formato <f> --tipo icones` e repita a pergunta.
3. Pergunte se quer salvar como padrão (`1. Sim, usar sempre / 2. Só neste vídeo`). Sim → grave em `config/marca.json` (`motion.estilo`, `motion.icones`; crie a partir de `config/marca.exemplo.json` se não existir).

## 2. Roteiro dos cards (você)

Leia `videos/.trabalho/<id>/palavras.json` (tempos já no vídeo cortado) e escreva `videos/.trabalho/<id>/motion/roteiro.json`. Vídeo de personagem de IA (`/video-avatar`): se existir `videos/.trabalho/<id>/avatar/roteiro.json`, use as `notas_edicao` dele como ponto de partida dos cards (números, divisões, nome do produto, chamada final), casando cada nota com a fala pelos tempos do `palavras.json`.

```json
{"estilo": "escuro", "icones": "duotone",
 "cards": [
  {"id": "card-01", "tipo": "apresentacao", "inicio": 0.9, "fim": 4.6, "icone": "hand-waving", "emoji": "👋",
   "campos": {"nome": "Cristiano", "palavra": "Cristiano", "subtitulo": "testando um projeto no Claude"}},
  {"id": "card-02", "tipo": "lista", "inicio": 4.75, "fim": 13.96, "icone": "list-checks", "emoji": "✅",
   "campos": {"titulo": "A função do projeto",
              "itens": [{"texto": "Editar vídeos", "palavra": "editar"},
                        {"texto": "Adicionar legendas", "palavra": "adicionar"}]}}
 ]}
```

Regras:
- Cada card tem relação direta com o que está sendo dito: números → `numero` (um) ou `grafico` (2 a 5 para comparar); duas coisas opostas → `comparacao`; abertura de capítulo → `capitulo`; enumerações → `lista` ou `passos`; ideia central → `titulo`; frase forte → `destaque`; palavra que resume → `palavra`; nome no começo → `apresentacao`; pedido no fim → `chamada-final`; pessoa, objeto ou ideia que vale ver desenhada → `pontilhismo`.
- `pontilhismo`: pontos formam um desenho por etapa (`imagem`, `texto` curto ou `forma`: circulo, anel, orbitas, onda, dispersar), cada um com `palavra`. Cada desenho precisa de ~2 s; no máximo 3 etapas num card de 6 a 8 s. Imagem: só fotos do próprio aluno (ou que ele enviou) e imagens do Wikimedia Commons (veja "Imagens" abaixo), salvas em `videos/.trabalho/<id>/motion/imagens/`; foto com rosto tem o fundo recortado sozinha. No máximo 1 ou 2 por vídeo, nos momentos fortes.
- Cards em 3D: `obra` (uma imagem flutuando, com título e crédito; ótima para falar de uma pessoa, obra, lugar ou produto), `galeria` (carrossel de 2 a 6 imagens ou textos, cada um vem para a frente quando é falado), `linha-do-tempo` (2 a 6 marcos em ordem: anos, fases de uma história) e `orbita` (uma ideia no centro e 3 a 6 palavras girando em volta). Use 1 ou 2 por capítulo, nos momentos fortes; não substituem os cards simples.
- Imagens (`obra`, `galeria`, `pontilhismo`): fotos do aluno, imagens que ele mandou, ou do Wikimedia Commons, nunca de busca aberta na internet (direito autoral). Commons:
  1. `{PY} editor.py imagens buscar <id> "<termos em inglês>"`: baixa até 8 opções com licença livre e monta `motion/imagens/_busca/galeria.jpg`.
  2. Mostre a galeria com `SendUserFile` e pergunte qual usar (`Digite o número`, com "Nenhuma, buscar outra coisa" como última opção). Cada imagem precisa da aprovação do aluno.
  3. `{PY} editor.py imagens usar <id> <número> --nome <nome-curto>`: grava `motion/imagens/<nome>.jpg` e o crédito. No roteiro, use o `caminho_no_roteiro` devolvido.
  - O crédito aparece sozinho no card e o `finalizar` grava `<nome>_creditos.txt`. Não use fotos de pessoas vivas e famosas em contexto de propaganda (direito de imagem), mesmo com licença livre.
- Ritmo: um card a cada ~6 a 12 s é bom. Não precisa cobrir o vídeo todo. Nunca dois cards ao mesmo tempo no vertical.
- Sincronia: use `"palavra"` (no card ou em cada item) com a palavra exatamente como falada; o gerador acha o tempo. `inicio` um pouco antes da primeira palavra-chave, `fim` quando o assunto muda.
- Textos curtos: títulos até ~6 palavras, itens até ~4 palavras. Corrija a grafia (acentos, nomes).
- Ícone: para cada card, rode `{PY} editor.py icones buscar "<termos do card em português>"` e escolha entre os 5. Preencha `emoji` também (usado se o estilo de ícone for emoji).
- Duração mínima de cada tipo no manifesto. Use `lado` só se precisar forçar a lateral.

Vídeo narrado (sem câmera, `layout.json` com `"centralizado": true`): os cards SÃO o vídeo.
- Cubra a narração inteira, sem tela vazia: o primeiro card começa em ~0,3 s, cada card termina quando o próximo começa e o último vai até o fim do vídeo (`fim` = duração do `cortado.mp4`).
- Um card por ideia ou frase forte, a cada ~4 a 8 s. Varie os tipos (título, lista, número, destaque, palavra) para não ficar repetitivo; nunca dois do mesmo tipo seguidos se der para evitar.
- Cards aparecem grandes e no centro, um por vez (o gerador cuida disso). `lado` não se aplica.
- Primeiro card: o gancho (título ou destaque com a frase de abertura). Último: `chamada-final`.
- Com capítulos (`videos/.trabalho/<id>/capitulos.json`): nenhum card atravessa o início de um capítulo (o card anterior termina antes dele) e cada capítulo, menos a abertura, começa com um card `capitulo` (número grande + nome do capítulo, 3 a 5 s; o número sai sozinho de `capitulos.json`). O fundo já muda sozinho a cada capítulo.
- Vídeo longo cansa se repetir: em cada capítulo use pelo menos 3 tipos diferentes. `comparacao` quando a fala opõe duas coisas (antes/depois, errado/certo, mito/verdade); `grafico` quando cita 2 a 5 números que dá para comparar; `numero` para um número sozinho; `destaque` para a frase que resume o capítulo.

Valide: `{PY} editor.py motion <id> validar` e corrija os avisos (palavra não encontrada, card curto).

## 3. Prévia para aprovar

Para cada formato: `⏳ Passo 2/4: montar os cards.` → `{PY} editor.py motion <id> montar --formato <f>` → leia os avisos → `{PY} editor.py motion <id> previa --formato <f>` → abra (Read) `motion/<f>/previa.jpg` e confira: nada sobre o rosto ou a legenda, textos legíveis, acentos certos. Se algo estiver errado, ajuste o roteiro e monte de novo ANTES de mostrar.

```
Estes são os cards do vídeo:

1. 0:01–0:04 Apresentação: "Cristiano, testando um projeto no Claude" (ícone: mão acenando)
2. 0:05–0:14 Lista: "A função do projeto": editar vídeos, adicionar legendas, imagens animadas (ícone: lista)

Prévia (um quadro de cada card):
{caminho absoluto da previa.jpg de cada formato}

1. Aprovar e gerar as animações
2. Mudar algum texto
3. Menos cards
4. Mais cards
5. Trocar o estilo
6. Pular as animações neste vídeo
7. Revisar no painel

Digite o número:
```

2/3/4 → pergunte o quê (uma pergunta), ajuste o roteiro, monte e mostre a prévia de novo. 5 → volte ao passo 1. 6 → siga sem motion.

**Vídeo longo** (`montar` listou capítulos; acontece com `capitulos.json` ou vídeo de 150 s ou mais): não mostre todos os cards de uma vez. Para cada capítulo, `{PY} editor.py motion <id> previa --formato <f> --capitulo N` → confira `motion/<f>/previa-capitulo-NN.jpg` → mostre com `SendUserFile` (legenda "Capítulo N de T: {título}") a lista dos cards daquele capítulo e pergunte:

```
Capítulo 2 de 5: Como resolver em 3 passos (6 cards)

1. Aprovar e ver o próximo capítulo
2. Mudar algum texto
3. Menos cards / mais cards neste capítulo
4. Aprovar este e todos os próximos sem revisar

Digite o número:
```

Ajustes mudam só aquele capítulo (monte de novo e mostre só ele). Os avisos do `montar` sobre onde o trecho de render começa são internos: não repasse ao aluno. No fim, siga para o render.

## 4. Renderizar

`🔍 Próximo passo: gerar as animações ({N} formato(s)). Tempo estimado: {4× D por formato, de tempo-estimado.md}.` → para cada formato: `⏳ Passo 4/4: renderizar ({formato}).` → `{PY} editor.py motion <id> render --formato <f>`.

Vídeo longo: o render sai capítulo por capítulo (`capítulo N/T: pronto` ou `sem mudança, aproveitado`). Rode em segundo plano e, a cada capítulo pronto, avise com `⏳ Capítulo {N} de {T} pronto.`. Se falhar ou a sessão cair, rodar o mesmo comando continua de onde parou.

Confira um quadro no meio de um card (`{PY} editor.py verificar <id> --formato <f>` → abra `verificacao.jpg`).

`✅ Concluído: animações prontas ({N} cards).`

Anote no `project.md`: estilo, ícones e a lista de cards.
