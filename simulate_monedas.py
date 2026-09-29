"""
Simulación PyBullet - Sistema logístico de monedas inteligentes
==================================================================
Flujo completo (tramo 1 + separador + tramo 2 + recolección):
1. TRAMO 1: las monedas cruzan la banda recta una por una (despacio).
2. SEPARADOR MECÁNICO: al final del tramo 1, cada moneda se clasifica
   por denominación (500 / 200 / 100), pasa físicamente por el canal
   inclinado que le corresponde y cae dentro de SU vaso.
3. Cuando un vaso ya recibió todas sus monedas, ese vaso (con su carga)
   se traslada sobre el TRAMO 2 (la banda ancha) hasta el punto de
   recogida, al final de la banda.
4. Un único DRON recorre las 3 denominaciones una por una: espera en el
   punto de recogida hasta que el vaso llega, lo "recoge" (desaparece,
   como si lo hubiera cargado), esquiva los 3 obstáculos volando hasta
   SU meta, y regresa por la siguiente denominación.
5. El dashboard va mostrando conteo, peso y valor por denominación.

Requisitos: pip install pybullet
Ejecutar:   python simulate_monedas.py
"""

import pybullet as p
import pybullet_data
import time
import math

FABRICA_URDF = "fabrica_monedas.urdf"
ROBOT_URDF = "dron_recolector.urdf"
ALTURA_VUELO = 0.35   # altura a la que vuela el dron

# --------------------------------------------------------------------
# 1. BANDA RECTA (transporte inicial)
# --------------------------------------------------------------------
P_ENTRADA = (-1.0, 0.0, 0.62)
P_SALIDA = (1.0, 0.0, 0.62)

N_MONEDAS = 6                   # 2 de cada denominación
INTERVALO_ENTRE_MONEDAS = 1.5   # s entre que sale una moneda y la siguiente
DURACION_RECORRIDO = 7.0        # s que tarda una moneda en cruzar la banda

# --------------------------------------------------------------------
# 2. DENOMINACIONES Y SEPARADOR (el elemento diferencial del proyecto)
# --------------------------------------------------------------------
TIPOS = [
    {"nombre": "$500", "valor": 500, "peso": 7.0, "color": [1.0, 0.84, 0.0, 1]},   # dorada
    {"nombre": "$200", "valor": 200, "peso": 5.5, "color": [0.75, 0.75, 0.78, 1]},  # plateada
    {"nombre": "$100", "valor": 100, "peso": 3.5, "color": [0.72, 0.45, 0.20, 1]},  # cobre
]

# Posición de cada vaso (coincide con el separador y los vasos reales del
# URDF: x=1.6, y=-0.4/0/0.4). Las monedas caen aquí, encima del vaso.
Y_OFFSETS_CANAL = [-0.4, 0.0, 0.4]
P_VASO = [
    (1.6, Y_OFFSETS_CANAL[i], 0.72) for i in range(3)
]
# Compatibilidad con el resto del script (punto de clasificación = vaso)
P_CLASIFICACION = P_VASO
DURACION_CLASIFICACION = 1.3   # s que tarda la moneda en atravesar el separador hasta su vaso

# --------------------------------------------------------------------
# 2b. TRAMO 2: una vez el vaso tiene todas sus monedas, viaja sobre la
#     banda ancha (cinta_seg2, x entre 1.4 y 2.8) hasta el punto de
#     recogida, cerca del final de la banda.
# --------------------------------------------------------------------
MONEDAS_POR_VASO = 2   # N_MONEDAS / 3 denominaciones
P_RECOGIDA = [
    (2.7, Y_OFFSETS_CANAL[i], 0.68) for i in range(3)
]
DURACION_TRANSPORTE_VASO = 2.5   # s que tarda el vaso cargado en recorrer el tramo 2

# --------------------------------------------------------------------
# 3. CORREDOR COMPARTIDO CON 3 OBSTÁCULOS + 3 METAS (una por denominación)
# --------------------------------------------------------------------
META_CENTRAL = (4.5, -7.5, 0.06)
Y_OFFSETS_META = [-0.6, 0.0, 0.6]
METAS = [
    (META_CENTRAL[0], META_CENTRAL[1] + Y_OFFSETS_META[i], 0.06) for i in range(3)
]

RADIO_SEGURIDAD = 0.32
VELOCIDAD_ROBOT = 1.3
UMBRAL_LLEGADA = 0.15


