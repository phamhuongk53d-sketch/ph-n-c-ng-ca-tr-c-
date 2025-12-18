import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Hệ thống Trực Công Bằng 2025",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def get_vietnamese_weekday(d: pd.Timestamp) -> str:
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[d.weekday()]}- {d.strftime('%d/%m')}"

# ==================================================
# ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
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
    df_raw = df_raw.dropna(subset=["Ngày"])
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

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

    st.header("Thời gian phân lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

# ==================================================
# TÍNH GIỜ LŨY KẾ
# ==================================================
history_before = df_raw[df_raw["Ngày"].dt.date < start_date]

luy_ke_hours = {
    s: history_before.loc[
        history_before["Nhân viên"] == s, "Giờ"
    ].sum()
    for s in staff
}

st.subheader(f"📊 Tổng giờ lũy kế đến {start_date - timedelta(days=1)}")
st.dataframe(pd.DataFrame([luy_ke_hours]))

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    work_hours = luy_ke_hours.copy()

    available_at = {
        s: datetime.combine(start_date - timedelta(days=1), datetime.min.time())
        for s in staff
    }

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())

        # ===== CA NGÀY (08–16) =====
        day_candidates = [
            s for s in staff
            if available_at[s] <= base.replace(hour=8)
        ]
        day_candidates.sort(
            key=lambda s: (0 if s in special_staff else 1, work_hours[s])
        )

        for s in day_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 8h00 - 16h00",
                "Nhân viên": s,
                "Giờ": 8
            })
            work_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # ===== CA ĐÊM (16–08) =====
        night_candidates = [
            s for s in staff
            if s not in special_staff
            and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: work_hours[s])

        for s in night_candidates[:2]:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 16h00 - 8h00",
                "Nhân viên": s,
                "Giờ": 16
            })
            work_hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# TẠO & LƯU LỊCH
# ==================================================
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    df_new = generate_schedule()
    df_total = pd.concat([history_before, df_new], ignore_index=True)

    # ================== HIỂN THỊ ĐÚNG THỨ TỰ ==================
    df_view = df_total.copy()
    df_view["Ngày"] = pd.to_datetime(df_view["Ngày"])

    df_group = (
        df_view
        .groupby(["Ngày", "Ca"], as_index=False)["Nhân viên"]
        .apply(lambda x: " ".join(x))
    )

    df_pivot = (
        df_group
        .pivot(index="Ngày", columns="Ca", values="Nhân viên")
        .reindex(columns=["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"])
        .fillna("")
        .reset_index()
        .sort_values("Ngày")
    )

    df_pivot["Ngày"] = df_pivot["Ngày"].apply(get_vietnamese_weekday)

    st.subheader("🗓️ Lịch trực mới")
    st.table(df_pivot)

    # ================== GHI GOOGLE SHEETS ==================
    df_save_raw = df_total.copy()
    df_save_raw["Ngày"] = pd.to_datetime(df_save_raw["Ngày"]).dt.strftime("%d/%m/%Y")

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        data=df_save_raw.reset_index(drop=True)
    )

    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Lich_Truc",
        data=df_pivot.reset_index(drop=True)
    )

    st.success("✅ Đã lưu lịch trực thành công!")

