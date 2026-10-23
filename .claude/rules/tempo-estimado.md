# Tempo estimado de cada operação

Use estas faixas no anúncio `🔍 Próximo passo: … Tempo estimado: …`. **D** = duração do vídeo (depois do corte, quando a etapa vem depois do corte). Some as etapas para o tempo total do `/video-editar`.

Medido em 2026-09-18 num PC com Ryzen 5 4600G (6 núcleos), 24 GB de RAM, sem placa de vídeo dedicada. Computadores mais fracos ou notebooks na bateria podem levar até o dobro.

| Operação | Tempo | Observação |
|---|---|---|
| Diagnóstico | cerca de 5 segundos | |
| Instalação do editor (bibliotecas, HyperFrames, ferramentas) | 5 a 10 minutos | medido: 6 min 17 s numa instalação limpa; depende da internet; só na primeira vez |
| Instalar programas do sistema (Python, Node, FFmpeg) | 5 a 15 minutos | winget no Windows, Homebrew no Mac |
| Transcrição via Groq | cerca de 10 segundos (vídeos até 10 min); cerca de 1 minuto por hora de vídeo | |
| Transcrição no computador (Whisper local) | cerca de 1× D; na 1ª vez + 3 a 10 minutos de download do modelo | |
| Transcrição via ElevenLabs | cerca de 20 a 60 segundos | |
| Análise de cor | cerca de 30 segundos | |
| Montar o rascunho do corte (com os zooms) | cerca de 0,6× D + 10 segundos | medido: 45 s de bruto (28 s depois do corte) levaram 33 s |
| Atualizar o rascunho depois de desligar zooms | cerca de 0,3× D + 5 segundos | medido: 28 s levaram 9 s |
| Galeria de opções da legenda (`/configurar-legenda`) | cerca de 5 a 10 segundos | |
| Corte final | cerca de 0,7× D + 5 segundos | 22 s de vídeo levaram 15 s |
| Formato horizontal sem zoom | cerca de 0,3× D | |
| Formato com zoom, vertical | cerca de 1× D | 14 s levaram 15 s |
| Formato horizontal com desfoque (e zoom) | cerca de 0,8× D | medido: 16 s levaram 13 s; sem zoom e sem desfoque continua 0,3× D |
| React (você + referência) | cerca de 2× D + 10 segundos | medido: 14 s levaram 33 s |
| Motion: montar e gerar a prévia dos cards | cerca de 20 a 40 segundos | medido: montar 5 s + prévia 10 s |
| Motion: galeria de estilos | cerca de 30 a 60 segundos | medido: 29 s (estilos), 50 s (ícones) |
| Motion: renderizar | cerca de 4× D | 14 s levaram 56 s |
| Motion com pontilhismo ou estilo Cinema: renderizar | cerca de 4× D | medido em 2026-10-10: 12 s (vertical, 3 cards, um pontilhismo) levaram 42 s, noutro PC (com GTX 1660 SUPER); em PC sem placa de vídeo conte até 5× D |
| Galeria de legendas | cerca de 10 segundos | |
| Buscar imagens no Wikimedia Commons (8 opções) | cerca de 10 segundos | medido em 2026-10-14: 7 s; depende da internet |
| Personagem: 3 opções de imagem (HeyGen) | 2 a 4 minutos | medido em 2026-10-23: 1 imagem levou cerca de 3 min (as 3 são pedidas juntas) |
| Vídeo com personagem: gerar os blocos (HeyGen) | cerca de 10× D (os blocos são gerados juntos); mínimo de 2 a 3 minutos | medido em 2026-10-23: 13 s levaram 2 min 16 s; depende da fila da HeyGen |
| Vídeo com personagem: juntar os blocos | cerca de 0,3× D | estimado |
| Narração: amostras de voz (3 a 4 vozes) | cerca de 10 a 20 segundos | estimado, falta medir com a chave real |
| Narração: gravar a narração (voz de IA) | cerca de 10 a 30 segundos por minuto de fala | estimado, falta medir com a chave real |
| Narração: montar o fundo (por formato) | cerca de 5 a 10 segundos; vídeo longo: cerca de 0,3× D | medido: 18 s de vídeo levaram 7 s; 60 s com 3 capítulos (um fundo por capítulo) levaram 20 s |
| Música: 3 amostras de 15 segundos | cerca de 30 a 60 segundos | estimado, falta medir com a chave real |
| Música: compor no tamanho do vídeo | cerca de 20 a 60 segundos | estimado, falta medir com a chave real |
| Música: prévia ou salvar com música (por formato) | cerca de 5 a 10 segundos | medido: 16 s de vídeo levaram cerca de 3 s (o vídeo não é recodificado) |
| Narração num vídeo existente: juntar a voz com o vídeo | cerca de 0,5× D + 10 segundos | estimado, falta medir com a chave real (mais a gravação da narração acima) |
| Motion de vídeo narrado: renderizar | cerca de 3× D | medido: 18 s levaram 52 s (vertical) |
| Motion de vídeo longo (por capítulo): renderizar | cerca de 3× D na 1ª vez; depois, só os capítulos que mudaram (3× a duração deles) | medido em 2026-10-14: 60 s em 3 capítulos (horizontal, Cinema) levaram 2 min 45 s; refazer 2 dos 3 levou 2 min 9 s |
| Legenda | cerca de 0,5× D + 5 segundos | por formato; medido: 14 s levaram 11 a 15 s |
| Salvar e verificar o vídeo final | cerca de 10 segundos | |
| Abrir o painel | cerca de 5 segundos | |
| Teste com o vídeo de exemplo | 2 a 4 minutos | medido: 90 s (3 min na primeira vez, com o navegador frio) |
| Ajuste de cards (`/video-ajustar`: motion + legenda + salvar) | cerca de 5× D + 30 segundos | medido: 14 s levaram 2 min 15 s |

Regra de unidade: até 120 segundos, fale em segundos ("cerca de 45 segundos"); acima, em minutos ("3 a 5 minutos"). Para vídeos longos, arredonde para cima.

Exemplo: vídeo de 5 min (D = 300 s, 4 min depois do corte), pacote completo, só horizontal:
transcrição 10 s + rascunho 3 min + corte 3,5 min + zoom 4 min + motion 16 min + legenda 2 min ≈ **29 a 32 minutos**.
