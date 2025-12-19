import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – Tái tạo theo ngày thay đổi",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"

REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    return ["T2","T3","T4","T5","T6","T7","CN"][d.weekday()] + " " + d.strftime("%d/%m/%Y")

def ensure_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df.columns = [str(c).strip() for c in df.columns]
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

# ==================================================
# ĐỌC DỮ LIỆU CŨ
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
df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce")
df_raw["Giờ"] = pd.to_numeric(df_raw["Giờ"], errors="coerce").fillna(0)
df_raw = df_raw.dropna(subset=["Ngày"])

# ==================================================
# SIDEBAR
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

    st.header("Thay đổi nhân sự đột xuất")
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
def generate_schedule():
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

        # CA NGÀY
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
            rows.append({"Ngày": curr,"Ca":"Ca ngày (08–16)","Nhân viên":s,"Giờ":8})
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # CA ĐÊM
        night_candidates = [
            s for s in active_staff
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: hours.get(s, 0))

        for s in night_candidates[:2]:
            rows.append({"Ngày": curr,"Ca":"Ca đêm (16–08)","Nhân viên":s,"Giờ":16})
            hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO & CẬP NHẬT
# ==================================================
if st.button("🚀 TẠO LẠI LỊCH TỪ NGÀY THAY ĐỔI"):
    df_new = generate_schedule()
    df_total = pd.concat([old_part, df_new], ignore_index=True)

    # ===== XUẤT THEO THÁNG =====
    df_total["Năm"] = df_total["Ngày"].dt.year
    df_total["Tháng"] = df_total["Ngày"].dt.month

    export_rows = []
    for (y, m), g in df_total.groupby(["Năm","Tháng"]):
        export_rows.append({"Ngày":f"LỊCH PHÂN CÔNG THÁNG {m} NĂM {y}","Ca":"","Nhân viên":"","Giờ":""})
        for _, r in g.sort_values("Ngày").iterrows():
            export_rows.append({
                "Ngày": vn_day(r["Ngày"]),
                "Ca": r["Ca"],
                "Nhân viên": r["Nhân viên"],
                "Giờ": r["Giờ"]
            })

    df_export = pd.DataFrame(export_rows)

    st.subheader("Lịch trực sau khi điều chỉnh")
    st.dataframe(df_export, use_container_width=True)

    # ===== GHI GOOGLE SHEETS =====
    df_save = df_total.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(SPREADSHEET_URL, SHEET_DATA, df_save.reset_index(drop=True))
    conn.update(SPREADSHEET_URL, SHEET_VIEW, df_export.reset_index(drop=True))

    st.success("✅ Đã cập nhật lịch từ ngày thay đổi nhân sự")
