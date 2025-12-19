# ==================================================
# app.py – HỆ THỐNG PHÂN CÔNG TRỰC CÔNG BẰNG
# ==================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import io

# ==================================================
# STREAMLIT CONFIG
# ==================================================
st.set_page_config(
    page_title="Hệ thống Trực Công Bằng",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# TIỆN ÍCH CHUNG
# ==================================================
def vn_day(d):
    days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{days[d.weekday()]} - {d.strftime('%d/%m')}"

def month_name(m):
    return f"Tháng {m}"

# ==================================================
# LOAD DATA (CACHED)
# ==================================================
@st.cache_data(ttl=300)
def load_data():
    try:
        df = conn.read(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Data_Log",
            ttl=0
        )
    except:
        df = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

    if not df.empty:
        df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Ngày"])
        df["Năm"] = df["Ngày"].dt.year
        df["Tháng"] = df["Ngày"].dt.month

    return df

df_raw = load_data()

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.header("👥 Nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    weekday_only = st.multiselect(
        "Chỉ trực T2–T6",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("⚖️ Cân bằng")
    balance_type = st.radio(
        "Chiến lược",
        ["Theo tháng", "Theo năm"]
    )

    st.header("📅 Thời gian")
    year = st.selectbox("Năm", [2024, 2025, 2026, 2027], index=2)
    start_month = st.selectbox("Từ tháng", range(1, 13), index=0)
    end_month = st.selectbox("Đến tháng", range(1, 13), index=11)

    start_date = datetime(year, start_month, 1)
    end_date = (
        datetime(year, 12, 31)
        if end_month == 12
        else datetime(year, end_month + 1, 1) - timedelta(days=1)
    )

# ==================================================
# TIỀN XỬ LÝ LỊCH SỬ
# ==================================================
history_before = df_raw[df_raw["Ngày"] < start_date]

history_monthly = (
    history_before
    .groupby(["Tháng", "Nhân viên"])["Giờ"]
    .sum()
    .to_dict()
)

# ==================================================
# THUẬT TOÁN PHÂN CA (SẠCH)
# ==================================================
def generate_schedule(
    staff, start_date, end_date,
    weekday_only, balance_type, history_monthly
):
    rows = []

    available_at = {s: start_date - timedelta(days=1) for s in staff}

    monthly_hours = {
        m: {s: history_monthly.get((m, s), 0) for s in staff}
        for m in range(start_date.month, end_date.month + 1)
    }

    yearly_hours = {
        s: sum(monthly_hours[m][s] for m in monthly_hours)
        for s in staff
    }

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        m = curr.month
        wd = curr.weekday()

        # ===== CA NGÀY =====
        day_candidates = [
            s for s in staff
            if available_at[s] <= base.replace(hour=8)
            and (wd < 5 or s not in weekday_only)
        ]

        key_func = (
            (lambda s: monthly_hours[m][s])
            if balance_type == "Theo tháng"
            else (lambda s: yearly_hours[s])
        )

        day_candidates.sort(key=key_func)
        selected_day = day_candidates[:2]

        for s in selected_day:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 8h00 - 16h00",
                "Nhân viên": s,
                "Giờ": 8,
                "Năm": curr.year,
                "Tháng": m
            })
            monthly_hours[m][s] += 8
            yearly_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in staff
            if s not in weekday_only
            and s not in selected_day
            and available_at[s] <= base.replace(hour=16)
        ]

        night_candidates.sort(key=key_func)
        selected_night = night_candidates[:2]

        for s in selected_night:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 16h00 - 8h00",
                "Nhân viên": s,
                "Giờ": 16,
                "Năm": curr.year,
                "Tháng": m
            })
            monthly_hours[m][s] += 16
            yearly_hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows), monthly_hours

# ==================================================
# MAIN
# ==================================================
st.title("📊 HỆ THỐNG PHÂN CÔNG TRỰC")

if st.button("🚀 TẠO LỊCH TRỰC"):
    df_new, monthly_hours = generate_schedule(
        staff,
        start_date,
        end_date,
        weekday_only,
        balance_type,
        history_monthly
    )

    df_total = (
        pd.concat([df_raw[df_raw["Ngày"] < start_date], df_new])
        .sort_values("Ngày")
        .reset_index(drop=True)
    )

    st.subheader(f"🗓️ LỊCH TRỰC NĂM {year}")

    for m in range(start_month, end_month + 1):
        df_m = df_total[(df_total["Năm"] == year) & (df_total["Tháng"] == m)]
        if df_m.empty:
            continue

        st.markdown(f"### {month_name(m)}")

        view = (
            df_m
            .groupby(["Ngày", "Ca"])["Nhân viên"]
            .apply(lambda x: ", ".join(x))
            .reset_index()
            .pivot(index="Ngày", columns="Ca", values="Nhân viên")
            .fillna("")
            .reset_index()
        )

        view["Ngày"] = view["Ngày"].apply(vn_day)
        st.dataframe(view, use_container_width=True)

        hours = (
            df_m.groupby("Nhân viên")["Giờ"]
            .sum()
            .reset_index()
            .sort_values("Giờ")
        )

        st.dataframe(hours, hide_index=True)

    st.success("✅ Hoàn tất phân công")
