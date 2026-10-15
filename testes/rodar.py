#!/usr/bin/env python3
"""Testes do robotica-so101 (sem rede, sem Codex): `python3 testes/rodar.py` (~1 min)."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from real2sim.cena2mjcf import carregar_cena, compilar, validar_cena  # noqa: E402
from real2sim.episodios import gerar  # noqa: E402
from real2sim.foto2cena import extrair_json, para_referencial_do_robo  # noqa: E402
from real2sim.provar import distribuir_vagas, provar  # noqa: E402
from real2sim.robos import SO101  # noqa: E402

MESA = carregar_cena(RAIZ / "exemplos/mesa-so101/cena.json")
falhas = []


def caso(nome):
    def deco(f):
        try:
            f()
            print(f"ok    {nome}")
        except Exception as e:  # noqa: BLE001
            falhas.append(nome)
            print(f"FALHA {nome}: {e}")
        return f
    return deco


@caso("cena fora do alcance do SO-101 é recusada (longe e colada na base)")
def _():
    for pos in ([0.6, 0.0], [0.05, 0.0]):
        c = json.loads(json.dumps(MESA))
        c["objetos"][0]["pos"] = pos
        try:
            validar_cena(c)
        except ValueError:
            continue
        raise AssertionError(f"aceitou objeto em {pos}")


@caso("tarefa com objeto inexistente é recusada")
def _():
    c = json.loads(json.dumps(MESA))
    c["tarefa"]["pegar"] = "unicornio"
    try:
        validar_cena(c)
    except ValueError:
        return
    raise AssertionError("aceitou objeto inexistente")


@caso("a cena compila com o SO-101 (5 juntas + garra, ponta e câmera do pulso)")
def _():
    m, xml = compilar(MESA)
    assert m.nu == 6, m.nu
    assert "gripperframe" in xml
    for cam in ("geral", "cima", "frente", "pulso"):
        m.camera(cam)


@caso("garra para baixo alcança de 15 a 30 cm da base, a 1,5 cm da mesa")
def _():
    import mujoco
    from real2sim.gerador import Gerador, ir_para_casa, rot_garra
    m, _ = compilar(MESA)
    d = mujoco.MjData(m)
    for r in (0.15, 0.22, 0.30):
        ir_para_casa(m, d)
        g = Gerador(m, d, "cubo_vermelho", "bandeja")
        g.R_alvo = rot_garra(np.array([1.0, 0, 0]))
        alvo = np.array([r, 0, 0.015])
        for _ in range(300):
            q = g.ik(alvo)
            g.dk.qpos[g.qadr] = q
        import mujoco as mj
        mj.mj_kinematics(m, g.dk)
        erro = np.linalg.norm(g.dk.site_xpos[g.tcp] - alvo)
        ori = np.degrees(np.arccos(np.clip(-g.dk.site_xmat[g.tcp].reshape(3, 3)[2, 0], -1, 1)))
        assert erro < 0.002 and ori < 3, f"r={r}: erro {erro * 1000:.1f} mm, inclinação {ori:.1f} graus"


@caso("resposta do modelo de visão -> referencial do robô (cm -> m, dentro do alcance, carga)")
def _():
    bruta = extrair_json('lixo antes {"mesa":{"largura_cm":80,"profundidade_cm":50,"cor":"bege"},'
                         '"objetos":[{"nome":"cubo","tipo":"caixa","tamanho":[3,3,3],"pos_cm":[5,0],'
                         '"cor":"vermelho","massa_g":20},{"nome":"lata_cheia","tipo":"cilindro",'
                         '"tamanho":[6.6,12],"pos_cm":[25,10],"massa_g":370},{"nome":"bandeja","tipo":"recipiente",'
                         '"tamanho":[20,14,3],"pos_cm":[40,-30],"cor":"cinza"}],'
                         '"tarefa":{"pegar":"cubo","destino":"bandeja"}} lixo depois')
    cena, avisos = para_referencial_do_robo(bruta)
    validar_cena(cena)
    assert cena["objetos"][0]["tamanho"] == [0.03, 0.03, 0.03]
    assert cena["objetos"][0]["pos"][0] >= 0.15, "não empurrou o objeto da borda para o alcance"
    assert max(np.hypot(*o["pos"]) for o in cena["objetos"]) <= 0.38
    assert any("empurrada" in a for a in avisos)
    assert any("lata_cheia" in a and "carga" in a for a in avisos), avisos


@caso("tarefa com dois objetos no 'pegar' vira aviso, não derruba a cena")
def _():
    bruta = {"objetos": [{"nome": "bola", "tipo": "esfera", "tamanho": [6], "pos_cm": [22, 0]},
                         {"nome": "bandeja", "tipo": "recipiente", "tamanho": [20, 14, 3], "pos_cm": [16, -15]}],
             "tarefa": {"pegar": "lata, bola", "destino": "bandeja"}}
    cena, avisos = para_referencial_do_robo(bruta)
    validar_cena(cena)
    assert "pegar" not in cena["tarefa"] and cena["tarefa"]["destino"] == "bandeja"
    assert any("descartado" in a for a in avisos)


@caso("cada objeto da cena vai para a bandeja (5 variações cada)")
def _():
    for o in MESA["objetos"]:
        if o["tipo"] == "recipiente":
            continue
        r = provar(MESA, [{"pegar": o["nome"], "destino": "bandeja"}], n=5, log=lambda *a: None)
        assert r["planos_completos"] >= 4, f"{o['nome']}: {r['planos_completos']}/5"


@caso("episódios gravam série temporal (5 juntas + garra) e anotação em 4 níveis")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        r = gerar(MESA, tmp, 3, semente=1, imagens=True, log=lambda *a: None)
        assert r["episodios"] == 3
        z = np.load(Path(tmp) / "ep_0000.npz")
        assert z["qpos"].shape[1] == 6 and z["ctrl"].shape[1] == 6 and len(z["t"]) > 100
        assert z["img_pulso"].shape[1:] == (128, 128, 3)
        a = json.loads((Path(tmp) / "ep_0000.json").read_text())
        assert a["nivel_1_objetivo"]
        assert [s["subtarefa"] for s in a["nivel_2_subtarefas"]][:3] == ["pegar", "levar", "soltar"]
        assert len(a["nivel_2_subtarefas"][0]["primitivas"]) == 3
        assert a["qualidade"]["peso_no_treino"] in (0.0, 1.0)


@caso("vagas: três objetos no mesmo recipiente ganham lugares que não se sobrepõem")
def _():
    nomes = ["cubo_vermelho", "bola_tenis", "potinho_azul"]
    passos = distribuir_vagas(MESA, [{"pegar": n, "destino": "bandeja"} for n in nomes])
    x = [p["vaga"][0] for p in passos]
    larg = {"cubo_vermelho": 0.03 * 2 ** 0.5, "bola_tenis": 0.067, "potinho_azul": 0.04}
    for (a, xa), (b, xb) in zip(zip(nomes, x), list(zip(nomes, x))[1:]):
        assert xb - xa >= (larg[a] + larg[b]) / 2, (a, b, xa, xb)
    assert x[-1] + larg["potinho_azul"] / 2 <= 0.1 - 0.006


@caso("a prova na simulação separa o plano ruim do bom (sem vagas < com vagas)")
def _():
    passos = [{"pegar": "cubo_vermelho", "destino": "bandeja"},
              {"pegar": "potinho_azul", "destino": "bandeja"}]
    ruim = provar(MESA, passos, n=6, log=lambda *a: None)
    bom = provar(MESA, distribuir_vagas(MESA, passos), n=6, log=lambda *a: None)
    assert bom["planos_completos"] > ruim["planos_completos"], (ruim["planos_completos"], bom["planos_completos"])
    assert bom["planos_completos"] >= 5


@caso("plano com os três objetos na bandeja passa na prova (>= 8/10)")
def _():
    nomes = ["cubo_vermelho", "bola_tenis", "potinho_azul"]
    r = provar(MESA, distribuir_vagas(MESA, [{"pegar": n, "destino": "bandeja"} for n in nomes]),
               n=10, log=lambda *a: None)
    assert r["planos_completos"] >= 8, r["planos_completos"]


@caso("objeto em cima de outro na bandeja não conta como 'dentro'")
def _():
    from real2sim.provar import rodar_plano
    passos = [{"pegar": "cubo_vermelho", "destino": "bandeja"}, {"pegar": "potinho_azul", "destino": "bandeja"}]
    res = rodar_plano(MESA, passos, None)
    assert res[0]["sucesso"] and not res[-1]["sucesso"], res


@caso("erro de medida: pior caso encolhe o recipiente 15% e não passa da garra (9 cm)")
def _():
    from real2sim.episodios import variar
    c = json.loads(json.dumps(MESA))
    c["objetos"][1]["tamanho"] = [0.088]  # bola quase do tamanho da garra
    c = variar(c, np.random.default_rng(0), tamanho=0.15, pior_caso=True)
    t = {o["nome"]: o["tamanho"] for o in c["objetos"]}
    t0 = {o["nome"]: o["tamanho"] for o in MESA["objetos"]}
    assert abs(t["bandeja"][0] - 0.85 * t0["bandeja"][0]) < 1e-9
    assert t["cubo_vermelho"][0] > t0["cubo_vermelho"][0] and t["bola_tenis"][0] <= SO101.abertura_max + 1e-9


@caso("sorteio das variações não deixa objetos encostados")
def _():
    from real2sim.episodios import _longe, variar
    rng = np.random.default_rng(3)
    for _ in range(30):
        objs = variar(MESA, rng)["objetos"]
        for i, a in enumerate(objs):
            for b in objs[i + 1:]:
                assert _longe(a, b, 0.0), (a["nome"], b["nome"])


print()
LEROBOT = RAIZ / ".venv-lerobot/bin/python"
if not LEROBOT.exists():
    print("pulado exportar para o LeRobot (sem .venv-lerobot; ./instalar.sh --lerobot)")
else:
    @caso("episódios com câmeras -> dataset LeRobot que abre de volta")
    def _():
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            gerar(MESA, Path(tmp) / "eps", 2, imagens=True, log=lambda *_: None)
            r = subprocess.run([str(LEROBOT), "-m", "real2sim.exportar", f"{tmp}/eps", f"{tmp}/ds"],
                               cwd=RAIZ, capture_output=True, text=True, timeout=300)
            assert r.returncode == 0, r.stderr[-500:]
            linha = [x for x in r.stdout.splitlines() if x.startswith("conferido:")]
            assert linha and "'episodios': 2" in linha[0] and "'fps': 10" in linha[0], r.stdout[-500:]
            assert "observation.images.cima" in linha[0] and "(6,)" in linha[0]

print("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
sys.exit(1 if falhas else 0)
