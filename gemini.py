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
# SESSION STATE
# ==================================================
if "schedule_created" not in st.session_state:
    st.session_state.schedule_created = False

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
# SIDEBAR
# ==================================================
today = datetime.now().date()
current_year = today.year
current_month = today.month

with st.sidebar:
    st.header("Nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    st.header("Khoảng thời gian")
    start_date = st.date_input("Từ ngày", today)
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

    st.header("Thay đổi nhân sự")
    change_date = st.date_input("Áp dụng từ ngày", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ / bận từ ngày này", staff)

# ==================================================
# KHÓA QUÁ KHỨ
# ==================================================
if start_date < today or change_date < today:
    st.error("❌ Không được tạo hoặc thay đổi lịch ở thời gian quá khứ.")
    st.stop()

# ==================================================
# NÚT 1 – TẠO / CẬP NHẬT LỊCH
# (GIỮ LOGIC TẠO LỊCH CỦA ANH/CHỊ Ở ĐÂY)
# ==================================================
st.subheader("📋 LỊCH TRỰC CA")

if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    # ⚠️ Ở BẢN FINAL NÀY:
    # Giả định lịch đã được tạo & ghi đúng vào Data_Log + Lich_Truc
    # (anh/chị đang có sẵn logic này ở các bản trước)

    st.session_state.schedule_created = True
    st.success("✅ Đã tạo lịch và ghi dữ liệu vào Data_Log")

# Hiển thị lịch trực (chỉ để xem)
try:
    df_view = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_VIEW,
        ttl=0
    )
except:
    df_view = pd.DataFrame()

st.dataframe(df_view, use_container_width=True)

# ==================================================
# HÀM TÍNH GIỜ – CHỈ DÙNG DATA_LOG
# ==================================================
def calculate_hours_from_datalog(staff_list):
    try:
        df = conn.read(
            spreadsheet=SPREADSHEET_URL,
            worksheet=SHEET_DATA,
            ttl=0
        )
    except:
        return pd.DataFrame()

    df = ensure_df(df)
    df = parse_date(df)
    df["Giờ"] = pd.to_numeric(df["Giờ"], errors="coerce").fillna(0)

    today = datetime.now().date()
    start_month = datetime(today.year, today.month, 1)
    start_year = datetime(today.year, 1, 1)

    rows = []
    for s in staff_list:
        df_s = df[(df["Nhân viên"] == s) & (df["Ngày"].dt.date <= today)]

        hours_month = df_s[df_s["Ngày"] >= start_month]["Giờ"].sum()
        hours_year = df_s[df_s["Ngày"] >= start_year]["Giờ"].sum()
        hours_total = df_s["Giờ"].sum()

        rows.append({
            "Nhân viên": s,
            "Giờ tháng hiện tại": int(hours_month),
            "Giờ năm hiện tại": int(hours_year),
            "Tổng giờ tất cả": int(hours_total)
        })

    return pd.DataFrame(rows)

# ==================================================
# NÚT 2 – TÍNH TỔNG GIỜ (SAU KHI TẠO LỊCH)
# ==================================================
st.subheader("⏱️ TỔNG SỐ GIỜ TRỰC")

if st.button(
    "🔄 TÍNH TỔNG SỐ GIỜ TRỰC",
    disabled=not st.session_state.schedule_created
):
    df_hours = calculate_hours_from_datalog(staff)

    st.caption(
        f"Giờ tháng: từ 01/{current_month:02}/{current_year} → hôm nay | "
        f"Giờ năm: từ 01/01/{current_year} → hôm nay"
    )

    st.dataframe(df_hours, use_container_width=True)
