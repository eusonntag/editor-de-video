---
name: editor-video:configurar-legenda
description: Configura a legenda em detalhes, vendo cada opção no próprio vídeo - estilo, fonte, tamanho, cor da palavra em destaque, cor das letras e do contorno, contorno ou tarja, quantas palavras por vez, maiúsculas, posição na tela e animação de entrada. Vale para todos os vídeos (padrão) ou só para um. Use para "configurar a legenda", "mais opções de legenda", "mudar a fonte da legenda", "legenda com tarja", "legenda sem contorno", "legenda no meio da tela", "menos palavras na legenda".
allowed-tools: Read, Bash, Glob, SendUserFile
model: sonnet
---

# Configurar a legenda

Siga o CLAUDE.md: uma pergunta por vez, opções numeradas, nada de comando cru, prévias mostradas dentro da conversa (regra "PRÉVIAS DENTRO DA CONVERSA"). Referência técnica: `docs/pipeline.md` → "Legendas".

As opções ficam guardadas e passam a valer em toda legenda gerada depois (pelo `/video-editar`, `/video-legendar` ou `/video-ajustar`). Vídeos prontos não mudam sozinhos: no fim, ofereça aplicar.

---

## Passo 0. Checagem (em silêncio)

1. Detecte `{PY}`. Sem `.venv`: oriente `/configurar-editor-video` e encerre.
2. Ache um vídeo para as prévias: `{PY} editor.py videos --json` e, entre os que têm layout pronto (pasta `videos/.trabalho/<id>/<formato>/base.mp4`), use o mais recente. Guarde `<id>` e `<formato>` (prefira o vertical se existir; é onde a legenda mais aparece).
   - Nenhum vídeo com layout: siga sem imagens, descrevendo cada opção em uma linha, e avise uma vez: `Ainda não tem vídeo cortado para eu mostrar a prévia; vou descrever as opções. Depois do primeiro vídeo, você pode voltar aqui e ver tudo no seu próprio vídeo.`

## Passo 1. Para quais vídeos

```
Essas configurações de legenda valem para:

1. Todos os vídeos (vira o seu padrão)
2. Só um vídeo

Digite o número:
```

- 1 → nos comandos abaixo, sem `--video`.
- 2 → escolha o vídeo com `.claude/etapas/escolher-video.md` (precisa do corte pronto) e use `--video <id>` em todos os comandos abaixo. As prévias usam esse vídeo.

## Passo 2. Como está agora

`{PY} editor.py legenda-config [--video <id>] --json` → leia `efetivo`.
`{PY} editor.py galeria-legendas <id> --formato <formato> --variar atual` → mostre a imagem `galeria-legendas-atual.jpg`.

```
Sua legenda hoje:
- Estilo: Dinâmica · Fonte: Montserrat · Tamanho: médio
- Destaque: amarelo · Contorno: normal · 3 palavras por vez
- Maiúsculas · Embaixo · Animação: pop
```
(Campo ausente no `efetivo` = padrão do estilo. Diga "padrão do estilo" em vez de inventar valor.)

## Passo 3. Menu

```
O que você quer ajustar?

1. Estilo (dinâmica, clássica, caixa, palavra)
2. Fonte
3. Tamanho
4. Cores (palavra em destaque, letras, contorno)
5. Contorno ou tarja atrás do texto
6. Quantas palavras aparecem por vez
7. Maiúsculas ou normal
8. Posição na tela
9. Animação de entrada
10. Voltar tudo ao padrão
11. Pronto, terminei

Digite o número:
```

Para cada item com galeria: `⏳ Passo 1/1: preparar as opções no seu vídeo.` → `{PY} editor.py galeria-legendas <id> --formato <formato> --variar <tipo>` → abra (Read) e confira a imagem `galeria-legendas-<tipo>.jpg` (ou `galeria-legendas.jpg` para estilo) → mostre na conversa → pergunte com as mesmas opções numeradas da imagem → grave com `{PY} editor.py legenda-config [--video <id>] --definir <chave>=<valor>`.

