# Pipeline técnico do editor (referência para o Claude)

Este arquivo é a referência técnica. O aluno nunca vê comandos: os arquivos em `.claude/commands/`
chamam `{PY} editor.py …` em silêncio e mostram só o resultado e o caminho do arquivo.

`{PY}` = `python3` ou `py -3` (detectar uma vez por sessão: `python3 --version 2>&1 || py -3 --version 2>&1`).
O `editor.py` se re-executa sozinho dentro do `.venv` com `-X utf8`.

## Ordem das etapas

```
transcrever → cortes-base → (Claude edita o EDL) → cortar --rascunho → aprovação → cortar
→ layout (horizontal | vertical | react, com os zooms) → motion → legenda → finalizar
```

Vídeo narrado (sem câmera): `narrar gerar` (voz de IA: já sai com `cortado.mp4` e `palavras.json`) ou
`narrar audio` → transcrever → cortar (estilo natural); depois `layout` (fundo) → motion → legenda → finalizar.

Zoom e layout não mudam a duração, então `palavras.json` vale para cards e legendas de todos os formatos.

## Pastas

```
videos/Para Editar/<arquivo>          bruto (NUNCA alterar nem apagar)
videos/Para Editar/referencias/       vídeos de referência do react
videos/Editados/<nome>_editado[_vertical|_react].mp4 (+ .srt)
videos/.trabalho/<id>/                <id> = nome do bruto sem extensão
  estado.json                         etapas feitas, escolhas, nome final, etapa em andamento (painel)
  project.md                          memória do vídeo (decisões e pendências)
  edit/transcripts/<id>.json          transcrição por palavra (cache: nunca retranscrever)
  edit/edl.json, edit/revisao.md      cortes (video-use) e revisão com alertas ⚠
  edit/correcoes.json                 {"errado": "Certo"} aplicado nas palavras
  rascunho.mp4, cortado.mp4           corte em baixa qualidade com zooms (aprovação) e final
  rascunho_sem_zoom.mp4               rascunho sem zoom (base para refazer a prévia dos zooms)
  palavras.json                       palavras na linha do tempo cortada
  dinamica.json                       zooms (punch, enfase, aproximacao)
  desfoque.json                       áreas borradas: inicio/fim (s, vídeo cortado) e x,y,w,h (fração do quadro)
  rosto.json, onda_*.json             rosto detectado e picos de áudio (painel)
  <formato>/base.mp4, layout.json     layout com zooms; áreas, rosto e posição da legenda
  <formato>/animado.mp4               com motion
  <formato>/final.mp4, legendas.ass/.srt
  motion/roteiro.json                 cards (compartilhado entre formatos)
  motion/<formato>/public/            composição gerada; previa.jpg, galeria-*.jpg, montagem.json
  ajustes.json                        pedidos feitos no painel (lidos pelo /video-ajustar)
```

## Comandos do editor.py