def punto_en_linea(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# Los 3 obstáculos quedan fijos en el corredor central, entre el punto de
# recogida (final del tramo 2) y las metas; el único dron los cruza
# varias veces (una vez por cada denominación que transporta).
P_INICIO_CORREDOR = P_RECOGIDA[1]
OBSTACULOS = [
    {"pos": punto_en_linea(P_INICIO_CORREDOR, METAS[1], 0.28), "radio": 0.15},
    {"pos": punto_en_linea(P_INICIO_CORREDOR, METAS[1], 0.55), "radio": 0.15},
    {"pos": punto_en_linea(P_INICIO_CORREDOR, METAS[1], 0.80), "radio": 0.15},
]

# --------------------------------------------------------------------
# 4. RECORRIDO DEL ÚNICO DRON: recoger vaso 0 -> meta 0 -> recoger
#    vaso 1 -> meta 1 -> recoger vaso 2 -> meta 2 (uno a la vez), siempre
#    en el punto de recogida al final del tramo 2.
# --------------------------------------------------------------------
RECORRIDO = []
for idx in range(3):
    RECORRIDO.append({"accion": "recoger", "tipo": idx, "pos": P_RECOGIDA[idx]})
    RECORRIDO.append({"accion": "entregar", "tipo": idx, "pos": METAS[idx]})

# --------------------------------------------------------------------
# CONEXIÓN Y ESCENA
# --------------------------------------------------------------------
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.81)
p.setTimeStep(1.0 / 240.0)

p.loadURDF("plane.urdf")
p.loadURDF(FABRICA_URDF, basePosition=[0, 0, 0], useFixedBase=True)

# --- Un solo dron, arranca esperando en el punto de recogida del tramo 2 ---
inicio_robot = (P_RECOGIDA[0][0], P_RECOGIDA[0][1], ALTURA_VUELO)
robot_id = p.loadURDF(ROBOT_URDF, basePosition=list(inicio_robot), useFixedBase=False)
p.resetBasePositionAndOrientation(robot_id, list(inicio_robot), [0, 0, 0, 1])

robot_x, robot_y = inicio_robot[0], inicio_robot[1]

# --- Obstáculos ---
for obs in OBSTACULOS:
    col = p.createCollisionShape(p.GEOM_CYLINDER, radius=obs["radio"], height=0.3)
    vis = p.createVisualShape(p.GEOM_CYLINDER, radius=obs["radio"], length=0.3, rgbaColor=[0.85, 0.1, 0.1, 1])
    p.createMultiBody(baseMass=0, baseCollisionShapeIndex=col, baseVisualShapeIndex=vis,
                       basePosition=[obs["pos"][0], obs["pos"][1], 0.15])

# --- 3 metas, cada una con el color de su denominación ---
for i, tipo in enumerate(TIPOS):
    meta_vis = p.createVisualShape(p.GEOM_CYLINDER, radius=0.18, length=0.02,
                                    rgbaColor=tipo["color"][:3] + [0.6])
    p.createMultiBody(baseMass=0, baseVisualShapeIndex=meta_vis, basePosition=list(METAS[i]))

# --- Punto de recogida al final del tramo 2 (marcador de color por denominación) ---
for i, tipo in enumerate(TIPOS):
    recogida_vis = p.createVisualShape(p.GEOM_CYLINDER, radius=0.14, length=0.02, rgbaColor=tipo["color"][:3] + [0.5])
    p.createMultiBody(baseMass=0, baseVisualShapeIndex=recogida_vis, basePosition=list(P_RECOGIDA[i]))

print(f"[DEBUG] Salida banda={P_SALIDA[:2]}  Metas={[m[:2] for m in METAS]}")
for i, obs in enumerate(OBSTACULOS):
    print(f"[DEBUG] Obstáculo {i+1} en {obs['pos']}")

# --------------------------------------------------------------------
# MONEDAS (sin física, se animan a mano)
# --------------------------------------------------------------------
monedas = []
for i in range(N_MONEDAS):
    tipo_idx = i % 3
    color = TIPOS[tipo_idx]["color"]
    vis = p.createVisualShape(p.GEOM_CYLINDER, radius=0.06, length=0.02, rgbaColor=color)
    mid = p.createMultiBody(baseMass=0, baseVisualShapeIndex=vis, basePosition=list(P_ENTRADA))
    monedas.append({
        "id": mid, "tipo": tipo_idx, "recogida": False,
        "inicio_banda": None, "en_banda": True,
        "inicio_clasif": None, "clasificada": False,
    })

t_arranque = time.time()
contador = [{"n": 0, "peso": 0.0, "valor": 0} for _ in range(3)]

