# Etapa: formato react (você + um vídeo de referência)

Pré-requisito: corte final feito. Uma pergunta por vez.

## 1. Vídeo de referência

Liste `videos/Para Editar/referencias/`:

```
Qual vídeo vai aparecer junto com você?

1. {arquivo 1} (1:20)
2. {arquivo 2} (0:45)
3. Vou colocar outro arquivo na pasta
4. Tenho um link (YouTube, Instagram, TikTok…)

Digite o número:
```

- 3 → mostre o caminho absoluto de `videos/Para Editar/referencias` e espere.
- 4 → peça o link e avise, antes de baixar:
  ```
  Importante: use só vídeos que você tem direito de usar (seus, com autorização ou dentro das regras da plataforma). A responsabilidade pelo uso é sua.

  Para baixar pelo link eu instalo uma ferramenta gratuita (yt-dlp), só na primeira vez.
  1. Pode baixar
  2. Prefiro colocar o arquivo na pasta

  Digite o número:
  ```
  1 → `{PY} editor.py baixar-referencia "<link>"`.

## 2. Posição

Formato de saída vertical (padrão):
```
Como fica a tela?

1. Referência em cima, você embaixo (mais comum)
2. Você em cima, referência embaixo

Digite o número:
```
Depois: `Tamanho das partes? 1. Metade e metade / 2. Referência menor (40%) e você maior (60%)`.

Se o aluno quiser o react horizontal (YouTube): `1. Lado a lado / 2. Você no cantinho da tela (PiP)`.

## 3. Trecho da referência

```
Vou usar a referência inteira ({duração})?

1. Sim, inteira
2. Só um trecho (ex.: de 0:30 até 1:10)

Digite o número:
```

Se o trecho for mais curto que a sua fala ({duração do corte}):
```
A referência ({x}) é mais curta que a sua fala ({y}). O que faço no fim dela?

1. Repetir desde o começo
2. Congelar no último quadro
3. Deixar mais lenta para caber

Digite o número:
```

## 4. Áudio da referência

```
E o som da referência?

1. Mudo (só a sua voz)
2. Baixinho o tempo todo
3. Automático: abaixa sozinho quando você fala (recomendado)

Digite o número:
```

## 5. Montar e conferir

`⏳ Passo 1/2: montar a tela dividida.` → `{PY} editor.py layout <id> react --referencia "<arquivo>" --posicao <cima|baixo|lado|pip> --proporcao <50|40> [--inicio s --fim s] --curta <repetir|congelar|velocidade> --audio <mudo|baixo|auto> [--orientacao horizontal]`

`{PY} editor.py conferir-layout <id> react` → abra e confira →

```
Assim fica o react:
{caminho absoluto de react/conferencia.jpg}

1. Tudo certo
2. Trocar a posição
3. Ajustar o trecho da referência

Digite o número:
```

No react, a legenda fica na emenda entre as duas partes, e os cards de motion só aparecem na parte da referência (ou ficam desligados, se o aluno preferir).

`✅ Concluído: react montado.`
