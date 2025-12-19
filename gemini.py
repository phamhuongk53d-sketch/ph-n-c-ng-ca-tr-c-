import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import numpy as np

# ==================================================
# CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Hệ thống Trực Công Bằng 2026",
    layout="wide"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def get_vietnamese_weekday(d: pd.Timestamp) -> str:
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[d.weekday()]}- {d.strftime('%d/%m')}"

def get_month_name(month_num: int) -> str:
    months = ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
              "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]
    return months[month_num]

# ==================================================
# ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
try:
    df_raw = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        ttl=0
    )
except Exception:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ", "Năm", "Tháng"])

if not df_raw.empty:
    df_raw["Ngày"] = pd.to_datetime(
        df_raw["Ngày"],
        dayfirst=True,
        errors="coerce"
    )
    df_raw = df_raw.dropna(subset=["Ngày"])
    # Thêm cột năm và tháng để dễ phân nhóm
    df_raw["Năm"] = df_raw["Ngày"].dt.year
    df_raw["Tháng"] = df_raw["Ngày"].dt.month
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ", "Năm", "Tháng"])

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("Cấu hình nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect(
        "Chỉ trực ca ngày",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("Thời gian phân lịch")
    
    # Cho phép chọn năm
    year = st.selectbox("Năm", [2026, 2025, 2027, 2024], index=0)
    
    # Cho phép chọn tháng bắt đầu và kết thúc
    col1, col2 = st.columns(2)
    with col1:
        start_month = st.selectbox("Tháng bắt đầu", range(1, 13), index=0, format_func=get_month_name)
    with col2:
        end_month = st.selectbox("Tháng kết thúc", range(1, 13), index=11, format_func=get_month_name)
    
    # Tự động tính ngày bắt đầu và kết thúc
    start_date = datetime(year, start_month, 1)
    
    # Tính ngày cuối cùng của tháng kết thúc
    if end_month == 12:
        end_date = datetime(year, 12, 31)
    else:
        next_month = datetime(year, end_month + 1, 1)
        end_date = next_month - timedelta(days=1)
    
    # Hiển thị thông tin đã chọn
    st.info(f"Phân công từ: {start_date.strftime('%d/%m/%Y')} đến: {end_date.strftime('%d/%m/%Y')}")
    
    st.header("Tùy chọn xuất dữ liệu")
    show_all_months = st.checkbox("Hiển thị tất cả các tháng", value=True)
    
    st.header("Điều chỉnh nhân sự")
    st.write("Thêm/xóa nhân sự từ ngày:")
    adjust_date = st.date_input("Ngày điều chỉnh", datetime.now().date())
    action = st.radio("Hành động", ["Thêm nhân sự", "Xóa nhân sự"])
    if action == "Thêm nhân sự":
        new_staff = st.text_input("Nhân viên mới")
    else:
        remove_staff = st.selectbox("Chọn nhân viên cần xóa", staff)

# ==================================================
# TÍNH GIỜ LŨY KẾ ĐẾN TRƯỚC NGÀY BẮT ĐẦU
# ==================================================
history_before = df_raw[df_raw["Ngày"].dt.date < start_date.date()]

luy_ke_hours = {
    s: history_before.loc[
        history_before["Nhân viên"] == s, "Giờ"
    ].sum()
    for s in staff
}

st.subheader(f"📊 Tổng giờ lũy kế đến {start_date.date() - timedelta(days=1)}")
st.dataframe(pd.DataFrame([luy_ke_hours]).T.rename(columns={0: "Số giờ"}))

# ==================================================
# THUẬT TOÁN PHÂN CA CẢI TIẾN
# ==================================================
def generate_schedule(staff_list, start_date, end_date, special_staff_list):
    rows = []
    work_hours = {s: luy_ke_hours.get(s, 0) for s in staff_list}
    
    # Khởi tạo thời gian có sẵn cho mỗi nhân viên
    available_at = {
        s: datetime.combine(start_date - timedelta(days=1), datetime.min.time())
        for s in staff_list
    }
    
    curr_date = start_date
    while curr_date <= end_date:
        base = datetime.combine(curr_date, datetime.min.time())
        
        # ===== CA NGÀY (08–16) =====
        day_candidates = [
            s for s in staff_list
            if available_at[s] <= base.replace(hour=8)
        ]
        # Ưu tiên nhân viên chỉ trực ca ngày, sau đó sắp xếp theo số giờ ít nhất
        day_candidates.sort(
            key=lambda s: (0 if s in special_staff_list else 1, work_hours[s])
        )
        
        # Chọn 2 người cho ca ngày
        selected_day = []
        for s in day_candidates:
            if len(selected_day) >= 2:
                break
            if s not in selected_day:
                selected_day.append(s)
        
        for s in selected_day:
            rows.append({
                "Ngày": curr_date,
                "Ca": "Ca: 8h00 - 16h00",
                "Nhân viên": s,
                "Giờ": 8,
                "Năm": curr_date.year,
                "Tháng": curr_date.month
            })
            work_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)
        
        # ===== CA ĐÊM (16–08) =====
        night_candidates = [
            s for s in staff_list
            if s not in special_staff_list
            and available_at[s] <= base.replace(hour=16)
            and s not in selected_day  # Tránh trùng với ca ngày cùng ngày
        ]
        night_candidates.sort(key=lambda s: work_hours[s])
        
        # Chọn 2 người cho ca đêm
        selected_night = []
        for s in night_candidates:
            if len(selected_night) >= 2:
                break
            if s not in selected_night:
                selected_night.append(s)
        
        for s in selected_night:
            rows.append({
                "Ngày": curr_date,
                "Ca": "Ca: 16h00 - 8h00",
                "Nhân viên": s,
                "Giờ": 16,
                "Năm": curr_date.year,
                "Tháng": curr_date.month
            })
            work_hours[s] += 16
            available_at[s] = base + timedelta(days=2)
        
        curr_date += timedelta(days=1)
    
    return pd.DataFrame(rows)

