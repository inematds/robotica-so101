# Goal — exercícios do estande com o SO-101 (19/10/2026)

Pedido do Nei: repo de exercício com 3 atividades para o braço SO-101 do estande —
(1) descobrir algo e fazer (chamar atenção), (2) ordem de limpeza: o que está fora da caixa vai para a caixa,
(3) falar com ele e ele obedecer usando a visão. Implementar e colocar junto no projeto do robô do eventos.

Decisão de lugar: código em `robotica-so101/exercicios/` (um projeto por robô); página em `inemaeventos/robot/`.
Tudo roda no gêmeo (braço físico não chegou; driver dos servos HX ainda [confirmar]).

## Critérios de pronto (nível 3)

1. `python3 -m exercicios.medir_visao --n 20` → erro médio de posição (visão × física) < 5 mm, máx < 10 mm.
2. `./r2s.py descobrir --n 20` → ≥ 18/20 acha o intruso só pela imagem e o põe na caixa.
3. `./r2s.py arrumar --n 20` → ≥ 18/20 terminam com 0 objetos fora da caixa (conferido pela física).
4. `./r2s.py obedecer --teste` → ≥ 9/10 frases fixas com intenção e execução certas; frase desconhecida → "não entendi" e o braço não se mexe.
5. `python3 testes/rodar.py` → TUDO OK, incluindo os testes novos.
6. 3 MP4 em `resultados/exercicios/`.
7. Seção no guia/README + página `eventos.inema.pro/robot` PT/EN/ES, push nos dois repos.
