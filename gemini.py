import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Hệ thống Trực Công Bằng 2025", layout="wide")

# --- CẤU HÌNH CỐ ĐỊNH ---
# Thay ID_FILE_CỦA_BẠN bằng chuỗi ký tự nằm giữa /d/ và /edit trên link trình duyệt của bạn
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?gid=726349550#gid=726349550"

# --- KẾT NỐI GOOGLE SHEETS ---
# Tự động sử dụng cấu hình Service Account trong .streamlit/secrets.toml hoặc Streamlit Cloud Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- HÀM HỖ TRỢ ĐỊNH DẠNG ---
def get_vietnamese_weekday(date_obj):
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[date_obj.weekday()]}- {date_obj.strftime('%d/%m')}"

# 1. ĐỌC DỮ LIỆU THÔ ĐỂ TÍNH TOÁN
try:
    # Đọc từ sheet Data_Log (nơi lưu mỗi người 1 dòng để máy tính hiểu)
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log")
    df_raw['Ngày'] = pd.to_datetime(df_raw['Ngày']).dt.date
except Exception as e:
    st.error(f"Không thể đọc sheet Data_Log. Hãy đảm bảo Service Account đã có quyền Editor. Lỗi: {e}")
    df_raw = pd.DataFrame(columns=['Ngày', 'Ca', 'Nhân viên', 'Giờ'])

# --- SIDEBAR CẤU HÌNH ---
with st.sidebar:
    st.header("Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên hiện tại", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",")]
    special_staff = st.multiselect("Chỉ trực ca ngày", staff, default=["Trung", "Ngà"])
    
    st.header("Thời gian phân lịch")
    start_date = st.date_input("Phân lịch từ ngày:", datetime.now().date())
    end_date = st.date_input("Đến hết ngày:", (datetime.now() + timedelta(days=30)).date())

# --- TÍNH TỔNG GIỜ LŨY KẾ ---
history_before = df_raw[df_raw['Ngày'] < start_date]
luy_ke_hours = {s: history_before[history_before['Nhân viên'] == s]['Giờ'].sum() for s in staff}

st.subheader(f"📊 Tổng giờ lũy kế tính đến trước ngày {start_date}")
st.write(pd.DataFrame([luy_ke_hours]))

# --- ĐĂNG KÝ NGÀY BẬN ---
if 'busy_dates' not in st.session_state: st.session_state.busy_dates = {}
with st.expander("📍 Đăng ký nhân viên nghỉ/bận"):
    c1, c2 = st.columns(2)
    d_b = c1.date_input("Chọn ngày bận")
    p_b = c2.multiselect("Người nghỉ", staff)
    if st.button("Xác nhận nghỉ"):
        st.session_state.busy_dates[str(d_b)] = p_b

# --- THUẬT TOÁN PHÂN LỊCH ---
def generate_dynamic_schedule():
    new_raw_entries = []
    current_work_hours = luy_ke_hours.copy()
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}
    
    current_day = start_date
    while current_day <= end_date:
        curr_datetime = datetime.combine(current_day, datetime.min.time())
        busy_today = st.session_state.busy_dates.get(str(current_day), [])

        # --- CA NGÀY (8h-16h) ---
        shift_start = curr_datetime.replace(hour=8)
        pot_day = [s for s in staff if available_at[s] <= shift_start and s not in busy_today]
        pot_day.sort(key=lambda s: (0 if s in special_staff else 1, current_work_hours[s]))
        
        assigned_day = pot_day[:2]
        for s in assigned_day:
            new_raw_entries.append({"Ngày": current_day, "Ca": "Ca: 8h00' – 16h00'", "Nhân viên": s, "Giờ": 8})
            current_work_hours[s] += 8
            available_at[s] = curr_datetime.replace(hour=16) + timedelta(hours=16)

        # --- CA ĐÊM (16h-8h) ---
        shift_start_n = curr_datetime.replace(hour=16)
        pot_night = [s for s in staff if s not in special_staff and available_at[s] <= shift_start_n and s not in busy_today]
        pot_night.sort(key=lambda s: current_work_hours[s])
        
        assigned_night = pot_night[:2]
        for s in assigned_night:
            new_raw_entries.append({"Ngày": current_day, "Ca": "Ca: 16h00' – 8h00'", "Nhân viên": s, "Giờ": 16})
            current_work_hours[s] += 16
            available_at[s] = curr_datetime.replace(hour=8) + timedelta(days=1, hours=24)
        
        current_day += timedelta(days=1)
    return pd.DataFrame(new_raw_entries)

# --- XỬ LÝ KẾT QUẢ ---
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT LÊN CLOUD"):
    df_new_raw = generate_dynamic_schedule()
    
    # 1. Gộp dữ liệu thô (Để lần sau tính toán lũy kế)
    df_final_raw = pd.concat([history_before, df_new_raw], ignore_index=True)
    
    # 2. Tạo bản hiển thị đẹp mắt (Giống ảnh mẫu)
    df_display = df_final_raw.copy()
    df_display['Ngày_Hien_Thi'] = df_display['Ngày'].apply(get_vietnamese_weekday)
    
    # Gộp tên và Pivot
    df_pivot = df_display.groupby(['Ngày_Hien_Thi', 'Ca'])['Nhân viên'].apply(lambda x: ' '.join(x)).reset_index()
    df_pivot = df_pivot.pivot(index='Ngày_Hien_Thi', columns='Ca', values='Nhân viên').reset_index()
    
    # Sắp xếp và đổi tên cột
    cols = ['Ngày_Hien_Thi', "Ca: 8h00' – 16h00'", "Ca: 16h00' – 8h00'"]
    df_pivot = df_pivot.reindex(columns=cols).fillna("")
    df_pivot.rename(columns={'Ngày_Hien_Thi': 'Ngày'}, inplace=True)

    st.subheader("🗓️ Lịch trực mới (Đã gộp ca)")
    st.table(df_pivot)

    # 3. GHI LÊN GOOGLE SHEETS
    try:
        # Ghi đè vào sheet thô để máy lưu lịch sử
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_final_raw)
        # Ghi đè vào sheet hiển thị để mọi người xem
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_pivot)
        st.success("✅ Đã cập nhật lịch thành công lên Google Sheets!")
    except Exception as e:
        st.error(f"Lỗi khi lưu dữ liệu: {e}. Hãy kiểm tra xem Service Account đã được cấp quyền Editor cho file chưa.")

