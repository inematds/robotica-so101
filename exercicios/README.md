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

## Lista do que precisamos ter no estande

Marque cada item antes do evento. As medidas são as que o software espera hoje; se algo for diferente
(caixa de outro tamanho, outra cor de peça), ajuste em "Opções de configuração", logo abaixo.

**Braço e energia**

- [ ] Kit Hiwonder SO-ARM101: braço líder + seguidor + placa BusLinker V3.0 (cabo USB para dados).
- [ ] Fonte de **12 V** para o seguidor e fonte de **5 V** para o líder, **etiquetadas**: trocar as duas queima
      os servos (`docs/PLANO.md`).
- [ ] Régua de tomadas com interruptor, ao alcance da mão: desligar os 12 V é a parada de emergência.
- [ ] Grampo (sargento) para prender a base do braço na mesa.

**Mesa e peças**

- [ ] Tampo **claro e fosco** (branco ou cinza claro, sem brilho), uns 60 × 70 cm. Mesa escura ou com
      desenho confunde a visão.
- [ ] Caixa **preta e fosca** de ~17 × 12 × 3 cm (borda baixa), à direita do braço. O robô reconhece a caixa
      por ser a mancha escura grande.
- [ ] Peças nas 6 cores (vermelho, laranja, amarelo, verde, azul, roxo): cubos de EVA de **3 cm** e bolinhas
      de espuma de **4 cm**. Para montar mesas com intruso e com repetição: **2 cubos e 2 bolas de cada cor
      (24 peças)**, mais algumas de reserva. Nada branco, preto ou cinza: a visão não vê essas cores. Peso
      bem abaixo de 200 g (carga do braço).
- [ ] Fita crepe colorida para marcar a área de trabalho (de 15 a 28 cm da base) e 4 marcas de calibração,
      mais uma trena.

**Câmera, luz e computador**

- [ ] Câmera USB (a externa do kit serve) presa num suporte ou tripé com braço, **~85 cm acima da mesa,
      olhando reto para baixo**.
- [ ] Luz difusa e constante sobre a mesa (luminária ou painel de LED). Sem sol direto: sombra e reflexo
      mudam a cor das peças.
- [ ] Computador com Linux. Para rodar o simulador e gravar vídeo é preciso placa de vídeo (EGL); sem
      ela, use `MUJOCO_GL=osmesa`, que é bem mais lento.
- [ ] Monitor ou TV virado para o público, mostrando o que a câmera vê.

**Voz (só para "Fale com o robô")**

- [ ] Microfone USB de mesa ou de lapela. O estande é barulhento: microfone perto da boca erra menos.
      Sem microfone, o monitor do estande digita a frase (`--texto`).
- [ ] Caixa de som pequena, para o robô responder falando (Piper).

**Software (uma vez, antes do evento)**

- [ ] `./instalar.sh` (MuJoCo + modelo do SO-101).
- [ ] `./instalar.sh --voz` (Whisper local) e `sudo apt install alsa-utils ffmpeg` (`arecord`, `aplay`, câmera).
- [ ] Piper + voz `pt_BR-faber-medium.onnx` em `~/.local/share/piper/`.
- [ ] Baixar o modelo do Whisper antes (rodar `./r2s.py obedecer --microfone` uma vez com internet): no
      estande ele roda sem rede.
- [ ] Ensaiar: `./r2s.py obedecer --teste` deve dar 11/11 e `./r2s.py visao -n 5` deve mostrar erro de poucos mm.

## Opções de configuração

### Na linha de comando

| Opção | Em quais comandos | O que faz | Padrão |
|---|---|---|---|
| `-n N` | todos | quantas mesas sorteadas rodar | 20 |
| `--semente S` | todos | muda o sorteio das mesas (a mesma semente repete a mesma mesa) | 0 |
| `--video arq.mp4` | descobrir, arrumar, obedecer | grava a 1ª mesa: câmera geral + o que a visão vê no canto + a fala na legenda | não grava |
| `--falar` | descobrir, arrumar, obedecer | o robô fala em voz alta (Piper) | só escreve |
| `--relatorio arq.json` | descobrir, arrumar, obedecer | salva o resultado de cada mesa em JSON | não salva |
| `--texto "frase"` | obedecer | frase digitada (pode repetir a opção) | — |
| `--microfone` | obedecer | ouve pelo microfone até ouvir "tchau robô" | — |
| `--segundos 4` | obedecer | quanto tempo grava cada frase | 4 |
| `--modelo-voz small\|medium` | obedecer | `small` responde mais rápido; `medium` erra menos (~3 s por frase) | small |
| `--teste` | obedecer | as 11 frases fixas, cada uma numa mesa nova | — |
| `--foto arq.png` | visao | salva a 1ª foto com o que a visão achou desenhado | — |