# --------------------------------------------------------------------
# VASOS: uno por denominación, VISIBLE desde el arranque, quieto en su
# puesto de clasificación (recibiendo las monedas que le van cayendo).
# En cuanto recibe todas sus monedas, ese mismo vaso se despega y se
# desliza sobre el tramo 2 hasta el punto de recogida, donde el dron
# lo espera.
# --------------------------------------------------------------------
vasos = []
for i, tipo in enumerate(TIPOS):
    vaso_vis = p.createVisualShape(p.GEOM_CYLINDER, radius=0.09, length=0.05, rgbaColor=tipo["color"])
    vid = p.createMultiBody(baseMass=0, baseVisualShapeIndex=vaso_vis, basePosition=list(P_VASO[i]))
    vasos.append({
        "id": vid, "salio": False, "en_transito": False,
        "inicio_transito": None, "lista": False, "en_dron": False,
    })

OFFSET_CARGA = (0.0, 0.0, -0.14)   # dónde cuelga el vaso debajo del dron

# --------------------------------------------------------------------
# NAVEGACIÓN (campo potencial: atrae al destino, repele de obstáculos)
# --------------------------------------------------------------------
def calcular_direccion(pos_robot, destino):
    gx, gy = destino[0] - pos_robot[0], destino[1] - pos_robot[1]
    dist = math.hypot(gx, gy)
    if dist > 1e-6:
        gx, gy = gx / dist, gy / dist
    rx, ry = 0.0, 0.0
    for obs in OBSTACULOS:
        ox, oy = pos_robot[0] - obs["pos"][0], pos_robot[1] - obs["pos"][1]
        d = math.hypot(ox, oy)
        if d < RADIO_SEGURIDAD and d > 1e-6:
            f = (RADIO_SEGURIDAD - d) / RADIO_SEGURIDAD
            rx += (ox / d) * f
            ry += (oy / d) * f
    dx, dy = gx + rx * 1.1, gy + ry * 1.1
    n = math.hypot(dx, dy)
    return (dx / n, dy / n, dist) if n > 1e-6 else (0, 0, dist)


# --------------------------------------------------------------------
# BUCLE PRINCIPAL
# --------------------------------------------------------------------
DT = 1.0 / 240.0
fase_robot = False
paso_actual = 0
mision_completa = False
print("Iniciando: las monedas van a cruzar la banda y clasificarse por denominación...")

