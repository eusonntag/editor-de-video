---
name: editor-video:configurar-editor-video
description: Instala e configura o editor de vídeo pela primeira vez (ou conserta uma instalação). Verifica Python, Node, FFmpeg e bibliotecas, instala o que faltar, conecta a transcrição (Groq, local ou ElevenLabs), cria a identidade visual e testa com um vídeo de exemplo. Use quando o aluno disser "instalar", "configurar", "primeira vez", "não está funcionando", "deu erro na instalação".
allowed-tools: Read, Write, Edit, Bash, Glob, SendUserFile
model: sonnet
---

# Configurar o editor de vídeo

Instalação guiada. Roda uma vez; pode rodar de novo para consertar. Siga o padrão do CLAUDE.md: uma pergunta por vez, anúncios 🔍/⏳/✅, nada de comando cru na tela.

## REGRA DE CUSTO

Instalar é grátis. Tudo roda no computador do aluno, menos a transcrição (que pode ser grátis também):

| O quê | Custo |
|---|---|
| Editor, cortes, zooms, motion, legendas | grátis, roda no seu computador |
| Transcrição com Groq (recomendado) | grátis no plano gratuito (até 8 h de áudio por dia) |
| Transcrição no computador | grátis, mais lenta |
| Transcrição com ElevenLabs | paga por minuto |

**Conta de padaria:** quem edita 3 vídeos de 5 minutos por dia usa 15 minutos de áudio. O limite gratuito do Groq é 8 horas por dia. Ou seja: custo zero.

---

## Passo 0. Verificar se já está configurado

Detecte o Python (`python3 --version 2>&1 || py -3 --version 2>&1`) e rode em silêncio `{PY} editor.py diagnostico --json`.

- Se o Python não responder, vá direto ao Passo 2 (o Python precisa ser instalado primeiro).
- Se `pronto` for `true`:
  ```
  Seu editor já está instalado e funcionando.

  ✓ Programas e bibliotecas
  ✓ Transcrição: {serviço}
  {✓ ou ○} Identidade visual

  O que quer fazer?
  1. Editar um vídeo agora (/video-editar)
  2. Testar com o vídeo de exemplo
  3. Refazer alguma configuração

  Digite o número:
  ```
  Opção 2 leva ao Passo 6. Opção 3: pergunte o quê (1. Transcrição / 2. Identidade visual / 3. Reinstalar tudo) e siga o passo correspondente.
- Se não estiver pronto, siga para o Passo 1.

---

## Passo 1. Boas-vindas

```
Vamos preparar seu editor. São 5 passos, cerca de 10 a 20 minutos, e só precisa fazer uma vez:

1. Conferir o que já existe no seu computador
2. Instalar o que faltar
3. Escolher como transcrever os vídeos
4. Sua identidade visual (opcional)
5. Um teste com um vídeo de exemplo

Pode começar?
1. Sim, vamos
2. Agora não

Digite o número:
```

---

## Passo 2. Conferir o computador

Anúncio: `🔍 Próximo passo: conferir o que já está instalado (1 passo). Tempo estimado: cerca de 5 segundos.`

Detecte o sistema (`uname -s`: `MINGW*`/`MSYS*` = Windows, `Darwin` = Mac). Rode `{PY} editor.py diagnostico` (ou, sem Python, conte que o Python falta) e mostre a lista em linguagem simples:

```
Seu computador (Windows):
✓ Python
✗ FFmpeg (programa que corta e junta vídeo)
✓ Node.js (programa que roda as animações)
✗ Bibliotecas do editor
…
```

---

## Passo 3. Instalar o que faltar

### 3a. Programas do sistema (Python, Node, FFmpeg, Git)

Só se algum deles faltar. Rode `{PY} editor.py instalar --sistema` (sem `--sim`, só lista). Mostre e pergunte:

```
Preciso instalar estes programas no seu computador:
- FFmpeg
- Node.js

{Windows:} Vou usar o instalador oficial do Windows (winget). Pode aparecer uma janela pedindo permissão: clique em "Sim".
{Mac:} Vou usar o Homebrew{, que também será instalado}. Ele pode pedir a senha do seu Mac no terminal.

1. Pode instalar
2. Prefiro instalar sozinho (mostro os links)

Digite o número:
```

- Opção 1: anúncio `🔍 Próximo passo: instalar os programas do sistema ({N} passos). Tempo estimado: 5 a 15 minutos.` e rode `{PY} editor.py instalar --sistema --sim`. Se o Python ainda não existia, use `winget install -e --id Python.Python.3.12` (Windows) ou `brew install python@3.12` (Mac) antes, com a mesma confirmação.
- Opção 2 ou se falhar: mostre os links (seção "Links úteis") com um passo a passo curto por programa e peça para avisar quando terminar.
- Depois de instalar, se algum programa continuar "não encontrado", peça para **fechar e abrir o Claude Code** (o computador só enxerga programas novos em janelas novas) e rodar `/configurar-editor-video` de novo. Ele retoma daqui.

