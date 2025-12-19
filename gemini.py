import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH ỨNG DỤNG
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – Bản chuẩn vận hành",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
SHEET_DATA = "Data_Log"

REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH (SAFE – KHÓA LỖI)
# ==================================================
def vn_day(d: pd.Timestamp) -> str:
    return ["T2","T3","T4","T5","T6","T7","CN"][d.weekday()] + " " + d.strftime("%d/%m/%Y")

def ensure_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df.columns = [str(c).strip() for c in df.columns]
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

def force_datetime(df: pd.DataFrame, col="Ngày") -> pd.DataFrame:
    df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df.dropna(subset=[col])

# ==================================================
# ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS (CHỈ PHỤC VỤ TÍNH)
# ==================================================
try:
    df_raw = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        ttl=0
    )
except Exception:
    df_raw = pd.DataFrame()

df_raw = ensure_dataframe(df_raw)
df_raw = force_datetime(df_raw, "Ngày")
df_raw["Giờ"] = pd.to_numeric(df_raw["Giờ"], errors="coerce").fillna(0)

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("Nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect(
        "Chỉ trực ca ngày",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("Khoảng tạo lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=365))

    st.header("Thay đổi nhân sự")
    change_date = st.date_input(
        "Ngày bắt đầu áp dụng thay đổi",
        start_date
    )

    absent_staff = st.multiselect(
        "Nhân sự nghỉ/bận từ ngày này",
        staff,
        default=[]
    )

# ==================================================
# GIỮ LỊCH CŨ TRƯỚC NGÀY THAY ĐỔI
# ==================================================
old_part = df_raw[df_raw["Ngày"].dt.date < change_date]

# ==================================================
# GIỜ LŨY KẾ ĐẾN TRƯỚC NGÀY THAY ĐỔI
# ==================================================
luy_ke = {}
for s in staff:
    mask = old_part["Nhân viên"].astype(str).str.strip() == s
    luy_ke[s] = old_part.loc[mask, "Giờ"].sum()

# ==================================================
# THUẬT TOÁN PHÂN CA TỪ NGÀY THAY ĐỔI
# ==================================================
def generate_schedule_from_change():
    rows = []
    active_staff = [s for s in staff if s not in absent_staff]
    hours = luy_ke.copy()

    available_at = {
        s: datetime.combine(change_date - timedelta(days=1), datetime.min.time())
        for s in active_staff
    }

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())

        # ===== CA NGÀY =====
        day_candidates = [
            s for s in active_staff
            if available_at[s] <= base.replace(hour=8)
        ]
        day_candidates.sort(
            key=lambda s: (
                0 if s in special_staff else 1,
                hours.get(s, 0)
            )
        )

        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca ngày (08–16)", "Nhân viên": s, "Giờ": 8})
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in active_staff
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: hours.get(s, 0))

        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm (16–08)", "Nhân viên": s, "Giờ": 16})
            hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO & HIỂN THỊ
# ==================================================
if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    df_new = generate_schedule_from_change()

    if df_new.empty:
        st.warning("Không có dữ liệu để tạo lịch")
        st.stop()

    df_new = ensure_dataframe(df_new)
    df_new = force_datetime(df_new, "Ngày")

    # GỘP LỊCH
    df_total = pd.concat([old_part, df_new], ignore_index=True)
    df_total = ensure_dataframe(df_total)
    df_total = force_datetime(df_total, "Ngày")

    # ==================================================
    # 1️⃣ HIỂN THỊ LỊCH TRỰC DẠNG GỘP NGƯỜI / CA
    # ==================================================
    df_view = df_total.copy()
    df_view["Ngày_hiển_thị"] = df_view["Ngày"].apply(vn_day)

    df_group = (
        df_view
        .groupby(["Ngày_hiển_thị", "Ca"], as_index=False)["Nhân viên"]
        .apply(lambda x: ", ".join(sorted(x)))
    )

    df_pivot = (
        df_group
        .pivot(index="Ngày_hiển_thị", columns="Ca", values="Nhân viên")
        .fillna("")
        .reset_index()
    )

    st.subheader("📅 Lịch trực tổng hợp")
    st.dataframe(df_pivot, use_container_width=True)

    # ==================================================
    # 2️⃣ TỔNG GIỜ TRỰC THEO THÁNG (01 → HIỆN TẠI)
    # ==================================================
    today = datetime.now().date()
    month_start = today.replace(day=1)

    df_month = df_total[
        (df_total["Ngày"].dt.date >= month_start) &
        (df_total["Ngày"].dt.date <= today)
    ]

    df_month_sum = (
        df_month
        .groupby("Nhân viên", as_index=False)["Giờ"]
        .sum()
        .sort_values("Giờ", ascending=False)
    )

    st.subheader(f"⏱️ Tổng giờ trực tháng {today.month}/{today.year}")
    st.dataframe(df_month_sum, use_container_width=True)

    # ==================================================
    # 3️⃣ TỔNG GIỜ TRỰC THEO NĂM (RESET MỖI NĂM)
    # ==================================================
    year_selected = st.number_input(
        "Chọn năm xem tổng giờ",
        min_value=2020,
        max_value=2100,
        value=today.year,
        step=1
    )

    year_start = datetime(year_selected, 1, 1).date()
    year_end = datetime(year_selected, 12, 31).date()

    df_year = df_total[
        (df_total["Ngày"].dt.date >= year_start) &
        (df_total["Ngày"].dt.date <= year_end)
    ]

    df_year_sum = (
        df_year
        .groupby("Nhân viên", as_index=False)["Giờ"]
        .sum()
        .sort_values("Giờ", ascending=False)
    )

    st.subheader(f"📊 Tổng giờ trực năm {year_selected}")
    st.dataframe(df_year_sum, use_container_width=True)

    st.success("✅ Đã tạo và hiển thị lịch trực đúng yêu cầu")