| Etapa | Comando | Saída |
|---|---|---|
| Diagnóstico | `diagnostico [--json]` | ✓/✗ de cada item; `pronto` no JSON |
| Instalação | `instalar [--sistema [--sim]] [--local]` | `--sistema` sem `--sim` só lista o que instalaria |
| Vídeos | `videos --json` | id, duração, orientação, status ⚪🟡🟢 |
| Estado | `estado <id> [--escolha k=v …] [--json]` | escolhas: pacote, estilo_edicao, formatos, legenda_estilo, motion |
| Custo | `custo <id>` | custo e tempo da transcrição em texto simples |
| Transcrição | `transcrever <id> [--motor groq\|whisper\|scribe]` | + `onda_original.json` |
| Texto | `texto <id>` | frases com tempo (mostrar ao aluno para achar nomes errados) |
| Base do corte | `cortes-base <id> --estilo natural\|dinamica\|acelerada` | `edl.json` + `revisao.md` (acelerada: pausa 0,2 s) |
| Tempos | `palavras <id> --ver 10 25` | palavras da ORIGEM num intervalo (para cortes parciais) |
| Rascunho | `cortar <id> --rascunho` | `rascunho.mp4` (720p, já com os zooms) + `rascunho_sem_zoom.mp4` + `palavras.json` + zooms do estilo |
| Corte final | `cortar <id>` | `cortado.mp4`; mantém os zooms aprovados se o EDL não mudou |
| Resumo | `corte-resumo <id> [--json]` | antes → depois, frases removidas, pausas |
| Cor | `analisar-imagem <id> [--comparar]`, `cor <id> --filtro "…"` / `--remover` | refazer o corte depois |
| Zooms | `dinamica <id> [--estilo X] [--listar] [--desligar 2,5] [--previa]` | numeração = lista mostrada; `--previa` refaz o rascunho com os zooms atuais |
| Desfoque | `desfoque <id> [--listar] [--adicionar --inicio S --fim S --area x,y,l,a [--rotulo T]] [--remover N,N] [--limpar] [--previa]` | `desfoque.json`; invalida layout, motion, legenda e final (refazer o layout) |
| Ajustes do painel | `ajustes-tempo <id>` | aplica de `ajustes.json`: `zoom_tempo`, `zoom_novo`, `card_tempo`, `desfoque_*`; lista o que falta fazer à mão |
| Layout | `layout <id> horizontal\|vertical\|react [--sem-zoom] [--seguir sim\|nao] [--centro-x N]` | `<formato>/base.mp4` |
| React | `layout <id> react --referencia <arq> [--orientacao vertical\|horizontal] [--posicao cima\|baixo\|lado\|pip] [--proporcao 50\|40] [--inicio s] [--fim s] [--curta repetir\|congelar\|velocidade] [--audio mudo\|baixo\|auto]` | |
| Conferência | `conferir-layout <id> <formato>` | `<formato>/conferencia.jpg` (3 quadros) |
| Referência | `baixar-referencia <url> [--nome x]` | instala o yt-dlp na 1ª vez (pedir confirmação antes) |
| Ícones | `icones buscar "termos em português"` | 5 nomes Phosphor |
| Narração | `narrar vozes\|biblioteca [--json]`, `narrar adicionar <dono> <voz> --nome X`, `narrar amostras --vozes a,b --texto-arquivo f --saida pasta [--nomes JSON]`, `narrar custo --texto-arquivo f`, `narrar gerar <id> --texto-arquivo f --voz V [--voz-nome N] [--formato vertical\|horizontal] [--velocidade 0.7–1.2] [--modelo X] [--refazer]`, `narrar audio <id> --audio arq [--formato F] [--refazer]` | ver "Narração" |
| Motion | `motion <id> validar\|montar\|previa\|galeria\|render --formato F [--estilo X] [--icones Y] [--tipo estilos\|icones]` | |
| Legenda | `galeria-legendas <id> --formato F [--variar estilo\|fonte\|tamanho\|cor\|contorno\|palavras\|maiusculas\|posicao\|atual]`, `legendar <id> --formato F [--estilo X] [--cor #hex] [--margem-v N] [--tamanho px]` | galeria: `galeria-legendas[-<variar>].jpg` |
| Config. da legenda | `legenda-config [--video <id>] [--definir k=v …] [--limpar k,k\|tudo] [--json]` | sem `--video`: `config/marca.json` → `legenda` (todos os vídeos); com `--video`: `estado.json` → `legenda_opcoes` |
| Entrega | `nome <id>` (sugestão), `nome <id> --verificar "x" --formatos a,b`, `finalizar <id> --nome x [--formatos a,b] [--substituir\|--nova-versao]` | código 3 = nome já existe |
| Verificação | `verificar <id> --formato F` | duração, áudio, `verificacao.jpg` |
| Painel | `painel [--video <id>] [--parar]` | http://localhost:8765 |
| Limpeza | `liberar-espaco [--confirmar]` | só `.trabalho/` de vídeos prontos |
| Teste | `exemplo` | pipeline completo com o vídeo de exemplo, sem API |

## Transcrição

