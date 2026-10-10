# Etapa: narração (vídeo novo só de animações ou narração num vídeo existente)

Usada pelo `/video-narrar` e pela opção "vídeo só de animações" do `/video-motion`. Referência técnica: `docs/pipeline.md` → "Narração".

Siga o CLAUDE.md (uma pergunta por vez, 🔍/⏳/✅, caminho absoluto, prévias na conversa).

## 0. O que narrar

Pule se o aluno já disse (ex.: veio do `/video-motion` opção 2 → opção 1 abaixo).

```
O que você quer fazer?

1. Criar um vídeo novo só de animações, sem gravar (voz de IA ou o seu áudio)
2. Narrar um vídeo meu que não tem fala (gravação de tela, produto, imagens)
3. Colocar narração em alguns trechos de um vídeo meu
4. Trocar a minha voz pela voz de IA no vídeo inteiro

Digite o número:
```

1 → passos 1 a 9 abaixo. 2, 3 e 4 → passo 10 (narração num vídeo existente).

## 1. De onde vem a voz

```
Como vai ser a voz do vídeo?

1. Voz de IA: você me manda o texto e eu gero a narração (recomendado)
2. Minha voz: você grava só o áudio (pode ser no celular) e me manda

Digite o número:
```

2 → vá para o passo 9.

## 2. Conexão com a ElevenLabs (só voz de IA)

Em silêncio: `{PY} editor.py chave testar elevenlabs`. Se der certo, siga para o passo 3 sem comentar.

Senão, explique uma vez:

```
A narração por IA usa a ElevenLabs, que funciona com créditos pré-pagos:
você coloca o valor que quiser e ele vai sendo descontado, sem mensalidade.
Um minuto de narração tem uns 1.000 caracteres.

Você já tem conta na ElevenLabs?

1. Sim
2. Não

Digite o número:
```

- Não: acesse https://elevenlabs.io, clique em "Sign up" e entre com Google ou e-mail. Para ter créditos: https://elevenlabs.io/app/subscription → "Add credits" (veja o preço atual em https://elevenlabs.io/pricing/api).
- Chave: em https://elevenlabs.io/app, perfil (canto de baixo, à esquerda) → "API Keys" → "Create API Key", nome `editor-video`, e libere **Text to Speech**, **Voices (leitura)**, **User (leitura)** e **Music** (para o fundo musical). Se a mesma chave também for usada para transcrever, libere também **Speech to Text**. Copie a chave (ela só aparece uma vez) e cole aqui.
- Salve com `{PY} editor.py chave gravar elevenlabs {CHAVE}` e mostre só a versão mascarada. Nunca repita a chave inteira.

## 3. Texto

```
Me mande o texto da narração. Pode ser:

1. O texto pronto (cole aqui na conversa)
2. Só o assunto: eu escrevo o roteiro para você aprovar (ex.: "3 erros de quem começa a vender no Instagram")

Digite o número (ou já cole o texto):
```

Se você for escrever o roteiro:
- Escrito para ser falado: frases curtas, uma ideia por frase, palavras do dia a dia.
- Gancho na primeira frase (até 3 segundos). Fechamento com uma chamada (seguir, comentar, link).
- Tamanho: Reels/TikTok 45 a 90 segundos (700 a 1.300 caracteres); YouTube o que o assunto pedir.
- Parágrafos separados por linha em branco: cada parágrafo vira uma "cena" (ajuda o ritmo dos cards).
- Siglas e nomes estrangeiros que a voz pode errar: escreva como se fala (ex.: "chat gê pê tê").
- Mostre o texto e pergunte `1. Aprovar o texto / 2. Quero mudar algo`.

Defina um `<id>` curto pelo assunto (ex.: `3-erros-instagram`) e grave o texto em `videos/.trabalho/_narracao/<id>.txt` (texto puro, UTF-8). Antes de gravar, confira se o `<id>` já existe em `{PY} editor.py videos --json`; se existir, acrescente `-2`.

## 4. Formato

```
Para onde é o vídeo?

1. Reels, TikTok e Shorts (em pé, 9:16)
2. YouTube (deitado, 16:9)
3. Os dois

Digite o número:
```

O primeiro formato vai no `gerar` (`vertical` para 1 e 3, `horizontal` para 2). O segundo é montado depois, no passo 6.

## 5. Voz

1. `⏳ Passo 1/2: buscar as vozes da sua conta.` → `{PY} editor.py narrar vozes --json`.
2. Escolha até 4 candidatas, nesta ordem: a voz clonada do aluno (tipo `cloned` ou `professional`), vozes marcadas com português, e vozes padrão variando homem e mulher. Se não houver nenhuma voz com português (ou o aluno pedir sotaque brasileiro), ofereça a biblioteca (passo 5.4).
3. `⏳ Passo 2/2: gravar um trecho do seu texto em cada voz.` → `{PY} editor.py narrar amostras --vozes id1,id2,id3 --texto-arquivo <txt> --saida videos/.trabalho/_narracao/<id>-amostras --nomes '<JSON [{"id","nome"}]>'`. Mande cada mp3 com `SendUserFile` (`display: "render"`, legenda com o número e o nome da voz) e pergunte:
   ```
   Ouça o começo do seu texto em cada voz:

   1. Ana: mulher, jovem, sotaque brasileiro
   2. Rafael: homem, voz grave
   3. Sarah: mulher, tom calmo
   4. Ver vozes brasileiras da biblioteca da ElevenLabs

   Digite o número:
   ```
