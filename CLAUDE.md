# CLAUDE.md — robotica-so101

Gêmeo de simulação do braço **Hiwonder SO-ARM101** (LeRobot) e o caminho até o braço real: foto da mesa →
cena MuJoCo com o SO-101 → gerador de movimento → prova na simulação → braço físico → treino LeRobot.
Um projeto por robô: o Franka Panda continua em `~/projetos/robotica-real2sim` (não mexer lá por causa deste).

- Roteiro: `docs/PLANO.md` (Fases 0–7, cada uma com critério `comando → saída esperada`). Estado: Fase 0.
- O código em `real2sim/` veio copiado do robotica-real2sim (15/10/2026) e **ainda está preso ao Panda**
  (juntas joint1–7, `tcp`, dedos, garra 0–255, alcance 0,25–0,80 m). A Fase 0 adapta tudo ao SO-101.
- Modelo: `vendor/menagerie/robotstudio_so101/so101.xml` (Menagerie, Apache-2.0; `./instalar.sh` baixa).
  Medido: alcance ~468 mm (o fabricante diz 400 mm: use o menor), garra abre até ~13 cm (8,6–9,0 cm a 1,0 rad),
  5 juntas no braço + garra, atuadores de posição com força máxima de 2,94 N·m.
- Kit real: servos Hiwonder HX-30HM/HX-10HM (não Feetech), carga 200 g, PLA, câmera no pulso + externa.
  **Líder em 5 V, seguidor em 12 V: trocar queima os servos.** Driver do LeRobot (`so101_follower`, Feetech)
  ainda não confirmado para os servos HX.
- Rodar: `./instalar.sh`; depois `./r2s.py <comando>`. Teste: `python3 testes/rodar.py`. Sempre `MUJOCO_GL=egl`.
- Visão e plano pela assinatura (Codex `gpt-6-astra`/`gpt-6-luna`, Claude). **Nunca** chamar API paga
  (Gemini, OpenRouter...) sem autorização explícita do dono.
- Nada vai ao braço real sem passar na prova da simulação no pior caso (`provar --pior-caso`).
- `vendor/` e `.venv/` não entram no git. Commits: autor `inematds <inematds@gmail.com>`.

## Self-learning

When I correct you, or you catch yourself making a mistake: before continuing, add the lesson as a one-line rule under ## Lessons, so it never happens again.

## Lessons

- (herdadas do robotica-real2sim, valem aqui) IK com atuador de posição: comando integrado com anti-windup; postura de descanso só no espaço nulo.
- Objeto alto: pegar no máximo 3 cm abaixo do topo. Cilindro × dedos: colisão como prisma convexo de 24 lados.
- Antes de culpar o controle, medir a força da garra. Torção baixa (`friction[1]` 0,02) deixa objeto girar entre os dedos; 0,06 resolveu.
- Câmera no pulso: o eixo -z da câmera é a direção de visão; conferir um quadro antes de filmar.
- Girar a garra em torno da vertical com o objeto na mão faz ele escorregar; inclinar demais deixa o pulso baixo e o braço não alcança.
- Contar "passa nos três modos" por script, com critério explícito (≥ 18/20 em cada modo).
