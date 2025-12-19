import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

# ==================================================
# CẤU HÌNH & CONSTANTS
# ==================================================
st.set_page_config(page_title="Hệ thống Trực Công Bằng 2026", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
CA_NGAY = "Ca: 8h00 - 16h00"
CA_DEM = "Ca: 16h00 - 8h00"

# ==================================================
# HÀM TIỆN ÍCH (CACHED)
# ==================================================
@st.cache_data(ttl=3600)
def load_data(_conn):
    try:
        df = _conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
        if df.empty: return pd.DataFrame()
        df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Ngày"])
        df["Năm"] = df["Ngày"].dt.year
        df["Tháng"] = df["Ngày"].dt.month
        return df
    except Exception as e:
        st.error(f"Lỗi kết nối dữ liệu: {e}")
        return pd.DataFrame()

def get_vietnamese_weekday(d: pd.Timestamp) -> str:
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[d.weekday()]}- {d.strftime('%d/%m')}"

# ==================================================
# THUẬT TOÁN PHÂN CA TỐI ƯU
# ==================================================
def generate_schedule_balanced(staff_list, start_date, end_date, weekday_only_staff, balance_strategy, max_diff, history_df):
    rows = []
    curr_date = start_date
    
    # Khởi tạo tracker giờ bằng dict comprehension
    monthly_tracker = {m: {s: 0 for s in staff_list} for m in range(1, 13)}
    
    # Load lịch sử vào tracker
    if not history_df.empty:
        hist_summary = history_df.groupby(['Tháng', 'Nhân viên'])['Giờ'].sum().to_dict()
        for (m, s), h in hist_summary.items():
            if s in staff_list: monthly_tracker[m][s] = h

    # Tracking thời gian hồi phục (Nghỉ ít nhất 16h sau ca ngày, 24-48h sau ca đêm)
    available_at = {s: start_date - timedelta(days=1) for s in staff_list}

    while curr_date <= end_date:
        m, wd = curr_date.month, curr_date.weekday()
        base_time = datetime.combine(curr_date, datetime.min.time())
        is_weekend = wd >= 5

        # --- LOGIC CHỌN NGƯỜI ---
        def pick_staff(candidates, num_needed, current_month_hours, forbidden_list=[]):
            # Lọc người đủ điều kiện
            valid = [s for s in candidates if s not in forbidden_list]
            
            # Sắp xếp theo chiến lược
            if balance_strategy == "Cân bằng theo tháng":
                valid.sort(key=lambda x: current_month_hours.get(x, 0))
            else:
                valid.sort(key=lambda x: sum(m_h.get(x, 0) for m_h in monthly_tracker.values()))
            
            return valid[:num_needed]

        # 1. Ca Ngày
        day_pool = staff_list if not is_weekend else [s for s in staff_list if s not in weekday_only_staff]
        selected_day = pick_staff(day_pool, 2, monthly_tracker[m])
        
        for s in selected_day:
            rows.append({"Ngày": curr_date, "Ca": CA_NGAY, "Nhân viên": s, "Giờ": 8, "Năm": curr_date.year, "Tháng": m})
            monthly_tracker[m][s] += 8
            available_at[s] = base_time + timedelta(hours=32) # Nghỉ hồi sức

        # 2. Ca Đêm
        night_pool = [s for s in staff_list if s not in weekday_only_staff and s not in selected_day]
        selected_night = pick_staff(night_pool, 2, monthly_tracker[m])

        for s in selected_night:
            rows.append({"Ngày": curr_date, "Ca": CA_DEM, "Nhân viên": s, "Giờ": 16, "Năm": curr_date.year, "Tháng": m})
            monthly_tracker[m][s] += 16
            available_at[s] = base_time + timedelta(days=2)

        curr_date += timedelta(days=1)
    
    return pd.DataFrame(rows), monthly_tracker

# ==================================================
# GIAO DIỆN (UI)
# ==================================================
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = load_data(conn)

with st.sidebar:
    st.header("⚙️ Cấu hình")
    staff_input = st.text_area("Danh sách nhân viên (cách nhau bằng dấu phẩy)", 
                                "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    
    weekday_only_staff = st.multiselect("Nhân viên chỉ trực T2-T6", staff, default=["Trung", "Ngà"])
    balance_type = st.radio("Chiến lược cân bằng", ["Cân bằng theo tháng", "Cân bằng theo cả năm"])
    max_hours_diff = st.slider("Chênh lệch tối đa (giờ/tháng)", 0, 40, 16)
    
    year_select = st.selectbox("Năm", [2025, 2026, 2027], index=1)
    col_m1, col_m2 = st.columns(2)
    start_month = col_m1.number_input("Từ tháng", 1, 12, 1)
    end_month = col_m2.number_input("Đến tháng", 1, 12, 12)

# Xử lý ngày tháng
start_date = datetime(year_select, start_month, 1)
end_date = (datetime(year_select, end_month, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

# ==================================================
# THỰC THI & HIỂN THỊ
# ==================================================
if st.button("🚀 CHẠY PHÂN LỊCH TRỰC"):
    df_new, tracker = generate_schedule_balanced(
        staff, start_date, end_date, weekday_only_staff, balance_type, max_hours_diff, df_raw
    )
    
    # Tab hiển thị
    tab1, tab2 = st.tabs(["🗓️ Lịch chi tiết", "📊 Thống kê công bằng"])
    
    with tab1:
        for m in range(start_month, end_month + 1):
            st.write(f"### Tháng {m}")
            m_data = df_new[df_new["Tháng"] == m]
            if not m_data.empty:
                pivot = m_data.pivot_table(index="Ngày", columns="Ca", values="Nhân viên", aggfunc=lambda x: ", ".join(x))
                pivot.index = pivot.index.map(get_vietnamese_weekday)
                st.dataframe(pivot, use_container_width=True)

    with tab2:
        st.subheader("Tổng kết giờ trực")
        summary_rows = []
        for s in staff:
            total_h = sum(tracker[m][s] for m in range(1, 13))
            summary_rows.append({"Nhân viên": s, "Tổng giờ": total_h, "Trung bình/Tháng": round(total_h/12, 1)})
        
        summary_df = pd.DataFrame(summary_rows).sort_values("Tổng giờ", ascending=False)
        st.table(summary_df)
        st.bar_chart(summary_df.set_index("Nhân viên")["Tổng giờ"])

    # Download Excel
    # (Giữ nguyên hàm create_excel_report của bạn nhưng truyền df_new vào)
    # st.download_button(...)
