---
name: editor-video:video-personagens
description: Cria, salva e organiza personagens de IA para usar nos vídeos (apresentador virtual) - descreve a pessoa, a roupa e o cenário, gera opções de imagem pela HeyGen, aprova uma e guarda junto com o jeito de falar, os gestos e a voz. Também cria novos visuais do mesmo personagem (outra roupa ou cenário, mesmo rosto), usa uma foto própria, lista, edita e apaga. Use para "personagem", "criar personagem", "apresentador de IA", "avatar", "salvar personagem", "meus personagens", "trocar a roupa do personagem".
allowed-tools: Read, Write, Edit, Bash, Glob, SendUserFile
model: opus
---

# Personagens de IA

Uma pergunta por vez. Os personagens ficam em `config/personagens/<slug>/` (imagem aprovada + `personagem.json`) e servem para todos os vídeos. Referência dos comandos: `docs/pipeline.md` (seção Personagens).

## Passo 0: preparar

1. Detecte `{PY}`. Sem `.venv` na raiz: oriente `/configurar-editor-video` e encerre.
2. `{PY} editor.py personagens listar --json`. Se houver salvos, mande a `galeria` com `SendUserFile` (legenda "Seus personagens") e pergunte:
   ```
   Seus personagens: Marcos, Carol

   1. Criar um personagem novo
   2. Novo visual de um personagem (outra roupa ou cenário, mesmo rosto)
   3. Ver ou editar um personagem (descrição, jeito de falar, gestos, voz)
   4. Apagar um personagem

   Digite o número:
   ```
   Sem nenhum salvo, vá direto ao "Criar".

## Chave e saldo (antes de gerar imagem)

`{PY} editor.py chave testar heygen`. Sem chave: explique que é preciso uma conta na HeyGen e a chave da API (app.heygen.com → Settings → API), e peça para colar em `HEYGEN_API_KEY=` no arquivo `.env` da raiz (caminho absoluto); nunca peça a chave no chat. Depois `{PY} editor.py personagens saldo`: com `saldo_usd` 0, diga em uma frase que a API usa uma carteira própria, separada dos créditos do site (que não valem aqui), e que é preciso colocar saldo na área da API (a partir de US$ 5). Pare até a pessoa avisar.

## Criar

1. **Nome**: `Como o personagem se chama? (ex.: "Marcos")`
2. **Foto ou descrição**:
   ```
   Como vamos fazer a imagem do personagem?

   1. Eu descrevo e a IA cria a pessoa (recomendado)
   2. Já tenho uma imagem pronta

   Digite o número:
   ```
   Imagem pronta: peça o arquivo (ou o caminho; pode mandar várias, uma por cenário), abra com Read, confira que é a mesma pessoa, de frente ou quase de frente, rosto bem visível, e pule para o passo 6. Se a foto for de uma pessoa real, confirme que é da própria pessoa ou que ela autorizou. Cada foto vira um visual (dê nome pelo cenário: `escritorio`, `sala`, `cozinha`). Para virar vídeo, a foto precisa ser registrada na HeyGen, e isso é cobrado (medido: cerca de US$ 1,30 por foto): mostre o custo e o saldo e pergunte quais registrar agora. As outras ficam salvas com `--sem-heygen` e são registradas depois com `{PY} editor.py personagens registrar <slug> --look <nome>`.