### Variáveis de ambiente

| Variável | Para quê | Padrão |
|---|---|---|
| `MUJOCO_GL` | desenho do simulador: `egl` (placa de vídeo) ou `osmesa` (sem placa, lento) | `egl` |
| `PIPER_VOZ` | caminho de outra voz do Piper | `~/.local/share/piper/pt_BR-faber-medium.onnx` |

### No código (para adaptar à mesa real)

| O quê | Onde | Valor hoje | Quando mudar |
|---|---|---|---|
| Tamanho e posição da caixa | `mesa.py` → `CAIXA` | 17 × 12 × 3 cm em (17 cm; −17 cm) | caixa de outro tamanho ou lugar |
| Tamanho das peças | `mesa.py` → `PECAS` | cubo 3 cm, bola 4 cm | peças de outro tamanho |
| Cores usadas no sorteio | `mesa.py` → `CORES` | as 6 cores | faltou alguma cor de peça |
| Área onde as peças aparecem | `mesa.py` → `lugares()` | 15 a 28 cm da base, 7 cm entre peças | mesa maior ou menor |
| Cor de cada peça (matiz) | `visao.py` → `MATIZ` | vermelho 3°, laranja 32°, amarelo 57°, verde 128°, azul 222°, roxo 275° | calibrar com as peças de verdade |
| Área de trabalho vista pela câmera | `visao.py` → `AREA` | x de 0 a 46 cm, y de −34 a 34 cm | para a câmera não ver o chão ou a parede |
| Quando um pixel é "colorido" | `visao.py` → `mascaras()` | saturação > 0,4 | luz fraca ou peças mais claras |
| Quando é a caixa preta | `visao.py` → `mascaras()` | brilho < 0,42 e saturação < 0,25 | caixa de outra cor ou luz diferente |
| Bola × cubo | `visao.py` → `forma_e_giro()` | redondo se área/círculo > 0,8 | peças de outro formato |
| Faixa onde o braço deitado fica | `visao.py` → `perceber(x_min=0.10)` | 10 cm | outra pose de foto |
| Pose de foto do braço | `braco.py` → `FOTO` | (−1,6; −1,2; 1,0; 1,4; 0,0) rad | o braço aparece na foto |
| Frases que o robô entende | `obedecer.py` → `ACOES`, `CORES`, `FORMAS` | regras em português | ensinar palavra nova ("pegue", "bolinha"…) |
| Vocabulário para o Whisper | `voz.py` → `DICA` | frases do estande | o Whisper troca palavras do pedido |
| Câmera real | `calibracao.json` (ver `visao.CamReal`) | `/dev/video0`, 640 × 480, 85 cm, 4 marcas medidas com fita | ao montar a câmera |

`calibracao.json` de exemplo (cada ponto: pixel na foto `u, v` e posição na mesa `x, y` em metros, medida
com fita a partir da base do braço):

```json
{"dispositivo": "/dev/video0", "largura": 640, "altura": 480, "altura_camera": 0.85,
 "pontos": [[102, 88, 0.40, 0.25], [530, 92, 0.40, -0.25], [520, 400, 0.10, -0.25], [110, 395, 0.10, 0.25]]}
```

Os comandos ainda não têm uma opção para usar a câmera real: `CamReal` está escrita, mas só entra quando
o braço chegar e a calibração for testada.

## Montar no estande (quando o braço chegar)

1. Prender o braço com o grampo e colar a fita da área de trabalho (15 a 28 cm da base) e as 4 marcas.
2. Caixa preta à direita do braço, na posição de `CAIXA` (ou mudar `CAIXA` para onde ela ficou).
3. Câmera a ~85 cm, reta para baixo; anotar o pixel de cada marca e montar o `calibracao.json`.
4. Conferir as cores com uma foto das peças de verdade (quando `CamReal` estiver ligada aos comandos);
   se uma cor errar, ajustar `MATIZ`.
5. Antes de qualquer movimento real: regras de segurança do `docs/PLANO.md` (5 V no líder, 12 V no
   seguidor, mão na tomada, ninguém com a mão na área).

## Limites

- **Só simulação.** O braço físico ainda não foi ligado; o driver dos servos Hiwonder HX no LeRobot
  segue sem confirmação. `CamReal` está escrita mas não foi testada com câmera de verdade.
- Cores fora das seis da lista e objetos brancos, pretos ou cinza não são reconhecidos.
- Na mesa sorteada, "bola" e "pote" redondo parecem iguais vistos de cima; a visão chama tudo que é
  redondo de bola.
- Caixa com 4 vagas (2 × 2); a quinta peça iria no meio, por cima das outras.
