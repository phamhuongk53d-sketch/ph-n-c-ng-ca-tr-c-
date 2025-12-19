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
# ĐỌC DATA_LOG (NGUỒN DUY NHẤT ĐỂ TÍNH GIỜ)
# ==================================================
try:
    df_log = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        ttl=0
    )
except:
    df_log = pd.DataFrame()

df_log = ensure_df(df_log)
df_log = parse_date(df_log)
df_log["Giờ"] = pd.to_numeric(df_log["Giờ"], errors="coerce").fillna(0)

# ==================================================
# SIDEBAR – DANH SÁCH NHÂN VIÊN
# ==================================================
with st.sidebar:
    st.header("Nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

# ==================================================
# MỐC THỜI GIAN CHUẨN
# ==================================================
today = datetime.now().date()

start_month = datetime(today.year, today.month, 1)
start_year = datetime(today.year, 1, 1)

# ==================================================
# TÍNH TỔNG GIỜ – CHUẨN 100%
# ==================================================
def calculate_hours_from_datalog(df, staff_list):
    # Chỉ lấy dữ liệu <= hôm nay
    df = df[df["Ngày"].dt.date <= today].copy()

    result = []

    for s in staff_list:
        df_s = df[df["Nhân viên"] == s]

        hours_month = df_s[
            (df_s["Ngày"] >= start_month) &
            (df_s["Ngày"].dt.date <= today)
        ]["Giờ"].sum()

        hours_year = df_s[
            (df_s["Ngày"] >= start_year) &
            (df_s["Ngày"].dt.date <= today)
        ]["Giờ"].sum()

        result.append({
            "Nhân viên": s,
            "Giờ tháng hiện tại": int(hours_month),
            "Giờ năm hiện tại": int(hours_year)
        })

    return pd.DataFrame(result)

# ==================================================
# HIỂN THỊ LỊCH (CHỈ ĐỂ XEM)
# ==================================================
try:
    df_view = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_VIEW,
        ttl=0
    )
except:
    df_view = pd.DataFrame()

st.subheader("📋 LỊCH TRỰC CA")
st.dataframe(df_view, use_container_width=True)

# ==================================================
# HIỂN THỊ TỔNG GIỜ (TÍNH TỪ DATA_LOG)
# ==================================================
st.subheader("⏱️ TỔNG SỐ GIỜ TRỰC")

df_hours = calculate_hours_from_datalog(df_log, staff)

st.caption(
    f"Giờ tháng: từ 01/{today.month:02}/{today.year} đến hôm nay | "
    f"Giờ năm: từ 01/01/{today.year} đến hôm nay"
)

st.dataframe(df_hours, use_container_width=True)
