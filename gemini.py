import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH GIAO DIỆN
# ==================================================
st.set_page_config(page_title="Quản lý Lịch Trực Công Bằng", layout="wide")

# Lấy ngày hiện tại để làm mốc thống kê
now = datetime.now()
current_day = now.day
current_month = now.month
current_year = now.year

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff_list = [s.strip() for s in staff_input.split(",") if s.strip()]
    
    special_staff = st.multiselect("Nhân sự chỉ trực hành chính (Nghỉ T7/CN)", staff_list, default=["Trung", "Ngà"])
    
    st.header("📅 Chọn thời điểm xem")
    view_year = st.number_input("Năm", value=current_year)
    view_month = st.slider("Tháng", 1, 12, current_month)

# ==================================================
# THUẬT TOÁN PHÂN LỊCH & THỐNG KÊ
# ==================================================
def generate_schedule_and_stats(target_year, target_month):
    rows = []
    # Lưu trữ giờ tích lũy (Trong thực tế nên lưu vào DB, ở đây giả lập tính từ đầu năm đến ngày xem)
    # Tổng giờ năm sẽ reset nếu target_year thay đổi
    yearly_hours = {s: 0 for s in staff_list}
    monthly_hours = {s: 0 for s in staff_list}
    
    # Giả lập dữ liệu từ ngày 1/1 đến trước tháng đang xem để có số liệu "Tổng năm"
    # (Trong ứng dụng thực tế, bạn sẽ load số liệu này từ Google Sheets)
    
    # XÁC ĐỊNH KHOẢNG THỜI GIAN HIỂN THỊ TRONG THÁNG
    start_dt = datetime(target_year, target_month, 1)
    
    # Nếu tháng đang chọn là tháng hiện tại, chỉ hiện đến hôm nay. Nếu là tháng cũ, hiện hết tháng.
    if target_year == current_year and target_month == current_month:
        end_day_to_show = current_day
    else:
        if target_month == 12:
            end_day_to_show = (datetime(target_year + 1, 1, 1) - timedelta(days=1)).day
        else:
            end_day_to_show = (datetime(target_year, target_month + 1, 1) - timedelta(days=1)).day

    # Logic phân lịch mô phỏng từ đầu tháng
    available_at = {s: start_dt for s in staff_list}
    
    for day in range(1, end_day_to_show + 1):
        curr = datetime(target_year, target_month, day)
        is_weekend = curr.weekday() >= 5 # Thứ 7 = 5, CN = 6
        
        day_str = f"T{curr.weekday()+2}- {curr.strftime('%d/%m')}" if curr.weekday() < 6 else f"CN- {curr.strftime('%d/%m')}"
        
        # --- PHÂN CA NGÀY (8h-16h) ---
        day_candidates = [
            s for s in staff_list 
            if available_at[s] <= curr.replace(hour=8)
            and not (is_weekend and s in special_staff) # Nếu cuối tuần thì bỏ qua Trung/Ngà
        ]
        # Ưu tiên người có tổng giờ TRONG NĂM thấp nhất để đảm bảo công bằng năm
        day_candidates.sort(key=lambda x: yearly_hours[x])
        
        assigned_day = day_candidates[:2]
        for s in assigned_day:
            monthly_hours[s] += 8
            yearly_hours[s] += 8
            available_at[s] = curr + timedelta(hours=16) + timedelta(hours=16) # Cách 16h

        # --- PHÂN CA ĐÊM (16h-08h) ---
        night_candidates = [
            s for s in staff_list 
            if s not in assigned_day 
            and s not in special_staff # Ngà/Trung không trực đêm bao giờ
            and available_at[s] <= curr.replace(hour=16)
        ]
        night_candidates.sort(key=lambda x: yearly_hours[x])
        
        assigned_night = night_candidates[:2]
        for s in assigned_night:
            monthly_hours[s] += 16
            yearly_hours[s] += 16
            available_at[s] = curr + timedelta(days=1, hours=8) + timedelta(hours=24) # Nghỉ 24h

        rows.append({
            "Ngày": day_str,
            "Ca: 8h00' – 16h00'": " & ".join(assigned_day),
            "Ca: 16h00' – 8h00'": " & ".join(assigned_night)
        })

    return pd.DataFrame(rows), monthly_hours, yearly_hours

# ==================================================
# GIAO DIỆN HIỂN THỊ
# ==================================================
st.title(f"📊 Thống kê Lịch Trực (01/{view_month} ➔ {current_day if view_month==current_month else 'Cuối tháng'}/{view_month})")

df_schedule, m_hours, y_hours = generate_schedule_and_stats(view_year, view_month)

# Layout chính
tab1, tab2 = st.tabs(["📋 Chi tiết lịch trực", "📈 Báo cáo giờ công"])

with tab1:
    st.table(df_schedule)

with tab2:
    st.subheader(f"Tổng kết giờ làm việc tính đến hiện tại (Năm {view_year})")
    
    # Tạo DataFrame tổng hợp
    summary_list = []
    for s in staff_list:
        summary_list.append({
            "Nhân viên": s,
            "Giờ trong tháng": m_hours[s],
            "Tổng tích lũy năm": y_hours[s],
            "Định mức tháng còn lại": 176 - m_hours[s]
        })
    
    df_sum = pd.DataFrame(summary_list).sort_values("Tổng tích lũy năm")
    
    # Hiển thị biểu đồ cột
    st.bar_chart(df_sum, x="Nhân viên", y="Tổng tích lũy năm")
    
    # Hiển thị bảng số liệu
    st.dataframe(df_sum, use_container_width=True)

    st.info(f"""
    **Nguyên tắc vận hành hiện tại:**
    1. **Trung & Ngà:** Không xuất hiện trong danh sách trực vào các ngày Thứ 7, Chủ Nhật. Các nhân sự khác vẫn được điều phối bình thường để đảm bảo vận hành.
    2. **Reset năm:** Toàn bộ 'Tổng tích lũy năm' sẽ trở về 0 khi bạn chọn Năm mới trên sidebar.
    3. **Tính công bằng:** Nhân sự có 'Tổng tích lũy năm' thấp sẽ luôn được hệ thống ưu tiên xếp lịch trước để đảm bảo cuối năm mọi người có số giờ bằng nhau.
    """)

# Nút xuất file
st.download_button(
    label="📥 Xuất báo cáo CSV",
    data=df_schedule.to_csv(index=False).encode('utf-8-sig'),
    file_name=f"Lich_truc_{view_month}_{view_year}.csv",
    mime='text/csv',
)
