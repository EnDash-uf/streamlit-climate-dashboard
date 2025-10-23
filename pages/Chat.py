"""Placeholder for the future conversational assistant."""

import streamlit as st

st.set_page_config(page_title="Ask Your Data", page_icon="💬", layout="wide")

if "auth_user" not in st.session_state:
    st.error("Please sign in from the main application to access this page.")
    st.stop()

st.title("💬 Ask Your Data (coming soon)")
st.write(
    "This page is reserved for a future Copilot or Zapier-powered chatbot that "
    "will answer natural-language questions using the datasets stored in your account."
)

st.info(
    "Once the core workflow is validated we will integrate a conversational layer "
    "so growers can ask questions like 'Why did VPD spike yesterday?' or "
    "'Compare this week's PAR to last month'."
)

