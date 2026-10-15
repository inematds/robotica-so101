# robotica-so101

Gêmeo de simulação do braço **SO-101** (kit Hiwonder SO-ARM101, LeRobot) e o caminho até o braço real.
É a continuação do [robotica-real2sim](https://github.com/inematds/robotica-real2sim), que faz o mesmo
com um Franka Panda simulado: foto da mesa → gêmeo MuJoCo → episódios → plano provado na física. Aqui
o gêmeo passa a ser o braço que vai estar na mesa de verdade.

**Estado (15/10/2026): começo da Fase 0.** O código em `real2sim/` foi copiado do projeto do Panda e ainda
não roda com o SO-101; a Fase 0 faz essa adaptação.

## Por que um projeto separado

O SO-101 é outra classe de braço: ~40 cm de alcance e 200 g de carga, contra ~85 cm e 3 kg do Panda.
Mudam o modelo, a cinemática (5 juntas em vez de 7), a garra, a mesa e os objetos. Separado, um não quebra
o outro.

## O braço

| Item | Valor |
|---|---|
| Kit | Hiwonder SO-ARM101: braço líder + seguidor, 12 servos |
| Servos | Hiwonder HX-30HM e HX-10HM, de barramento, 12 V (líder em 5 V) |
| Carga | 200 g |
| Alcance | 400 mm (fabricante); ~468 mm no modelo MuJoCo |
| Garra | abre até ~13 cm no modelo |
| Câmeras | pulso + externa |

## Roteiro

Plano completo em [docs/PLANO.md](docs/PLANO.md):

0. Gêmeo do SO-101 no simulador (sem o braço)
1. Mesa real medida com fita métrica (sem ligar motor)
2. Montar, ligar e calibrar
3. Comparar gêmeo e braço
4. Câmera dá a posição (marcadores ArUco)
5. Primeira prova física
6. Treino com LeRobot (dados reais + simulados)
7. Publicar

## Instalar

```bash
./instalar.sh          # venv com MuJoCo + modelo do SO-101 (MuJoCo Menagerie, Apache-2.0)
```

Licença: MIT (código). O modelo do SO-101 vem do MuJoCo Menagerie (Apache-2.0).
