"""Movimentos simples do braço por juntas (pose de foto, casa, acenar, apontar) no gêmeo.

A pose de foto deita o braço de lado, rente à base, para a câmera de cima ver a mesa inteira.
"""
from __future__ import annotations

import mujoco
import numpy as np

from real2sim.robos import SO101

FOTO = (-1.6, -1.2, 1.0, 1.4, 0.0)
CASA = SO101.casa


def _ids(m):
    atu = [m.actuator(n).id for n in SO101.juntas]
    qadr = [m.jnt_qposadr[m.joint(n).id] for n in SO101.juntas]
    return atu, qadr, m.actuator(SO101.junta_garra).id


def ir_juntas(m, d, alvo, segundos: float = 1.5, garra: float | None = None, gravar=lambda: None) -> None:
    """Interpola o comando das juntas do ponto atual até `alvo` (perfil suave) e espera assentar."""
    atu, qadr, ag = _ids(m)
    q0 = np.array([d.ctrl[a] for a in atu])
    alvo = np.array(alvo, float)
    g0 = float(d.ctrl[ag])
    g1 = g0 if garra is None else garra
    dt = 0.02
    sub = int(dt / m.opt.timestep)
    n = max(int(segundos / dt), 1)
    for i in range(1, n + 1):
        s = i / n
        s = s * s * (3 - 2 * s)
        d.ctrl[atu] = q0 + (alvo - q0) * s
        d.ctrl[ag] = g0 + (g1 - g0) * s
        for _ in range(sub):
            mujoco.mj_step(m, d)
        gravar()
    for _ in range(10):
        for _ in range(sub):
            mujoco.mj_step(m, d)
        gravar()


def pose_foto(m, d, gravar=lambda: None, segundos: float = 1.2) -> None:
    ir_juntas(m, d, FOTO, segundos, SO101.garra_aberta, gravar)


def casa(m, d, gravar=lambda: None, segundos: float = 1.2) -> None:
    ir_juntas(m, d, CASA, segundos, SO101.garra_aberta, gravar)


def acenar(m, d, gravar=lambda: None, vezes: int = 2) -> None:
    """Braço para cima e pulso balançando: o 'tchau' do robô."""
    alto = np.array([0.0, -0.4, -0.6, 0.0, 0.0])
    ir_juntas(m, d, alto, 1.0, SO101.garra_aberta, gravar)
    for _ in range(vezes):
        for lado in (0.6, -0.6):
            q = alto.copy(); q[0] = lado * 0.5; q[3] = lado
            ir_juntas(m, d, q, 0.45, None, gravar)
    ir_juntas(m, d, alto, 0.4, None, gravar)


def bater_garra(m, d, gravar=lambda: None, vezes: int = 3) -> None:
    """Abre e fecha a garra rápido (comemoração)."""
    atu, _, ag = _ids(m)
    q = [d.ctrl[a] for a in atu]
    for _ in range(vezes):
        ir_juntas(m, d, q, 0.2, 0.2, gravar)
        ir_juntas(m, d, q, 0.2, SO101.garra_aberta, gravar)


def estado_inicial(m, d) -> None:
    """Braço em casa, física assentada."""
    from real2sim.gerador import ir_para_casa
    ir_para_casa(m, d)
    for _ in range(250):
        mujoco.mj_step(m, d)
