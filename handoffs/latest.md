# Handoffs — trabalhos abertos

Cada linha é um assunto em andamento: leia o snapshot do assunto que for continuar. Gravado por handoff-grava.py.

<!-- handoff-indice:inicio -->
- `fase0-gemeo-so101` · handoffs/history/2026-10-15T204817Z-fase0-gemeo-so101.md · 15/10 17:48
<!-- handoff-indice:fim -->

---

Cópia integral do snapshot mais recente (handoffs/history/2026-10-15T204817Z-fase0-gemeo-so101.md):

# Handoff — 2026-10-15 — Fase 0: código adaptado ao SO-101, gerador funcionando (testes em execução)

## Projeto e escopo
robotica-so101, raiz ~/projetos/robotica-so101. O usuário pediu "faça todos os passos" da Fase 0 (handoff anterior): adaptar real2sim/ do Panda para o SO-101. Tudo local, sem API.

## Objetivo atual
Fase 0 de docs/PLANO.md. Critério: `python3 testes/rodar.py` → TUDO OK; `./r2s.py episodios exemplos/mesa-so101/cena.json /tmp/ep -n 50` → 45/50 ou mais.

## Estado aceito
- [confirmed] `real2sim/robos.py` novo: config do SO-101 (juntas, gripperframe, garra 1,5/−0,17 rad, casa, alcance 0,12–0,38, abertura 9 cm, carga 200 g, dedo_fixo −0,012, folga 0,004, altura_seg 0,05, vel 0,25)
- [confirmed] `real2sim/cena2mjcf.py`: carrega so101.xml, mesa menor, câmeras geral/cima/frente (helper `olhar`), wrist_cam → "pulso", validar_cena com alcance do robô
- [confirmed] `real2sim/gerador.py` reescrito: IK sobre postura comandada (cópia cinemática `dk`, sem integrar erro medido), pesos inclinação 0,05 / giro 0,5, junta no limite sai do cálculo, pegada encostada no dedo fixo, esfera 0,4 raio abaixo do centro, direção da pegada na média dos ângulos pega/destino, desvio ponta-objeto congelado após subir, sobe acima da borda antes de andar, pontos de desvio em volta de obstáculos, `dentro_do_destino` exige apoiado no fundo; `deitar` devolve falha explícita
- [confirmed] `episodios.py` (estado/ação 6 valores, sorteio sem objetos encostados), `provar.py` (prompt com 9 cm/200 g, vagas por largura de cada objeto), `foto2cena.py` (alcance 0,15–0,30, aviso de carga, mesa menor), `exportar.py` (nomes so101_follower `*.pos`, robot_type so101_follower), `ferramentas/matriz_prova.py` (cena mesa-so101, planos de 3 objetos)
- [confirmed] `exemplos/mesa-so101/cena.json`: cubo 3 cm, bola de tênis 6,7 cm, potinho 4×5 cm, bandeja 20×14×3 em (0,16, −0,15)
- [confirmed] 50 episódios: cubo 50/50, bola 50/50, potinho 50/50 (antes da mudança de `dentro_do_destino`)
- [confirmed] Vídeo `resultados/mesa-so101/tres-objetos.mp4`: plano de 3 objetos com sucesso
- [confirmed] `testes/rodar.py` reescrito para o SO-101 (14 casos); CLAUDE.md e README.md atualizados com estado e lições

## Proposto / tentado, não confirmado
- [?] `testes/rodar.py` ainda rodando no fim deste snapshot — conferir resultado
- [?] Matriz de prova (medida, ±15%, pior caso) rodando — conferir ≥18/20 por modo
- [unverified] 50 episódios depois da mudança de `dentro_do_destino` (apoiado no fundo) — rodar de novo

## Decisões e restrições
- Integrar erro medido (lição do Panda) não vale no SO-101: servo rígido, oscilava.
- Passar por cima da bola é inalcançável com garra para baixo: contornar.
- Lata deitada não portada para o SO-101 (adiado).
- docs/PLANO.md ainda não atualizado com o fim da Fase 0.

## Arquivos alterados
- `real2sim/robos.py` (novo), `real2sim/cena2mjcf.py`, `real2sim/gerador.py`, `real2sim/episodios.py`, `real2sim/provar.py`, `real2sim/foto2cena.py`, `real2sim/exportar.py`, `ferramentas/matriz_prova.py`, `testes/rodar.py`, `exemplos/mesa-so101/cena.json` (novo), `resultados/mesa-so101/` (novo), `CLAUDE.md`, `README.md` — nada disso commitado ainda
- Fora do projeto: nenhum

## Memória e regras duráveis tocadas
- `~/projetos/robotica-so101/CLAUDE.md` — estado da Fase 0 e 5 lições novas do SO-101 (IK, garra assimétrica, transporte, variações)

## Verificação
- Rodado: `./r2s.py episodios exemplos/mesa-so101/cena.json <scratch>/ep -n 50` → 50/50 (cubo); idem bola e potinho 50/50
- Rodado: plano 3 objetos com vagas, provar n=20 → 18/20; cubo+potinho sem vagas 0/6, com vagas 6/6
- Rodado: `./r2s.py filmar ... --plano resultados/mesa-so101/plano.json` → sucesso nos 3
- Não rodado ainda: `testes/rodar.py` completo (em execução), matriz_prova (em execução)

## Estado em execução
- Processos em segundo plano: `testes/rodar.py` (task bsoisqc9k) e `ferramentas/matriz_prova.py` (task bn038r4aw); terminam sozinhos
- Servidores / portas: nenhum
- Worktrees / branches abertos: nenhum

## Perguntas abertas e adiados
- Aberta: driver dos servos HX (Feetech?) — antes da Fase 2
- Adiado: lata deitada no SO-101; Fases 1–7

## Próxima ação exata
Ler o resultado dos testes e da matriz; corrigir falhas; rerodar 50 episódios; atualizar docs/PLANO.md (Fase 0 feita); commit (autor inematds) + push.

## Mapa de retomada
- `docs/PLANO.md` — roteiro e critério da Fase 0
- `real2sim/gerador.py` — o núcleo adaptado
- `real2sim/robos.py` — parâmetros do SO-101
- `testes/rodar.py` — critério
- `CLAUDE.md` — lições novas

## Checagem de compartilhamento
- Sem segredos, tokens, cookies, dados pessoais ou endpoints privados: sim
