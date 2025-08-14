# scripts/script_b.py
"""
Script que requiere la variable 'df_initial' de otro script
para realizar un agrupamiento y generar un nuevo DataFrame.
"""
import pandas as pd

# ORCHESTRATOR.REQUIRES: df_initial

print("Procesando DataFrame 'df_initial'...")
print(f"DataFrame 'df_initial' recibido:\n{df_initial}")

# Realiza la operación de agrupamiento
df_grouped = df_initial.groupby('category')['total_value'].sum().reset_index()

print(f"DataFrame 'df_grouped' procesado:\n{df_grouped}")
# ORCHESTRATOR.PRODUCE: df_grouped