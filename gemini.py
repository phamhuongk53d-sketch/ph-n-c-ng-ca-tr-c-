import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Hệ thống Trực Công Bằng 2025", layout="wide")

# --- CẤU HÌNH ---
# Thay ID thực tế của bạn vào đây
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing "

conn = st.connection("gsheets", type=GSheetsConnection)

def get_vietnamese_weekday(date_obj):
    if pd.isnull(date_obj): return ""
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[date_obj.weekday()]}- {date_obj.strftime('%d/%m')}"

# 1. ĐỌC DỮ LIỆU THÔ (Xử lý lỗi Response [200] và Định dạng ngày)
try:
    # Sử dụng tham số ttl=0 để luôn lấy dữ liệu mới nhất
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        # Khắc phục lỗi Screenshot 022813: ép kiểu ngày tháng linh hoạt
        df_raw['Ngày'] = pd.to_datetime(df_raw['Ngày'], dayfirst=True, errors='coerce').dt.date
        df_raw = df_raw.dropna(subset=['Ngày'])
    else:
        df_raw = pd.DataFrame(columns=['Ngày', 'Ca', 'Nhân viên', 'Giờ'])
except Exception:
    # Nếu sheet trống hoặc lỗi kết nối ban đầu, khởi tạo bảng rỗng
    df_raw = pd.DataFrame(columns=['Ngày', 'Ca', 'Nhân viên', 'Giờ'])
    st.info("💡 Hệ thống đang bắt đầu với dữ liệu mới.")

# --- SIDEBAR CẤU HÌNH ---
with st.sidebar:
    st.header("Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",")]
    special_staff = st.multiselect("Chỉ trực ca ngày", staff, default=["Trung", "Ngà"])
    
    st.header("Thời gian phân lịch")
    start_date = st.date_input("Phân lịch từ ngày:", datetime.now().date())
    end_date = st.date_input("Đến hết ngày:", (datetime.now() + timedelta(days=30)).date())

# --- TÍNH LŨY KẾ ---
history_before = df_raw[df_raw['Ngày'] < start_date]
luy_ke_hours = {s: history_before[history_before['Nhân viên'] == s]['Giờ'].sum() for s in staff}

st.subheader(f"📊 Tổng giờ lũy kế tính đến ngày {start_date - timedelta(days=1)}")
st.write(pd.DataFrame([luy_ke_hours]))

# --- THUẬT TOÁN PHÂN LỊCH ---
def generate_schedule():
    new_entries = []
    work_hours = luy_ke_hours.copy()
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}
    
    curr = start_date
    while curr <= end_date:
        curr_dt = datetime.combine(curr, datetime.min.time())
        busy_today = st.session_state.get('busy_dates', {}).get(str(curr), [])

        # Ca Ngày
        pot_day = [s for s in staff if available_at[s] <= curr_dt.replace(hour=8) and s not in busy_today]
        pot_day.sort(key=lambda s: (0 if s in special_staff else 1, work_hours[s]))
        for s in pot_day[:2]:
            new_entries.append({"Ngày": curr, "Ca": "Ca: 8h00' – 16h00'", "Nhân viên": s, "Giờ": 8})
            work_hours[s] += 8
            available_at[s] = curr_dt.replace(hour=16) + timedelta(hours=16)

        # Ca Đêm
        pot_night = [s for s in staff if s not in special_staff and available_at[s] <= curr_dt.replace(hour=16) and s not in busy_today]
        pot_night.sort(key=lambda s: work_hours[s])
        for s in pot_night[:2]:
            new_entries.append({"Ngày": curr, "Ca": "Ca: 16h00' – 8h00'", "Nhân viên": s, "Giờ": 16})
            work_hours[s] += 16
            available_at[s] = curr_dt.replace(hour=8) + timedelta(days=2) # Nghỉ 24h sau ca đêm
        
        curr += timedelta(days=1)
    return pd.DataFrame(new_entries)

# --- XỬ LÝ LƯU ---
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    df_new = generate_schedule()
    df_total_raw = pd.concat([history_before, df_new], ignore_index=True)
    
    # Tạo bản hiển thị (Giống ảnh h1.jpg)
    df_view = df_total_raw.copy()
    df_view['Ngày_HT'] = pd.to_datetime(df_view['Ngày']).apply(get_vietnamese_weekday)
    
    # Gộp tên nhân viên cùng ca
    df_pivot = df_view.groupby(['Ngày_HT', 'Ca'])['Nhân viên'].apply(lambda x: ' '.join(x)).reset_index()
    df_pivot = df_pivot.pivot(index='Ngày_HT', columns='Ca', values='Nhân viên').reset_index()
    
    # Sắp xếp cột đúng mẫu
    target_cols = ['Ngày_HT', "Ca: 8h00' – 16h00'", "Ca: 16h00' – 8h00'"]
    df_pivot = df_pivot.reindex(columns=target_cols).fillna("")
    df_pivot.rename(columns={'Ngày_HT': 'Ngày'}, inplace=True)

    st.subheader("🗓️ Lịch trực mới")
    st.table(df_pivot)

    # Ghi dữ liệu - Khắc phục lỗi ghi dữ liệu
    try:
        # Ghi vào Data_Log (dạng thô)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_total_raw)
        # Ghi vào Lich_Truc (dạng hiển thị gộp tên)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_pivot)
        st.success("✅ Đã lưu thành công lên Google Sheets!")
    except Exception as e:
        st.error(f"Lỗi ghi dữ liệu: {e}. Vui lòng kiểm tra quyền Editor của Service Account.")

