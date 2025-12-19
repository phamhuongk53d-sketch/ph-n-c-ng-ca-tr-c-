import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH CHUNG
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực ca – FINAL",
    layout="wide"
)

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
# ĐỌC DỮ LIỆU CŨ
# ==================================================
try:
    df_old = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
except:
    df_old = pd.DataFrame()

df_old = ensure_df(df_old)
df_old = parse_date(df_old)
df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)

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

    special_staff = ["Trung", "Ngà"]

    st.header("Khoảng tạo lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

# ==================================================
# KHÓA TẠO LỊCH TRƯỚC NGÀY HIỆN TẠI
# ==================================================
today = datetime.now().date()
if start_date < today:
    st.error("❌ Không cho phép tạo hoặc chỉnh sửa lịch trước ngày hiện tại.")
    st.stop()

# ==================================================
# GIỮ LỊCH CŨ
# ==================================================
df_fixed = df_old[df_old["Ngày"].dt.date < start_date]

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
    available_at = {s: datetime.min for s in staff}

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5

        # ===== CA NGÀY =====
        day_candidates = []
        for s in staff:
            if available_at[s] <= base.replace(hour=8):
                if s in special_staff:
                    if is_weekday:
                        day_candidates.append(s)
                else:
                    day_candidates.append(s)

        day_candidates.sort(key=lambda s: hours[s])
        for s in day_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca ngày (08–16)",
                "Nhân viên": s,
                "Giờ": 8
            })
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in staff
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: hours[s])

        for s in night_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca đêm (16–08)",
                "Nhân viên": s,
                "Giờ": 16
            })
            hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO LỊCH
# ==================================================
if st.button("🚀 TẠO LỊCH"):
    df_new = generate_schedule()
    df_all = pd.concat([df_fixed, df_new], ignore_index=True)
    df_all = parse_date(df_all)

    # ===== HIỂN THỊ GIỐNG BIỂU MẪU GIẤY =====
    display = []
    for d, g in df_all.groupby("Ngày"):
        display.append({
            "Ngày": vn_day(d),
            "Ca: 8h00 – 16h00": ", ".join(g[g["Ca"].str.contains("ngày")]["Nhân viên"]),
            "Ca: 16h00 – 8h00": ", ".join(g[g["Ca"].str.contains("đêm")]["Nhân viên"])
        })

    df_display = pd.DataFrame(display).sort_values("Ngày")

    st.subheader("📋 LỊCH TRỰC CA")
    st.dataframe(df_display, use_container_width=True)

    # ===== GHI GOOGLE SHEETS =====
    df_save = df_all.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_display)

    st.success("✅ Đã tạo và chốt lịch thành công – bản FINAL")
