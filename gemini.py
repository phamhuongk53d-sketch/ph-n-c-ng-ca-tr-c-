import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH TRANG & KẾT NỐI
# ==================================================
st.set_page_config(page_title="Hệ thống Lịch trực ca & Thống kê", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"
REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# 2. HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    """Định dạng ngày tiếng Việt: T2 - 01/01/2024"""
    days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{days[d.weekday()]} - {d.strftime('%d/%m/%Y')}"

def ensure_df(df):
    """Đảm bảo DataFrame đúng cấu trúc"""
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

def parse_date(df):
    """Chuyển đổi cột Ngày sang datetime"""
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Ngày"])

# ==================================================
# 3. ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
try:
    # Đọc dữ liệu gốc từ sheet Data_Log
    df_old = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_old = ensure_df(df_old)
    df_old = parse_date(df_old)
    df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)
except Exception as e:
    st.error(f"Lỗi kết nối dữ liệu: {e}")
    df_old = pd.DataFrame(columns=REQUIRED_COLS)

# ==================================================
# 4. SIDEBAR - CẤU HÌNH NHÂN SỰ & THỜI GIAN
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình hệ thống")
    
    st.subheader("👥 Nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên (cách nhau bởi dấu phẩy)",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = ["Trung", "Ngà"] # Chỉ trực ca ngày trong tuần

    st.subheader("📅 Khoảng thời gian")
    start_date = st.date_input("Ngày bắt đầu lịch mới", datetime.now().date())
    end_date = st.date_input("Ngày kết thúc", start_date + timedelta(days=30))

    st.subheader("🔄 Thay đổi nhân sự")
    change_date = st.date_input("Áp dụng từ ngày", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ / bận", staff)

# ==================================================
# 5. LOGIC PHÂN CA TỰ ĐỘNG
# ==================================================
def generate_schedule():
    rows = []
    # Lấy dữ liệu cố định trước ngày thay đổi
    df_fixed = df_old[df_old["Ngày"].dt.date < change_date].copy()
    
    # Tính giờ lũy kế từ quá khứ
    current_hours = {s: df_fixed[df_fixed["Nhân viên"] == s]["Giờ"].sum() for s in staff}
    
    active_staff = [s for s in staff if s not in absent_staff]
    available_at = {s: datetime.min for s in active_staff}

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5

        # --- PHÂN CA NGÀY (8h - 16h) ---
        day_candidates = []
        for s in active_staff:
            if available_at[s] <= base.replace(hour=8):
                if s in special_staff:
                    if is_weekday: day_candidates.append(s)
                else:
                    day_candidates.append(s)
        
        day_candidates.sort(key=lambda s: current_hours[s])
        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca ngày", "Nhân viên": s, "Giờ": 8})
            current_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # --- PHÂN CA ĐÊM (16h - 8h sáng mai) ---
        night_candidates = [
            s for s in active_staff 
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: current_hours[s])

        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm", "Nhân viên": s, "Giờ": 16})
            current_hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    df_new = pd.DataFrame(rows)
    df_new["Ngày"] = pd.to_datetime(df_new["Ngày"])
    return pd.concat([df_fixed, df_new], ignore_index=True).sort_values("Ngày")

# ==================================================
# 6. GIAO DIỆN CHÍNH
# ==================================================
st.title("🗓️ Quản lý Lịch trực & Tổng hợp công")

# Kiểm tra ngày quá khứ
today = datetime.now().date()
if start_date < today or change_date < today:
    st.warning("⚠️ Lưu ý: Bạn đang thao tác trên các ngày đã qua hoặc hiện tại.")

# --- KHỐI 1: TẠO LỊCH ---
if st.button("🚀 TẠO / CẬP NHẬT LỊCH TRỰC", type="primary"):
    with st.spinner("Đang tính toán lịch trực tối ưu..."):
        df_all = generate_schedule()
        
        # Hiển thị bảng lịch trực
        display_rows = []
        for d, g in df_all.groupby("Ngày", sort=False):
            display_rows.append({
                "Ngày": vn_day(d),
                "Ca: 8h00 – 16h00": ", ".join(g[g["Ca"] == "Ca ngày"]["Nhân viên"]),
                "Ca: 16h00 – 8h00": ", ".join(g[g["Ca"] == "Ca đêm"]["Nhân viên"])
            })
        df_display = pd.DataFrame(display_rows)
        
        st.subheader("📋 LỊCH TRỰC CHI TIẾT")
        st.dataframe(df_display, use_container_width=True, height=400)

        # Lưu vào Google Sheets
        df_save = df_all.copy()
        df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_display)
        st.success("✅ Đã cập nhật lịch mới lên Google Sheets!")

st.write("---")

# --- KHỐI 2: THỐNG KÊ TỔNG GIỜ ---
st.subheader("📊 THỐNG KÊ TỔNG GIỜ TRỰC")
st.info("Dữ liệu được lấy trực tiếp từ file Data_Log để đảm bảo tính chính xác theo thời gian thực.")

if st.button("🔢 TÍNH TỔNG SỐ GIỜ TRỰC"):
    if df_old.empty:
        st.error("❌ Không tìm thấy dữ liệu trong Data_Log.")
    else:
        # Xử lý dữ liệu thống kê
        df_stats = df_old.copy()
        df_stats['Tháng'] = df_stats['Ngày'].dt.month
        df_stats['Năm'] = df_stats['Ngày'].dt.year
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📅 Tổng giờ theo Tháng")
            summary_month = df_stats.groupby(['Nhân viên', 'Năm', 'Tháng'])['Giờ'].sum().reset_index()
            summary_month['Thời gian'] = summary_month.apply(lambda x: f"T{int(x['Tháng'])}/{int(x['Năm'])}", axis=1)
            pivot_month = summary_month.pivot(index='Nhân viên', columns='Thời gian', values='Giờ').fillna(0)
            st.dataframe(pivot_month.style.highlight_max(axis=0, color='#90ee90'), use_container_width=True)

        with col2:
            st.markdown("#### 🗓️ Tổng giờ theo Năm")
            summary_year = df_stats.groupby(['Nhân viên', 'Năm'])['Giờ'].sum().reset_index()
            pivot_year = summary_year.pivot(index='Nhân viên', columns='Năm', values='Giờ').fillna(0)
            st.dataframe(pivot_year.style.format("{:.0f} giờ"), use_container_width=True)
        
        st.balloons()

# Footer
st.markdown("---")
st.caption("Hệ thống tự động cân bằng giờ trực dựa trên nguyên tắc ưu tiên người có số giờ thấp nhất.")
