"""Streamlit entry point for the climate dashboard application."""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.auth import (
    create_user,
    default_settings,
    ensure_admin_exists,
    get_user,
    list_users,
    reset_password,
    update_user_settings,
    verify_password,
)
from utils.data_tools import (
    build_pdf,
    build_report_text,
    load_latest_dataset,
    save_uploaded_dataset,
    summarize_numeric_columns,
)


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Climate Control Dashboard", page_icon="🌱", layout="wide")
ensure_admin_exists()


def _reset_session() -> None:
    """Clear authentication state and refresh the application."""

    for key in ["auth_user", "auth_role"]:
        st.session_state.pop(key, None)
    st.experimental_rerun()


def login_view() -> None:
    """Render the login form when no authenticated user is present."""

    st.title("🌱 Climate Control Dashboard")
    st.write("Please sign in to access your personalised climate insights.")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="e.g. grower@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        user = get_user(username)
        if not user or not verify_password(password, user["password_hash"]):
            st.error("Invalid username or password. Please try again.")
            return

        st.session_state["auth_user"] = username
        st.session_state["auth_role"] = user.get("role", "user")
        st.success("Successfully signed in — loading your workspace…")
        st.experimental_rerun()

    st.info(
        "Accounts are managed by the administrator. Contact your admin if you "
        "need access or a password reset."
    )


def render_sidebar(username: str, role: str) -> str:
    """Show navigation and account information in the sidebar."""

    st.sidebar.header("Account")
    st.sidebar.success(f"Signed in as {username}")
    if st.sidebar.button("Log out", use_container_width=True):
        _reset_session()

    nav_items: List[str] = ["Dashboard", "Settings"]
    if role == "admin":
        nav_items.append("Admin")
    selection = st.sidebar.radio("Navigate", nav_items, label_visibility="collapsed")
    st.sidebar.caption("Need richer analytics or chat-based insights? They're on the roadmap!")
    return selection


def dashboard_view(username: str, role: str) -> None:
    """Main dashboard that handles uploads, previews, and visualisations."""

    st.title("📊 Climate Performance Overview")
    st.write(
        "Upload your latest climate CSV to generate a quick summary, review "
        "interactive charts, and download a shareable PDF report."
    )

    # --- Upload block -----------------------------------------------------
    st.subheader("1. Upload climate data")

    target_user = username
    if role == "admin":
        user_list = [user["username"] for user in list_users()]
        if user_list:
            default_index = user_list.index(username) if username in user_list else 0
            target_user = st.selectbox(
                "Manage data for user", options=user_list, index=default_index
            )
        else:
            st.info("No users available yet. Add a user from the Admin console.")
            return

    uploaded = st.file_uploader("Select a CSV file", type="csv", accept_multiple_files=False)
    if uploaded and st.button("Save dataset", type="primary", use_container_width=False):
        file_bytes = uploaded.getvalue()
        info = save_uploaded_dataset(target_user, uploaded.name, file_bytes)
        st.success(
            f"Stored {uploaded.name} for {target_user} with {info.rows} rows and {info.columns} columns."
        )
        st.experimental_rerun()

    # --- Load the most recent dataset ------------------------------------
    df, info = load_latest_dataset(target_user)
    if df is None:
        st.info("No data uploaded yet. Upload a CSV file to begin analysis.")
        return

    st.caption(
        f"Using dataset **{info.path.name}** uploaded on {info.uploaded_at:%Y-%m-%d %H:%M UTC}."
    )

    # --- Preview block ----------------------------------------------------
    st.subheader("2. Preview data")
    st.dataframe(df.head(50), use_container_width=True)

    # --- Summary block ----------------------------------------------------
    st.subheader("3. Summary statistics")
    summary = summarize_numeric_columns(df)
    if summary.empty:
        st.warning("No numeric columns found for statistical summary.")
    else:
        st.dataframe(summary, use_container_width=True)

    # --- Visualisation block ---------------------------------------------
    st.subheader("4. Visualise trends")
    x_axis = st.selectbox("Select the x-axis", options=list(df.columns), index=0)
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    if not numeric_columns:
        st.warning("No numeric columns available for plotting.")
    else:
        default_cols = numeric_columns[: min(len(numeric_columns), 3)]
        selected_cols = st.multiselect(
            "Choose one or more numeric columns to plot",
            options=numeric_columns,
            default=default_cols,
        )
        if selected_cols:
            for column in selected_cols:
                fig = px.line(df, x=x_axis, y=column, title=f"{column} over {x_axis}")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pick at least one column to generate charts.")

    # --- Reporting block --------------------------------------------------
    st.subheader("5. Download your report")
    user = get_user(target_user)
    settings = user.get("settings", default_settings()) if user else default_settings()
    report_text = build_report_text(df, settings)
    pdf_bytes = build_pdf(report_text, summary)

    st.download_button(
        "⬇️ Download PDF report",
        data=pdf_bytes,
        file_name="climate_report.pdf",
        mime="application/pdf",
    )
    with st.expander("View report details"):
        st.markdown(report_text)

    st.info(
        "Future updates will add anomaly detection, season-over-season comparisons, "
        "and conversational querying through Copilot or Zapier integrations."
    )


