import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH HỆ THỐNG
# ==================================================
st.set_page_config(
    page_title="Hệ thống phân công trực – Tối ưu hóa",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"

REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH (HELPER FUNCTIONS)
# ==================================================
def vn_day(d):
    """Định dạng ngày sang kiểu Việt Nam: T2 15/01/2026"""
    return ["T2","T3","T4","T5","T6","T7","CN"][d.weekday()] + " " + d.strftime("%d/%m/%Y")

def clean_dataframe(df):
    """Làm sạch và chuẩn hóa cấu trúc DataFrame"""
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    # Chuyển đổi Ngày sang Datetime chuẩn của Pandas
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    # Chuyển đổi Giờ sang Số
    df["Giờ"] = pd.to_numeric(df["Giờ"], errors="coerce").fillna(0)
    return df.dropna(subset=["Ngày"])

def group_view(df):
    """Gộp các dòng nhân viên lẻ thành một dòng hiển thị (Ca ngày: A, B)"""
    return (
        df.groupby(["Ngày", "Ca"], as_index=False)
        .agg({"Nhân viên": lambda x: ", ".join(sorted(x)), "Giờ": "sum"})
        .sort_values("Ngày")
    )

def calculate_summary(df_source, staff_list, end_date_limit, label_m, label_y):
    """Hàm tính toán tổng giờ làm việc chính xác"""
    # Chuẩn hóa mốc thời gian để so sánh
    today_ts = pd.Timestamp(datetime.now().date())
    ref_date = pd.Timestamp(end_date_limit)
    start_month = ref_date.replace(day=1)
    start_year = ref_date.replace(month=1, day=1)

    # Lọc dữ liệu trong khoảng
    df_m = df_source[(df_source["Ngày"] >= start_month) & (df_source["Ngày"] <= ref_date)]
    df_y = df_source[(df_source["Ngày"] >= start_year) & (df_source["Ngày"] <= ref_date)]

    summary = pd.DataFrame({"Nhân viên": staff_list})
    summary[label_m] = summary["Nhân viên"].map(df_m.groupby("Nhân viên")["Giờ"].sum()).fillna(0)
    summary[label_y] = summary["Nhân viên"].map(df_y.groupby("Nhân viên")["Giờ"].sum()).fillna(0)
    return summary

# ==================================================
# ĐỌC DỮ LIỆU GỐC
# ==================================================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_raw = clean_dataframe(df_raw)
except Exception:
    df_raw = pd.DataFrame(columns=REQUIRED_COLS)

today = datetime.now().date()

# ==================================================
# THANH CÀI ĐẶT (SIDEBAR)
# ==================================================
with st.sidebar:
    st.header("⚙️ Cài đặt")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect("Chỉ trực ca ngày", staff, default=["Trung", "Ngà"])
    
    st.divider()
    end_date = st.date_input("Tạo lịch đến hết ngày", today + timedelta(days=30))
    change_date = st.date_input("Thời điểm áp dụng lịch mới", today)
    absent_staff = st.multiselect("Nhân sự nghỉ", staff)

# ==================================================
# LOGIC PHÂN CA
# ==================================================
def generate_schedule(start_d, end_d, staff_list, special_list, absent_list):
    rows = []
    active = [s for s in staff_list if s not in absent_list]
    # Trạng thái sẵn sàng của nhân viên (tính từ ngày hôm trước của ngày bắt đầu)
    available = {s: datetime.combine(start_d - timedelta(days=1), datetime.min.time()) for s in active}

    curr_d = start_d
    while curr_d <= end_d:
        base = datetime.combine(curr_d, datetime.min.time())
        
        # 1. PHÂN CA NGÀY (08-16h)
        day_cand = [s for s in active if available[s] <= base.replace(hour=8)]
        # Ưu tiên người chỉ trực ngày lên đầu
        day_cand.sort(key=lambda s: (0 if s in special_list else 1))
        
        for s in day_cand[:2]:
            rows.append({"Ngày": curr_d, "Ca": "Ca ngày (08–16)", "Nhân viên": s, "Giờ": 8})
            available[s] = base.replace(hour=16) + timedelta(hours=16) # Nghỉ ít nhất 16h

        # 2. PHÂN CA ĐÊM (16-08h)
        night_cand = [s for s in active if s not in special_list and available[s] <= base.replace(hour=16)]
        # Ưu tiên người có thời gian nghỉ lâu nhất (để xoay vòng đều)
        night_cand.sort(key=lambda s: available[s])
        
        for s in night_cand[:2]:
            rows.append({"Ngày": curr_d, "Ca": "Ca đêm (16–08)", "Nhân viên": s, "Giờ": 16})
            available[s] = base + timedelta(days=2) # Nghỉ 1 ngày sau ca đêm

        curr_d += timedelta(days=1)
    return pd.DataFrame(rows)

# ==================================================
# XỬ LÝ CHÍNH
# ==================================================
if change_date < today:
    st.error("⛔ Không được phân lịch cho ngày đã qua.")
    st.stop()

# Tách lịch sử và phần sẽ ghi đè
old_part = df_raw[df_raw["Ngày"].dt.date < change_date].copy()

if st.button("🚀 TẠO LỊCH & CẬP NHẬT"):
    # 1. Tạo dữ liệu mới
    df_new = generate_schedule(change_date, end_date, staff, special_staff, absent_staff)
    df_new["Ngày"] = pd.to_datetime(df_new["Ngày"])
    
    # 2. Hợp nhất
    df_total = pd.concat([old_part, df_new], ignore_index=True)
    
    # 3. Tính toán các bảng giờ (Dùng df_total để có số liệu mới nhất)
    df_hours_today = calculate_summary(df_total, staff, today, "Giờ tháng (đến hôm nay)", "Giờ năm (đến hôm nay)")
    df_hours_plan = calculate_summary(df_total, staff, change_date, "Giờ tháng (đến ngày phân ca)", "Giờ năm (đến ngày phân ca)")
    
    # 4. Chuẩn bị bản in (View)
    df_view_raw = group_view(df_total)
    export_rows = []
    for (y, m), g in df_view_raw.groupby([df_view_raw["Ngày"].dt.year, df_view_raw["Ngày"].dt.month]):
        export_rows.append({"Ngày": f"--- THÁNG {m}/{y} ---", "Ca": "", "Nhân viên": "", "Giờ": ""})
        for _, r in g.iterrows():
            export_rows.append({"Ngày": vn_day(r["Ngày"]), "Ca": r["Ca"], "Nhân viên": r["Nhân viên"], "Giờ": r["Giờ"]})
    df_export = pd.DataFrame(export_rows)

    # 5. HIỂN THỊ KẾT QUẢ
    st.subheader("📅 Lịch trực mới nhất")
    st.dataframe(df_export, use_container_width=True, height=400)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("⏱️ Tổng giờ - ĐẾN HIỆN TẠI")
        st.dataframe(df_hours_today, use_container_width=True)
    with c2:
        st.subheader("📌 Tổng giờ - ĐẾN NGÀY PHÂN CA")
        st.dataframe(df_hours_plan, use_container_width=True)

    # 6. GHI DỮ LIỆU
    with st.spinner("Đang lưu vào Google Sheets..."):
        df_save = df_total.copy()
        df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_export)
        st.success("✅ Đã cập nhật database thành công!")

else:
    st.info("Nhấn nút phía trên để tính toán và cập nhật lịch.")
    if not df_raw.empty:
        st.subheader("📊 Thống kê giờ làm việc hiện tại (Từ Database)")
        df_current_stat = calculate_summary(df_raw, staff, today, "Giờ tháng hiện tại", "Giờ năm hiện tại")
        st.dataframe(df_current_stat, use_container_width=True)