### 3b. Bibliotecas e ferramentas do editor

Anúncio: `🔍 Próximo passo: instalar as bibliotecas e ferramentas do editor (6 passos). Tempo estimado: 3 a 8 minutos.`

Rode `{PY} editor.py instalar`. Ele imprime `⏳ Passo X/6` sozinho. No fim, rode o diagnóstico de novo e mostre o resultado. Se algo der ✗, explique e tente resolver (internet, espaço em disco, antivírus bloqueando).

---

## Passo 4. Serviço de transcrição

A transcrição é o que permite cortar erros, sincronizar os cards e gerar a legenda. Pergunte:

```
Como você quer transcrever os vídeos?

1. Groq (recomendado): grátis para uso normal e muito rápido. Precisa criar uma conta (2 minutos).
2. No meu computador: grátis e sem conta, porém mais lento (um vídeo de 5 min leva uns 5 min) e baixa um arquivo de 1,5 GB na primeira vez.
3. ElevenLabs: pago por minuto, é o melhor para pegar hesitações ("é…", "hã") e cortar erros com precisão.

Digite o número:
```

Siga o comando `/configurar-transcricao` com a opção escolhida (leia `.claude/commands/configurar-transcricao.md` e execute a partir do passo da opção, sem repetir esta pergunta). Ao terminar, volte aqui.

---

## Passo 5. Identidade visual (opcional)

```
Quer configurar agora sua identidade visual? (nome, @, cor, fonte, logo e o estilo das animações e legendas)
Assim todos os vídeos já saem com a sua cara.

1. Sim, agora (cerca de 3 minutos)
2. Depois (uso um estilo padrão bonito e você muda quando quiser com /video-marca)

Digite o número:
```

Opção 1: execute o fluxo do `/video-marca` e volte aqui.

---

## Passo 6. Teste com o vídeo de exemplo

```
Último passo: um teste completo com um vídeo curto de exemplo (sem custo, não usa a transcrição).
Ele passa por corte, zoom, animação e legenda. Assim temos certeza de que está tudo funcionando.

1. Fazer o teste (2 a 4 minutos)
2. Pular

Digite o número:
```

Opção 1: anúncio `🔍 Próximo passo: editar o vídeo de exemplo (5 passos). Tempo estimado: 2 a 4 minutos.` e rode `{PY} editor.py exemplo`. Abra (Read) o quadro de verificação que ele gerar e confira. Entregue:

```
✅ Concluído: teste aprovado. O vídeo de exemplo editado está em:
{caminho absoluto}
```

Se falhar, mostre a etapa que falhou em uma frase e tente resolver (rode o diagnóstico).

---

## Passo 7. Tudo pronto

```
Seu editor está pronto!

Como usar:
1. Coloque o vídeo em: {caminho absoluto de videos/Para Editar}
   (ou me envie o arquivo aqui no chat)
2. Digite /video-editar

Os vídeos prontos ficam em: {caminho absoluto de videos/Editados}
```

---

## Perguntas frequentes

**Preciso saber programar?** Não. Você só responde perguntas e aprova as prévias.

**Funciona no Mac?** Sim. No Mac a instalação usa o Homebrew, e o Mac pode pedir a sua senha no terminal.

**Quanto espaço ocupa?** Cerca de 1,5 GB (bibliotecas + navegador que renderiza as animações). A transcrição no computador ocupa mais 1,5 GB.

**O antivírus bloqueou algo.** Libere a pasta do projeto e rode /configurar-editor-video de novo.

**Instalei tudo e diz que o FFmpeg não foi encontrado.** Feche e abra o Claude Code (programas novos só aparecem em janelas novas).

**Posso usar sem internet?** A edição sim. A transcrição pelo Groq ou ElevenLabs precisa de internet; use a opção "no meu computador" para ficar 100% offline.

## Links úteis

- Python: https://www.python.org/downloads/ (no Windows, marque "Add Python to PATH")
- Node.js 22 ou mais novo (versão LTS): https://nodejs.org/
- FFmpeg Windows: https://www.gyan.dev/ffmpeg/builds/ · Mac: `brew install ffmpeg-full` (https://brew.sh; o `ffmpeg` simples vem sem legendas)
- Git: https://git-scm.com/downloads
- Groq (transcrição): https://console.groq.com
