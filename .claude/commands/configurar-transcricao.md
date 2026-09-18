---
name: editor-video:configurar-transcricao
description: Escolhe e conecta o serviço que transcreve os vídeos (Groq recomendado e grátis, Whisper no próprio computador, ou ElevenLabs pago). Passo a passo para criar a conta, pegar a chave de API, testar e salvar no .env. Use quando o aluno quiser configurar, trocar ou consertar a transcrição, ou quando a transcrição falhar por chave, limite ou internet.
allowed-tools: Read, Edit, Bash
model: sonnet
---

# Configurar a transcrição

A transcrição transforma a fala do vídeo em texto com o tempo de cada palavra. É ela que permite cortar erros, sincronizar as animações e gerar a legenda. Só precisa configurar uma vez.

Quando este comando é chamado por outro (`/configurar-editor-video` ou uma etapa que falhou), use só `⏳ Passo X/Y` e, no fim, **volte ao fluxo que chamou** e continue de onde parou.

## REGRA DE CUSTO

| Serviço | Custo | Velocidade | Conta |
|---|---|---|---|
| **Groq** (recomendado) | grátis no plano gratuito: até 2 h de áudio por hora e 8 h por dia. Acima disso, cerca de US$ 0,11 por hora de áudio | um vídeo de 10 min em ~10 s | sim, grátis, sem cartão |
| **No meu computador** (Whisper) | grátis | ~1× a duração do vídeo; baixa 1,5 GB na primeira vez | não |
| **ElevenLabs** | pago por minuto de áudio (veja o preço atual no site) | ~30 s | sim |

**Conta de padaria:** 3 vídeos de 5 min por dia = 15 min de áudio. O Groq grátis aguenta 8 horas por dia. Custo zero.

---

## Passo 0. Verificar

Leia (sem mostrar) o motor atual: `{PY} editor.py diagnostico --json` → item `transcricao`.

- Se chamado com uma opção já escolhida (ex.: pelo `/configurar-editor-video`), pule para o roteiro dessa opção.
- Se já estiver configurado e funcionando (`{PY} editor.py chave testar groq` devolve `"ok": true`):
  ```
  Sua transcrição já está configurada: {serviço}, chave {mascarada}. Está funcionando.

  1. Manter assim
  2. Trocar de serviço

  Digite o número:
  ```
- Senão, pergunte:
  ```
  Como você quer transcrever os vídeos?

  1. Groq (recomendado): grátis para uso normal e muito rápido
  2. No meu computador: grátis e sem conta, porém mais lento
  3. ElevenLabs: pago, o melhor para pegar hesitações e cortar erros

  Digite o número:
  ```

---

## Opção 1. Groq

### 1.1 Conta

```
Você já tem conta no Groq?

1. Sim
2. Não

Digite o número:
```

Se não:

```
Para criar a conta (grátis, sem cartão):

1. Acesse https://console.groq.com
2. Clique em "Sign in" e entre com o Google (mais rápido) ou com seu e-mail
3. Pronto, a conta está criada

Me avise quando entrar no painel.
```

### 1.2 Chave de API

```
Agora a chave de API (é como uma senha que deixa o editor usar sua conta):

1. No painel do Groq, clique em "API Keys" (menu da esquerda)
2. Clique em "Create API Key"
3. Dê um nome, por exemplo: editor-video
4. Clique em "Submit" e copie a chave (começa com gsk_)

Atenção: a chave só aparece uma vez. Se fechar sem copiar, é só criar outra.

Cole a chave aqui:
```

### 1.3 Testar e salvar

`⏳ Passo 1/2: testar a chave.` Rode `{PY} editor.py chave gravar groq {CHAVE}` (ele testa e só grava no `.env` se funcionar). Depois `{PY} editor.py chave motor groq`.

- `"ok": true` → `✅ Concluído: chave do Groq testada e salva ({chave mascarada}).`
- `"ok": false` → mostre a `mensagem` em linguagem simples e peça para copiar de novo (volte ao 1.2). Se for internet, ofereça tentar de novo.

---

## Opção 2. No meu computador (Whisper)

```
A transcrição vai rodar no seu computador, sem conta e sem custo.
Na primeira vez, baixo o modelo de reconhecimento de voz (cerca de 1,5 GB).
Depois disso, um vídeo de 5 minutos leva uns 5 minutos para transcrever.

1. Pode instalar
2. Prefiro outra opção

Digite o número:
```

Opção 1: `🔍 Próximo passo: instalar a transcrição local (2 passos). Tempo estimado: 2 a 5 minutos.` → `{PY} editor.py chave motor whisper` e `{PY} editor.py instalar --local`. Confira com `{PY} editor.py diagnostico` (item Transcrição ✓). O modelo em si é baixado na primeira transcrição (avise isso quando ela acontecer).

---

## Opção 3. ElevenLabs

### 3.1 Conta e plano

```
Você já tem conta na ElevenLabs?

1. Sim
2. Não

Digite o número:
```

Se não: acesse https://elevenlabs.io, clique em "Sign up", entre com Google ou e-mail. A transcrição (Scribe) é cobrada por minuto; confira o preço atual em https://elevenlabs.io/pricing/api.

### 3.2 Chave

```
Para pegar a chave:

1. Entre em https://elevenlabs.io/app
2. Clique no seu perfil (canto de baixo, à esquerda) e em "API Keys"
3. Clique em "Create API Key", dê um nome (editor-video) e deixe marcada a permissão "Speech to Text"
4. Copie a chave (ela só aparece uma vez)

Cole a chave aqui:
```

### 3.3 Testar e salvar

`{PY} editor.py chave gravar elevenlabs {CHAVE}` e `{PY} editor.py chave motor scribe`. Mesmas mensagens da opção 1.

---

## Fim

```
✅ Concluído: transcrição configurada com {serviço}.
```

Se veio de outro fluxo, volte a ele. Senão, sugira `/video-editar`.

## Se a transcrição falhar depois (limite, internet, chave)

Os comandos de edição oferecem, na hora do erro:

```
A transcrição não funcionou: {motivo em uma frase}.

1. Tentar de novo
2. Transcrever no meu computador desta vez (grátis, mais lento)
3. Configurar outra chave

Digite o número:
```

A opção 2 usa `--motor whisper` só naquele vídeo (instala o Whisper se precisar, com confirmação).

---

## Perguntas frequentes

**Preciso de cartão de crédito no Groq?** Não. O plano gratuito não pede cartão.

**E se eu passar do limite gratuito?** O Groq recusa por alguns minutos (limite por hora) e volta sozinho. O editor espera e tenta de novo; se continuar, oferece transcrever no computador.

**Perdi a chave.** Crie outra no painel (API Keys → Create API Key) e rode /configurar-transcricao de novo.

**Qual é mais preciso?** Para português, os três são muito bons. A ElevenLabs preserva melhor os "é…", "hã" e repetições, o que ajuda a cortar erros.

**Meus vídeos ficam guardados no Groq?** O editor envia só o áudio, para transcrever. Veja a política de privacidade do serviço em https://groq.com/privacy-policy.

## Links úteis

- Groq: https://console.groq.com · limites: https://console.groq.com/docs/rate-limits · preços: https://groq.com/pricing
- ElevenLabs: https://elevenlabs.io/app · preços da API: https://elevenlabs.io/pricing/api
- Whisper local (faster-whisper): https://github.com/SYSTRAN/faster-whisper
