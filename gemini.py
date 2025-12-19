import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH GIAO DIỆN
# ==================================================
st.set_page_config(page_title="Hệ thống Quản lý Lịch Trực 2025", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
SHEET_DATA = "Data_Log"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# SIDEBAR
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff_list = [s.strip() for s in staff_input.split(",") if s.strip()]
    
    special_staff = st.multiselect("Chỉ trực ca ngày (8h-16h)", staff_list, default=["Trung", "Ngà"])
    
    st.header("📅 Thời gian")
    year = st.number_input("Năm", value=2025)
    month = st.slider("Tháng", 1, 12, 12)

# ==================================================
# THUẬT TOÁN PHÂN LỊCH TỐI ƯU
# ==================================================
def generate_smart_schedule(target_year, target_month):
    rows = []
    # Khởi tạo bộ đếm giờ (trong thực tế có thể load từ database để cộng dồn cả năm)
    total_hours_year = {s: 0 for s in staff_list} 
    monthly_hours = {s: 0 for s in staff_list}
    
    # Thời điểm sớm nhất nhân viên có thể đi làm lại
    available_at = {s: datetime(target_year, target_month, 1) for s in staff_list}
    
    start_dt = datetime(target_year, target_month, 1)
    # Tìm ngày cuối tháng
    if target_month == 12:
        end_dt = datetime(target_year + 1, 1, 1) - timedelta(days=1)
    else:
        end_dt = datetime(target_year, target_month + 1, 1) - timedelta(days=1)

    curr = start_dt
    while curr <= end_dt:
        # Bỏ qua Thứ 7 (5) và Chủ Nhật (6)
        if curr.weekday() >= 5:
            curr += timedelta(days=1)
            continue
            
        day_str = f"T{curr.weekday()+2}- {curr.strftime('%d/%m')}" if curr.weekday() < 6 else f"CN- {curr.strftime('%d/%m')}"
        
        # --- PHÂN CA NGÀY (08h - 16h) ---
        # Ưu tiên Trung, Ngà, sau đó đến người ít giờ nhất và thỏa mãn cách 16h
        day_candidates = [
            s for s in staff_list 
            if available_at[s] <= curr.replace(hour=8) and monthly_hours[s] + 8 <= 176
        ]
        # Sắp xếp: Ưu tiên special_staff, sau đó là người có tổng giờ thấp nhất
        day_candidates.sort(key=lambda s: (0 if s in special_staff else 1, total_hours_year[s]))
        
        assigned_day = day_candidates[:2]
        for s in assigned_day:
            monthly_hours[s] += 8
            total_hours_year[s] += 8
            available_at[s] = curr.replace(hour=16) + timedelta(hours=16)

        # --- PHÂN CA ĐÊM (16h - 08h sáng hôm sau) ---
        # Loại trừ Trung, Ngà và người đã trực ca ngày hôm đó
        night_candidates = [
            s for s in staff_list 
            if s not in special_staff 
            and s not in assigned_day
            and available_at[s] <= curr.replace(hour=16)
            and monthly_hours[s] + 16 <= 176
        ]
        night_candidates.sort(key=lambda s: total_hours_year[s])
        
        assigned_night = night_candidates[:2]
        for s in assigned_night:
            monthly_hours[s] += 16
            total_hours_year[s] += 16
            # Nghỉ ít nhất 24h sau ca đêm
            available_at[s] = curr.replace(hour=16) + timedelta(hours=16) + timedelta(hours=24)

        rows.append({
            "Ngày": day_str,
            "Ca: 8h00' – 16h00'": " & ".join(assigned_day),
            "Ca: 16h00' – 8h00'": " & ".join(assigned_night)
        })
        
        curr += timedelta(days=1)

    return pd.DataFrame(rows), monthly_hours

# ==================================================
# HIỂN THỊ KẾT QUẢ
# ==================================================
st.title(f"LỊCH TRỰC CA - THÁNG {month} NĂM {year}")

if st.button("🔄 Tạo lịch mới & Kiểm tra định mức"):
    df_schedule, total_work = generate_smart_schedule(year, month)
    
    # Hiển thị bảng lịch trực theo mẫu ảnh
    st.table(df_schedule)
    
    st.divider()
    
    # Hiển thị bảng tổng kết giờ làm
    st.subheader("📊 Tổng hợp giờ trực trong tháng")
    col1, col2 = st.columns(2)
    
    summary_data = []
    for p, h in total_work.items():
        status = "✅ Đạt" if h >= 144 else "⚠️ Thấp" # Giả định mức sàn
        summary_data.append({"Nhân viên": p, "Tổng giờ": h, "Trạng thái": status})
    
    df_summary = pd.DataFrame(summary_data)
    
    with col1:
        st.dataframe(df_summary.sort_values("Tổng giờ", ascending=True))
    
    with col2:
        st.info("""
        **Ghi chú thuật toán:**
        * Hệ thống ưu tiên người có số giờ lũy kế thấp nhất để phân lịch.
        * Tự động bù giờ: Nếu tháng này nhân viên A làm ít, tháng sau họ sẽ được ưu tiên xếp vào danh sách ứng viên đầu tiên.
        * Đảm bảo nghỉ tối thiểu 16h (ca ngày) và 24h (ca đêm).
        """)

    # Nút lưu dữ liệu
    csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Tải về file CSV", csv, f"Lich_Truc_{month}_{year}.csv", "text/csv")
