import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – FINAL LOCKED",
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
# ĐỌC DATA_LOG (NGUỒN DUY NHẤT TÍNH GIỜ)
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

today = datetime.now().date()

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

    start_date = st.date_input("Tạo lịch từ ngày", today)
    end_date = st.date_input("Đến ngày", today + timedelta(days=365))

    change_date = st.date_input("Thời điểm phân ca (kế hoạch)", today)
    absent_staff = st.multiselect("Nhân sự nghỉ", staff)

# ==================================================
# KHÓA CHỈNH SỬA LỊCH ĐÃ QUA
# ==================================================
if change_date < today:
    st.error("⛔ Không được phân ca hoặc chỉnh sửa lịch cho ngày đã qua.")
    st.stop()

# ==================================================
# GIỮ LỊCH CŨ
# ==================================================
old_part = df_raw[df_raw["Ngày"].dt.date < change_date]

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    active = [s for s in staff if s not in absent_staff]

    available = {
        s: datetime.combine(change_date - timedelta(days=1), datetime.min.time())
        for s in active
    }

    d = change_date
    while d <= end_date:
        base = datetime.combine(d, datetime.min.time())

        # CA NGÀY
        day_cand = [s for s in active if available[s] <= base.replace(hour=8)]
        day_cand.sort(key=lambda s: (0 if s in special_staff else 1))

        for s in day_cand[:2]:
            rows.append({"Ngày": d, "Ca": "Ca ngày (08–16)", "Nhân viên": s, "Giờ": 8})
            available[s] = base.replace(hour=16) + timedelta(hours=16)

        # CA ĐÊM
        night_cand = [
            s for s in active
            if s not in special_staff and available[s] <= base.replace(hour=16)
        ]

        for s in night_cand[:2]:
            rows.append({"Ngày": d, "Ca": "Ca đêm (16–08)", "Nhân viên": s, "Giờ": 16})
            available[s] = base + timedelta(days=2)

        d += timedelta(days=1)

    return pd.DataFrame(rows)

# ==================================================
# XỬ LÝ CHÍNH KHI BẤM NÚT
# ==================================================
if st.button("🚀 TẠO LỊCH & CẬP NHẬT"):
    df_new = generate_schedule()
    df_new = ensure_df(df_new)
    df_new = force_date(df_new)

    # Hợp nhất lịch cũ và lịch mới
    df_total = pd.concat([old_part, df_new], ignore_index=True)

    # ================= LỊCH TRỰC VIEW =================
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

    # ================= TÍNH GIỜ (DÙNG DF_TOTAL ĐỂ CẬP NHẬT MỚI NHẤT) =================
    start_month = pd.to_datetime(today.replace(day=1))
    start_year = pd.to_datetime(today.replace(month=1, day=1))
    today_dt = pd.to_datetime(today)
    change_date_dt = pd.to_datetime(change_date)

    # Bảng 1: Đến hôm nay
    df_m_today = df_total[(df_total["Ngày"] >= start_month) & (df_total["Ngày"] <= today_dt)]
    df_y_today = df_total[(df_total["Ngày"] >= start_year) & (df_total["Ngày"] <= today_dt)]

    df_hours_today = pd.DataFrame({"Nhân viên": staff})
    df_hours_today["Giờ tháng (đến hôm nay)"] = df_hours_today["Nhân viên"].map(
        df_m_today.groupby("Nhân viên")["Giờ"].sum()
    ).fillna(0)
    df_hours_today["Giờ năm (đến hôm nay)"] = df_hours_today["Nhân viên"].map(
        df_y_today.groupby("Nhân viên")["Giờ"].sum()
    ).fillna(0)

    # Bảng 2: Đến ngày phân ca
    df_m_plan = df_total[(df_total["Ngày"] >= start_month) & (df_total["Ngày"] <= change_date_dt)]
    df_y_plan = df_total[(df_total["Ngày"] >= start_year) & (df_total["Ngày"] <= change_date_dt)]

    df_hours_plan = pd.DataFrame({"Nhân viên": staff})
    df_hours_plan["Giờ tháng (đến ngày phân ca)"] = df_hours_plan["Nhân viên"].map(
        df_m_plan.groupby("Nhân viên")["Giờ"].sum()
    ).fillna(0)
    df_hours_plan["Giờ năm (đến ngày phân ca)"] = df_hours_plan["Nhân viên"].map(
        df_y_plan.groupby("Nhân viên")["Giờ"].sum()
    ).fillna(0)

    # ================= HIỂN THỊ =================
    st.subheader("📅 Lịch trực")
    st.dataframe(df_export, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏱️ Tổng giờ làm việc – ĐẾN HIỆN TẠI")
        st.dataframe(df_hours_today, use_container_width=True)
    with col2:
        st.subheader("📌 Tổng giờ làm việc – ĐẾN THỜI ĐIỂM PHÂN CA")
        st.dataframe(df_hours_plan, use_container_width=True)

    # ================= GHI GOOGLE SHEET =================
    df_save = df_total.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")

    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save.reset_index(drop=True))
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_export.reset_index(drop=True))

    st.success("✅ Đã cập nhật lịch thành công!")

else:
    # HIỂN THỊ DỮ LIỆU CŨ KHI CHƯA BẤM NÚT
    st.info("Nhấn nút '🚀 TẠO LỊCH & CẬP NHẬT' để tính toán lịch mới.")
    if not df_raw.empty:
        st.subheader("⏱️ Tổng giờ làm việc hiện tại (từ database)")
        # Logic tính giờ nhanh từ df_raw có sẵn
        start_month = pd.to_datetime(today.replace(day=1))
        df_m = df_raw[df_raw["Ngày"] >= start_month]
        df_summary = pd.DataFrame({"Nhân viên": staff})
        df_summary["Giờ tháng hiện tại"] = df_summary["Nhân viên"].map(df_m.groupby("Nhân viên")["Giờ"].sum()).fillna(0)
        st.dataframe(df_summary, use_container_width=True)
