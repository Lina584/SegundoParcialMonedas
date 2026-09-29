"""
Simulador del ESP32 maestro publicando métricas por Wi-Fi/MQTT
================================================================
Hace las veces del ESP32 real mientras no hay hardware: en el proyecto
físico, el ESP32 leería el separador de monedas y publicaría estos
mismos datos por MQTT (Wi-Fi) hacia el dashboard. Este script genera
eventos de ejemplo (clasificación por denominación) y los publica en el
mismo tema que lee dashboard_streamlit.py, para demostrar el enlace
inalámbrico ESP32 -> Streamlit definido en la arquitectura del proyecto.

Cuando exista el ESP32 real, este script se reemplaza por el firmware
que publique el mismo JSON a este mismo tema MQTT.

Requisitos: pip install paho-mqtt
Ejecutar:   python simulador_esp32.py
"""
import json
import random
import time
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"   # broker público de pruebas (sin autenticación)
PUERTO = 1883
TEMA = "unimilitar/linamoreno/sistemamonedas/metricas"

TIPOS = [
    {"nombre": "$500", "valor": 500, "peso": 7.0},
    {"nombre": "$200", "valor": 200, "peso": 5.5},
    {"nombre": "$100", "valor": 100, "peso": 3.5},
]

cliente = mqtt.Client()
cliente.connect(BROKER, PUERTO, keepalive=60)
cliente.loop_start()

totales = {t["nombre"]: {"n": 0, "peso": 0.0, "valor": 0} for t in TIPOS}

print(f"[ESP32-sim] Publicando en {BROKER}:{PUERTO}  tema='{TEMA}'")
print("[ESP32-sim] Presiona Ctrl+C para detener.\n")

try:
    while True:
        tipo = random.choice(TIPOS)
        totales[tipo["nombre"]]["n"] += 1
        totales[tipo["nombre"]]["peso"] += tipo["peso"]
        totales[tipo["nombre"]]["valor"] += tipo["valor"]

        payload = {
            "evento": "moneda_clasificada",
            "denominacion": tipo["nombre"],
            "totales": totales,
            "timestamp": time.time(),
        }
        cliente.publish(TEMA, json.dumps(payload))
        print(f"[ESP32-sim] Publicado: {tipo['nombre']} -> {totales[tipo['nombre']]}")
        time.sleep(random.uniform(2.0, 4.0))
except KeyboardInterrupt:
    print("\n[ESP32-sim] Deteniendo simulador...")
    cliente.loop_stop()
    cliente.disconnect()
