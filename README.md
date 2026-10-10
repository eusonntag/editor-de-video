# Editor de Vídeo com IA

Você grava um vídeo falando para a câmera. O editor, guiado pelo Claude Code, entrega o vídeo pronto:

- ✂️ **Corte**: tira silêncios, pausas longas, hesitações ("é…", "hã") e frases que você repetiu, mantendo sempre a última versão.
- 🔍 **Edição dinâmica**: zoom a cada corte e nas frases importantes (opcional).
- ✨ **Animações (motion)**: títulos, listas, números, passo a passo e chamadas que aparecem no momento em que você fala, no estilo da sua marca, sem cobrir o seu rosto.
- 💬 **Legenda**: dinâmica (estilo Reels) ou clássica, com a palavra falada em destaque, mais o arquivo `.srt`.
- 📱 **Versão vertical** 9:16 para Reels, TikTok e Shorts, e o formato **react** (você + outro vídeo na tela).
- 🖥️ **Painel visual**: uma linha do tempo estilo CapCut para revisar cortes, cards e legenda com cliques.

Você aprova cada etapa vendo uma prévia. Não precisa saber programar nem editar vídeo.

---

## Comece aqui

### 1. Instale o Claude Code

Siga as instruções oficiais: https://docs.claude.com/pt-BR/docs/claude-code/overview (aplicativo para Windows e Mac, extensão do VS Code ou terminal). É preciso ter uma conta Claude com acesso ao Claude Code.

### 2. Baixe este projeto

- **Com Git**: `git clone <endereço deste repositório>`
- **Sem Git**: botão verde **Code → Download ZIP** no GitHub e extraia a pasta onde quiser (ex.: Documentos).

### 3. Abra a pasta no Claude Code e rode a configuração

Abra a pasta do projeto no Claude Code e digite:

```
/configurar-editor-video
```

Ele confere o seu computador, instala o que faltar (Python, Node.js, FFmpeg e as bibliotecas do editor, sempre pedindo sua permissão), conecta a transcrição e faz um teste com um vídeo de exemplo. Leva de 10 a 20 minutos, uma vez só.

### 4. Edite seu primeiro vídeo

1. Coloque o vídeo na pasta `videos/Para Editar` (ou envie o arquivo no chat do Claude).
2. Digite `/video-editar` e responda às perguntas.
3. O vídeo pronto aparece em `videos/Editados`, com o nome que você escolher + `_editado`.

Lista completa de comandos: [COMO-USAR.md](COMO-USAR.md).

---

## Quanto custa?

| O quê | Custo |
|---|---|
| Editor, cortes, zooms, animações e legendas | grátis, roda no seu computador |
| Transcrição com **Groq** (recomendado) | grátis no plano gratuito (até 8 horas de áudio por dia) |
| Transcrição no seu computador | grátis, mais lenta |
| Transcrição com ElevenLabs | paga por minuto (opcional) |
| Narração por voz de IA (ElevenLabs, `/video-narrar`) | créditos pré-pagos, cerca de 1.000 caracteres por minuto de fala (opcional) |
| Fundo musical por IA (ElevenLabs Music, `/video-musica`) | créditos por minuto de música; uso comercial pede plano pago na ElevenLabs (opcional; dá para usar uma música sua de graça) |

Você só precisa da sua conta do Claude. O `/configurar-transcricao` mostra o passo a passo para criar a conta gratuita do Groq.

---

## Requisitos

- Windows 10/11 ou macOS 12+
- 8 GB de RAM (16 GB recomendado) e ~3 GB livres
- Internet para instalar e para a transcrição pelo Groq (a edição em si funciona offline)

Dica de gravação: luz de frente, câmera na altura dos olhos, microfone perto. Se puder, grave em 4K: os zooms e a versão vertical ficam mais nítidos.

---

## Problemas comuns

| Problema | O que fazer |
|---|---|
| "FFmpeg não encontrado" logo depois de instalar | Feche e abra o Claude Code (programas novos só aparecem em janelas novas) e rode `/configurar-editor-video` de novo. |
| No Mac, pediu senha no terminal | É o Homebrew instalando programas. Digite a senha do seu Mac (ela não aparece enquanto você digita). |
| O antivírus bloqueou algo | Libere a pasta do projeto e rode `/configurar-editor-video` de novo. |
| A transcrição falhou | Pode ser a chave, o limite gratuito ou a internet. O editor oferece tentar de novo ou transcrever no computador. `/configurar-transcricao` troca a chave. |
| O vídeo original não toca no painel | Vídeos HEVC (celular, webcam) ganham uma cópia leve automaticamente; espere alguns segundos. |
| Pouco espaço no disco | `/video-ajuda` → "Liberar espaço" apaga só os arquivos intermediários de vídeos já prontos. |
| Qualquer outra coisa | Rode `/configurar-editor-video`: ele diagnostica e conserta. |

Instalação manual (se o instalador automático falhar): Python 3.12 (https://www.python.org/downloads/, marque "Add Python to PATH"), Node.js 22 ou mais novo (versão LTS em https://nodejs.org), FFmpeg (Windows: https://www.gyan.dev/ffmpeg/builds/, Mac: `brew install ffmpeg-full`, que inclui as legendas) e Git (https://git-scm.com). Depois, `/configurar-editor-video`.

---

## Como funciona por dentro

- `editor.py`: ponto de entrada único, chamado pelos comandos do Claude (`.claude/commands/`). Funciona igual no Windows e no Mac.
- Corte: [video-use](https://github.com/browser-use/video-use). Animações: [HyperFrames](https://github.com/heygen-com/hyperframes) + GSAP. Legendas: FFmpeg/libass com fontes livres embutidas.
- Documentação técnica: [docs/pipeline.md](docs/pipeline.md). Créditos e licenças: [CREDITOS.md](CREDITOS.md).
