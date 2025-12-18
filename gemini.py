import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Hệ thống Phân Ca Trực Thông Minh 2025",
    layout="wide",
    page_icon="📅"
)

# --- CẤU HÌNH KẾT NỐI ---
# Thay URL Google Sheet của bạn vào đây nếu cần thay đổi
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# 2. HÀM TIỆN ÍCH (HELPER FUNCTIONS)
# ==================================================
def get_vietnamese_weekday(d):
    """Chuyển đổi ngày thành thứ tiếng Việt (T2, T3...)"""
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return weekdays[d.weekday()]

def get_month_key(d):
    """Trả về key định danh tháng (YYYY, MM)"""
    return (d.year, d.month)

# ==================================================
# 3. ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
@st.cache_data(ttl=5)
def load_data():
    try:
        df = conn.read(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Data_Log",
            ttl=0
        )
        # Chuẩn hóa tên cột (xóa khoảng trắng thừa)
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        # Trả về bảng rỗng nếu chưa có dữ liệu hoặc lỗi kết nối
        return pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

df_raw = load_data()

# Xử lý dữ liệu thô ban đầu
if not df_raw.empty:
    # Cố gắng chuyển đổi cột Ngày sang datetime
    df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce")
    # Loại bỏ các dòng không có ngày hợp lệ
    df_raw = df_raw.dropna(subset=["Ngày"])
    # Đảm bảo cột Giờ là số
    df_raw["Giờ"] = pd.to_numeric(df_raw["Giờ"], errors="coerce").fillna(0)
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

# ==================================================
# 4. SIDEBAR – CẤU HÌNH INPUT
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên (cách nhau dấu phẩy)",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B",
        height=100
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    st.info("Quy tắc: Nhân viên đặc biệt chỉ làm ca ngày, nghỉ T7, CN.")
    # Mặc định chọn Trung và Ngà nếu họ có trong danh sách
    default_special = [s for s in ["Trung", "Ngà"] if s in staff]
    special_staff = st.multiselect(
        "Nhân viên đặc biệt",
        staff,
        default=default_special
    )

    st.divider()
    st.header("⏳ Thời gian phân lịch")
    # Mặc định ngày bắt đầu là hôm nay
    start_date = st.date_input("Từ ngày", datetime.now().date())
    # Mặc định xếp lịch cho 30 ngày tới
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))
    
    max_hours_per_month = st.number_input("Giới hạn giờ/tháng", value=176, step=8)

# ==================================================
# 5. TÍNH TOÁN DỮ LIỆU LỊCH SỬ (Pre-calculation)
# ==================================================
# Chỉ lấy dữ liệu trước ngày bắt đầu xếp lịch để làm căn cứ tính công bằng
history_before = df_raw[df_raw["Ngày"].dt.date < start_date].copy()

# A. Tổng giờ tích lũy trọn đời (Lifetime) - Dùng để cân bằng cả năm
lifetime_hours = {s: 0.0 for s in staff}

# B. Tổng giờ theo tháng (Monthly) - Dùng để kiểm tra giới hạn 176h
monthly_hours_history = {} # Key: (Name, Year, Month) -> Hours

if not history_before.empty:
    # Tính lifetime
    temp_lifetime = history_before.groupby("Nhân viên")["Giờ"].sum()
    for s in staff:
        lifetime_hours[s] = temp_lifetime.get(s, 0.0)
    
    # Tính monthly history
    history_before["MonthKey"] = history_before["Ngày"].apply(lambda x: (x.year, x.month))
    temp_monthly = history_before.groupby(["Nhân viên", "MonthKey"])["Giờ"].sum()
    
    for idx, val in temp_monthly.items():
        name, m_key = idx
        if name in staff:
            if name not in monthly_hours_history:
                monthly_hours_history[name] = {}
            monthly_hours_history[name][m_key] = val

# ==================================================
# 6. GIAO DIỆN CHÍNH (HEADER)
# ==================================================
st.title("📊 Hệ thống Phân Ca Trực Công Bằng")
col1, col2 = st.columns(2)
with col1:
    st.metric("Tổng nhân sự", len(staff))
with col2:
    st.metric("Ngày bắt đầu chạy lịch", start_date.strftime("%d/%m/%Y"))

