---
name: editor-video:video-editar
description: Porta principal do editor. Edita um vídeo de pessoa falando do começo ao fim, com aprovação em cada etapa - escolhe o vídeo, o pacote (só cortar, cortar + legenda, completo ou personalizado), o estilo de edição (natural, dinâmica com zooms, acelerada) e o formato (original, vertical, os dois ou react); transcreve, corta pausas e erros, aplica zooms, cria animações (motion) sincronizadas com a fala, coloca legenda e salva em videos/Editados. Retoma um vídeo em andamento. Use para "editar vídeo", "editar meu vídeo", "cortar e legendar", "fazer o vídeo completo", "começar".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
model: opus
---

# Editar um vídeo (do começo ao fim)

Siga o CLAUDE.md: uma pergunta por vez, opções numeradas, anúncios 🔍/⏳/✅ com tempos de `.claude/rules/tempo-estimado.md`, nada de comando cru, caminho absoluto em toda entrega. Referência técnica: `docs/pipeline.md`.

As etapas ficam em `.claude/etapas/video-editar/`. Leia cada arquivo na hora de executar a etapa.

---

## Passo 0. Checagem rápida (em silêncio)

1. Detecte `{PY}` (se ainda não fez nesta sessão).
2. Se não existir `.venv` na raiz ou `{PY} editor.py diagnostico --json` não estiver `pronto`: diga em uma frase o que falta e oriente `/configurar-editor-video`. Encerre.
3. `{PY} editor.py videos --json`. Se algum estiver 🟡 em andamento:
   ```
   Você tem um vídeo em andamento: {id} ({etapa concluída}).

   1. Continuar de onde parou
   2. Começar outro vídeo

   Digite o número:
   ```
   Opção 1: leia o `estado.json` desse vídeo e pule direto para a próxima etapa não feita (as escolhas já estão lá).

---

## Passo 1. Escolher o vídeo

Se o aluno mandou um vídeo pelo chat, copie para `videos/Para Editar/` (mantendo o nome) e use esse.

Liste os vídeos da pasta:

```
Qual vídeo vamos editar?

1. ⚪ gravação aula 3  (4:12, horizontal)
2. 🟢 teste  (0:22, horizontal), já editado → teste_editado.mp4

Digite o número:
```

Se a pasta estiver vazia:

```
Ainda não tem vídeo na pasta de edição. Você pode:
- colocar o arquivo em: {caminho absoluto de videos/Para Editar}
- ou me enviar o vídeo aqui no chat

Me avise quando estiver lá.
```

Vídeo já editado (🟢): pergunte se quer refazer do zero (1) ou ajustar algo (2 → `/video-ajustar`).

---

## Passo 2. Escolhas (uma pergunta por vez)

### 2.1 Pacote
```
O que você quer neste vídeo?

1. Só cortar (tira pausas, erros e repetições)
2. Cortar + legenda
3. Completo: corte + animações (motion) + legenda (recomendado)
4. Personalizado (você escolhe as etapas)

Digite o número:
```
Personalizado: `Além do corte, quais etapas? Digite os números separados por vírgula (ex.: 1,2): 1. Motion (animações) 2. Legenda`. Os zooms vêm do estilo de edição (próxima pergunta).

### 2.2 Estilo de edição
```
Qual ritmo de edição?

1. Natural: só os cortes, sem zoom
2. Dinâmica: zoom a cada corte e zoom nas frases importantes (recomendado para redes sociais)
3. Acelerada: pausas mínimas e zooms frequentes, ritmo de Reels

Digite o número:
```
Se `config/marca.json` tiver `edicao.estilo`, mostre esse como "(seu padrão)" na lista.

### 2.3 Formato
Para vídeo horizontal:
```
Em qual formato?

1. Igual ao original (horizontal, YouTube)
2. Vertical 9:16 (Reels, TikTok, Shorts)
3. Os dois
4. React: você + outro vídeo na mesma tela

Digite o número:
```
Vídeo gravado em pé (vertical): o formato é vertical; pergunte só `1. Vertical / 2. React`.

Grave as escolhas: `{PY} editor.py estado <id> --escolha pacote=<n> estilo_edicao=<natural|dinamica|acelerada> formatos='["horizontal","vertical"]'` (etapas do personalizado em `etapas='["motion","legenda"]'`).

---

## Passo 3. Resumo e confirmação

Calcule o tempo total somando as linhas de `tempo-estimado.md` (D = duração do vídeo; depois do corte, estime 80% de D).

```
Resumo do que vou fazer:
- Vídeo: gravação aula 3 (4:12)
- Pacote: completo (corte + motion + legenda)
- Edição: dinâmica (zooms)
- Formatos: horizontal e vertical
- Tempo total estimado: 35 a 45 minutos
- Você aprova: o corte, as animações, a legenda e o nome do arquivo

1. Tudo certo, pode começar
2. Quero ajustar algo

Digite o número:
```

---

## Passo 4. Etapas

Execute na ordem, lendo cada arquivo de etapa. Entre uma etapa e outra, mostre o progresso:

```
… Etapa 2/5 concluída …
Corte: 4:12 → 3:21 (4 frases repetidas e 38 s de pausas removidos)
Próximo: Formato e zooms
```

| # | Etapa | Arquivo | Quando |
|---|---|---|---|
| 1 | Transcrição | `.claude/etapas/video-editar/transcrever.md` | sempre |
| 2 | Corte (+ zooms + cor) | `.claude/etapas/video-editar/cortar.md` | sempre |
| 3 | Formato | `verticalizar.md` (vertical), `react.md` (react); horizontal: `{PY} editor.py layout <id> horizontal` em silêncio | sempre |
| 4 | Motion | `.claude/etapas/video-editar/motion.md` | pacote 3 ou personalizado com motion |
| 5 | Legenda | `.claude/etapas/video-editar/legendar.md` | pacotes 2 e 3 ou personalizado com legenda |
| 6 | Finalizar | `.claude/etapas/video-editar/finalizar.md` | sempre |

Com mais de um formato: faça a etapa 3 para todos, depois motion (um roteiro só, prévia de cada formato), depois legenda de todos, e finalize tudo junto.

Em cada portão de aprovação das etapas, inclua a opção "Revisar no painel": rode o fluxo do `/video-painel` (abre no vídeo atual), espere o aluno voltar e retome a mesma aprovação. Se ele usou "Aplicar alterações" no painel, aplique o `ajustes.json` como no `/video-ajustar` antes de seguir.

---

## Passo 5. Memória do vídeo

Ao fim de cada etapa, acrescente ao `videos/.trabalho/<id>/project.md` (crie se não existir) uma linha curta: data, etapa, decisão ("Corte: removidas 3 frases repetidas; pausas até 0,35 s. Zooms: 12, 2 desligados."). É isso que permite retomar e ajustar depois.

---

## Se algo falhar

Explique em uma frase e ofereça caminhos numerados. Nunca mostre o erro técnico cru. Exemplos:
- Transcrição: veja a seção "Se a transcrição falhar" do `/configurar-transcricao`.
- Falta de espaço em disco: diga quanto precisa e ofereça o "Liberar espaço" do `/video-ajuda`.
- Render do motion falhou: tente uma vez de novo; se repetir, ofereça "1. Seguir sem motion / 2. Tentar com menos cards".
