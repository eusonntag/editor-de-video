# Etapa: legenda

A legenda é sempre a última camada (vai por cima do motion). Posição automática por formato: horizontal embaixo; vertical abaixo do queixo e acima da interface do Reels; react na emenda.

## 1. Estilo

Se `config/marca.json` tem `legenda.estilo`, ou se `estado.json` já tem `escolhas.legenda_estilo` para este vídeo: use e não pergunte.

Senão: `⏳ Passo 1/2: preparar a galeria de legendas.` → `{PY} editor.py galeria-legendas <id> --formato <formato principal>` → abra e confira a imagem.

```
Escolha o estilo da legenda (no seu próprio vídeo):
{caminho absoluto de galeria-legendas.jpg}

1. Dinâmica: poucas palavras, a palavra falada em destaque (Reels/TikTok)
2. Clássica: frase inteira, discreta (YouTube, aulas)
3. Caixa: palavras numa tarja
4. Palavra: uma palavra por vez, grande

Digite o número:
```

Depois: `Quer usar esse estilo em todos os vídeos? 1. Sim / 2. Só neste` → Sim: grave `legenda.estilo` em `config/marca.json`.

Cor de destaque: padrão amarelo (#FFD400) ou `legenda.cor` da marca. Só pergunte se o aluno pedir.

## 2. Gerar

Para cada formato: `⏳ Passo 2/2: colocar a legenda ({formato}).` → `{PY} editor.py legendar <id> --formato <f> --estilo <estilo>`.

Confira um quadro: `{PY} editor.py verificar <id> --formato <f>` → abra `verificacao.jpg`: a legenda não pode cobrir a boca, cards ou sair da tela. No vertical, se estiver alta ou baixa demais, refaça com `--margem-v <px>` (maior = mais para cima).

`✅ Concluído: legenda pronta.`