# ==================================================
# 7. THUẬT TOÁN PHÂN CA (CORE LOGIC)
# ==================================================
def generate_schedule_advanced():
    rows = []
    
    # Copy trạng thái hiện tại để không ảnh hưởng dữ liệu gốc khi tính toán
    current_lifetime_hours = lifetime_hours.copy()
    
    # available_at: Thời điểm sớm nhất nhân viên có thể nhận ca tiếp theo
    # Mặc định: Rảnh từ 00:00 ngày bắt đầu
    available_at = {
        s: datetime.combine(start_date, time(0,0)) for s in staff
    }
    
    # Tracking giờ theo tháng (để check max 176h)
    current_monthly_hours = monthly_hours_history.copy()
    for s in staff:
        if s not in current_monthly_hours:
            current_monthly_hours[s] = {}

    curr = start_date
    
    while curr <= end_date:
        # Các mốc thời gian quan trọng trong ngày
        date_start_day = datetime.combine(curr, time(8, 0))   # 8h sáng nay
        date_end_day   = datetime.combine(curr, time(16, 0))  # 16h chiều nay
        date_end_night = date_start_day + timedelta(days=1)   # 8h sáng mai
        
        month_key = (curr.year, curr.month)
        weekday = curr.weekday() # 0=T2, ..., 6=CN
        is_weekend = (weekday >= 5) # T7, CN

        # --- CA NGÀY (08:00 - 16:00) ---
        day_candidates = []
        for s in staff:
            # 1. Check thời gian nghỉ: Phải rảnh trước hoặc đúng 8h sáng
            if available_at[s] > date_start_day:
                continue
            
            # 2. Check Max 176h
            curr_month_h = current_monthly_hours[s].get(month_key, 0)
            if curr_month_h + 8 > max_hours_per_month:
                continue
                
            # 3. Check Đặc biệt: Không làm T7, CN
            if s in special_staff and is_weekend:
                continue
            
            day_candidates.append(s)

        # Sắp xếp ưu tiên:
        # - Nếu ngày thường: Ưu tiên nhóm đặc biệt (Trung/Ngà) trước để đảm bảo họ đủ giờ
        # - Sau đó ưu tiên người có tổng giờ (lifetime) thấp nhất
        def sort_key_day(x):
            is_special = x in special_staff
            prio_special = 0 if (is_special and not is_weekend) else 1
            return (prio_special, current_lifetime_hours[x])

        day_candidates.sort(key=sort_key_day)
        selected_day = day_candidates[:2] # Chọn 2 người
        
        for s in selected_day:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 8h00 - 16h00",
                "Nhân viên": s,
                "Giờ": 8,
                "Loại Ca": "Ngày"
            })
            current_lifetime_hours[s] += 8
            current_monthly_hours[s][month_key] = current_monthly_hours[s].get(month_key, 0) + 8
            
            # Cập nhật thời gian rảnh: Ca ngày nghỉ 16h -> Rảnh 8h sáng hôm sau
            available_at[s] = date_end_day + timedelta(hours=16)

        # --- CA ĐÊM (16:00 - 08:00 hôm sau) ---
        night_candidates = []
        for s in staff:
            # 1. Nhân viên đặc biệt KHÔNG trực đêm
            if s in special_staff:
                continue
                
            # 2. Check thời gian nghỉ: Phải rảnh trước hoặc đúng 16h chiều
            # (Người vừa làm ca sáng nay sẽ không thỏa mãn điều kiện này vì họ rảnh lúc 8h sáng mai)
            if available_at[s] > date_end_day:
                continue
            
            # 3. Check Max 176h
            curr_month_h = current_monthly_hours[s].get(month_key, 0)
            if curr_month_h + 16 > max_hours_per_month:
                continue
                
            night_candidates.append(s)
            
        # Sắp xếp: Ai ít giờ nhất làm trước
        night_candidates.sort(key=lambda x: current_lifetime_hours[x])
        selected_night = night_candidates[:2] # Chọn 2 người
        
        for s in selected_night:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 16h00 - 8h00",
                "Nhân viên": s,
                "Giờ": 16,
                "Loại Ca": "Đêm"
            })
            current_lifetime_hours[s] += 16
            current_monthly_hours[s][month_key] = current_monthly_hours[s].get(month_key, 0) + 16
            
            # Cập nhật thời gian rảnh: Ca đêm nghỉ 24h -> Rảnh 8h sáng ngày mốt
            # (Tức là nghỉ trọn vẹn ngày hôm sau)
            finish_time = date_end_night 
            available_at[s] = finish_time + timedelta(hours=24)

        curr += timedelta(days=1)

    return pd.DataFrame(rows), current_monthly_hours

