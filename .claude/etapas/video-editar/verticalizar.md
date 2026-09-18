# Etapa: versão vertical 9:16 (Reels, TikTok, Shorts)

Pré-requisito: corte final feito (`cortado.mp4`). Os zooms da edição dinâmica entram aqui também (mais suaves no vertical, para não perder nitidez).

## 1. Montar o recorte

`⏳ Passo 1/2: recortar o vídeo em pé, centralizado no seu rosto.` → `{PY} editor.py layout <id> vertical`

## 2. Conferir o enquadramento

`{PY} editor.py conferir-layout <id> vertical` → abra (Read) `vertical/conferencia.jpg` e confira: cabeça inteira, rosto centralizado nos 3 quadros. Se `layout.json` → `sem_rosto: true`, avise que não achei um rosto e que o recorte ficou no centro.

```
Assim fica a versão vertical (3 momentos do vídeo):
{caminho absoluto de conferencia.jpg}

1. Tudo certo
2. O rosto está cortado ou fora do centro

Digite o número:
```

2 → `Para que lado devo mover? 1. Mais para a esquerda / 2. Mais para a direita / 3. Acompanhar o meu movimento` → refaça com `--centro-x <x>` (some/subtraia ~150 px do centro atual; o centro atual está em `rosto.json` → `mediana.cx`) ou `--seguir sim` → confira de novo.

`✅ Concluído: versão vertical montada.`