3. **Aparência**: `Descreva a pessoa: idade, jeito, cabelo, barba... (ex.: "homem brasileiro de uns 32 anos, cabelo curto escuro, barba rala")`
4. **Roupa fixa**: `Qual a roupa fixa dele? (ex.: "camiseta lisa azul-marinho, calça jeans e relógio no pulso esquerdo")`
5. **Cenário e enquadramento**: `Onde ele aparece? (ex.: "escritório em casa, parede marrom, janela à esquerda, estante com livros à direita, sentado numa cadeira preta")`. Depois o formato: `1. Horizontal 16:9 (YouTube) / 2. Vertical 9:16 (Reels)`.
6. **Jeito de falar e gestos**: `Como ele fala e se mexe? (ex.: "calmo e simpático, gesticula pouco com as mãos abertas, sorri de leve")`. Guarde em português em `jeito_de_falar` (usado para escrever os roteiros no jeito dele: vocabulário, ritmo, gírias, expressões regionais) e escreva você mesmo a versão curta em inglês para `gestos` (vai para a HeyGen como orientação de movimento, ex.: `"calm, minimal hand gestures with open palms, slight smile"`). Escolha `expressividade` a partir do relato: `low` (calmo), `medium`, `high` (animado). Cada visual pode ter `gestos` próprios, coerentes com a pose da imagem (no sofá, braço no encosto; na mesa, mãos perto do notebook): grave em `looks.<nome>.gestos`. O sotaque vem da voz escolhida (passo 8); o texto só ajuda com palavras e expressões.
7. **Gerar as opções** (só no caminho da descrição):
   - Escreva o prompt em inglês, até 900 caracteres, nesta ordem: "Photorealistic photo", proporção, a pessoa com `{variacao}` no lugar do traço que vai variar (cabelo/barba/rosto), expressão, roupa, posição (sentado de frente para a câmera, mãos livres apoiadas), cenário, "Fixed camera, medium shot, eye level, 35mm lens. Natural matte skin, visible pores, no retouching. No text, no logos." Siga a descrição à risca e invente só o que falta.
   - 3 variações que respeitem a descrição (ex.: barba rala / sem barba / barba cheia).
   - Mostre o custo antes (`personagens saldo` → `custo_por_imagem_usd`, hoje US$ 1 por imagem, ou seja, US$ 3 pelas 3 opções) com o saldo atual, e peça `1. Pode gerar / 2. Quero ajustar a descrição`. Saldo menor que o custo: ofereça gerar menos opções.
   - `🔍 Próximo passo: criar 3 opções do personagem (1 passo). Tempo estimado: {tempo-estimado.md}.` → `{PY} editor.py personagens opcoes <slug> --prompt "<prompt>" --variacoes "<a>" "<b>" "<c>" --proporcao <16:9|9:16>`.
   - Abra a `galeria` com Read, confira se as três seguem a descrição (roupa, cenário, sem texto estranho) e mande com `SendUserFile` (`display: "render"`, legenda "Opções do personagem"). Pergunte:
     ```
     Qual delas vira o Marcos?

     1. Opção 1
     2. Opção 2
     3. Opção 3
     4. Nenhuma, quero ajustar a descrição

     Digite o número:
     ```
     Ajuste: mude só o que foi pedido no prompt e gere de novo (cada rodada é cobrada).
8. **Voz** (opcional): `1. Escolher a voz agora (ouvindo amostras) / 2. Escolher depois, no primeiro vídeo`. Agora: siga o passo 5 de `.claude/etapas/narrar.md` (vozes da ElevenLabs, amostras com uma fala curta do jeito do personagem) e guarde `{"provedor": "elevenlabs", "voice_id", "nome"}`.
9. **Resumo e salvar**:
   ```
   Personagem: Marcos
   - Aparência: homem de uns 32 anos, cabelo curto escuro, barba rala
   - Roupa: camiseta azul-marinho, jeans, relógio no pulso esquerdo
   - Cenário: escritório em casa (16:9)
   - Jeito: calmo e simpático, gesticula pouco
   - Voz: Rafael (ElevenLabs)

   1. Tudo certo, pode salvar
   2. Quero ajustar algo
   ```
   Escreva `videos/.trabalho/personagens/<slug>/dados.json` com `nome`, `descricao` (uma linha), `aparencia`, `roupa`, `cenario`, `jeito_de_falar`, `gestos`, `expressividade`, `voz` → `{PY} editor.py personagens salvar <slug> --opcao <N> --dados <dados.json>` (imagem própria: `--arquivo <caminho>`).
   `✅ Concluído: personagem Marcos salvo. Caminho: {caminho absoluto de config/personagens/<slug>}`

## Novo visual (outra roupa ou cenário)

Escolha o personagem → `Qual o nome desse visual? (ex.: "cozinha", "terno")` → o que muda (só roupa, só cenário ou os dois). Prompt em inglês descrevendo só o que muda (a pessoa vem da imagem salva) → custo → `{PY} editor.py personagens opcoes <slug> --base <slug> --prompt "<prompt>" --variacoes "" "" ""` (3 tentativas do mesmo pedido) → galeria e escolha como no Criar → `{PY} editor.py personagens salvar <slug> --opcao <N> --look <nome-do-visual>`. Personagem criado de foto própria não tem visual registrado na HeyGen: avise que dá para criar a partir da descrição ou mandar outra foto.

## Ver ou editar

`{PY} editor.py personagens mostrar <slug>` → mostre o resumo (como no passo 9) e a imagem do visual padrão com `SendUserFile`. Pergunte o que mudar, uma coisa por vez. Grave só os campos mudados num JSON e rode `{PY} editor.py personagens editar <slug> --dados <json>`. Trocar o visual padrão: `{"look_padrao": "<nome>"}`. Mudar a aparência ou a roupa da imagem é um "Novo visual", não uma edição de texto.

## Apagar

Confirme mostrando o nome e a imagem: `1. Sim, apagar o Marcos / 2. Não`. Só então `{PY} editor.py personagens apagar <slug> --confirmar` (um visual só: `--look <nome>`).

## Fim

Sugira o próximo passo: `/video-avatar` para fazer um vídeo com o personagem falando.