- Motor em `.env`: `TRANSCRICAO_MOTOR=groq|whisper|scribe`. Chaves: `GROQ_API_KEY`, `ELEVENLABS_API_KEY` (nunca mostrar a chave; só mascarada).
- Groq (`whisper-large-v3`): plano gratuito cobre uso normal; pago ~US$0,11/hora. `--modelo whisper-large-v3-turbo` é mais barato e um pouco menos preciso.
- Áudio vai como mp3 mono 16 kHz; acima de 24 MB divide em pedaços de ~20 min nos silêncios.
- Whisper local: `faster-whisper` (instalar com `editor.py instalar --local`), `medium` ≈ 1× a duração na CPU.
- Os tempos por palavra são corrigidos pelo áudio (linha "ajuste pelo áudio"). Se o corte de silêncio parecer tímido, conferir com `palavras <id> --ver`.
- Nunca retranscrever um vídeo já transcrito (cache em `edit/transcripts/`).

## Regras do corte (o Claude edita o `edl.json`)

- Ler `edit/revisao.md` inteiro. Remover: tentativas falhas e frases refeitas (manter SEMPRE a última versão), falsos começos, hesitações isoladas ("é…", "hã"), fala fora do conteúdo ("corta isso", "vou de novo").
- Alertas ⚠ são pistas, não verdade: procurar repetições que o detector não pegou e checar se é repetição intencional (ênfase) antes de cortar.
- Corte parcial dentro de um trecho: dividir/ajustar `start`/`end` com `palavras <id> --ver`; borda sempre entre palavras, com 30–200 ms de folga.
- "Pausas mais naturais": refazer `cortes-base` com `--pausa 0.5` (ou aumentar o `pad-out`). "Cortar mais": `--pausa 0.25` e revisar de novo.
- "Manter algo": devolver o trecho ao EDL (voltar a faixa de tempo da frase).
- Após mudar o EDL: `cortar --rascunho` para aprovar; depois `cortar`. Refazer o corte invalida layout, motion e legenda (o editor desmarca sozinho).
- Regras de produção do video-use: `tools/video-use/SKILL.md` (Hard Rules).

## Cor (só quando a análise indicar ou o aluno pedir)

- `analisar-imagem <id>` mede pele (R > G > B), cinza médio, exposição e estouro. `precisa_corrigir` = oferecer ao aluno.
- `--comparar` gera `cor-comparacao.jpg` (antes em cima, depois embaixo). Não aceitar filtro com `estouro_novo: true`.
- Referência (webcam fria/escura): `colorbalance=rs=0.04:bs=-0.07:rm=0.07:gm=0.02:bm=-0.12:rh=0.05:gh=0.02:bh=-0.10,curves=master='0/0 0.25/0.29 0.5/0.56 0.75/0.8 1/1',eq=contrast=1.04:saturation=1.08`

## Edição dinâmica (zooms)

- natural: sem zoom. dinamica: punch a cada corte (alternando 100%/112%) + ênfase (~120%) a cada ~12 s. acelerada: pausa 0,2 s no corte, punch em todo corte, ênfase a cada ~7 s, aproximação lenta nos trechos > 4 s.
- Zooms ancorados no rosto, curvas suaves. No vertical e no react a intensidade cai para 60% (nitidez).
- Ajuste fino: editar `dinamica.json` (campo `ativo`, `inicio`, `fim`, `intensidade`) e refazer o layout.

## Desfoque

- Regiões em `desfoque.json`, na linha do tempo do `cortado.mp4`; área em frações do quadro (vale em qualquer formato e resolução).
- O `layout.py` borra a área no quadro de origem ANTES do zoom e do recorte (inclui o rascunho e o react). Sem zoom e com desfoque, o horizontal usa o render quadro a quadro (cerca de 0,8× D) em vez da recodificação rápida.
- Desfoque Gaussiano dosado pelo tamanho da área (sigma = 12% do lado menor, mínimo 4 px): tampa o texto sem borrar demais. O painel mostra a mesma força; conferir sempre um quadro dentro do trecho.
- No vertical, uma área fora do recorte não aparece (nada a fazer).

## Layout