def settings_view(username: str) -> None:
    """Allow the current user to adjust personal settings."""

    st.title("⚙️ Personal settings")
    user = get_user(username)
    current_settings = user.get("settings", default_settings()) if user else default_settings()
    setpoints = current_settings.get("ideal_setpoints", {})

    with st.form("settings_form"):
        st.write("Update your preferred units and climate setpoints.")
        unit_preference = st.selectbox(
            "Unit preference",
            options=["metric", "imperial"],
            index=0 if current_settings.get("unit_preference", "metric") == "metric" else 1,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            temp = st.number_input(
                "Ideal temperature",
                value=float(setpoints.get("temperature", 22.0)),
                help="Specify the target canopy or air temperature.",
            )
        with col2:
            humidity = st.number_input(
                "Ideal humidity",
                value=float(setpoints.get("humidity", 55.0)),
                help="Relative humidity percentage.",
            )
        with col3:
            vpd = st.number_input(
                "Ideal VPD",
                value=float(setpoints.get("vpd", 0.8)),
                help="Vapour pressure deficit setpoint.",
            )

        submit = st.form_submit_button("Save settings", type="primary")

    if submit:
        new_settings = {
            "unit_preference": unit_preference,
            "ideal_setpoints": {
                "temperature": temp,
                "humidity": humidity,
                "vpd": vpd,
            },
        }
        update_user_settings(username, new_settings)
        st.success("Settings updated successfully.")

    st.info(
        "Settings are stored securely per user so each grower can tailor the "
        "dashboard to their own environment."
    )


def admin_view(current_username: str) -> None:
    """Administrative workspace for managing accounts and datasets."""

    st.title("🔐 Admin console")
    st.write("Add users, reset passwords, and manage stored datasets.")

    users = list(list_users())
    if users:
        st.subheader("Registered users")
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)
    else:
        st.info("No users found. Use the form below to create the first account.")

    with st.expander("Add a new user"):
        with st.form("create_user_form"):
            username = st.text_input("Username (email recommended)")
            name = st.text_input("Display name")
            password = st.text_input("Temporary password", type="password")
            role = st.selectbox("Role", options=["user", "admin"])
            submitted = st.form_submit_button("Create user", type="primary")

        if submitted:
            if not username or not password or not name:
                st.error("All fields are required to create a user.")
            else:
                try:
                    create_user(username, name, password, role=role)
                    st.success(f"Created user {username} with role {role}.")
                except ValueError as exc:
                    st.error(str(exc))

    with st.expander("Reset a user's password"):
        usernames = [user["username"] for user in users]
        if usernames:
            with st.form("reset_password_form"):
                target = st.selectbox("Select user", options=usernames)
                new_password = st.text_input("New password", type="password")
                submitted = st.form_submit_button("Reset password", type="primary")
            if submitted:
                if not new_password:
                    st.error("Please provide a new password.")
                else:
                    reset_password(target, new_password)
                    st.success(f"Password updated for {target}.")
        else:
            st.info("No users available for password reset.")

    with st.expander("Delete a user"):
        usernames = [user["username"] for user in users if user["username"] != current_username]
        if usernames:
            with st.form("delete_user_form"):
                target = st.selectbox("Select user to delete", options=usernames)
                confirm = st.checkbox(
                    "I understand this will remove all stored data for the user.", value=False
                )
                submitted = st.form_submit_button("Delete user", type="primary")
            if submitted:
                if not confirm:
                    st.error("Please confirm deletion to proceed.")
                else:
                    from utils.auth import delete_user

                    delete_user(target)
                    st.success(f"Removed user {target} and associated files.")
        else:
            st.info("No other users available to delete.")


def main() -> None:
    if "auth_user" not in st.session_state:
        login_view()
        return

    username = st.session_state["auth_user"]
    role = st.session_state.get("auth_role", "user")
    selection = render_sidebar(username, role)

    if selection == "Dashboard":
        dashboard_view(username, role)
    elif selection == "Settings":
        settings_view(username)
    elif selection == "Admin":
        if role != "admin":
            st.error("You do not have permission to view this page.")
            return
        admin_view(username)


if __name__ == "__main__":
    main()

