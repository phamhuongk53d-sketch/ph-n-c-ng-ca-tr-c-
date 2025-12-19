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
    df_old = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        ttl=0
    )
except:
    df_old = pd.DataFrame()

df_old = ensure_df(df_old)
df_old = parse_date(df_old)
df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.header("👥 Nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = ["Trung", "Ngà"]

    st.header("📅 Khoảng thời gian")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

    st.header("🔄 Thay đổi nhân sự")
    change_date = st.date_input("Áp dụng từ ngày", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ / bận", staff)

# ==================================================
# KHÓA QUÁ KHỨ
# ==================================================
today = datetime.now().date()
if start_date < today or change_date < today:
    st.error("❌ Không được tạo hoặc chỉnh lịch trong quá khứ")
    st.stop()

# ==================================================
# GIỮ LỊCH CŨ
# ==================================================
df_fixed = df_old[df_old["Ngày"].dt.date < change_date]

# ==================================================
# GIỜ LŨY KẾ
# ==================================================
hours = {s: 0 for s in staff}
for s in staff:
    hours[s] = df_fixed[df_fixed["Nhân viên"] == s]["Giờ"].sum()

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    active_staff = [s for s in staff if s not in absent_staff]
    available_at = {s: datetime.min for s in active_staff}

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5

        # ===== CA NGÀY =====
        day_candidates = []
        for s in active_staff:
            if available_at[s] <= base.replace(hour=8):
                if s in special_staff:
                    if is_weekday:
                        day_candidates.append(s)
                else:
                    day_candidates.append(s)

        day_candidates.sort(key=lambda x: hours[x])
        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca ngày", "Nhân viên": s, "Giờ": 8})
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in active_staff
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]

        night_candidates.sort(key=lambda x: hours[x])
        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm", "Nhân viên": s, "Giờ": 16})
            hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO / CẬP NHẬT LỊCH
# ==================================================
if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    df_new = generate_schedule()
    df_all = pd.concat([df_fixed, df_new], ignore_index=True)
    df_all = parse_date(df_all).sort_values("Ngày")

    # ===== BẢNG HIỂN THỊ =====
    rows = []
    for d, g in df_all.groupby("Ngày"):
        rows.append({
            "Ngày": vn_day(d),
            "Ca 08:00–16:00": ", ".join(g[g["Ca"] == "Ca ngày"]["Nhân viên"]),
            "Ca 16:00–08:00": ", ".join(g[g["Ca"] == "Ca đêm"]["Nhân viên"])
        })

    df_display = pd.DataFrame(rows)

    st.subheader("📋 LỊCH TRỰC CA")
    st.dataframe(df_display, use_container_width=True)

    # ===== LƯU GOOGLE SHEET =====
    df_save = df_all.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_display)

    st.success("✅ Đã tạo & cập nhật lịch trực")

# ==================================================
# TỔNG SỐ GIỜ TRỰC (DATA_LOG)
# ==================================================
st.markdown("---")
st.subheader("📊 TỔNG SỐ GIỜ TRỰC")

if st.button("📌 XEM TỔNG SỐ GIỜ TRỰC"):
    if df_old.empty:
        st.warning("Không có dữ liệu Data_Log")
    else:
        today = datetime.now().date()

        # ===== THÁNG =====
        month_start = today.replace(day=1)
        df_month = df_old[
            (df_old["Ngày"].dt.date >= month_start) &
            (df_old["Ngày"].dt.date <= today)
        ]

        month_summary = (
            df_month.groupby("Nhân viên", as_index=False)["Giờ"]
            .sum()
            .rename(columns={"Giờ": "Tổng giờ tháng"})
            .sort_values("Tổng giờ tháng", ascending=False)
        )

        # ===== NĂM =====
        year_start = today.replace(month=1, day=1)
        df_year = df_old[
            (df_old["Ngày"].dt.date >= year_start) &
            (df_old["Ngày"].dt.date <= today)
        ]

        year_summary = (
            df_year.groupby("Nhân viên", as_index=False)["Giờ"]
            .sum()
            .rename(columns={"Giờ": "Tổng giờ năm"})
            .sort_values("Tổng giờ năm", ascending=False)
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🗓️ Tổng giờ tháng")
            st.dataframe(month_summary, use_container_width=True)

        with col2:
            st.markdown("### 📅 Tổng giờ năm")
            st.dataframe(year_summary, use_container_width=True)
