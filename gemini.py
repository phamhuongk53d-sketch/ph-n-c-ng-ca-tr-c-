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

with st.sidebar:
    st.header("Nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    st.header("Khoảng thời gian")
    start_date = st.date_input("Từ ngày", today)
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=7))

# ==================================================
# KHÓA QUÁ KHỨ
# ==================================================
if start_date < today:
    st.error("❌ Không được tạo lịch ở thời gian quá khứ.")
    st.stop()

# ==================================================
# THUẬT TOÁN TẠO LỊCH (MẪU – CHẠY ĐƯỢC NGAY)
# 👉 SẼ THAY BẰNG THUẬT TOÁN CHÍNH CỦA ANH/CHỊ
# ==================================================
def generate_schedule():
    rows = []
    curr = start_date
    while curr <= end_date:
        for s in staff[:2]:
            rows.append({
                "Ngày": curr.strftime("%d/%m/%Y"),
                "Ca": "Ca ngày",
                "Nhân viên": s,
                "Giờ": 8
            })
        curr += timedelta(days=1)
    return pd.DataFrame(rows)

# ==================================================
# NÚT 1 – TẠO / CẬP NHẬT LỊCH (GHI DATA_LOG)
# ==================================================
st.subheader("📋 LỊCH TRỰC CA")

if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    df_new = generate_schedule()
    df_new = ensure_df(df_new)

    # 🔥 GHI THẬT VÀO DATA_LOG
    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        data=df_new.reset_index(drop=True)
    )

    # (tuỳ chọn) ghi lịch hiển thị
    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_VIEW,
        data=df_new.reset_index(drop=True)
    )

    st.session_state.schedule_created = True
    st.success("✅ Đã tạo lịch và GHI vào Data_Log thành công")

# ==================================================
# TÍNH TỔNG GIỜ – CHỈ SAU KHI ĐÃ GHI DATA_LOG
# ==================================================
st.subheader("⏱️ TỔNG SỐ GIỜ TRỰC")

def calculate_hours_from_datalog():
    df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df = ensure_df(df)
    df = parse_date(df)
    df["Giờ"] = pd.to_numeric(df["Giờ"], errors="coerce").fillna(0)

    today = datetime.now().date()
    start_month = datetime(today.year, today.month, 1)
    start_year = datetime(today.year, 1, 1)

    rows = []
    for s in staff:
        df_s = df[df["Nhân viên"] == s]
        rows.append({
            "Nhân viên": s,
            "Giờ tháng hiện tại": int(df_s[df_s["Ngày"] >= start_month]["Giờ"].sum()),
            "Giờ năm hiện tại": int(df_s[df_s["Ngày"] >= start_year]["Giờ"].sum()),
            "Tổng giờ": int(df_s["Giờ"].sum())
        })

    return pd.DataFrame(rows)

if st.button(
    "🔄 TÍNH TỔNG GIỜ",
    disabled=not st.session_state.schedule_created
):
    df_hours = calculate_hours_from_datalog()
    st.dataframe(df_hours, use_container_width=True)
