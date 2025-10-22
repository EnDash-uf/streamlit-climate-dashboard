from __future__ import annotations
import os, json
import pandas as pd, numpy as np
from pathlib import Path
def load_and_concat(dfs):
    if not dfs: return None
    df = pd.concat(dfs, ignore_index=True)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=False)
        df = df.dropna(subset=['timestamp']).sort_values('timestamp')
    return df
def clean_and_engineer(df: pd.DataFrame, units: dict) -> pd.DataFrame:
    df = df.drop_duplicates(subset=['timestamp']).copy()
    for col in ['air_temp_C','rh_percent','par_umol_m2_s','vpd_kPa']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['air_temp_C','rh_percent','vpd_kPa'])
    df = df.set_index('timestamp').sort_index()
    df = df.resample('1H').mean().interpolate(limit=2).reset_index()
    return df
def compute_kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty: return {}
    return {
        'air_temp_avg': float(df['air_temp_C'].mean()),
        'air_temp_day_max': float(df['air_temp_C'].rolling(24, min_periods=1).max().iloc[-1]),
        'rh_avg': float(df['rh_percent'].mean()),
        'vpd_avg': float(df['vpd_kPa'].mean()),
        'par_daily_mol': float((df['par_umol_m2_s'].fillna(0).sum() * 3600) / 1e6),
    }
def build_plotly_specs(df: pd.DataFrame) -> dict:
    import plotly.graph_objects as go
    figs = {}
    f1 = go.Figure(); f1.add_trace(go.Scatter(x=df['timestamp'], y=df['air_temp_C'], mode='lines', name='Air Temp (C)'))
    f1.update_layout(title='Air Temperature (C)', xaxis_title='Time', yaxis_title='°C', height=350)
    figs['air_temp'] = f1.to_plotly_json()
    f2 = go.Figure(); f2.add_trace(go.Scatter(x=df['timestamp'], y=df['rh_percent'], mode='lines', name='RH (%)'))
    f2.update_layout(title='Relative Humidity (%)', xaxis_title='Time', yaxis_title='%', height=350)
    figs['rh'] = f2.to_plotly_json()
    f3 = go.Figure(); f3.add_trace(go.Scatter(x=df['timestamp'], y=df['vpd_kPa'], mode='lines', name='VPD (kPa)'))
    f3.update_layout(title='VPD (kPa)', xaxis_title='Time', yaxis_title='kPa', height=350)
    figs['vpd'] = f3.to_plotly_json()
    return figs
def write_artifacts(email: str, df: pd.DataFrame, kpis: dict, figs: dict, base_dir: str):
    out = Path(base_dir) / email.replace('@','_at_'); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out/'processed_hourly.csv', index=False)
    (out/'kpis.json').write_text(json.dumps(kpis, indent=2))
    (out/'figures.json').write_text(json.dumps(figs))
    md = ['# Climate Report','','## Key Metrics',
          f"- Avg Air Temp: **{kpis.get('air_temp_avg',0):.2f} °C**",
          f"- 24h Max Air Temp: **{kpis.get('air_temp_day_max',0):.2f} °C**",
          f"- Avg RH: **{kpis.get('rh_avg',0):.1f} %**",
          f"- Avg VPD: **{kpis.get('vpd_avg',0):.2f} kPa**",
          f"- Cumulative PAR (approx): **{kpis.get('par_daily_mol',0):.2f} mol m⁻²**",
          '','## Notes','- MVP report generated from hourly-resampled data.']
    (out/'report.md').write_text('\n'.join(md), encoding='utf-8'); return str(out)