# ==================================================
# 8. XỬ LÝ SỰ KIỆN & HIỂN THỊ (UI)
# ==================================================
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    with st.spinner("Đang tính toán phân bổ công bằng..."):
        df_new, final_monthly_status = generate_schedule_advanced()
    
    if df_new.empty:
        st.warning("⚠️ Không tạo được lịch nào (có thể do đã hết ngày hoặc cấu hình quá chặt).")
    else:
        # Gộp dữ liệu cũ và mới
        df_total = pd.concat([history_before, df_new], ignore_index=True)
        
        # --- [FIX BUG QUAN TRỌNG] ---
        # Ép kiểu dữ liệu cột Ngày về datetime một lần nữa để đảm bảo tính nhất quán
        # trước khi dùng .dt accessor
        df_total["Ngày"] = pd.to_datetime(df_total["Ngày"], errors='coerce')
        
        # --- TAB VIEW ---
        tab1, tab2, tab3 = st.tabs(["🗓️ Lịch Chi Tiết", "📈 Báo Cáo Tháng", "💾 Dữ liệu Thô"])
        
        with tab1:
            st.subheader("Lịch trực hiển thị")
            
            # Lọc dữ liệu trong khoảng thời gian chọn
            mask = (df_total["Ngày"].dt.date >= start_date) & (df_total["Ngày"].dt.date <= end_date)
            df_view = df_total[mask].copy()
            
            # Tạo cột hiển thị ngày đẹp: "T2 (19/12)"
            df_view["Ngày Str"] = df_view["Ngày"].apply(
                lambda x: f"{get_vietnamese_weekday(x)} ({x.strftime('%d/%m')})"
            )
            
            # Gom nhóm tên nhân viên (nếu 1 ca có nhiều người)
            df_group = df_view.groupby(["Ngày Str", "Ca", "Ngày"], as_index=False)["Nhân viên"].apply(lambda x: ", ".join(x))
            
            # Pivot table
            df_pivot = df_group.pivot(index=["Ngày", "Ngày Str"], columns="Ca", values="Nhân viên").reset_index()
            df_pivot = df_pivot.sort_values("Ngày") # Sắp xếp theo ngày
            
            # Hiển thị
            df_display = df_pivot.drop(columns=["Ngày"]).set_index("Ngày Str")
            cols_order = [c for c in ["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"] if c in df_display.columns]
            st.table(df_display[cols_order].fillna("-"))

        with tab2:
            st.subheader("Báo cáo tổng giờ làm theo tháng")
            
            # Chuyển đổi dữ liệu báo cáo
            report_data = []
            for name, months in final_monthly_status.items():
                for m_key, hours in months.items():
                    report_data.append({
                        "Tháng": f"{m_key[1]}/{m_key[0]}",
                        "Nhân viên": name,
                        "Tổng giờ": hours
                    })
            
            df_report = pd.DataFrame(report_data)
            
            # Chỉ hiển thị các tháng liên quan
            relevant_months = set([(d.year, d.month) for d in pd.date_range(start_date, end_date)])
            df_report = df_report[df_report["Tháng"].isin([f"{m}/{y}" for y, m in relevant_months])]
            
            if not df_report.empty:
                rp_pivot = df_report.pivot(index="Nhân viên", columns="Tháng", values="Tổng giờ").fillna(0)
                st.dataframe(rp_pivot.style.background_gradient(cmap="RdYlGn", axis=0))
                st.caption(f"*Giới hạn tối đa: {max_hours_per_month} giờ/tháng*")
            else:
                st.info("Chưa có dữ liệu báo cáo.")

        with tab3:
            st.dataframe(df_total)

        # --- SAVE TO SHEETS ---
        # Chuẩn bị định dạng lưu (Convert datetime -> string dd/mm/yyyy)
        df_save_raw = df_total.copy()
        
        # Xóa các cột phụ trợ không cần lưu
        if "MonthKey" in df_save_raw.columns: del df_save_raw["MonthKey"]
        if "Loại Ca" in df_save_raw.columns: del df_save_raw["Loại Ca"]
            
        df_save_raw["Ngày"] = df_save_raw["Ngày"].dt.strftime("%d/%m/%Y")
        
        # Ghi vào Sheet 1: Data Log (Lịch sử + Mới)
        conn.update(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Data_Log",
            data=df_save_raw
        )
        
        # Ghi vào Sheet 2: Lịch Trực (View đẹp cho mọi người xem)
        df_sheet_view = df_pivot.drop(columns=["Ngày"]).rename(columns={"Ngày Str": "Ngày"})
        conn.update(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Lich_Truc",
            data=df_sheet_view
        )
        
        st.success("✅ Đã cập nhật lịch lên Google Sheets thành công!")

# ==================================================
# 9. FOOTER - HIỂN THỊ TRẠNG THÁI
# ==================================================
st.divider()
st.subheader("📊 Trạng thái lũy kế (Lifetime) trước khi chạy")
st.caption("Thuật toán sẽ ưu tiên người có giờ thấp nhất trong bảng này.")
df_lifetime = pd.DataFrame(list(lifetime_hours.items()), columns=["Nhân viên", "Tổng giờ (All time)"])
st.dataframe(df_lifetime.sort_values("Tổng giờ (All time)"))
