import streamlit as st
import yaml, os, pandas as pd, json, pathlib
#from streamlit_authenticator import Authenticate, Hasher
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
from utils.apps_script_client import AppsScriptClient
from utils.processing import load_and_concat, clean_and_engineer, compute_kpis, build_plotly_specs, write_artifacts
import plotly.io as pio

st.set_page_config(page_title='Climate Dashboard', page_icon='🌱', layout='wide')

hashed = stauth.Hasher(["demo"]).generate()
authenticator = stauth.Authenticate(credentials, "grower_auth", "abcdef", cookie_expiry_days=30)
#hashed = Hasher(['demo']).generate()
credentials = {'usernames': {'demo@client.com': {'name': 'Demo Grower', 'password': hashed[0]}}}
#authenticator = Authenticate(credentials, 'grower_auth', 'abcdef', cookie_expiry_days=30)
name, auth_status, username = authenticator.login('sidebar')
if auth_status is False:
    st.error('Incorrect username or password'); st.stop()
elif auth_status is None:
    st.warning('Please enter your username and password'); st.stop()

st.sidebar.success(f'Logged in as {username}')
authenticator.logout('Logout', 'sidebar')

import yaml
with open('configs/clients.yaml','r') as f:
    clients_cfg = yaml.safe_load(f)
client = clients_cfg.get('clients',{}).get(username,None)
if not client:
    st.error('No configuration found for this user.'); st.stop()

st.title(f"🌱 Climate Dashboard — {client.get('display_name','Client')}")
colA, colB, colC = st.columns([2,1,1])
with colA:
    st.markdown('**Client Settings**')
    st.json({'drive_folder_id': client.get('drive_folder_id','(using local sample)'), 'units': client.get('units',{}), 'setpoints': client.get('setpoints',{})})
with colB:
    run_ingest = st.button('🔄 Sync via Apps Script', type='primary', use_container_width=True)
with colC:
    use_local = st.toggle('Use local sample data', value=(not bool(client.get('drive_folder_id'))))

dfs = []
if run_ingest:
    if use_local or not client.get('drive_folder_id'):
        st.info('Using local sample_data file (no Drive folder configured).')
        df_local = pd.read_csv('sample_data/climate_sample.csv'); dfs.append(df_local)
    else:
        cfg = st.secrets.get('apps_script', {})
        web_url = cfg.get('web_app_url',''); secret = cfg.get('secret','')
        if not web_url or not secret:
            st.error('Missing apps_script.web_app_url or apps_script.secret in secrets.'); st.stop()
        try:
            as_client = AppsScriptClient(web_url, secret)
            try:
                meta = as_client.fetch_latest_meta()
                st.caption(f"Newest file: {meta.get('name','?')} (modified {meta.get('modifiedTime','?')})")
            except Exception as meta_err:
                st.warning(f'Could not fetch file metadata: {meta_err}')
            df_i = as_client.fetch_latest_csv()
            if df_i is None or df_i.empty: st.warning('Apps Script returned no data.')
            else: dfs.append(df_i); st.success(f'Fetched {len[df_i]} row(s) from Apps Script')
        except Exception as ex:
            st.error(f'Failed to fetch from Apps Script: {ex}')

    if not dfs: st.stop()
    st.info('Processing data...')
    df_raw = load_and_concat(dfs)
    df = clean_and_engineer(df_raw, client.get('units',{}))
    kpis = compute_kpis(df)
    figs = build_plotly_specs(df)
    out_dir = write_artifacts(username, df, kpis, figs, base_dir='artifacts')
    st.success(f'Artifacts updated at: {out_dir}')

user_dir = pathlib.Path('artifacts') / username.replace('@','_at_')
kpi_path = user_dir/'kpis.json'; fig_path = user_dir/'figures.json'; report_path = user_dir/'report.md'; df_path = user_dir/'processed_hourly.csv'

st.header('📊 Report')
if kpi_path.exists() and fig_path.exists():
    kpis = json.loads(kpi_path.read_text()); figs = json.loads(fig_path.read_text())
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric('Avg Air Temp (°C)', f"{kpis.get('air_temp_avg',0):.2f}")
    c2.metric('24h Max Temp (°C)', f"{kpis.get('air_temp_day_max',0):.2f}")
    c3.metric('Avg RH (%)', f"{kpis.get('rh_avg',0):.1f}")
    c4.metric('Avg VPD (kPa)', f"{kpis.get('vpd_avg',0):.2f}")
    c5.metric('Cum. PAR (mol m⁻²)', f"{kpis.get('par_daily_mol',0):.2f}")
    st.plotly_chart(pio.from_json(figs['air_temp']), use_container_width=True)
    st.plotly_chart(pio.from_json(figs['rh']), use_container_width=True)
    st.plotly_chart(pio.from_json(figs['vpd']), use_container_width=True)
else:
    st.info('No artifacts yet. Click **Sync via Apps Script** to create them.')

st.header('📄 Report Text')
if report_path.exists(): st.markdown(report_path.read_text())
else: st.write('No report generated yet.')

st.header('🧪 Data Preview')
if df_path.exists(): st.dataframe(pd.read_csv(df_path).head(50), use_container_width=True, hide_index=True)
