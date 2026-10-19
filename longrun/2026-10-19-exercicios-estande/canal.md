# Canal — exercicios-estande (só acrescentar; nunca reescrever)

Conhecimento do projeto que a compactação perde: fatos descobertos, aprendizados, glossário, armadilhas, onde estão as coisas.
Não é estado da tarefa (isso vai em state/plan/progress). Preencha cedo — o hook avisa na faixa 1 (~50% do contexto).

Formato: `- AAAA-MM-DD HH:MM · fato|aprendizado|glossário|armadilha · texto`


## 19/10/2026 — registro do que se aprendeu
- Onde: `exercicios/` (visao, braco, mesa, pegar, atividades, obedecer, rodar, voz, testar_voz, medir_visao). CLI no `r2s.py`.
- Câmera `cima` (0,85 m, reta para baixo); imagem: coluna → -y do mundo, linha para cima → +x. Pose de foto `braco.FOTO` deita o braço em x < 0,1.
- Luz da cena original estoura a câmera: `mesa.montar(luz=0.6)`. Caixa preta: v<0,42 & s<0,25 dentro da área de trabalho.
- `GeradorVisao`: posição/largura/giro da foto; segurando (2 dedos) → objeto = ponta + desvio. `dentro_do_destino` usa a física só para medir.
- Armadilha: `pkill -f` dentro do mesmo bash matou o shell; usar PID. Screenshot: chrome --headless travou; usar playwright de ~/projetos/agent-browser/node_modules.
- Tradução: `~/projetos/wifi/scripts/inema-traduz` (Sonnet assinatura). Eventos: editar PT → scripts/translate.py --lang en|es → npm run build:i18n → npm test.
