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
    special_staff = ["Trung", "Ngà"]

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
# (GIỮ NGUYÊN) HÀM TÍNH GIỜ
# ==================================================
def calculate_hours(df, staff_list):
    df = df[df["Ngày"].dt.date <= today].copy()
    df["Năm"] = df["Ngày"].dt.year
    df["Tháng"] = df["Ngày"].dt.month

    month_sum = df[
        (df["Năm"] == current_year) &
        (df["Tháng"] == current_month)
    ].groupby("Nhân viên")["Giờ"].sum()

    year_sum = df[
        df["Năm"] == current_year
    ].groupby("Nhân viên")["Giờ"].sum()

    total_sum = df.groupby("Nhân viên")["Giờ"].sum()

    rows = []
    for s in staff_list:
        rows.append({
            "Nhân viên": s,
            "Giờ tháng hiện tại": int(month_sum.get(s, 0)),
            "Giờ năm hiện tại": int(year_sum.get(s, 0)),
            "Tổng giờ tất cả": int(total_sum.get(s, 0))
        })

    return pd.DataFrame(rows)

# ==================================================
# NÚT 1: TẠO / CẬP NHẬT LỊCH
# (GIỮ NGUYÊN LUỒNG – CHỖ NÀY GẮN LOGIC TẠO LỊCH CỦA ANH/CHỊ)
# ==================================================
st.subheader("📋 LỊCH TRỰC CA")

if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    # Sau khi tạo lịch và ghi Data_Log thành công
    st.session_state.schedule_created = True
    st.success("✅ Đã tạo lịch và ghi dữ liệu vào Data_Log")

# Hiển thị lịch từ Google Sheets
try:
    df_view = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, ttl=0)
except:
    df_view = pd.DataFrame()

st.dataframe(df_view, use_container_width=True)

# ==================================================
# NÚT 2: TÍNH TỔNG GIỜ (CHỈ SAU KHI TẠO LỊCH)
# ==================================================
st.subheader("⏱️ TỔNG SỐ GIỜ TRỰC")

if st.button(
    "🔄 TÍNH TỔNG SỐ GIỜ TRỰC",
    disabled=not st.session_state.schedule_created
):
    # ĐỌC LẠI DATA_LOG TẠI THỜI ĐIỂM BẤM NÚT
    try:
        df_log = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    except:
        df_log = pd.DataFrame()

    df_log = ensure_df(df_log)
    df_log = parse_date(df_log)
    df_log["Giờ"] = pd.to_numeric(df_log["Giờ"], errors="coerce").fillna(0)

    df_hours = calculate_hours(df_log, staff)

    st.caption(
        f"Giờ tháng: từ 01/{current_month:02}/{current_year} → hôm nay | "
        f"Giờ năm: từ 01/01/{current_year} → hôm nay"
    )

    st.dataframe(df_hours, use_container_width=True)
