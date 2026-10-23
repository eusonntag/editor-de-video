# Como usar o Editor de Vídeo

Todos os comandos começam com `/` e são digitados no chat do Claude Code, com a pasta do projeto aberta. O Claude faz uma pergunta por vez, mostra prévias e pede sua aprovação antes de gerar.

## Primeira vez

| Comando | O que faz |
|---|---|
| `/configurar-editor-video` | Instala e configura tudo, com um teste no final. Rode de novo se algo quebrar. |
| `/configurar-transcricao` | Escolhe como transcrever: Groq (grátis, recomendado), no computador ou ElevenLabs. |
| `/video-marca` | Seu nome, @, cor, fonte, logo e os estilos padrão de animação, legenda e edição. |
| `/configurar-legenda` | Detalhes da legenda vendo no seu vídeo: fonte, tamanho, cores, contorno ou tarja, palavras por vez, posição e animação. |

## Editar

| Comando | O que faz |
|---|---|
| `/video-editar` | **Porta principal.** Do começo ao fim: corte, zooms, animações, legenda e formatos. Retoma um vídeo pela metade. |
| `/video-cortar` | Só o corte (pausas, erros, repetições), com estilo natural, dinâmico (zooms) ou acelerado. |
| `/video-legendar` | Coloca ou troca a legenda, escolhendo numa galeria feita com o seu próprio vídeo. |
| `/video-motion` | Coloca ou refaz as animações (cards), com prévia antes de gerar. Também cria um vídeo só de animações. |
| `/video-narrar` | Voz de IA (ou o seu áudio). Cria um vídeo só de animações sem gravar a câmera, narra um vídeo seu sem fala (tela, produto), coloca narração em trechos ou troca a sua voz pela voz de IA. |
| `/video-musica` | Fundo musical por baixo da voz: criado por IA no clima do vídeo (você ouve amostras) ou uma música sua. Abaixa sozinho quando alguém fala. |
| `/video-personagens` | Cria e guarda apresentadores de IA: você descreve a pessoa, a roupa e o cenário, escolhe entre 3 opções de imagem e salva com o jeito de falar e a voz. Também cria outra roupa ou cenário com o mesmo rosto. |
| `/video-avatar` | Vídeo com o seu personagem de IA falando, sem gravar nada: roteiro a partir de um tema ou de um vídeo de referência, escolha da voz, custo antes, um trecho de amostra e depois o resto. Sai como uma gravação normal e segue para a edição (cortes, zoom, cards, legenda, Reels). |
| `/video-verticalizar` | Cria a versão 9:16 para Reels, TikTok e Shorts. |
| `/video-react` | Você + outro vídeo na mesma tela (em cima/embaixo, lado a lado ou no cantinho). |
| `/video-ajustar` | Muda algo num vídeo pronto: "tira o card 3", "legenda mais pra cima", "manter a frase da piada". |
| `/video-painel` | Abre o painel visual com a linha do tempo. `/video-painel fechar` fecha. |

## Ajuda

| Comando | O que faz |
|---|---|
| `/video-ajuda` | Explica o editor, mostra o status dos seus vídeos e libera espaço no disco. |

## Fluxos recomendados

**Vídeo para Reels/TikTok**
1. Grave (de pé ou deitado)
2. `/video-editar` → Completo → Dinâmica → Vertical

**Aula ou vídeo para YouTube**
1. `/video-editar` → Cortar + legenda → Natural → Igual ao original
2. Na legenda, escolha "Clássica"
3. Suba o `.srt` que fica ao lado do vídeo como legenda separada

**Um vídeo, dois formatos**
1. `/video-editar` → Completo → "Os dois" (horizontal + vertical)

**Reagir a um vídeo**
1. Coloque o vídeo de referência em `videos/Para Editar/referencias` (ou tenha o link)
2. `/video-react`

**Vídeo sem aparecer (só animações e narração)**
1. `/video-narrar` → mande o texto ou só o assunto
2. Escolha a voz ouvindo as amostras (precisa de créditos pré-pagos na ElevenLabs)
3. Aprove a narração, o estilo e os cards

**Revisar com o mouse**
1. `/video-painel`
2. Clique nas frases para manter ou cortar, edite os textos dos cards, corrija palavras
3. "Aplicar alterações" e volte ao Claude com `/video-ajustar`

## Onde ficam os arquivos

| Pasta | O quê |
|---|---|
| `videos/Para Editar` | Seus vídeos originais (o editor nunca altera nem apaga) |
| `videos/Para Editar/referencias` | Vídeos para o formato react |
| `videos/Editados` | Vídeos prontos: `<nome>_editado.mp4`, `_editado_vertical.mp4`, `_editado_react.mp4` e `.srt` |
| `videos/.trabalho` | Arquivos intermediários de cada vídeo (pode liberar pelo `/video-ajuda`) |
| `config/marca.json` | Sua identidade visual |

## Dicas de gravação

- Luz de frente (janela ou ring light), fundo simples, câmera na altura dos olhos.
- Microfone perto da boca: legenda e corte ficam muito mais precisos.
- Errou? Pare, respire e fale a frase de novo. O editor mantém a última versão.
- Deixe um segundo de silêncio antes de começar e depois de terminar.
- Grave em 4K se puder: zooms e versão vertical ficam mais nítidos.
