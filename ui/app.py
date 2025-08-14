# ui/streamlit_app.py
"""
Interfaz Streamlit mínima:
- Lista scripts
- Muestra grafo de dependencias (NetworkX + matplotlib)
- Botones: Run script, Run all, Clear var
"""

import streamlit as st
from shared.registry import discover_scripts
from core.script_runner import ScriptRunner
from shared.shared_api import has_var
import networkx as nx
import matplotlib.pyplot as plt
import os

st.set_page_config(layout="wide", page_title="Orquestador Visual")

st.title("Orquestador de scripts (visual)")

registry = discover_scripts()
runner = ScriptRunner()

# --- Left panel: scripts list ---
st.sidebar.header("Scripts")
for path, meta in registry.items():
    st.sidebar.write(f"- {os.path.basename(path)}")
    st.sidebar.write(f"  Produces: {meta.get('produces')}")
    st.sidebar.write(f"  Requires: {meta.get('requires')}")

# --- Build dependency graph ---
G = nx.DiGraph()
for path, meta in registry.items():
    script_name = os.path.basename(path)
    G.add_node(script_name, path=path)
    for produced in meta.get("produces", []):
        G.add_node(produced)
        G.add_edge(script_name, produced)
    for req in meta.get("requires", []):
        G.add_node(req)
        G.add_edge(req, script_name)

# --- central UI ---
col1, col2 = st.columns([1,2])

with col1:
    st.subheader("Controles")
    selected = st.selectbox("Selecciona script", list(registry.keys()))
    if st.button("Run selected (background)"):
        st.write("Lanzando...")
        pid = runner.run_background(selected)
        st.write(f"PID: {pid}")

    var_to_wait = st.text_input("Run & wait for variable (ej: df_ventas)")
    if st.button("Run selected and wait for var"):
        if not var_to_wait:
            st.warning("Escribe nombre de variable")
        else:
            ok = runner.run_and_wait_for_var(selected, var_to_wait, timeout=60)
            st.write("OK" if ok else "Timeout/failure")

    if st.button("Run all (topo order)"):
        # topological order: run producers first
        try:
            order = list(nx.topological_sort(G))
        except Exception:
            order = list(registry.keys())
        # run scripts only (nodes that look like scripts)
        for node in order:
            candidate = os.path.join("scripts", node) if node.endswith(".py") else None
            if candidate and os.path.exists(candidate):
                st.write("Running", candidate)
                runner.run_background(candidate)

    st.subheader("Variables en memoria")
    # show variables (simple)
    try:
        from shared.memory_server import store  # only for quick debug; better use client
        vars_list = store.list_vars()
    except Exception:
        vars_list = []
    st.write(vars_list)

with col2:
    st.subheader("Grafo de dependencias")
    plt.figure(figsize=(8,6))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_size=1200, font_size=9)
    st.pyplot(plt)
