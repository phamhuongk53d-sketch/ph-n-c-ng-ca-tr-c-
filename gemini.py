import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(page_title="Lịch trực ca – FINAL", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"

REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    return ["T2","T3","T4","T5","T6","T7","CN"][d.weekday()] + " - " + d.strftime("%d/%m/%Y")

def ensure_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

def parse_date(df):
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Ngày"])

# ==================================================
# ĐỌC DATA_LOG
# ==================================================
try:
    df_log = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
except:
    df_log = pd.DataFrame()

df_log = ensure_df(df_log)
df_log = parse_date(df_log)
df_log["Giờ"] = pd.to_numeric(df_log["Giờ"], errors="coerce").fillna(0)

today = datetime.now().date()
current_year = today.year
current_month = today.month

# ==================================================
# TÍNH GIỜ THÁNG / NĂM
# ==================================================
def calculate_hours(df):
    df = df[df["Ngày"].dt.date <= today].copy()

    df["Năm"] = df["Ngày"].dt.year
    df["Tháng"] = df["Ngày"].dt.month

    # Giờ tháng hiện tại
    df_month = df[
        (df["Năm"] == current_year) &
        (df["Tháng"] == current_month)
    ].groupby("Nhân viên")["Giờ"].sum()

    # Giờ năm hiện tại
    df_year = df[
        df["Năm"] == current_year
    ].groupby("Nhân viên")["Giờ"].sum()

    staff = sorted(set(df["Nhân viên"]))

    rows = []
    for s in staff:
        rows.append({
            "Nhân viên": s,
            "Giờ tháng hiện tại": int(df_month.get(s, 0)),
            "Giờ năm hiện tại": int(df_year.get(s, 0))
        })

    return pd.DataFrame(rows)

# ==================================================
# HIỂN THỊ LỊCH (TỪ Lich_Truc)
# ==================================================
try:
    df_view = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, ttl=0)
except:
    df_view = pd.DataFrame()

st.subheader("📋 LỊCH TRỰC CA")
st.dataframe(df_view, use_container_width=True)

# ==================================================
# HIỂN THỊ TỔNG GIỜ
# ==================================================
st.subheader("⏱️ TỔNG SỐ GIỜ TRỰC")

df_hours = calculate_hours(df_log)

st.caption(
    f"Giờ tháng: tính từ 01/{current_month:02}/{current_year} đến hôm nay | "
    f"Giờ năm: tính từ 01/01/{current_year} đến hôm nay"
)

st.dataframe(df_hours, use_container_width=True)
