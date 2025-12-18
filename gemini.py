import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Hệ thống Trực Công Bằng 2025", layout="wide")

# --- CẤU HÌNH ---
# Thay ID_FILE thực tế của bạn vào đây
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing "
conn = st.connection("gsheets", type=GSheetsConnection)

def get_vietnamese_weekday(date_obj):
    if pd.isnull(date_obj): return ""
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[date_obj.weekday()]}- {date_obj.strftime('%d/%m')}"

# 1. ĐỌC DỮ LIỆU THÔ (Khắc phục lỗi Response [200])
try:
    # Thêm ttl=0 để luôn đọc dữ liệu mới nhất, tránh cache lỗi
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        # Sửa lỗi định dạng ngày tháng: ép kiểu linh hoạt
        df_raw['Ngày'] = pd.to_datetime(df_raw['Ngày'], dayfirst=True, errors='coerce').dt.date
        df_raw = df_raw.dropna(subset=['Ngày'])
    else:
        df_raw = pd.DataFrame(columns=['Ngày', 'Ca', 'Nhân viên', 'Giờ'])
except Exception as e:
    # Nếu lỗi Response [200], khởi tạo bảng trống thay vì dừng chương trình
    df_raw = pd.DataFrame(columns=['Ngày', 'Ca', 'Nhân viên', 'Giờ'])
    st.info("💡 Lưu ý: Đang bắt đầu với dữ liệu mới (Data_Log trống hoặc mới khởi tạo).")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên hiện tại", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
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

# --- ĐĂNG KÝ BẬN ---
if 'busy_dates' not in st.session_state: st.session_state.busy_dates = {}
with st.expander("📍 Đăng ký nhân viên nghỉ/bận"):
    c1, c2 = st.columns(2)
    d_b = c1.date_input("Chọn ngày")
    p_b = c2.multiselect("Người nghỉ", staff)
    if st.button("Xác nhận nghỉ"):
        st.session_state.busy_dates[str(d_b)] = p_b

# --- THUẬT TOÁN ---
def generate_dynamic_schedule():
    new_raw_entries = []
    current_work_hours = luy_ke_hours.copy()
    # Nghỉ tối thiểu 16h
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}
    
    current_day = start_date
    while current_day <= end_date:
        curr_dt = datetime.combine(current_day, datetime.min.time())
        busy_today = st.session_state.busy_dates.get(str(current_day), [])

        # Ca Ngày
        pot_day = [s for s in staff if available_at[s] <= curr_dt.replace(hour=8) and s not in busy_today]
        pot_day.sort(key=lambda s: (0 if s in special_staff else 1, current_work_hours[s]))
        for s in pot_day[:2]:
            new_raw_entries.append({"Ngày": current_day, "Ca": "Ca: 8h00' – 16h00'", "Nhân viên": s, "Giờ": 8})
            current_work_hours[s] += 8
            available_at[s] = curr_dt.replace(hour=16) + timedelta(hours=16)

        # Ca Đêm
        pot_night = [s for s in staff if s not in special_staff and available_at[s] <= curr_dt.replace(hour=16) and s not in busy_today]
        pot_night.sort(key=lambda s: current_work_hours[s])
        for s in pot_night[:2]:
            new_raw_entries.append({"Ngày": current_day, "Ca": "Ca: 16h00' – 8h00'", "Nhân viên": s, "Giờ": 16})
            current_work_hours[s] += 16
            available_at[s] = curr_dt.replace(hour=8) + timedelta(days=1, hours=24)
        
        current_day += timedelta(days=1)
    return pd.DataFrame(new_raw_entries)

# --- XỬ LÝ LƯU ---
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    df_new_raw = generate_dynamic_schedule()
    df_final_raw = pd.concat([history_before, df_new_raw], ignore_index=True)
    
    # Tạo bản hiển thị gộp (theo ảnh h1.jpg)
    df_display = df_final_raw.copy()
    df_display['Ngày_HT'] = pd.to_datetime(df_display['Ngày']).apply(get_vietnamese_weekday)
    
    df_p = df_display.groupby(['Ngày_HT', 'Ca'])['Nhân viên'].apply(lambda x: ' '.join(x)).reset_index()
    df_p = df_p.pivot(index='Ngày_HT', columns='Ca', values='Nhân viên').reset_index()
    
    cols = ['Ngày_HT', "Ca: 8h00' – 16h00'", "Ca: 16h00' – 8h00'"]
    df_p = df_p.reindex(columns=cols).fillna("")
    df_p.rename(columns={'Ngày_HT': 'Ngày'}, inplace=True)

    st.subheader("🗓️ Lịch trực mới")
    st.table(df_p)

    try:
        # Quan trọng: Ghi dữ liệu thô vào Data_Log trước
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_final_raw)
        # Sau đó ghi bản gộp vào Lich_Truc
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_p)
        st.success("✅ Đã lưu thành công!")
    except Exception as e:
        st.error(f"Lỗi ghi dữ liệu: {e}")

