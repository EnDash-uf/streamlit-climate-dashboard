import streamlit as st, pathlib, re
from collections import Counter
st.set_page_config(page_title='Ask Your Data', page_icon='💬', layout='wide')
st.title('💬 Ask Your Data')
def user_dir_from_cookie(): return pathlib.Path('artifacts') / 'demo_at_client.com'
user_dir = user_dir_from_cookie(); report_path = user_dir / 'report.md'
if not report_path.exists():
    st.info('No report found. Go to the main page and run Sync first.'); st.stop()
report_text = report_path.read_text(encoding='utf-8')
q = st.text_input('Type a question about your latest report or climate trends:', placeholder='e.g., Why was VPD high yesterday?')
if st.button('Answer', type='primary'):
    if not q.strip(): st.warning('Please enter a question.')
    else:
        paras = [p.strip() for p in report_text.split('\n\n') if p.strip()]
        q_terms = re.findall(r'[A-Za-z0-9\.]+', q.lower())
        best, best_score = None, -1
        for p in paras:
            p_terms = re.findall(r'[A-Za-z0-9\.]+', p.lower())
            score = sum((Counter(q_terms) & Counter(p_terms)).values())
            if score > best_score: best_score, best = score, p
        st.subheader('Answer (from your report context)' if best else 'No direct match found')
        st.write(best or 'Try rephrasing, or regenerate the report with more details.')
