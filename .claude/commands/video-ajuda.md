---
name: editor-video:video-ajuda
description: Explica como o editor funciona, lista os comandos por categoria e mostra o status dos vídeos (novos, em andamento, prontos). Também oferece "Liberar espaço" (apaga só os arquivos intermediários de vídeos já prontos). Use para "ajuda", "como funciona", "o que dá para fazer", "quais comandos", "status dos vídeos", "liberar espaço", "está ocupando muito espaço".
allowed-tools: Read, Bash, SendUserFile
model: sonnet
---

# Ajuda do editor

## 1. Explicação curta

```
Como funciona:
1. Você grava e coloca o vídeo em: {caminho absoluto de videos/Para Editar}
2. Digita /video-editar e responde algumas perguntas
3. Eu transcrevo, corto pausas e erros, coloco zooms, animações e legenda
4. Você aprova cada etapa vendo uma prévia
5. O vídeo pronto aparece em: {caminho absoluto de videos/Editados}
```

## 2. Comandos

```
Editar
- /video-editar: do começo ao fim (recomendado)
- /video-cortar: só cortar pausas e erros
- /video-legendar: colocar ou trocar a legenda
- /video-motion: colocar ou refazer as animações
- /video-verticalizar: versão 9:16 para Reels/TikTok
- /video-react: você + outro vídeo na mesma tela
- /video-ajustar: pedir uma mudança num vídeo pronto
- /video-painel: painel visual com a linha do tempo

Configurar
- /video-marca: suas cores, fonte, logo e estilos padrão
- /configurar-legenda: fonte, cores, tamanho e posição da legenda
- /configurar-transcricao: trocar o serviço de transcrição
- /configurar-editor-video: instalar ou consertar o editor
```

## 3. Status dos vídeos

Rode `{PY} editor.py videos --json` e mostre:

```
Seus vídeos:
⚪ aula 4 (novo)
🟡 aula 3 (em andamento: corte concluído)
🟢 teste → teste_editado.mp4
```

Sem vídeos: diga onde colocar.

## 4. O que mais quer?

```
1. Editar um vídeo agora
2. Liberar espaço no computador
3. Entender alguma coisa (me pergunte)

Digite o número:
```

### Liberar espaço

`{PY} editor.py liberar-espaco` (sem `--confirmar`, só lista):

```
Posso apagar os arquivos intermediários de {N} vídeos já prontos e liberar {X} MB:
- teste (120 MB)
- aula 2 (840 MB)

Os vídeos prontos (Editados) e os originais (Para Editar) NÃO são apagados.
Depois disso, para ajustar um desses vídeos será preciso editar de novo do começo (inclusive transcrever de novo).

1. Pode apagar
2. Não

Digite o número:
```

1 → `{PY} editor.py liberar-espaco --confirmar` → `✅ Concluído: {X} MB liberados.`
Nada a apagar → `Não há arquivos intermediários de vídeos prontos para apagar.`

## Perguntas frequentes

**Onde ficam meus vídeos?** Originais em `videos/Para Editar`, prontos em `videos/Editados`, com o nome que você escolheu + `_editado`.

**Posso fechar o Claude no meio?** Pode. No `/video-editar`, ele pergunta se quer continuar de onde parou.

**Quanto custa?** A edição é grátis. A transcrição pelo Groq é grátis no uso normal (veja `/configurar-transcricao`).

**Funciona com vídeo gravado no celular?** Sim, em pé ou deitado. Vídeo em pé já sai no formato de Reels.

**Qual a melhor forma de gravar?** Boa luz de frente, câmera na altura dos olhos, microfone perto. Se puder, grave em 4K: os zooms e a versão vertical ficam mais nítidos.
