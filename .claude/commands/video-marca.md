---
name: editor-video:video-marca
description: Cria ou edita a identidade visual usada em todos os vídeos - nome, @ do perfil, cor de destaque, fonte dos títulos, logo, estilo das animações (escolhido numa galeria com o próprio vídeo), estilo de ícones, estilo e cor da legenda e ritmo de edição padrão. Salva em config/marca.json. Use para "minha marca", "minhas cores", "identidade visual", "logo", "mudar a cor dos cards", "estilo padrão".
allowed-tools: Read, Write, Edit, Bash, Glob, SendUserFile
model: sonnet
---

# Identidade visual

Uma pergunta por vez. Tudo é opcional: "pular" deixa o padrão do estilo.

## Passo 0

Se `config/marca.json` existe **e tem `nome`**, mostre o resumo atual e pergunte (um arquivo só com `legenda` foi criado pelo `/configurar-legenda`: trate como marca nova e mantenha a seção `legenda` ao salvar):
```
Sua identidade atual:
- Nome: Cristiano · @cristiano
- Cor de destaque: #c4ff5e (verde neon)
- Animações: Escuro elegante, ícones duotone
- Legenda: Dinâmica, amarelo
- Edição: Dinâmica

1. Mudar alguma coisa
2. Refazer tudo
3. Está bom assim

Digite o número:
```
"Mudar alguma coisa" → pergunte o quê e vá direto à pergunta correspondente.

## Perguntas

1. `Qual nome aparece no card de apresentação? (ex.: "Cristiano Silva")`
2. `Qual é o seu @? (ex.: "@cristiano.silva", ou digite 1 para pular)`
3. Cor de destaque:
   ```
   Qual a cor de destaque da sua marca?

   1. Verde neon #c4ff5e
   2. Amarelo #FFD400
   3. Azul #2F6BFF
   4. Laranja #FF7A1A
   5. Rosa #FF4D8D
   6. Outra (digite o código, ex.: #7C3AED, ou o nome da cor)

   Digite o número:
   ```
   Nome de cor → converta para hex e confirme.
4. Fonte dos títulos:
   ```
   Qual fonte para os títulos dos cards?

   1. Do próprio estilo (recomendado)
   2. Inter: moderna e neutra
   3. Montserrat: geométrica, forte
   4. Poppins: arredondada, amigável
   5. Playfair Display: serifada, elegante
   6. Space Grotesk: tecnológica

   Digite o número:
   ```
5. Logo: `Tem um logo? Coloque o arquivo PNG (de preferência com fundo transparente) na pasta {caminho absoluto de config} e me diga o nome, ou digite 1 para pular.` → confira que existe e grave o caminho relativo (`config/logo.png`).
6. Estilo das animações: se existir algum vídeo com layout pronto, mostre a galeria com ele (`{PY} editor.py motion <id> galeria --formato <f> --tipo estilos`). Senão, descreva os 5 estilos (texto dos arquivos `motion/estilos/*.json` → `descricao`) e pergunte `1. Escuro elegante / 2. Claro minimalista / 3. Colorido pop / 4. Editorial / 5. Cinema`.
7. Ícones: `1. Linha / 2. Preenchido / 3. Duotone / 4. Emoji (muda um pouco entre Windows e Mac) / 5. Sem ícones`.
8. Legenda: galeria se houver vídeo (`galeria-legendas`), senão descreva; `1. Dinâmica / 2. Clássica / 3. Caixa / 4. Palavra`. Depois a cor da palavra em destaque: `1. Amarelo (padrão) / 2. A cor da marca / 3. Branco (sem destaque) / 4. Outra`. Para fonte, tamanho, contorno, tarja e posição da legenda, indique `/configurar-legenda`.
9. Ritmo de edição padrão: `1. Natural / 2. Dinâmica / 3. Acelerada / 4. Perguntar em cada vídeo`.

## Confirmar e salvar

Mostre o resumo (como no Passo 0) + `1. Tudo certo, pode salvar / 2. Quero ajustar algo`. Salve `config/marca.json` seguindo `config/marca.exemplo.json` (sem o campo `_obs`; campos pulados ficam vazios). Não apague opções da `legenda` que já existam (vieram do `/configurar-legenda`).

`✅ Concluído: identidade visual salva. Caminho: {caminho absoluto de config/marca.json}`

Os próximos vídeos já saem com ela. Vídeos prontos não mudam sozinhos: para aplicar num vídeo pronto, `/video-ajustar` ("aplicar minha marca nos cards").
