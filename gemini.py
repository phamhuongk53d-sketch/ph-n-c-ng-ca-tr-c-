import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(
    page_title="Hệ thống Trực Công Bằng – Theo Năm",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    return ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][d.weekday()] + f" {d.strftime('%d/%m/%Y')}"

# ==================================================
# ĐỌC DỮ LIỆU
# ==================================================
try:
    df_raw = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        ttl=0
    )
except:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce")
df_raw = df_raw.dropna(subset=["Ngày"])

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.header("Nhân sự")

    staff = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
    )
    staff = [s.strip() for s in staff.split(",") if s.strip()]

    special_staff = st.multiselect(
        "Chỉ trực ca ngày",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("Thời gian xuất lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=365))

# ==================================================
# GIỜ LŨY KẾ TOÀN NĂM
# ==================================================
history_before = df_raw[df_raw["Ngày"].dt.date < start_date]

luy_ke = {
    s: history_before.loc[
        history_before["Nhân viên"] == s, "Giờ"
    ].sum()
    for s in staff
}

st.subheader("Tổng giờ lũy kế trước thời điểm xuất")
st.dataframe(pd.DataFrame([luy_ke]))

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    hours = luy_ke.copy()

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
                hours[s]
            )
        )

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
            if s not in special_staff
            and available_at[s] <= base.replace(hour=16)
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
# TẠO & GHI LỊCH
# ==================================================
if st.button("TẠO LỊCH & CẬP NHẬT"):
    df_new = generate_schedule()

    # GIỮ LỊCH CŨ TRƯỚC START_DATE – GHI ĐÈ PHẦN SAU
    df_total = pd.concat(
        [history_before, df_new],
        ignore_index=True
    )

    # ================== CHIA THEO THÁNG ==================
    df_total["Năm"] = df_total["Ngày"].dt.year
    df_total["Tháng"] = df_total["Ngày"].dt.month

    output_rows = []

    for (y, m), g in df_total.groupby(["Năm", "Tháng"]):
        title = f"LỊCH PHÂN CÔNG THÁNG {m} NĂM {y}"
        output_rows.append({"Ngày": title, "Ca": "", "Nhân viên": "", "Giờ": ""})

        for _, r in g.sort_values("Ngày").iterrows():
            output_rows.append({
                "Ngày": vn_day(r["Ngày"]),
                "Ca": r["Ca"],
                "Nhân viên": r["Nhân viên"],
                "Giờ": r["Giờ"]
            })

    df_export = pd.DataFrame(output_rows)

    st.subheader("Lịch trực theo tháng")
    st.dataframe(df_export)

    # ================== GHI GOOGLE SHEETS ==================
    df_save = df_total.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        data=df_save.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Lich_Truc",
        data=df_export.reset_index(drop=True)
    )

    st.success("Đã cập nhật lịch trực theo năm và theo tháng")
