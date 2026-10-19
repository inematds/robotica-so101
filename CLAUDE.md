# CLAUDE.md — robotica-so101

Gêmeo de simulação do braço **Hiwonder SO-ARM101** (LeRobot) e o caminho até o braço real: foto da mesa →
cena MuJoCo com o SO-101 → gerador de movimento → prova na simulação → braço físico → treino LeRobot.
Um projeto por robô: o Franka Panda continua em `~/projetos/robotica-real2sim` (não mexer lá por causa deste).

- Roteiro: `docs/PLANO.md` (Fases 0–7, cada uma com critério `comando → saída esperada`). Estado: Fase 0
  feita (15/10/2026); próxima: Fase 1 (mesa real medida com fita, sem ligar motor).
- Tudo que muda de robô fica em `real2sim/robos.py` (juntas, ponta `gripperframe`, garra em rad, casa,
  alcance 0,12–0,38 m, abertura 9 cm, carga 200 g). Cena de exemplo: `exemplos/mesa-so101/cena.json`.
- Ainda não existe para o SO-101: lata deitada (`--deitar` devolve falha explícita).
- Modelo: `vendor/menagerie/robotstudio_so101/so101.xml` (Menagerie, Apache-2.0; `./instalar.sh` baixa).
  Medido: alcance ~468 mm (o fabricante diz 400 mm: use o menor), garra abre até ~13 cm (8,6–9,0 cm a 1,0 rad),
  5 juntas no braço + garra, atuadores de posição com força máxima de 2,94 N·m.
- Kit real: servos Hiwonder HX-30HM/HX-10HM (não Feetech), carga 200 g, PLA, câmera no pulso + externa.
  **Líder em 5 V, seguidor em 12 V: trocar queima os servos.** Driver do LeRobot (`so101_follower`, Feetech)
  ainda não confirmado para os servos HX.
- Exercícios do estande (19/10/2026): `exercicios/` — descobrir o intruso, arrumar (ordem de limpeza),
  obedecer (frase/voz). Visão só por foto da câmera de cima; `./r2s.py descobrir|arrumar|obedecer|visao`.
  Detalhes e números em `exercicios/README.md`. Página: eventos.inema.pro/robot (seção do estande).
- Rodar: `./instalar.sh`; depois `./r2s.py <comando>`. Teste: `python3 testes/rodar.py`. Sempre `MUJOCO_GL=egl`.
- Visão e plano pela assinatura (Codex `gpt-6-astra`/`gpt-6-luna`, Claude). **Nunca** chamar API paga
  (Gemini, OpenRouter...) sem autorização explícita do dono.
- Nada vai ao braço real sem passar na prova da simulação no pior caso (`provar --pior-caso`).
- `vendor/` e `.venv/` não entram no git. Commits: autor `inematds <inematds@gmail.com>`.

## Self-learning

When I correct you, or you catch yourself making a mistake: before continuing, add the lesson as a one-line rule under ## Lessons, so it never happens again.

## Lessons

- Visão de cima: o braço em casa tapa a mesa e é amarelo; tirar a foto na pose de foto (`exercicios/braco.FOTO`) e só olhar dentro da área de trabalho.
- Cor por matiz MAIS PRÓXIMO (argmin), não por raio em volta de cada cor: o amarelo renderizado sai em 60°, longe do 47° chutado.
- Garra aberta toda (11 cm) empurra a peça vizinha e a bola rola para fora da mesa: abrir só largura + 3,5 cm.
- faster-whisper 1.2 quebra com PyAV 19 (`metadata_errors`): fixar `av<16` em requirements-voz.txt.

- (herdada do Panda, NÃO vale no SO-101) comando integrado com anti-windup: o servo do SO-101 é rígido (kp ~1000) e integrar o erro medido fazia o braço oscilar; a IK roda sobre a postura comandada.
- IK do SO-101: posição manda; inclinação da garra com peso 0,05 (cede quando não alcança), giro em torno do eixo da garra com peso 0,5; junta no limite sai do cálculo. Garra reto para baixo só até ~8 cm de altura a 15–30 cm da base.
- Garra do SO-101 é assimétrica: pegar com o objeto encostado no dedo fixo (casco convexo em −12 mm no eixo z da ponta); esfera pega 0,4 raio abaixo do centro, senão o dedo móvel empurra para baixo e ela escorrega.
- Transporte: medir o desvio ponta-objeto uma vez, com o objeto no ar (medir a cada passo puxa o alvo para cima quando ele escorrega); contornar objetos no caminho, não passar por cima.
- Variações de treino: sortear de novo quando objetos ficam encostados; "dentro do destino" exige apoiado no fundo (em cima de outro não conta).
- (herdadas do robotica-real2sim) Objeto alto: pegar no máximo 3 cm abaixo do topo. Cilindro × dedos: colisão como prisma convexo de 24 lados.
- Antes de culpar o controle, medir a força da garra. Torção baixa (`friction[1]` 0,02) deixa objeto girar entre os dedos; 0,06 resolveu.
- Câmera no pulso: o eixo -z da câmera é a direção de visão; conferir um quadro antes de filmar.
- Girar a garra em torno da vertical com o objeto na mão faz ele escorregar; inclinar demais deixa o pulso baixo e o braço não alcança.
- Contar "passa nos três modos" por script, com critério explícito (≥ 18/20 em cada modo).
