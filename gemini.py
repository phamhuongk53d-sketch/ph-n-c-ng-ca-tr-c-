import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – FINAL",
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

def ensure_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

def force_date(df):
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Ngày"])

def group_shift(df):
    return (
        df.groupby(["Ngày", "Ca"], as_index=False)
        .agg({
            "Nhân viên": lambda x: ", ".join(sorted(x)),
            "Giờ": "sum"
        })
        .sort_values("Ngày")
    )

# ==================================================
# ĐỌC DATA_LOG
# ==================================================
try:
    df_raw = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        ttl=0
    )
except Exception:
    df_raw = pd.DataFrame()

df_raw = ensure_df(df_raw)
df_raw = force_date(df_raw)
df_raw["Giờ"] = pd.to_numeric(df_raw["Giờ"], errors="coerce").fillna(0)

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
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

    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=365))

    change_date = st.date_input("Áp dụng thay đổi từ", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ", staff)

# ==================================================
# GIỮ LỊCH CŨ
# ==================================================
old_part = df_raw[df_raw["Ngày"].dt.date < change_date]

# ==================================================
# LŨY KẾ CŨ
# ==================================================
luy_ke = {
    s: old_part.loc[old_part["Nhân viên"] == s, "Giờ"].sum()
    for s in staff
}

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate():
    rows = []
    active = [s for s in staff if s not in absent_staff]
    hours = luy_ke.copy()

    available = {
        s: datetime.combine(change_date - timedelta(days=1), datetime.min.time())
        for s in active
    }

    d = change_date
    while d <= end_date:
        base = datetime.combine(d, datetime.min.time())

        # CA NGÀY
        day_cand = [s for s in active if available[s] <= base.replace(hour=8)]
        day_cand.sort(key=lambda s: (0 if s in special_staff else 1, hours[s]))

        for s in day_cand[:2]:
            rows.append({"Ngày": d, "Ca": "Ca ngày (08–16)", "Nhân viên": s, "Giờ": 8})
            hours[s] += 8
            available[s] = base.replace(hour=16) + timedelta(hours=16)

        # CA ĐÊM
        night_cand = [
            s for s in active
            if s not in special_staff and available[s] <= base.replace(hour=16)
        ]
        night_cand.sort(key=lambda s: hours[s])

        for s in night_cand[:2]:
            rows.append({"Ngày": d, "Ca": "Ca đêm (16–08)", "Nhân viên": s, "Giờ": 16})
            hours[s] += 16
            available[s] = base + timedelta(days=2)

        d += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO LỊCH
# ==================================================
if st.button("🚀 TẠO LẠI LỊCH"):
    df_new = generate()
    df_new = ensure_df(df_new)
    df_new = force_date(df_new)

    df_total = pd.concat([old_part, df_new], ignore_index=True)

    # ================= LỊCH TRỰC (TOÀN BỘ) =================
    df_view = group_shift(df_total)

    export = []
    for (y, m), g in df_view.groupby([df_view["Ngày"].dt.year, df_view["Ngày"].dt.month]):
        export.append({"Ngày": f"LỊCH THÁNG {m}/{y}", "Ca": "", "Nhân viên": "", "Giờ": ""})
        for _, r in g.iterrows():
            export.append({
                "Ngày": vn_day(r["Ngày"]),
                "Ca": r["Ca"],
                "Nhân viên": r["Nhân viên"],
                "Giờ": r["Giờ"]
            })

    df_export = pd.DataFrame(export)

    # ================= TỔNG GIỜ (ĐẾN HÔM NAY – ĐỦ NHÂN VIÊN) =================
    today = datetime.now().date()
    start_month = today.replace(day=1)
    start_year = today.replace(month=1, day=1)

    df_month = df_total[
        (df_total["Ngày"].dt.date >= start_month) &
        (df_total["Ngày"].dt.date <= today)
    ]

    df_year = df_total[
        (df_total["Ngày"].dt.date >= start_year) &
        (df_total["Ngày"].dt.date <= today)
    ]

    hours_month = df_month.groupby("Nhân viên")["Giờ"].sum()
    hours_year = df_year.groupby("Nhân viên")["Giờ"].sum()

    df_hours = pd.DataFrame({"Nhân viên": staff})
    df_hours["Giờ tháng"] = df_hours["Nhân viên"].map(hours_month).fillna(0)
    df_hours["Giờ năm"] = df_hours["Nhân viên"].map(hours_year).fillna(0)

    # ================= HIỂN THỊ =================
    st.subheader("📅 Lịch trực (toàn bộ ca)")
    st.dataframe(df_export, use_container_width=True)

    st.subheader("⏱️ Tổng giờ làm việc")
    st.dataframe(df_hours, use_container_width=True)

    # ================= GHI GOOGLE SHEET (ĐÃ FIX LỖI) =================
    df_save = df_total.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_DATA,
        data=df_save.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet=SHEET_VIEW,
        data=df_export.reset_index(drop=True)
    )

    st.success("✅ Đã tạo lịch & cập nhật Google Sheet – FILE FINAL OK")