# ==================================================
# XỬ LÝ ĐIỀU CHỈNH NHÂN SỰ
# ==================================================
def handle_staff_adjustment(df_existing, adjust_date, action, staff_list):
    """Xử lý điều chỉnh nhân sự từ một ngày cụ thể"""
    df_adjusted = df_existing.copy()
    
    # Xóa tất cả dữ liệu từ ngày điều chỉnh trở đi
    mask = df_adjusted["Ngày"].dt.date >= adjust_date
    df_to_keep = df_adjusted[~mask].copy()
    
    return df_to_keep

# ==================================================
# TẠO & HIỂN THỊ LỊCH THEO THÁNG
# ==================================================
if st.button("🚀 TẠO & CẬP NHẬT LỊCH TRỰC"):
    # Xử lý điều chỉnh nhân sự nếu có
    if 'adjust_date' in locals() and adjust_date >= start_date.date():
        df_raw = handle_staff_adjustment(df_raw, adjust_date, action, staff)
        # Cập nhật staff list nếu cần
        if action == "Thêm nhân sự" and 'new_staff' in locals() and new_staff:
            staff.append(new_staff.strip())
        elif action == "Xóa nhân sự" and 'remove_staff' in locals() and remove_staff in staff:
            staff.remove(remove_staff)
    
    # Tạo lịch mới
    df_new = generate_schedule(staff, start_date, end_date, special_staff)
    
    # Kết hợp dữ liệu cũ (trước ngày bắt đầu) và mới
    # Loại bỏ các ngày trùng trong khoảng thời gian mới
    mask_old = (df_raw["Ngày"].dt.date >= start_date.date()) & (df_raw["Ngày"].dt.date <= end_date.date())
    df_old_outside_range = df_raw[~mask_old]
    
    df_total = pd.concat([df_old_outside_range, df_new], ignore_index=True)
    df_total = df_total.sort_values("Ngày").reset_index(drop=True)
    
    # ================== HIỂN THỊ THEO THÁNG ==================
    st.subheader(f"🗓️ LỊCH PHÂN CÔNG NĂM {year}")
    
    # Hiển thị tất cả tháng hoặc chỉ tháng được chọn
    if show_all_months:
        display_months = range(1, 13)
    else:
        display_months = range(start_month, end_month + 1)
    
    for month in display_months:
        # Lọc dữ liệu theo tháng
        month_data = df_total[
            (df_total["Năm"] == year) & 
            (df_total["Tháng"] == month)
        ].copy()
        
        if not month_data.empty:
            st.markdown(f"### 📅 LỊCH PHÂN CÔNG {get_month_name(month).upper()} NĂM {year}")
            
            # Chuẩn bị dữ liệu hiển thị
            df_month_view = month_data.copy()
            
            df_group = (
                df_month_view
                .groupby(["Ngày", "Ca"], as_index=False)["Nhân viên"]
                .apply(lambda x: " ".join(x))
            )
            
            df_pivot = (
                df_group
                .pivot(index="Ngày", columns="Ca", values="Nhân viên")
                .reindex(columns=["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"])
                .fillna("")
                .reset_index()
                .sort_values("Ngày")
            )
            
            df_pivot["Ngày"] = df_pivot["Ngày"].apply(get_vietnamese_weekday)
            
            # Hiển thị bảng
            st.table(df_pivot)
            
            # Tính tổng giờ mỗi nhân viên trong tháng
            st.markdown("**Tổng giờ trực theo nhân viên:**")
            month_hours = (
                month_data
                .groupby("Nhân viên")["Giờ"]
                .sum()
                .reset_index()
                .sort_values("Giờ")
            )
            st.dataframe(month_hours, hide_index=True)
            
            st.markdown("---")
    
    # ================== THỐNG KÊ TỔNG QUAN ==================
    st.subheader("📈 THỐNG KÊ TỔNG QUAN CẢ NĂM")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Tổng giờ mỗi nhân viên cả năm
        yearly_hours = (
            df_total[df_total["Năm"] == year]
            .groupby("Nhân viên")["Giờ"]
            .sum()
            .reset_index()
            .sort_values("Giờ")
        )
        st.write("**Tổng giờ trực cả năm:**")
        st.dataframe(yearly_hours, hide_index=True)
    
    with col2:
        # Tổng giờ mỗi tháng
        monthly_hours = (
            df_total[df_total["Năm"] == year]
            .groupby("Tháng")["Giờ"]
            .sum()
            .reset_index()
        )
        monthly_hours["Tháng"] = monthly_hours["Tháng"].apply(get_month_name)
        st.write("**Tổng giờ trực theo tháng:**")
        st.dataframe(monthly_hours, hide_index=True)
    
    # ================== GHI GOOGLE SHEETS ==================
    # Lưu dữ liệu chi tiết
    df_save_raw = df_total.copy()
    df_save_raw["Ngày"] = pd.to_datetime(df_save_raw["Ngày"]).dt.strftime("%d/%m/%Y")
    
    conn.update(
        spreadsheet=SPREADSHEET_URL,
        worksheet="Data_Log",
        data=df_save_raw.reset_index(drop=True)
    )
    
    # Tạo sheet riêng cho mỗi tháng
    for month in range(1, 13):
        month_data = df_total[
            (df_total["Năm"] == year) & 
            (df_total["Tháng"] == month)
        ].copy()
        
        if not month_data.empty:
            # Chuẩn bị dữ liệu cho sheet tháng
            df_month_view = month_data.copy()
            df_group = (
                df_month_view
                .groupby(["Ngày", "Ca"], as_index=False)["Nhân viên"]
                .apply(lambda x: " ".join(x))
            )
            
            df_pivot = (
                df_group
                .pivot(index="Ngày", columns="Ca", values="Nhân viên")
                .reindex(columns=["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"])
                .fillna("")
                .reset_index()
                .sort_values("Ngày")
            )
            
            df_pivot["Ngày"] = df_pivot["Ngày"].apply(get_vietnamese_weekday)
            
            # Cập nhật sheet tháng (tạo mới nếu chưa có)
            sheet_name = f"Tháng {month}"
            try:
                conn.update(
                    spreadsheet=SPREADSHEET_URL,
                    worksheet=sheet_name,
                    data=df_pivot.reset_index(drop=True)
                )
            except:
                # Nếu sheet chưa tồn tại, tạo mới
                st.warning(f"Sheet '{sheet_name}' chưa tồn tại, cần tạo thủ công")
    
    st.success("✅ Đã lưu lịch trực thành công!")

# ==================================================
# HIỂN THỊ LỊCH HIỆN TẠI
# ==================================================
if not df_raw.empty:
    st.subheader("📋 Lịch trực hiện tại")
    
    # Hiển thị theo từng tháng
    current_year = datetime.now().year
    for month in range(1, 13):
        month_data = df_raw[
            (df_raw["Năm"] == current_year) & 
            (df_raw["Tháng"] == month)
        ].copy()
        
        if not month_data.empty:
            st.markdown(f"### 📅 LỊCH PHÂN CÔNG {get_month_name(month).upper()} NĂM {current_year} (HIỆN TẠI)")
            
            df_month_view = month_data.copy()
            df_group = (
                df_month_view
                .groupby(["Ngày", "Ca"], as_index=False)["Nhân viên"]
                .apply(lambda x: " ".join(x))
            )
            
            df_pivot = (
                df_group
                .pivot(index="Ngày", columns="Ca", values="Nhân viên")
                .reindex(columns=["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"])
                .fillna("")
                .reset_index()
                .sort_values("Ngày")
            )
            
            df_pivot["Ngày"] = df_pivot["Ngày"].apply(get_vietnamese_weekday)
            
            st.table(df_pivot)
            st.markdown("---")
