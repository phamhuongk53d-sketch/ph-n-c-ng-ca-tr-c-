import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực công bằng",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

CA_NGAY = "Ca: 8h00 - 16h00"
CA_DEM  = "Ca: 16h00 - 8h00"
MAX_HOURS_MONTH = 176

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def vn_weekday(d):
    return ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][d.weekday()]

def is_weekend(d):
    return d.weekday() >= 5

def display_date(d):
    return f"{vn_weekday(d)}- {d.strftime('%d/%m')}"

# ==================================================
# ĐỌC DỮ LIỆU GOOGLE SHEETS
# ==================================================
try:
    df_raw = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        ttl=0
    )
except Exception:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

if not df_raw.empty:
    df_raw["Ngày"] = pd.to_datetime(
        df_raw["Ngày"],
        dayfirst=True,
        errors="coerce"
    )
    df_raw.dropna(subset=["Ngày"], inplace=True)

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("Cấu hình phân lịch")

    staff = [
        s.strip() for s in st.text_area(
            "Danh sách nhân viên",
            "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
        ).split(",") if s.strip()
    ]

    special_staff = ["Trung", "Ngà"]

    year = st.number_input(
        "Năm",
        min_value=2020,
        max_value=2100,
        value=datetime.now().year,
        step=1
    )

    month = st.selectbox(
        "Tháng",
        list(range(1, 13)),
        index=datetime.now().month - 1
    )

# ==================================================
# TÍNH GIỜ LŨY KẾ
# ==================================================
df_raw["Year"] = df_raw["Ngày"].dt.year
df_raw["Month"] = df_raw["Ngày"].dt.month

year_hours = (
    df_raw[df_raw["Year"] == year]
    .groupby("Nhân viên")["Giờ"]
    .sum()
    .to_dict()
)

month_hours = (
    df_raw[(df_raw["Year"] == year) & (df_raw["Month"] == month)]
    .groupby("Nhân viên")["Giờ"]
    .sum()
    .to_dict()
)

for s in staff:
    year_hours.setdefault(s, 0)
    month_hours.setdefault(s, 0)

st.subheader(f"📊 Giờ lũy kế tháng {month}/{year}")
st.dataframe(pd.DataFrame({
    "Giờ tháng": month_hours,
    "Giờ năm": year_hours
}))

# ==================================================
# THUẬT TOÁN PHÂN CÔNG
# ==================================================
def generate_schedule():
    rows = []
    available_at = {
        s: datetime(year, month, 1) - timedelta(days=1)
        for s in staff
    }

    start = datetime(year, month, 1)
    end = (start + pd.offsets.MonthEnd()).date()

    curr = start.date()
    while curr <= end:

        # Không phân công T7, CN cho Trung & Ngà
        if is_weekend(curr):
            curr += timedelta(days=1)
            continue

        base = datetime.combine(curr, datetime.min.time())

        # ===== CA NGÀY =====
        day_candidates = [
            s for s in staff
            if available_at[s] <= base
            and month_hours[s] + 8 <= MAX_HOURS_MONTH
        ]
        day_candidates.sort(key=lambda s: (month_hours[s], year_hours[s]))

        selected_day = day_candidates[:2]
        for s in selected_day:
            rows.append({
                "Ngày": curr,
                "Ca": CA_NGAY,
                "Nhân viên": s,
                "Giờ": 8
            })
            month_hours[s] += 8
            year_hours[s] += 8
            available_at[s] = base + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in staff
            if s not in special_staff
            and available_at[s] <= base
            and month_hours[s] + 16 <= MAX_HOURS_MONTH
        ]
        night_candidates.sort(key=lambda s: (month_hours[s], year_hours[s]))

        selected_night = night_candidates[:2]
        for s in selected_night:
            rows.append({
                "Ngày": curr,
                "Ca": CA_DEM,
                "Nhân viên": s,
                "Giờ": 16
            })
            month_hours[s] += 16
            year_hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# CHẠY PHÂN LỊCH
# ==================================================
if st.button("🚀 TẠO LỊCH TRỰC"):
    df_new = generate_schedule()
    df_all = pd.concat([df_raw, df_new], ignore_index=True)

    # ===== HIỂN THỊ LỊCH =====
    df_view = df_new.copy()
    df_view["Ngày"] = pd.to_datetime(df_view["Ngày"])

    df_pivot = (
        df_view
        .groupby(["Ngày", "Ca"])["Nhân viên"]
        .apply(lambda x: " ".join(x))
        .unstack()
        .reindex(columns=[CA_NGAY, CA_DEM])
        .fillna("")
        .reset_index()
        .sort_values("Ngày")
    )

    df_pivot["Ngày"] = df_pivot["Ngày"].apply(display_date)

    st.subheader("🗓️ Lịch trực tháng")
    st.table(df_pivot)

    # ===== BÁO CÁO GIỜ =====
    summary_month = (
        df_new.groupby("Nhân viên")["Giờ"]
        .sum()
        .reset_index()
        .rename(columns={"Giờ": "Giờ tháng"})
    )

    summary_year = (
        df_all[df_all["Year"] == year]
        .groupby("Nhân viên")["Giờ"]
        .sum()
        .reset_index()
        .rename(columns={"Giờ": "Giờ năm"})
    )

    st.subheader("📊 Tổng giờ tháng")
    st.table(summary_month)

    st.subheader("📊 Tổng giờ năm")
    st.table(summary_year)

    # ===== LƯU GOOGLE SHEETS =====
    df_all_save = df_all.copy()
    df_all_save["Ngày"] = df_all_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        data=df_all_save.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Lich_Truc",
        data=df_pivot.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Tong_Gio_Thang",
        data=summary_month.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Tong_Gio_Nam",
        data=summary_year.reset_index(drop=True)
    )

    st.success("✅ Phân lịch & lưu dữ liệu hoàn tất!")