while p.isConnected():
    ahora = time.time() - t_arranque

    for i, m in enumerate(monedas):
        tipo = TIPOS[m["tipo"]]

        # Fase 1: cruzando la banda recta
        if m["inicio_banda"] is None and ahora >= i * INTERVALO_ENTRE_MONEDAS:
            m["inicio_banda"] = ahora

        if m["inicio_banda"] is not None and m["en_banda"]:
            t = (ahora - m["inicio_banda"]) / DURACION_RECORRIDO
            if t >= 1.0:
                m["en_banda"] = False
                m["inicio_clasif"] = ahora
                p.resetBasePositionAndOrientation(m["id"], list(P_SALIDA), [0, 0, 0, 1])
            else:
                pos = punto_en_linea(P_ENTRADA, P_SALIDA, t) + (P_ENTRADA[2],)
                p.resetBasePositionAndOrientation(m["id"], list(pos), [0, 0, 0, 1])

        # Fase 2: desviándose hacia su canal de clasificación (según denominación)
        elif m["inicio_clasif"] is not None and not m["clasificada"]:
            t = (ahora - m["inicio_clasif"]) / DURACION_CLASIFICACION
            destino = P_CLASIFICACION[m["tipo"]]
            if t >= 1.0:
                p.resetBasePositionAndOrientation(m["id"], list(destino), [0, 0, 0, 1])
                m["clasificada"] = True
                c = contador[m["tipo"]]
                c["n"] += 1
                c["peso"] += tipo["peso"]
                c["valor"] += tipo["valor"]
                print(f"[DASHBOARD] Moneda {tipo['nombre']} clasificada -> "
                      f"canal {tipo['nombre']}: {c['n']} monedas, "
                      f"{c['peso']:.1f} g, ${c['valor']}")
            else:
                pos = punto_en_linea(P_SALIDA, destino, t) + (P_SALIDA[2],)
                p.resetBasePositionAndOrientation(m["id"], list(pos), [0, 0, 0, 1])

    todas_clasificadas = all(m["clasificada"] for m in monedas)
    if todas_clasificadas:
        fase_robot = True

    # --- Vasos: al completarse una denominación, el vaso sale cargado por
    #     el tramo 2 hacia el punto de recogida ---
    for i, vaso in enumerate(vasos):
        c = contador[i]
        if not vaso["salio"] and c["n"] >= MONEDAS_POR_VASO:
            vaso["salio"] = True
            vaso["en_transito"] = True
            vaso["inicio_transito"] = ahora
            p.resetBasePositionAndOrientation(vaso["id"], list(P_VASO[i]), [0, 0, 0, 1])
            print(f"[DASHBOARD] Vaso {TIPOS[i]['nombre']} completo, sale por el tramo 2 "
                  f"hacia el punto de recogida...")

        if vaso["en_transito"]:
            t = (ahora - vaso["inicio_transito"]) / DURACION_TRANSPORTE_VASO
            if t >= 1.0:
                p.resetBasePositionAndOrientation(vaso["id"], list(P_RECOGIDA[i]), [0, 0, 0, 1])
                vaso["en_transito"] = False
                vaso["lista"] = True
                print(f"[DASHBOARD] Vaso {TIPOS[i]['nombre']} llegó al punto de recogida.")
            else:
                pos = punto_en_linea(P_VASO[i], P_RECOGIDA[i], t) + (P_VASO[i][2],)
                p.resetBasePositionAndOrientation(vaso["id"], list(pos), [0, 0, 0, 1])

    # --- El único dron recorre vaso->meta->vaso->meta... en orden ---
    if fase_robot and not mision_completa:
        paso = RECORRIDO[paso_actual]
        dx, dy, dist = calcular_direccion((robot_x, robot_y, ALTURA_VUELO), paso["pos"])

        # Antes de "recoger", el dron espera a que el vaso de esa
        # denominación haya llegado al punto de recogida.
        esperando_vaso = paso["accion"] == "recoger" and not vasos[paso["tipo"]]["lista"]

        # Cámara: mientras el dron sólo está ESPERANDO un vaso (o toda la
        # banda sigue clasificando), usamos la vista amplia para que se
        # vea el vaso llegando al punto de recogida; solo cuando el dron
        # ya va volando de verdad usamos la cámara que lo sigue de cerca.
        if esperando_vaso:
            p.resetDebugVisualizerCamera(5.6, 50, -38, [1.4, 0.0, 0])
        else:
            p.resetDebugVisualizerCamera(4.5, 0, -89.9, [robot_x, robot_y, 0])

        if dist < UMBRAL_LLEGADA and not esperando_vaso:
            tipo = TIPOS[paso["tipo"]]
            if paso["accion"] == "recoger":
                # El dron engancha el vaso ya lleno: a partir de ahora el
                # vaso viaja pegado al dron (se ve lo que el dron se lleva).
                vasos[paso["tipo"]]["en_dron"] = True
                c = contador[paso["tipo"]]
                print(f"[DASHBOARD] Dron recoge el vaso {tipo['nombre']}: "
                      f"{c['n']} monedas, {c['peso']:.1f} g, ${c['valor']}")
            else:
                # Entrega: el vaso se suelta y queda depositado en la meta.
                vasos[paso["tipo"]]["en_dron"] = False
                p.resetBasePositionAndOrientation(vasos[paso["tipo"]]["id"], list(paso["pos"]), [0, 0, 0, 1])
                c = contador[paso["tipo"]]
                print(f"[DASHBOARD] Dron entrega en meta {tipo['nombre']}: "
                      f"{c['n']} monedas, {c['peso']:.1f} g, ${c['valor']}")

            paso_actual += 1
            if paso_actual >= len(RECORRIDO):
                mision_completa = True
                print("[DASHBOARD] Recorrido completo: las 3 denominaciones fueron "
                      "recogidas y entregadas en su meta.")
        elif not esperando_vaso:
            robot_x += dx * VELOCIDAD_ROBOT * DT
            robot_y += dy * VELOCIDAD_ROBOT * DT
            yaw = math.atan2(dy, dx)
            p.resetBasePositionAndOrientation(robot_id, [robot_x, robot_y, ALTURA_VUELO],
                                               p.getQuaternionFromEuler([0, 0, yaw]))
    else:
        # Vista amplia que cubre banda + separador + vasos + tramo 2
        p.resetDebugVisualizerCamera(5.2, 50, -40, [1.2, 0.0, 0])

    # --- El vaso enganchado (si hay uno) sigue al dron colgando debajo ---
    for vaso in vasos:
        if vaso["en_dron"]:
            pos_carga = (robot_x + OFFSET_CARGA[0], robot_y + OFFSET_CARGA[1], ALTURA_VUELO + OFFSET_CARGA[2])
            p.resetBasePositionAndOrientation(vaso["id"], list(pos_carga), [0, 0, 0, 1])

    p.stepSimulation()
    time.sleep(DT) 
