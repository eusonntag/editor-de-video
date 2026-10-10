# Etapa: finalizar (nome, salvar, verificar, entregar)

## 0. Fundo musical (só na primeira entrega)

Se o vídeo ainda não tem `nome_final`, não existe `videos/.trabalho/<id>/musica/musica.json` e `estado.escolhas.musica` está vazio:

```
Quer um fundo musical por baixo da voz?

1. Não, sem música
2. Sim, colocar uma música (feita por IA no clima do vídeo, ou uma sua)

Digite o número:
```

1 → `{PY} editor.py estado <id> --escolha musica=nao`. 2 → `{PY} editor.py estado <id> --escolha musica=sim` e siga `.claude/etapas/musica.md` (passos 1 a 3); depois volte aqui. Se `config/marca.json` tem `musica.sempre: true`, pule a pergunta e vá direto para a etapa da música.

## 1. Nome do arquivo

Se `estado.json` já tem `nome_final` (vídeo refeito pelo `/video-ajustar`, `/video-legendar` etc.): use o mesmo nome, sem perguntar, e avise `Vou substituir {nome}_editado.mp4 pela versão nova.`

Senão, sugira um nome pelo conteúdo (leia a transcrição; o `{PY} editor.py nome <id>` dá uma sugestão automática que você pode melhorar):

```
Com qual nome você quer salvar o vídeo?
(sugestão: "3-dicas-para-vender-mais". Digite outro nome ou 1 para usar a sugestão)
```

Limpe o nome digitado com `{PY} editor.py nome <id> --limpar "<texto>"` (tira caracteres inválidos, troca espaço por hífen, mantém acentos) e confira se já existe: `{PY} editor.py nome <id> --verificar "<nome>" --formatos <formatos>`.

Se existir:
```
Já existe um vídeo chamado {nome}_editado.mp4.

1. Substituir
2. Salvar como {alternativa, ex.: nome_editado-2.mp4}

Digite o número:
```

## 2. Salvar e verificar

`⏳ Passo 1/2: salvar o vídeo final.` → `{PY} editor.py finalizar <id> --nome "<nome>" --formatos <formatos> [--substituir | --nova-versao]`

`⏳ Passo 2/2: conferir o resultado.` → para cada formato, `{PY} editor.py verificar <id> --formato <f>` e abra (Read) `verificacao.jpg`. Confira: duração bate com o corte (`ok: true`), tem áudio, card legível, legenda não coberta, rosto inteiro. Se algo estiver errado, corrija a etapa responsável antes de entregar.

## 3. Entregar

```
✅ Concluído: vídeo pronto!

📁 {caminho absoluto de videos/Editados/<nome>_editado.mp4}
📁 {caminho absoluto de <nome>_editado_vertical.mp4, se houver}
📝 Legenda separada (para subir no YouTube): {caminho do .srt, se houver}

Duração: 3:21 (era 4:12)

Próximos passos:
- /video-verticalizar: criar a versão para Reels/TikTok {só se ainda não tiver}
- /video-ajustar: pedir alguma mudança ("tira o card 3", "legenda mais para cima")
- /video-musica: colocar, trocar ou tirar o fundo musical
- /video-painel: ver a linha do tempo do vídeo
- /video-editar: editar o próximo vídeo
```

Registre no `project.md`: nome final, formatos, caminhos. O `estado.json` já fica atualizado pelo editor.
