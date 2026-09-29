"""
Dashboard Streamlit - Sistema logístico de monedas inteligentes
==================================================================
Primer avance del Objetivo 4: la aplicación web se comunica de forma
inalámbrica (Wi-Fi + MQTT) con el ESP32 y muestra en vivo el conteo,
peso y valor de las monedas procesadas, por denominación.

Mientras no hay ESP32 físico, corre junto con simulador_esp32.py, que
publica al mismo tema MQTT haciendo de "ESP32" de prueba. El día que
el ESP32 real publique al mismo tema, este dashboard no necesita
cambiar nada.

Requisitos: pip install streamlit paho-mqtt pandas
Ejecutar:   streamlit run dashboard_streamlit.py
(en otra terminal, al tiempo: python simulador_esp32.py)
"""
import json
import time

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PUERTO = 1883
TEMA = "unimilitar/linamoreno/sistemamonedas/metricas"

st.set_page_config(page_title="Sistema de monedas inteligentes", layout="wide")

# Estado compartido entre el hilo de MQTT (en segundo plano) y la interfaz
estado_compartido = {"ultimo": None}


def al_recibir(client, userdata, msg):
    try:
        estado_compartido["ultimo"] = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        pass


@st.cache_resource
def iniciar_mqtt():
    cliente = mqtt.Client()
    cliente.on_message = al_recibir
    cliente.connect(BROKER, PUERTO, keepalive=60)
    cliente.subscribe(TEMA)
    cliente.loop_start()
    return cliente


iniciar_mqtt()

st.title("Sistema logístico de monedas inteligentes")
st.caption(f"Conectado por Wi-Fi/MQTT al tema `{TEMA}` en `{BROKER}`")

placeholder = st.empty()

while True:
    datos = estado_compartido["ultimo"]

    with placeholder.container():
        if datos is None:
            st.info("Esperando datos del ESP32 (o del simulador)... "
                    "corre `python simulador_esp32.py` en otra terminal.")
        else:
            totales = datos["totales"]
            total_n = sum(t["n"] for t in totales.values())
            total_peso = sum(t["peso"] for t in totales.values())
            total_valor = sum(t["valor"] for t in totales.values())

            col1, col2, col3 = st.columns(3)
            col1.metric("Monedas procesadas", total_n)
            col2.metric("Peso total", f"{total_peso:.1f} g")
            col3.metric("Valor total", f"${total_valor:,}")

            st.subheader("Desglose por denominación")
            cols = st.columns(len(totales))
            for col, (nombre, datos_tipo) in zip(cols, totales.items()):
                with col:
                    st.metric(nombre, f"{datos_tipo['n']} monedas")
                    st.caption(f"{datos_tipo['peso']:.1f} g · ${datos_tipo['valor']:,}")

            df = pd.DataFrame(
                {"denominación": list(totales.keys()),
                 "cantidad": [t["n"] for t in totales.values()]}
            ).set_index("denominación")
            st.bar_chart(df)

            st.caption(f"Último evento: {datos['denominacion']} clasificada")

    time.sleep(1)
