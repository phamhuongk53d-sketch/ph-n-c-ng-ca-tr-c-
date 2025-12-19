import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – Reset toàn bộ khi cập nhật",
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
    return ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][d.weekday()] + " " + d.strftime("%d/%m/%Y")

def ensure_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df.columns = [str(c).strip() for c in df.columns]
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("Cấu hình nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect(
        "Chỉ trực ca ngày",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("Thời gian tạo lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=365))

# ==================================================
# THUẬT TOÁN PHÂN CA (RESET HOÀN TOÀN)
# ==================================================
def generate_schedule():
    rows = []
    work_hours = {s: 0 for s in staff}

    available_at = {
        s: datetime.combine(start_date - timedelta(days=1), datetime.min.time())
        for s in staff
    }

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())

        # ===== CA NGÀY =====
        day_candidates = [
            s for s in staff
            if available_at[s] <= base.replace(hour=8)
        ]
        day_candidates.sort(
            key=lambda s: (
                0 if s in special_staff else 1,
                work_hours[s]
            )
        )

        for s in day_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca ngày (08–16)",
                "Nhân viên": s,
                "Giờ": 8
            })
            work_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM =====
        night_candidates = [
            s for s in staff
            if s not in special_staff
            and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: work_hours[s])

        for s in night_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca đêm (16–08)",
                "Nhân viên": s,
                "Giờ": 16
            })
            work_hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO LỊCH – GHI ĐÈ TOÀN BỘ
# ==================================================
if st.button("🚀 TẠO LỊCH & GHI ĐÈ TOÀN BỘ"):
    df_new = generate_schedule()

    if df_new.empty:
        st.warning("Không có dữ liệu để tạo lịch")
        st.stop()

    # ÉP KIỂU NGÀY
    df_new = ensure_dataframe(df_new)
    df_new["Ngày"] = pd.to_datetime(df_new["Ngày"], errors="coerce")
    df_new = df_new.dropna(subset=["Ngày"])

    # ===== CHIA THEO THÁNG =====
    df_new["Năm"] = df_new["Ngày"].dt.year
    df_new["Tháng"] = df_new["Ngày"].dt.month

    export_rows = []

    for (y, m), g in df_new.groupby(["Năm", "Tháng"]):
        export_rows.append({
            "Ngày": f"LỊCH PHÂN CÔNG THÁNG {m} NĂM {y}",
            "Ca": "",
            "Nhân viên": "",
            "Giờ": ""
        })

        for _, r in g.sort_values("Ngày").iterrows():
            export_rows.append({
                "Ngày": vn_day(r["Ngày"]),
                "Ca": r["Ca"],
                "Nhân viên": r["Nhân viên"],
                "Giờ": r["Giờ"]
            })

    df_export = pd.DataFrame(export_rows)

    st.subheader("Lịch trực mới (đã ghi đè toàn bộ)")
    st.dataframe(df_export, use_container_width=True)

    # ===== GHI GOOGLE SHEETS (XÓA CŨ – GHI MỚI) =====
    df_save = df_new.copy()
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

    st.success("✅ Đã xóa toàn bộ dữ liệu cũ và thay thế bằng lịch mới")