| Item | Galeria (`--variar`) | Opções e o que gravar |
|---|---|---|
| 1. Estilo | `estilo` | 1 Dinâmica `estilo=dinamica` · 2 Clássica `classica` · 3 Caixa `caixa` · 4 Palavra `palavra`. Ao trocar de estilo, pergunte `Quer manter os ajustes que você já fez (fonte, tamanho, cores)? 1. Sim / 2. Não, usar o jeito do estilo` → 2: `--limpar fonte,escala,tamanho,contorno,fundo,max_palavras,maiusculas,destaque,animacao`. |
| 2. Fonte | `fonte` | 1 Montserrat `fonte=montserrat` · 2 Poppins `poppins` · 3 Inter `inter` · 4 Space Grotesk `space-grotesk` · 5 Playfair Display `playfair` |
| 3. Tamanho | `tamanho` | 1 Pequena `escala=0.8` · 2 Média `1` · 3 Grande `1.2` · 4 Gigante `1.45`. Grave também `--limpar tamanho` (o tamanho em px vence a escala). |
| 4. Cores | `cor` | Primeiro: `Qual cor? 1. Da palavra em destaque / 2. Das letras / 3. Do contorno`. Destaque: galeria `cor` → 1 a 5 = `cor=<hex da imagem> destaque=true`; 6 Sem destaque `destaque=false`. Letras (`cor_texto`) e contorno (`cor_contorno`): sem galeria, `1. Branco #FFFFFF / 2. Preto #000000 / 3. Amarelo #FFD400 / 4. Outra (digite o código, ex.: #7C3AED, ou o nome da cor)`; nome de cor → converta para hex e confirme. Depois mostre a prévia `atual`. |
| 5. Contorno ou tarja | `contorno` | 1 Sem contorno (sombra suave) `contorno=sem fundo=nenhum` · 2 Fino `contorno=fino fundo=nenhum` · 3 Normal `normal` · 4 Grosso `grosso` · 5 Tarja escura `fundo=translucido` · 6 Tarja branca `fundo=tarja`. Na tarja, pergunte se quer outra cor de tarja (`cor_caixa`). |
| 6. Palavras por vez | `palavras` | 1 `max_palavras=1` · 2 `2` · 3 `3` · 4 Frase `7` |
| 7. Maiúsculas | `maiusculas` | 1 `maiusculas=true` · 2 `maiusculas=false` |
| 8. Posição | `posicao` | 1 Embaixo `posicao=baixo subir=0` · 2 Um pouco mais alto `posicao=baixo subir=0.06` · 3 Bem mais alto `posicao=baixo subir=0.14` · 4 Meio da tela `posicao=centro`. No vertical, avise que embaixo já fica acima dos botões do Reels/TikTok. No react a legenda fica sempre na emenda (não muda). |
| 9. Animação | sem galeria | `1. Pop: a palavra cresce de leve ao entrar / 2. Nenhuma: aparece parada` → `animacao=pop` ou `animacao=nenhuma` |
| 10. Padrão | sem galeria | `Voltar a legenda ao jeito original do estilo? 1. Sim / 2. Não` → `--limpar tudo` |

Depois de cada mudança: gere e mostre a prévia `atual` (`--variar atual`), com `✅ Ajustado: {o que mudou}.` e volte ao menu. Uma pergunta por mensagem: a prévia e o menu vão juntos na mesma mensagem.

## Passo 4. Terminar

Mostre o resumo final (como no Passo 2) e a prévia `atual`.

Se a configuração foi para todos os vídeos e existe vídeo 🟢 pronto ou com legenda feita, ou se foi para um vídeo só:
```
Quer aplicar essa legenda agora em "{nome do vídeo}"?

1. Sim, refazer só a legenda
2. Não, só nos próximos vídeos

Digite o número:
```
1 → anuncie (`🔍 Próximo passo: refazer a legenda ({N} formato(s)). Tempo estimado: {0,5× D + 5 s por formato}.`), rode `{PY} editor.py legendar <id> --formato <f>` para cada formato em `escolhas.formatos` (as opções salvas entram sozinhas), confira com `verificar` e salve com `.claude/etapas/video-editar/finalizar.md` (substituindo o arquivo, avisando).

`✅ Concluído: legenda configurada.` + caminho absoluto de `config/marca.json` (para todos) ou do vídeo salvo.

Próximo passo: `/video-editar` para um vídeo novo, ou `/video-legendar` para trocar a legenda de outro vídeo.
