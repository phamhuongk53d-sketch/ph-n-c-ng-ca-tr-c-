import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# Cấu hình trang
st.set_page_config(page_title="Phần mềm Phân ca Trực", layout="wide")

st.title("📅 Hệ thống Phân công Ca trực Tự động")
st.markdown("---")

# --- PHẦN 1: NHẬP DỮ LIỆU ---
with st.sidebar:
    st.header("Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên (cách nhau bằng dấu phẩy)", 
                               "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",")]
    
    special_staff = st.multiselect("Nhân viên CHỈ trực ca ngày (8h-16h)", staff, default=["Trung", "Ngà"])
    
    st.header("Thời gian & Giới hạn")
    month = st.number_input("Tháng", min_value=1, max_value=12, value=datetime.now().month)
    year = st.number_input("Năm", min_value=2024, max_value=2030, value=datetime.now().year)
    max_hours = st.number_input("Số giờ tối đa/người", value=176)

    st.header("Bù giờ tháng trước")
    carried_over = {}
    for s in staff:
        carried_over[s] = st.number_input(f"Giờ đã làm tháng trước của {s}", value=0)

# --- PHẦN 2: QUẢN LÝ NGƯỜI BẬN ---
st.subheader("📍 Đăng ký ngày bận (Nghỉ)")
if 'busy_dates' not in st.session_state:
    st.session_state.busy_dates = {}

col1, col2, col3 = st.columns([2, 3, 1])
with col1:
    date_b = st.date_input("Chọn ngày nhân viên bận")
with col2:
    people_b = st.multiselect("Chọn những người bận vào ngày này", staff)
with col3:
    if st.button("Thêm vào danh sách bận"):
        st.session_state.busy_dates[str(date_b)] = people_b
        st.success(f"Đã lưu ngày {date_b}")

if st.session_state.busy_dates:
    with st.expander("Xem danh sách bận hiện tại"):
        st.write(st.session_state.busy_dates)
        if st.button("Xóa tất cả danh sách bận"):
            st.session_state.busy_dates = {}
            st.rerun()

# --- PHẦN 3: THUẬT TOÁN PHÂN CA ---
def generate_schedule():
    days_in_month = pd.Period(f"{year}-{month}").days_in_month
    schedule_data = []
    work_hours = {s: carried_over.get(s, 0) for s in staff}
    available_at = {s: datetime(year, month, 1, 0, 0) for s in staff}
    normal_staff = [s for s in staff if s not in special_staff]

    for day in range(1, days_in_month + 1):
        curr_date = datetime(year, month, day)
        curr_date_str = str(curr_date.date())
        busy_today = st.session_state.busy_dates.get(curr_date_str, [])

        # Ca Ngày
        shift_day_start = curr_date.replace(hour=8)
        pot_day = [s for s in staff if available_at[s] <= shift_day_start and s not in busy_today and work_hours[s] + 8 <= max_hours]
        pot_day.sort(key=lambda s: (0 if s in special_staff else 1, work_hours[s]))
        
        assigned_day = pot_day[:2]
        for s in assigned_day:
            schedule_data.append({"Ngày": curr_date_str, "Ca": "Ngày (8-16h)", "Nhân viên": s, "Giờ": 8})
            work_hours[s] += 8
            available_at[s] = curr_date.replace(hour=16) + timedelta(hours=16)

        # Ca Đêm
        shift_night_start = curr_date.replace(hour=16)
        pot_night = [s for s in normal_staff if available_at[s] <= shift_night_start and s not in busy_today and work_hours[s] + 16 <= max_hours]
        pot_night.sort(key=lambda s: work_hours[s])
        
        assigned_night = pot_night[:2]
        for s in assigned_night:
            schedule_data.append({"Ngày": curr_date_str, "Ca": "Đêm (16-8h)", "Nhân viên": s, "Giờ": 16})
            work_hours[s] += 16
            available_at[s] = curr_date.replace(hour=8) + timedelta(days=1, hours=24)

    return pd.DataFrame(schedule_data), pd.DataFrame(list(work_hours.items()), columns=['Nhân viên', 'Tổng giờ'])

# --- PHẦN 4: HIỂN THỊ KẾT QUẢ & XUẤT EXCEL ---
if st.button("🚀 CHẠY PHÂN CA TRỰC"):
    df_main, df_summary = generate_schedule()
    
    col_res1, col_res2 = st.columns([3, 1])
    with col_res1:
        st.subheader("Bảng phân ca chi tiết")
        st.dataframe(df_main, use_container_width=True)
    
    with col_res2:
        st.subheader("Tổng hợp giờ làm")
        st.dataframe(df_summary, use_container_width=True)

    # Xuất file Excel vào bộ nhớ để tải về
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='Lich_Chi_Tiet', index=False)
        df_summary.to_excel(writer, sheet_name='Tong_Hop_Gio', index=False)
    
    st.download_button(
        label="📥 Tải về file Excel",
        data=output.getvalue(),
        file_name=f"Lich_Truc_{month}_{year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )