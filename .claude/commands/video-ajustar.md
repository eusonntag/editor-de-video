---
name: editor-video:video-ajustar
description: Aplica mudanças num vídeo já editado, refazendo só a etapa afetada - pedidos livres ("tira o card 3", "legenda mais pra baixo", "manter a frase da piada", "corrige o nome", "sem zoom no começo", "troca o estilo dos cards") ou as alterações feitas no painel visual (botão Aplicar alterações, arquivo ajustes.json). Use para "ajustar", "mudar", "corrigir", "tira", "coloca", "apliquei no painel".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile
model: opus
---

# Ajustar um vídeo pronto

Regra de ouro: **edição cirúrgica**. Mude só o que foi pedido e refaça só as etapas que dependem da mudança.

## 1. Vídeo e pedido

- `.claude/etapas/escolher-video.md` (se o aluno não disse, o mais recente em andamento ou editado).
- Existe `videos/.trabalho/<id>/ajustes.json` (vindo do painel) mais novo que o último `estado.json` → `atualizado`? Leia e use como pedido. Depois de aplicar, renomeie para `ajustes-aplicados-<data>.json`.
- Senão, se o aluno ainda não disse o que quer: `O que você quer mudar? (ex.: "tira o card 3", "legenda um pouco mais pra cima", "manter a frase sobre o preço")`.

## 2. O que cada pedido refaz

| Pedido | O que mudar | Refazer depois |
|---|---|---|
| Manter ou cortar uma frase/trecho (`manter_trecho`, `cortar_trecho`) | `edit/edl.json` (regras de `docs/pipeline.md`) | corte → layout de cada formato → motion (revise os tempos do roteiro pelo `palavras.json` novo) → legenda → finalizar |
| Corrigir palavra (`corrigir_palavra`) | `edit/correcoes.json` e `{PY} editor.py palavras <id>` | legenda (e o card, se a palavra estiver num card) → finalizar |
| Ligar/desligar zoom (`zoom`) | `dinamica.json` → `ativo` (ou `{PY} editor.py dinamica <id> --desligar N`) | layout → motion render → legenda → finalizar |
| Texto, ícone ou card ligado/desligado (`card_texto`, `card_ativo`) | `motion/roteiro.json` | motion montar + prévia → render → legenda → finalizar |
| Estilo dos cards (`estilo_motion`) | `roteiro.json` → `estilo`/`icones` | motion montar + prévia → render → legenda → finalizar |
| Legenda: estilo, cor, tamanho, posição (`estilo_legenda`) | opções do `editor.py legendar` | legenda → finalizar |
| Cor da imagem | `{PY} editor.py cor <id> --filtro …` | corte → tudo depois |
| Versão vertical: recorte | `layout <id> vertical --centro-x / --seguir` | layout vertical → motion vertical → legenda vertical → finalizar vertical |

A mudança vale para todos os formatos já feitos, a não ser que o aluno fale de um só.

## 3. Resumo e confirmação

```
Vou fazer assim:
- Tirar o card 3 ("3 dicas")
- Refazer as animações e a legenda do horizontal e do vertical
- Substituir aula-3_editado.mp4 e aula-3_editado_vertical.mp4

Tempo estimado: {soma das etapas}

1. Tudo certo, pode fazer
2. Quero ajustar algo

Digite o número:
```

## 4. Executar

Use as etapas de `.claude/etapas/video-editar/` só a partir do ponto afetado. Quando a etapa tem prévia (motion, corte), mostre a prévia de novo e peça aprovação, a não ser que o aluno tenha dito para ir direto. Finalize com o mesmo `nome_final` (substituindo, com aviso).

## 5. Entregar

Mesma entrega do `finalizar.md`, dizendo o que mudou: `✅ Concluído: card 3 removido. Caminho: …`. Registre no `project.md`.
