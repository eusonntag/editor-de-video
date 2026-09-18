# Etapa: transcrição

Usada pelo `/video-editar` e pelos avulsos que precisarem de transcrição. `<id>` = vídeo escolhido.

## 1. Já transcrito?

Se `{PY} editor.py estado <id> --json` já tem `etapas.transcricao`: pule para o passo 3 (nunca retranscrever).

## 2. Transcrever

1. Rode `{PY} editor.py custo <id>` e, só na primeira transcrição da sessão, conte em uma linha: `A transcrição deste vídeo ({duração}) sai {custo}.`
2. Anúncio (nível 2 se veio do `/video-editar`): `⏳ Passo 1/2: transcrever a fala do vídeo.` (nível 1 com o tempo de `tempo-estimado.md` se for comando avulso).
3. `{PY} editor.py transcrever <id>`.
4. Em paralelo (mesma mensagem), rode `{PY} editor.py analisar-imagem <id>` e guarde o resultado para a etapa de corte (não mostre agora).

Se falhar:

```
A transcrição não funcionou: {motivo em uma frase, ex.: "a chave do Groq foi recusada" / "sem internet" / "limite do plano gratuito por agora"}.

1. Tentar de novo
2. Transcrever no meu computador desta vez (grátis, mais lento)
3. Configurar outra chave

Digite o número:
```
2 → `{PY} editor.py transcrever <id> --motor whisper` (se o Whisper local não estiver instalado, pergunte antes e rode `{PY} editor.py instalar --local`). 3 → `/configurar-transcricao` e volte.

## 3. Conferir nomes e termos

Rode `{PY} editor.py texto <id>` e mostre o texto ao aluno (se for longo, mostre as primeiras ~25 frases e diga que o resto está no painel):

```
Transcrevi o vídeo. Dá uma olhada se algum nome, marca ou termo saiu errado:

[0:01] Fala, tudo bem?
[0:02] Me chamo Cristiano, estou testando aqui um projeto no cloud.
…

Algo para corrigir? Escreva no formato errado → certo (ex.: "cloud → Claude, vtsd → VTSD"),
ou digite 1 se está tudo certo.
```

Você também procura sozinho: nomes próprios, marcas e siglas que o Whisper costuma errar (ex.: "cloud" quando o assunto é Claude). Sugira na mesma mensagem: `Acho que "cloud" deveria ser "Claude". Confirma?`

Grave as correções em `videos/.trabalho/<id>/edit/correcoes.json` (`{"cloud": "Claude"}`, juntando com o que já existir). Elas entram nas legendas e nos cards automaticamente.

`✅ Concluído: transcrição pronta ({N} palavras).`
