# Exercícios do estande com o SO-101

Três atividades para chamar a atenção de quem passa pelo estande. Nas três, o braço **vê a mesa por
uma câmera de cima** e decide sozinho o que fazer. Por enquanto tudo roda no gêmeo de simulação
(MuJoCo): o braço físico ainda não foi ligado (ver "Limites").

| # | Exercício | O que o público vê | Comando |
|---|---|---|---|
| 1 | **Descobrir o intruso** | Quatro peças na mesa, uma diferente (cor ou forma). O robô olha, diz qual é o intruso e por quê, guarda na caixa e comemora. | `./r2s.py descobrir` |
| 2 | **Ordem de limpeza** | Peças espalhadas. O robô guarda na caixa tudo que estiver fora dela, olha de novo depois de cada peça e só para com a mesa limpa. | `./r2s.py arrumar` |
| 3 | **Fale com o robô** | A pessoa pede ("pega o cubo vermelho", "cadê a bola azul?", "arruma a mesa", "dá tchau") e o robô acha a peça pela câmera e obedece. | `./r2s.py obedecer` |

## Resultados medidos (19/10/2026, sementes padrão)

| Medida | Resultado |
|---|---|
| Visão × física, 20 mesas (70 peças) | erro médio **1,1 mm**, máximo 2,1 mm; cor e forma 70/70; 0 perdidas, 0 inventadas |
| `descobrir -n 20` | **20/20** acharam o intruso só pela imagem e o guardaram na caixa |
| `arrumar -n 20` | **20/20** mesas limpas (3 ou 4 peças), conferido pela física; o robô disse a verdade em 20/20 |
| `obedecer --teste` | **11/11** frases entendidas e feitas, incluindo "cadê a bola laranja?" sem bola laranja na mesa (responde que não vê e não se mexe) e "faz um bolo de chocolate" (não entendi) |

| Ouvido (`python3 -m exercicios.testar_voz`): voz do Piper → Whisper local → frase | small **6–7/8**, medium 7/8; erram saudações curtas ("oi robô" → "pera robô"): aí o robô diz "não entendi" e fica parado |

Vídeos: `resultados/exercicios/*.mp4` (geral + o que a câmera vê no canto + a fala do robô na legenda).

## Rodar

```bash
./instalar.sh                         # uma vez (MuJoCo + modelo do SO-101)
./r2s.py visao -n 20                  # mede o erro da visão
./r2s.py descobrir -n 20              # taxa de acerto em 20 mesas sorteadas
./r2s.py arrumar -n 1 --video arrumar.mp4 --falar
./r2s.py obedecer --texto "o que você está vendo?" --texto "pega o cubo vermelho" --video conversa.mp4
./r2s.py obedecer --teste             # 11 frases fixas
./instalar.sh --voz                   # opcional: Whisper local para ouvir pelo microfone
./r2s.py obedecer --microfone --falar # fala com o robô; "tchau robô" encerra
./r2s.py obedecer --microfone --modelo-voz medium   # erra menos, ~3 s por frase
```

`--falar` usa a voz pt-BR do Piper (`~/.local/share/piper/pt_BR-faber-medium.onnx`), se existir.
Nada aqui chama API ou nuvem: visão, entendimento da frase, voz e Whisper rodam na máquina.

## Como funciona

1. **Pose de foto** (`braco.py`): o braço deita de lado, rente à base, e libera a vista da mesa.
2. **Visão** (`visao.py`): uma foto RGB da câmera de cima → pixels coloridos separados da mesa pela
   saturação → cor pelo matiz mais próximo → manchas → forma (cubo ou bola pela razão área/círculo) →
   posição: o raio da câmera corta a mesa na altura estimada da peça. A caixa é a mancha escura grande.
   Só olha dentro da área de trabalho (no estande, marcada com fita).
3. **Pegar guiado pela câmera** (`pegar.py`): o gerador de movimento do projeto pega onde a FOTO disse
   que a peça está, com o giro do cubo também medido na foto. Depois que os dois dedos seguram, a
   peça anda com a garra. A garra abre só o necessário (largura + 3,5 cm): aberta toda (11 cm), o dedo
   empurrava a bola vizinha para fora da mesa.
4. **Conferir pela câmera**: depois de cada peça o robô volta à pose de foto e olha de novo. Conta as
   peças no começo e no fim: se uma sumiu (caiu da mesa), ele avisa em vez de dizer "mesa limpa".
5. **Frase → ação** (`obedecer.py`): regras em português, instantâneas e sem internet. Frase que não casa
   com nada → "não entendi" e o braço fica parado.

A física do simulador entra em dois lugares só: sentir o contato dos dedos (no braço real: a corrente
ou a posição do servo da garra) e, no fim do teste, conferir de forma independente o que ficou na caixa.

## Montar no estande (quando o braço chegar)

- Mesa clara e fosca; caixa **preta** de ~17 × 12 × 3 cm à direita do braço; peças de 3–4 cm nas cores
  vermelho, laranja, amarelo, verde, azul e roxo (cubos de EVA e bolinhas de espuma: não rolam longe).
- Área de trabalho marcada com fita: de 15 a 28 cm da base do braço.
- Câmera USB fixa ~85 cm acima da mesa, olhando reto para baixo; calibrar com 4 marcas medidas com fita
  (`visao.CamReal`, arquivo `calibracao.json`).
- Antes de qualquer movimento real: regras de segurança do `docs/PLANO.md` (5 V no líder, 12 V no
  seguidor, mão na tomada, ninguém com a mão na área).

## Limites

- **Só simulação.** O braço físico ainda não foi ligado; o driver dos servos Hiwonder HX no LeRobot
  segue sem confirmação. `CamReal` está escrita mas não foi testada com câmera de verdade.
- Cores fora das seis da lista e objetos brancos, pretos ou cinza não são reconhecidos.
- Na mesa sorteada, "bola" e "pote" redondo parecem iguais vistos de cima; a visão chama tudo que é
  redondo de bola.
- Caixa com 4 vagas (2 × 2); a quinta peça iria no meio, por cima das outras.
