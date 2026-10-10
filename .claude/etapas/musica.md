# Etapa: fundo musical

A música é a última camada: entra por baixo da voz na hora de salvar (`finalizar`), abaixando sozinha quando alguém fala. Trocar a música ou o volume não refaz animações nem legenda. Referência técnica: `docs/pipeline.md` → "Fundo musical".

Siga o CLAUDE.md (uma pergunta por vez, 🔍/⏳/✅, caminho absoluto, prévias na conversa).

Pré-requisito: o vídeo tem corte (`cortado.mp4`). Funciona em qualquer vídeo: gravado, narrado ou só de animações.

## 1. De onde vem a música

```
Qual música vai no fundo?

1. Criar uma música com IA, no clima do vídeo (recomendado)
2. Usar uma música minha (arquivo mp3, wav ou m4a)
3. Sem música

Digite o número:
```

- 2 → peça o arquivo; se veio pelo chat, copie para `videos/Para Editar/musicas/` (nunca altere o original). `{PY} editor.py musica usar <id> --arquivo "<caminho>"`. Lembre em uma frase: `Use só música que você tem direito de usar (biblioteca do YouTube, Epidemic, músicas livres); música de artista famoso derruba ou desmonetiza o vídeo.` Vá para o passo 3.
- 3 → `{PY} editor.py musica config <id> --desligar` (se havia música) e encerre a etapa.

## 2. Música com IA (ElevenLabs Music)

1. Conexão: igual ao passo 2 de `.claude/etapas/narrar.md` (a mesma chave da narração; libere também **Music** na chave). Na primeira vez, avise em uma frase: `Para usar a música em vídeos comerciais ou monetizados, a ElevenLabs pede um plano pago; confira em https://elevenlabs.io/pricing.`
2. Se `config/marca.json` tem `musica.prompt` (o estilo de música da marca), ofereça `1. Usar o seu estilo de sempre ({descrição curta}) / 2. Escolher outro` e, no 1, pule para o item 5.
3. Leia a transcrição (ou o texto da narração) e proponha 3 climas diferentes que combinem com o assunto. Para cada um, escreva um prompt em inglês (o modelo entende melhor), sempre instrumental, sem vocais, para fundo de fala. Exemplos:
   - `calm lo-fi hip hop beat, soft piano and vinyl crackle, relaxed, background music for a talking video, no vocals`
   - `uplifting corporate pop, light acoustic guitar and claps, positive and motivating, background for narration, no vocals`
   - `minimal electronic tech groove, warm synth pads, modern and focused, subtle background, no vocals`
4. `⏳ Passo 1/1: compor 3 amostras de 15 segundos.` → `{PY} editor.py musica amostras <id> --prompts "<p1>" "<p2>" "<p3>" --duracao 15`. Mande cada mp3 com `SendUserFile` (legenda com o número e o clima em português) e pergunte:
   ```
   Ouça os três climas:

   1. Lo-fi calmo
   2. Pop animado
   3. Eletrônico moderno
   4. Quero outro clima (me diga qual, ex.: "rock leve", "sertanejo instrumental")

   Digite o número:
   ```
5. `🔍 Próximo passo: compor a música no tamanho do vídeo (1 passo). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py musica gerar <id> --prompt "<prompt escolhido>"` (a música sai com a duração do vídeo + 3 s; sai suave no fim).
6. Pergunte se quer salvar esse clima como padrão (`1. Sim, usar nos próximos vídeos / 2. Só neste`). Sim: grave `musica.prompt` e `musica.descricao` em `config/marca.json`.

## 3. Volume e prévia

Volume padrão: `musica.volume` da marca ou `baixo`. Não pergunte antes da prévia.

`⏳ Passo 1/1: montar a prévia com a música.` → `{PY} editor.py musica previa <id> --formato <formato principal>` → mande `videos/.trabalho/<id>/musica/previa_<formato>.mp4` com `SendUserFile` (legenda "Prévia com o fundo musical") e pergunte:

```
Como ficou a música?

1. Perfeito
2. Mais baixa
3. Mais alta
4. Trocar a música
5. Tirar a música

Digite o número:
```

- 2/3: um degrau por vez na escala `minimo` → `baixo` → `medio` → `alto` com `{PY} editor.py musica config <id> --volume <nível>` e refaça a prévia. Já no `minimo` e o aluno quer mais baixo: sugira tirar a música.
- 4: volte ao passo 1. 5: `musica config <id> --desligar`.
- No 1, se o volume mudou do padrão, pergunte se quer usar esse volume sempre (`musica.volume` na marca).

Vídeo sem nenhuma fala (só música e animações): use `--abaixar nao` e `--volume alto`.

## 4. Salvar

- Vídeo ainda não entregue: siga para `.claude/etapas/video-editar/finalizar.md` (a música entra sozinha).
- Vídeo já entregue (`estado.nome_final` existe): `{PY} editor.py finalizar <id> --nome "<nome_final>" --substituir` e avise `Atualizei {nome}_editado.mp4 com o fundo musical.`

Registre no `project.md`: origem da música (IA com o prompt ou arquivo), volume, se abaixa na fala.