- horizontal: mesmo quadro do original (máx. 1920 px). Sem zoom, só reencoda com keyframe denso.
- vertical: 1080×1920, recorte fixo no rosto; se o rosto sair do recorte em mais de 5% do tempo, o recorte acompanha o rosto suavemente (`--seguir sim|nao` força). `--centro-x` força o centro manualmente.
- react vertical: referência em cima ou embaixo (50/50 ou 40/60), linha fina na cor da marca na emenda; legenda centralizada na emenda. react horizontal: lado a lado ou PiP (você no canto superior direito).
- Áudio da referência: mudo, baixo (15%) ou automático (abaixa quando você fala, `sidechaincompress`).
- Referência mais curta que a fala: repetir, congelar no último quadro ou ajustar a velocidade.

## Motion 2.0

- Claude escreve só `motion/roteiro.json`; o gerador monta HTML, animação, posição, fontes e ícones.
- Tipos (campos em `motion/modelos/<tipo>/manifesto.json`): `apresentacao`, `titulo`, `lista`, `numero`, `destaque`, `passos`, `palavra`, `chamada-final` e `personalizado` (HTML à mão, saída de emergência).
- Card precisa ter relação direta com a fala: números viram `numero`, listas viram `lista`/`passos`, conceitos viram `titulo`/`palavra`. Um card a cada ~6–12 s é um bom ritmo; nunca dois ao mesmo tempo no vertical.
- Sincronia: `"palavra": "editar"` no card ou em cada item → aparece quando a palavra é falada (dentro do intervalo do card). `"em": 6.2` força o segundo.
- Ícone de cada card: `editor.py icones buscar "termos"` e escolher entre os 5 nomes. Estilo de ícone: linha, preenchido, duotone, emoji (campo `emoji` no card; muda entre Windows e Mac) ou nenhum.
- Estilos: `escuro`, `claro`, `pop`, `editorial` (`motion/estilos/*.json`). A marca (`config/marca.json`) sobrepõe cor de destaque, fonte do título e logo.
- Posição automática: horizontal na lateral oposta ao rosto (fora dos 20% de baixo); vertical na faixa de cima, acima do rosto; react só na área da referência. O `montar` mede cada card no Chrome e encolhe/troca de lado se encostar no rosto ou na legenda; os avisos saem no terminal e em `montagem.json`.
- `lado: "esquerda"|"direita"` força a lateral (horizontal).
- `personalizado`: seguir o contrato do HyperFrames (timeline GSAP única e pausada, `window.__timelines`, `class="clip"` com `data-start`/`data-duration`/`data-track-index`). Documentação: `npx hyperframes docs` ou https://github.com/heygen-com/hyperframes (skill `talking-head-recut`).
- NÃO rodar `hyperframes skills` (instala skills globais). Snapshot sempre com `--describe false` (o editor já faz; existe GEMINI_API_KEY em algumas máquinas).
- Sempre abrir e conferir a `previa.jpg` (Read) antes de mostrar ao aluno e antes do render.

## Narração (vídeo só de animações)

- Voz de IA: ElevenLabs, endpoint `text-to-speech/{voz}/with-timestamps` (alinhamento por caractere → palavras; não precisa transcrever). Chave `ELEVENLABS_API_KEY` com Text to Speech + Voices (leitura) + User (leitura, para o saldo). Créditos pré-pagos (pay as you go) na conta.
- Modelo: `NARRACAO_MODELO` no `.env` (padrão `eleven_multilingual_v2`, 1 crédito por caractere; `eleven_flash_v2_5` custa metade e soa um pouco mais "robótico"). Texto dividido em parágrafos de até 2.000 caracteres, com `previous_text`/`next_text` para a entonação continuar.
- Saídas em `.trabalho/<id>/`: `narracao.wav` (0,4 s de silêncio antes, 1,2 s depois), `narracao.json` (tipo `ia`|`audio`, voz, modelo, caracteres), `<id>.mp4` (o "bruto": fundo + narração; `listar_brutos` inclui), `cortado.mp4`, `palavras.json`, `edit/transcripts/<id>.json`, `roteiro-narracao.txt`. `estado.origem` = `narracao` ou `audio`.
- Áudio do aluno (`narrar audio`): vira `<id>.mp4` com fundo e segue o corte normal (estilo natural, sem zoom).
- `layout <id> horizontal|vertical [--estilo X] [--fundo img]`: para vídeo narrado, monta o fundo do estilo (gradiente + brilhos nas cores de destaque; escuro se o texto do estilo é claro) com o áudio do `cortado.mp4`. Sem react. `layout.json` sai com `"centralizado": true` e sem rosto.
- Motion com `centralizado`: cards grandes no centro (horizontal 60% da largura; vertical quase a largura toda), um por vez, centralizados na altura livre acima da legenda. A galeria de estilos usa o fundo de cada estilo.
- `finalizar` também exporta `videos/Editados/<nome>_narracao.mp3` (só voz de IA).

