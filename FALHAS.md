# FALHAS — robotica-so101

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-10-19 | exercícios: a bola vizinha rolava para fora da mesa (garra abrindo 11 cm ao pegar a peça ao lado) | abrir só largura + 3,5 cm; contar peças no início e no fim | prompt |
| 2026-10-19 | faster-whisper 1.2 quebrou com PyAV 19 (`metadata_errors`) | fixar `av<16` em requirements-voz.txt | infra |
| 2026-10-19 | visão: braço amarelo em casa tapava a mesa e virava "cubo amarelo"; amarelo real (60°) caía fora do raio de cor | pose de foto + área de trabalho; cor pelo matiz mais próximo | prompt |
| 2026-10-15 | `testes/rodar.py` ficou 27 min em CPU sem terminar (rodando junto com matriz_prova e filmar); a mesma suíte rodou de novo em 12 s, sem achar a causa | rodar os testes com `timeout` e `python -u` | infra |
| 2026-10-15 | 3 objetos na bandeja: o último batia na bola ou ficava em cima dela e contava como "dentro" | contornar objetos no caminho; "dentro" exige apoiado no fundo | prompt |
| 2026-10-15 | objetos sorteados encostados: a garra não entrava entre eles | sortear de novo se a folga < 1 cm | prompt |
| 2026-10-15 | braço parava longe do alvo com o punho no limite | junta no limite sai da IK; peso da inclinação 0,05 | prompt |
| 2026-10-15 | bola escorregava no transporte e o alvo subia junto | desvio ponta-objeto medido uma vez; pegar esfera 0,4 raio abaixo do centro | prompt |
| 2026-10-15 | braço do SO-101 oscilava (comando integrado herdado do Panda) | IK sobre a postura comandada, sem integrar o erro medido | prompt |
| 2026-10-15 | dedo fixo derrubava o cubo na descida | face do dedo fixo pelo casco convexo (−12 mm), não pela ponta | prompt |