4. Biblioteca: `{PY} editor.py narrar biblioteca --json` → escolha 3 variadas (gênero, uso "narration"/"social media") → `{PY} editor.py narrar adicionar <dono> <voz> --nome "<nome>"` para cada uma → amostras como acima. Se a ElevenLabs recusar adicionar (conta grátis não usa vozes da biblioteca pela API), explique em uma frase e volte às vozes da conta.
5. Depois da voz, o ritmo:
   ```
   E o ritmo da fala?

   1. Normal
   2. Um pouco mais rápido (bom para Reels)
   3. Mais calmo

   Digite o número:
   ```
   Velocidade: 1 → 1.0, 2 → 1.1, 3 → 0.9.

Quer a própria voz clonada e não tem? Explique que isso se faz no site (https://elevenlabs.io/app/voice-lab → "Add a new voice" → "Instant Voice Clone", com 1 a 2 minutos de áudio limpo) e que depois ela aparece aqui sozinha.

## 6. Resumo, custo e geração

`{PY} editor.py narrar custo --texto-arquivo <txt>` e mostre:

```
Resumo da narração:
- Texto: 1.050 caracteres (cerca de 1 minuto e 10 segundos de fala)
- Voz: Ana, ritmo um pouco mais rápido
- Formato: Reels (9:16)
- Custo: cerca de 1.050 créditos da ElevenLabs (saldo atual: 28.400)

1. Tudo certo, pode gerar
2. Quero ajustar algo

Digite o número:
```

(Sem o campo `saldo` no resultado, omita o "saldo atual".)

`🔍 Próximo passo: gravar a narração e montar o vídeo (2 passos). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py narrar gerar <id> --texto-arquivo <txt> --voz <voice_id> --voz-nome "<nome>" --formato <f> --velocidade <v>`.

Mande `videos/.trabalho/<id>/narracao.wav` com `SendUserFile` (legenda "Narração completa") e pergunte:

```
Ouça a narração completa.

1. Ficou boa, seguir para as animações
2. Trocar a voz ou o ritmo
3. Mudar o texto

Digite o número:
```

2 ou 3 → ajuste e rode o `gerar` de novo com `--refazer` (apaga só a narração gerada deste vídeo). Uma palavra pronunciada errado: reescreva como se fala só naquele trecho e gere de novo.

## 7. Estilo, fundo e formato

1. Estilo das animações: passo 1 de `.claude/etapas/video-editar/motion.md` (galeria com `--formato <f>`: cada estilo aparece com o próprio fundo).
2. `⏳ Passo 1/1: montar o fundo no estilo escolhido.` → `{PY} editor.py layout <id> <f> --estilo <estilo>` para cada formato (no "Os dois", também o segundo formato). Fundo personalizado (o aluno mandou uma imagem): `--fundo "<caminho>"`.

## 8. Animações, legenda e entrega

1. Motion: passos 2 a 4 de `.claude/etapas/video-editar/motion.md`, com as regras de vídeo narrado de lá (cards cobrindo o vídeo inteiro).
2. Legenda: pergunte `1. Com legenda (recomendado) / 2. Sem legenda`. Com: `.claude/etapas/video-editar/legendar.md`.
3. Entrega: `.claude/etapas/video-editar/finalizar.md`. No voz de IA, o `finalizar` também salva só o áudio em `videos/Editados/<nome>_narracao.mp3`: mostre o caminho junto (`🎙️ Só a narração: …`).

## 9. Minha voz (áudio gravado pelo aluno)

1. Dicas antes de gravar (se ainda não gravou): lugar silencioso, celular a um palmo da boca, pode errar e repetir a frase (o editor corta).
2. O áudio (mp3, m4a, wav) vai para `videos/Para Editar/` (se veio pelo chat, copie para lá; nunca altere o original).
3. Formato: passo 4. `<id>` pelo nome do arquivo ou pelo assunto.
4. `{PY} editor.py narrar audio <id> --audio "<caminho em Para Editar>" --formato <f>`.
5. Daí em diante é o corte normal, sempre no estilo natural (sem zoom, não há rosto): `.claude/etapas/video-editar/transcrever.md` e `.claude/etapas/video-editar/cortar.md` com `cortes-base <id> --estilo natural`. O rascunho é o fundo com a sua voz: peça para ouvir.
6. Depois do corte, siga do passo 7 desta etapa.

## 10. Narração num vídeo existente (opções 2, 3 e 4)

O editor guarda o corte original e grava a narração no `cortado.mp4`; layout, motion e legenda daquele vídeo precisam ser refeitos depois (o editor desmarca sozinho). Zooms, desfoques e cards andam junto quando a imagem pausa.

1. **Vídeo**: `.claude/etapas/escolher-video.md`.
   - Opção 2 (sem fala): pode ser o bruto, sem corte. Se já foi cortado, a narração vai sobre o corte.
   - Opções 3 e 4: precisam de transcrição e corte. Faltando, ofereça fazer antes (`/video-cortar`) e volte.
2. **Conexão com a ElevenLabs**: passo 2.
3. **O que a voz vai falar**:
   - Opção 2: peça o texto ou ofereça escrever. Para escrever, olhe 4 a 6 quadros do vídeo (extraia com o ffmpeg em instantes espalhados e abra com Read) e escreva um texto que acompanhe o que aparece. Tamanho: cerca de 14 caracteres por segundo de vídeo (se passar, a última imagem fica parada até a voz terminar; avise). Pergunte o volume do som original:
     ```
     E o som que já está no vídeo?

     1. Tirar (só a narração)
     2. Deixar bem baixinho por baixo da voz
     3. Manter como está

     Digite o número:
     ```
     → `--audio-original mudo|baixo|manter`. Grave o texto em `videos/.trabalho/_narracao/<id>.txt`.
   - Opção 3: mostre o vídeo em frases com tempo (leia `videos/.trabalho/<id>/palavras.json`, agrupe em frases, `0:12 "texto"`). Pergunte onde entra cada narração e o que ela diz (você pode sugerir o texto). Para cada trecho, pergunte se o vídeo para:
     ```
     Enquanto a narração fala, o vídeo:

     1. Para (a imagem congela e o vídeo continua depois): bom para introduções e explicações extras
     2. Continua rodando, com a sua voz abaixada: bom para partes sem fala ou demonstrações

     Digite o número:
     ```
     Grave `videos/.trabalho/_narracao/<id>-trechos.json`: `[{"em": 12.4, "texto": "…", "pausar": true}]` (`em` = segundos no vídeo cortado; prefira o fim de uma frase, nunca o meio de uma palavra). Com "continua rodando", use `--audio-original baixo` (ou `mudo`, se o aluno pedir).
   - Opção 4: avise antes, em uma frase: `A voz nova fala o mesmo texto, frase por frase, no ritmo da sua; a boca não acompanha exatamente, então funciona melhor com a sua voz clonada e em vídeos com cortes e zooms.` O texto é a própria transcrição (corrija nomes errados antes com `edit/correcoes.json` + `{PY} editor.py palavras <id>`).
4. **Custo**: `{PY} editor.py narrar sobre <id> --modo inteiro|trechos|trocar [--texto-arquivo f | --trechos-arquivo j] --so-custo` (não gasta nada; grava o texto final em `videos/.trabalho/<id>/narracao_texto.txt`).
5. **Voz e ritmo**: passo 5, com as amostras feitas do `narracao_texto.txt`. Na opção 4, coloque a voz clonada do aluno em primeiro, se existir.
6. **Resumo e confirmação**: como no passo 6 (texto, voz, ritmo, som original, custo, saldo).
7. **Gerar**: `🔍 Próximo passo: gravar a narração e juntar com o vídeo ({N} passos). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py narrar sobre <id> --modo <m> --voz <voice_id> --voz-nome "<nome>" --velocidade <v> [--texto-arquivo f | --trechos-arquivo j] [--inicio s] [--audio-original x]`.
   Leia os `avisos` (voz nova bem mais longa ou curta, narração falando junto com o aluno) e mostre os que importam em linguagem simples.
8. **Prévia**: mande `videos/.trabalho/<id>/cortado.mp4` com `SendUserFile` (legenda "Vídeo com a narração") e pergunte `1. Ficou bom, continuar / 2. Mudar o texto / 3. Trocar a voz ou o ritmo / 4. Desfazer a narração`. 2 e 3: ajuste e rode o `sobre` de novo (ele sempre parte do vídeo original, não acumula). 4: `{PY} editor.py narrar remover <id>`.
9. **Refazer as etapas seguintes**, só as que o vídeo já tinha ou que o aluno pedir, para cada formato em `escolhas.formatos` (ou pergunte o formato, como no `/video-editar`):
   - Formato: `{PY} editor.py layout <id> <f>` (vídeo com câmera usa o layout normal; os zooms já foram deslocados).
   - Animações: se já existia `motion/roteiro.json`, os cards foram deslocados; vá para a prévia do `motion.md` (passo 3). Senão, ofereça criar (`motion.md` inteiro).
   - Legenda (`legendar.md`) e entrega (`finalizar.md`). Com nome final já existente, substitui. O `finalizar` também salva `<nome>_narracao.mp3` (só a narração).
10. Se depois o aluno refizer o corte (`/video-cortar`), a narração sai junto (o editor avisa): refaça este passo.

Registre no `project.md`: tipo de voz, voz escolhida, velocidade, formato, estilo, custo em caracteres; nas opções 2 a 4, o modo, os trechos e o volume do som original.
