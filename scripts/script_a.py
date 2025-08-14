# scripts/script_a.py
"""
Script que crea un DataFrame inicial, realiza transformaciones básicas
y produce dos DataFrames: df_initial y df_final.
"""
import pandas as pd
import numpy as np

# --- Part 1: Create the Initial DataFrame (df_initial) and its Transformations ---

# Create some sample data for the initial DataFrame.
data = {
    'product_id': [101, 102, 103, 104, 105, 106, 107, 108],
    'product_name': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Webcam', 'Speaker', 'Headphones', 'Tablet'],
    'price_usd': [1200.50, 25.00, 75.99, 300.00, 45.50, 89.99, 150.00, 600.00],
    'stock_quantity': [50, 200, 150, 75, 100, 80, 120, 30],
    'category': ['Electronics', 'Electronics', 'Electronics', 'Electronics', 'Electronics', 'Electronics', 'Electronics', 'Electronics'],
    'last_updated': ['2023-01-15', '2023-01-16', '2023-01-15', '2023-01-17', '2023-01-16', '2023-01-18', '2023-01-17', '2023-01-18'],
    'is_active': [True, True, True, True, False, True, False, True]
}

df_initial = pd.DataFrame(data)

print("--- Initial DataFrame (df_initial) ---")
print(df_initial)
print("\n" + "="*50 + "\n")

# --- Initial Transformations for df_initial ---

df_initial['last_updated'] = pd.to_datetime(df_initial['last_updated'])
df_initial['tax_usd'] = df_initial['price_usd'] * 0.10
df_initial['total_value'] = df_initial['price_usd'] * df_initial['stock_quantity']

print("--- df_initial after Initial Transformations ---")
print(df_initial)
print("\n" + "="*50 + "\n")

# ORCHESTRATOR.PRODUCE: df_initial

# --- Part 2: Create the Final DataFrame (df_final) and its Transformations ---

df_final = df_initial.copy()
df_final = df_final[df_final['is_active'] == True]
df_final = df_final.drop(columns=['is_active', 'last_updated', 'tax_usd']).reset_index(drop=True)

def categorize_price(price):
    if price > 500:
        return 'High-end'
    elif price > 100:
        return 'Mid-range'
    else:
        return 'Low-end'

df_final['price_category'] = df_final['price_usd'].apply(categorize_price)
df_final = df_final.rename(columns={
    'product_name': 'Product',
    'price_usd': 'Price',
    'stock_quantity': 'Stock',
    'total_value': 'Total_Inventory_Value'
})

print("--- Final DataFrame (df_final) ---")
print(df_final)

# ORCHESTRATOR.PRODUCE: df_final