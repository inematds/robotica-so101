"""Configuração do robô: tudo o que muda de um braço para outro fica aqui.

Hoje só existe o SO-101 (Hiwonder SO-ARM101 / LeRobot); o Panda continua no robotica-real2sim.
Medidas tiradas do modelo do Menagerie (vendor/menagerie/robotstudio_so101/so101.xml), 15/10/2026.

Referencial da ponta (site `gripperframe`): eixo x local = direção de aproximação (sai da garra),
eixo z local = direção em que a garra abre (o dedo móvel vai para +z, o dedo fixo fica em -z).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Robo:
    nome: str
    xml: Path
    juntas: tuple[str, ...]          # juntas do braço, na ordem dos atuadores
    junta_garra: str
    ponta: str                       # site da ponta da garra
    corpos_dedos: tuple[str, ...]    # corpos cujos geoms de colisão contam como "dedo"
    garra_aberta: float              # comando da garra (rad)
    garra_fechada: float
    casa: tuple[float, ...]          # postura de descanso das juntas do braço
    alcance: tuple[float, float]     # raio válido dos objetos na mesa (m)
    abertura_max: float              # maior objeto que a garra pega (m), com folga
    carga_max: float                 # kg
    dedo_fixo: float                 # face do dedo fixo, no eixo z local da ponta (m)
    folga_dedo: float                # distância deixada entre o dedo fixo e o objeto na descida (m)
    camera_pulso: str                # câmera do modelo que vira "pulso"
    altura_seg: float                # altura de segurança acima do objeto (m)
    vel: float                       # velocidade de cruzeiro da ponta (m/s)

    @property
    def n(self) -> int:
        return len(self.juntas)


SO101 = Robo(
    nome="so101",
    xml=RAIZ / "vendor/menagerie/robotstudio_so101/so101.xml",
    juntas=("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"),
    junta_garra="gripper",
    ponta="gripperframe",
    corpos_dedos=("gripper", "moving_jaw_so101_v1"),
    garra_aberta=1.5,      # vão de ~11 cm entre as pontas
    garra_fechada=-0.17,   # fechada além do contato: o servo aperta com a força máxima (2,94 N·m)
    casa=(0.0, -1.2, 1.0, 1.4, 0.0),
    alcance=(0.12, 0.38),  # o fabricante diz 400 mm; com a garra para baixo o útil vai a ~0,30
    abertura_max=0.09,
    carga_max=0.2,
    dedo_fixo=-0.012,      # face do dedo fixo pelo casco convexo da malha (a ponta fica em -0,019)
    folga_dedo=0.004,
    camera_pulso="wrist_cam",
    altura_seg=0.05,      # acima de ~8 cm de altura o pulso bate no limite com a garra para baixo
    vel=0.25,
)

ROBOS = {"so101": SO101}


def robo(nome: str = "so101") -> Robo:
    if nome not in ROBOS:
        raise ValueError(f"robô desconhecido: {nome} (conhecidos: {', '.join(ROBOS)})")
    return ROBOS[nome]


def casa(r: Robo = SO101) -> np.ndarray:
    return np.array(r.casa, dtype=float)
