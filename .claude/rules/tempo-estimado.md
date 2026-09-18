# Tempo estimado de cada operação

Use estas faixas no anúncio `🔍 Próximo passo: … Tempo estimado: …`. **D** = duração do vídeo (depois do corte, quando a etapa vem depois do corte). Some as etapas para o tempo total do `/video-editar`.

Medido em 2026-09-18 num PC com Ryzen 5 4600G (6 núcleos), 24 GB de RAM, sem placa de vídeo dedicada. Computadores mais fracos ou notebooks na bateria podem levar até o dobro.

| Operação | Tempo | Observação |
|---|---|---|
| Diagnóstico | cerca de 5 segundos | |
| Instalação do editor (bibliotecas, HyperFrames, ferramentas) | 3 a 8 minutos | depende da internet; só na primeira vez |
| Instalar programas do sistema (Python, Node, FFmpeg) | 5 a 15 minutos | winget no Windows, Homebrew no Mac |
| Transcrição via Groq | cerca de 10 segundos (vídeos até 10 min); cerca de 1 minuto por hora de vídeo | |
| Transcrição no computador (Whisper local) | cerca de 1× D; na 1ª vez + 3 a 10 minutos de download do modelo | |
| Transcrição via ElevenLabs | cerca de 20 a 60 segundos | |
| Análise de cor | cerca de 30 segundos | |
| Montar o rascunho do corte | cerca de 0,3× D + 10 segundos | |
| Corte final | cerca de 0,7× D + 5 segundos | 22 s de vídeo levaram 15 s |
| Formato horizontal sem zoom | cerca de 0,3× D | |
| Formato com zoom, vertical | cerca de 1× D | 14 s levaram 15 s |
| React (você + referência) | cerca de 1,2× D + 10 segundos | |
| Motion: montar e gerar a prévia dos cards | cerca de 20 a 40 segundos | |
| Motion: galeria de estilos | cerca de 30 a 60 segundos | |
| Motion: renderizar | cerca de 4× D | 14 s levaram 56 s |
| Galeria de legendas | cerca de 10 segundos | |
| Legenda | cerca de 0,5× D + 5 segundos | por formato |
| Salvar e verificar o vídeo final | cerca de 10 segundos | |
| Abrir o painel | cerca de 5 segundos | |
| Teste com o vídeo de exemplo | 2 a 4 minutos | |

Regra de unidade: até 120 segundos, fale em segundos ("cerca de 45 segundos"); acima, em minutos ("3 a 5 minutos"). Para vídeos longos, arredonde para cima.

Exemplo: vídeo de 5 min (D = 300 s, 4 min depois do corte), pacote completo, só horizontal:
transcrição 10 s + rascunho 1,5 min + corte 3,5 min + zoom 4 min + motion 16 min + legenda 2 min ≈ **27 a 30 minutos**.