### Narração num vídeo existente (`narrar sobre`)

- Modos: `inteiro` (uma narração a partir de `--inicio`, vídeo sem fala; pode usar o bruto sem corte), `trechos` (`--trechos-arquivo [{"em", "texto", "pausar"}]`, `em` na linha do tempo do `cortado.mp4`), `trocar` (mesmo texto da transcrição; voz de IA frase a frase, cada frase esticada ou encolhida com `atempo` entre 0,8× e 1,3× para caber no tempo original; som original mudo).
- `--audio-original mudo|baixo|manter`: no `inteiro` vale para o vídeo todo; no `trechos` só enquanto a narração fala (rampas de 0,2 s). Palavras originais abafadas saem do `palavras.json` (a legenda mostra a narração).
- `pausar`: a imagem congela (foto do quadro naquele ponto) pela duração da fala + 0,3 s. Narração que passa do fim do vídeo: a última imagem fica parada. Tudo depois da pausa anda junto: palavras, `dinamica.json`, `desfoque.json`, `motion/roteiro.json` (início, fim e `em` dos cards).
- Na 1ª vez guarda `cortado_sem_narracao.mp4` e `<nome>_sem_narracao.json` (palavras, dinamica, desfoque, motion/roteiro); cada `sobre` novo parte deles (não acumula). `narrar remover <id>` volta tudo. Saídas: `narracao.wav` (só a voz, na linha do tempo nova), `narracao_extra.json`, `estado.narracao_extra`. Desmarca layout, motion, legenda e final.
- `--so-custo`: só calcula caracteres e créditos e grava `narracao_texto.txt` (para as amostras).
- Refazer o corte (`cortar`) apaga a narração sobre o vídeo (o corte parte do bruto).

## Legendas

- Estilos: `dinamica` (padrão, 1–3 palavras, maiúsculas, palavra falada em cor), `classica` (aulas/YouTube), `caixa` (tarja), `palavra` (uma por vez).
- Opções finas (`/configurar-legenda`): `fonte` (montserrat, poppins, inter, space-grotesk, playfair), `cor`, `destaque`, `cor_texto`, `cor_contorno`, `contorno` (sem, fino, normal, grosso), `fundo` (nenhum, tarja, translucido), `cor_caixa`, `escala`, `tamanho`, `max_palavras`, `maiusculas`, `animacao` (pop, nenhuma), `posicao` (baixo, centro), `subir`. Ordem: estilo < marca < vídeo < opção explícita do `legendar`. Lista completa: `legenda-config --json`.
- Fontes TTF em `assets/fontes` (Montserrat, Inter, Poppins, Playfair Display, Space Grotesk): iguais no Windows e no Mac.
- Posição vem do `layout.json`: horizontal 8% da altura; vertical abaixo do queixo e acima de y ≈ 1570 (interface do Reels/TikTok); react na emenda.
- Termos errados: `edit/correcoes.json` = `{"errado": "Certo"}`; aplicado no próximo `cortar` (ou `palavras <id>`), depois refazer a legenda.

## Verificação antes de entregar

- `verificar <id> --formato F`: duração ≈ `cortado.mp4`, áudio presente, quadros início/meio/fim em `verificacao.jpg` (abrir e olhar: card legível, legenda não coberta, rosto inteiro).
- Registrar decisões em `videos/.trabalho/<id>/project.md`.

## Tempos medidos

Ver `.claude/rules/tempo-estimado.md`.
