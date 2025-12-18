import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Hệ thống Phân Ca Trực Thông Minh 2025",
    layout="wide",
    page_icon="📅"
)

# Thay URL của bạn vào đây
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def get_vietnamese_weekday(d):
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return weekdays[d.weekday()]

def get_month_key(d):
    """Trả về key định danh tháng (YYYY, MM)"""
    return (d.year, d.month)

# ==================================================
# ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
@st.cache_data(ttl=5)
def load_data():
    try:
        df = conn.read(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Data_Log",
            ttl=0
        )
        # Chuẩn hóa tên cột
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

df_raw = load_data()

# Xử lý dữ liệu thô
if not df_raw.empty:
    df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce")
    df_raw = df_raw.dropna(subset=["Ngày"])
    df_raw["Giờ"] = pd.to_numeric(df_raw["Giờ"], errors="coerce").fillna(0)
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình nhân sự")

    staff_input = st.text_area(
        "Danh sách nhân viên (cách nhau dấu phẩy)",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B",
        height=100
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    st.info("Quy tắc: Trung, Ngà chỉ làm ca ngày, nghỉ T7, CN.")
    special_staff = st.multiselect(
        "Nhân viên đặc biệt (Chỉ ca ngày & Nghỉ cuối tuần)",
        staff,
        default=[s for s in ["Trung", "Ngà"] if s in staff]
    )

    st.divider()
    st.header("⏳ Thời gian phân lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))
    
    max_hours_per_month = st.number_input("Giới hạn giờ/tháng", value=176, step=8)

# ==================================================
# TÍNH TOÁN DỮ LIỆU LỊCH SỬ
# ==================================================
# Lọc dữ liệu trước ngày bắt đầu để tính lũy kế (đảm bảo công bằng dài hạn)
history_before = df_raw[df_raw["Ngày"].dt.date < start_date].copy()

# Tổng giờ tích lũy trọn đời (để cân bằng cả năm)
lifetime_hours = {s: 0.0 for s in staff}
# Tổng giờ theo tháng (để kiểm tra cap 176h) - Chỉ tính dữ liệu lịch sử
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

st.title("📊 Hệ thống Phân Ca Trực Công Bằng")
col1, col2 = st.columns(2)
with col1:
    st.metric("Tổng nhân sự", len(staff))
with col2:
    st.metric("Ngày bắt đầu chạy lịch", start_date.strftime("%d/%m/%Y"))

# ==================================================
# THUẬT TOÁN PHÂN CA (NÂNG CẤP)
# ==================================================
def generate_schedule_advanced():
    rows = []
    
    # Copy trạng thái hiện tại
    current_lifetime_hours = lifetime_hours.copy()
    
    # Trạng thái thời gian rảnh (Available time)
    # Mặc định tất cả rảnh từ 00:00 ngày start_date
    # Logic: available_at[s] = datetime mà nhân viên đó hết thời gian nghỉ
    available_at = {
        s: datetime.combine(start_date, time(0,0)) for s in staff
    }
    
    # Tracking giờ theo tháng trong quá trình chạy (bao gồm cả lịch sử)
    # Cấu trúc: current_monthly_hours[name][(year, month)] = hours
    current_monthly_hours = monthly_hours_history.copy()
    for s in staff:
        if s not in current_monthly_hours:
            current_monthly_hours[s] = {}

    curr = start_date
    
    while curr <= end_date:
        # Xác định mốc thời gian của các ca
        date_start_day = datetime.combine(curr, time(8, 0))   # 8h sáng
        date_end_day   = datetime.combine(curr, time(16, 0))  # 16h chiều
        date_end_night = date_start_day + timedelta(days=1)   # 8h sáng hôm sau
        
        month_key = (curr.year, curr.month)
        weekday = curr.weekday() # 0=Mon, 5=Sat, 6=Sun
        is_weekend = (weekday >= 5) # T7, CN

        # ----------------------------------------
        # 1. PHÂN CA NGÀY (08:00 - 16:00) - Cần 2 người
        # ----------------------------------------
        day_candidates = []
        for s in staff:
            # Check 1: Thời gian nghỉ (Rest time)
            # Muốn làm ca sáng (8h), thì phải rảnh trước hoặc đúng 8h sáng nay
            if available_at[s] > date_start_day:
                continue
            
            # Check 2: Max Hours (176h)
            curr_month_h = current_monthly_hours[s].get(month_key, 0)
            if curr_month_h + 8 > max_hours_per_month:
                continue
                
            # Check 3: Đặc biệt (Trung/Ngà) không làm T7, CN
            if s in special_staff and is_weekend:
                continue
            
            day_candidates.append(s)

        # Sắp xếp ứng viên:
        # Tiêu chí 1: Ưu tiên nhân viên đặc biệt (nếu không phải cuối tuần) để lấp đầy giờ của họ
        # Tiêu chí 2: Ai có tổng giờ tích lũy (lifetime) thấp nhất thì làm -> Công bằng dài hạn
        def sort_key_day(x):
            is_special = x in special_staff
            # Nếu là ngày thường, ưu tiên đặc biệt xếp trước để đảm bảo họ đủ giờ
            # (Vì họ không làm được ca đêm và cuối tuần nên pool giờ của họ hạn hẹp)
            prio_special = 0 if (is_special and not is_weekend) else 1
            return (prio_special, current_lifetime_hours[x])

        day_candidates.sort(key=sort_key_day)
        
        selected_day = day_candidates[:2]
        
        # Ghi nhận Ca Ngày
        for s in selected_day:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 8h00 - 16h00",
                "Nhân viên": s,
                "Giờ": 8,
                "Loại Ca": "Ngày"
            })
            # Cập nhật giờ
            current_lifetime_hours[s] += 8
            current_monthly_hours[s][month_key] = current_monthly_hours[s].get(month_key, 0) + 8
            
            # Cập nhật thời gian rảnh:
            # Luật: Ca ngày cách ca tiếp theo tối thiểu 16h
            # Kết thúc 16h + 16h nghỉ = 8h sáng hôm sau -> OK để trực tiếp
            available_at[s] = date_end_day + timedelta(hours=16)

        # ----------------------------------------
        # 2. PHÂN CA ĐÊM (16:00 - 08:00 hôm sau) - Cần 2 người
        # ----------------------------------------
        night_candidates = []
        for s in staff:
            # Check 1: Nhân viên đặc biệt KHÔNG làm đêm
            if s in special_staff:
                continue
                
            # Check 2: Đã làm ca ngày hôm nay rồi thì không làm đêm (Available check sẽ lo việc này, nhưng check lại cho chắc)
            # Muốn làm ca đêm (16h), phải rảnh trước hoặc đúng 16h
            if available_at[s] > date_end_day:
                continue
            
            # Check 3: Max Hours
            curr_month_h = current_monthly_hours[s].get(month_key, 0)
            if curr_month_h + 16 > max_hours_per_month:
                continue
                
            night_candidates.append(s)
            
        # Sắp xếp: Ai ít giờ nhất làm trước
        night_candidates.sort(key=lambda x: current_lifetime_hours[x])
        
        selected_night = night_candidates[:2]
        
        # Ghi nhận Ca Đêm
        for s in selected_night:
            rows.append({
                "Ngày": curr,
                "Ca": "Ca: 16h00 - 8h00",
                "Nhân viên": s,
                "Giờ": 16,
                "Loại Ca": "Đêm"
            })
            # Cập nhật giờ
            current_lifetime_hours[s] += 16
            current_monthly_hours[s][month_key] = current_monthly_hours[s].get(month_key, 0) + 16
            
            # Cập nhật thời gian rảnh:
            # Luật: Ca đêm cách ca tiếp theo tối thiểu 24h
            # Kết thúc 8h sáng hôm sau (curr + 1) -> Nghỉ 24h -> Rảnh lúc 8h sáng ngày (curr + 2)
            # Tức là nghỉ trọn vẹn ngày (curr + 1)
            finish_time = date_end_night # 8h sáng hôm sau
            available_at[s] = finish_time + timedelta(hours=24)

        curr += timedelta(days=1)

    return pd.DataFrame(rows), current_monthly_hours

# ==================================================
# UI: NÚT TẠO LỊCH & BÁO CÁO
# ==================================================
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    with st.spinner("Đang tính toán phân bổ công bằng..."):
        df_new, final_monthly_status = generate_schedule_advanced()
    
    if df_new.empty:
        st.warning("Không tạo được lịch nào (có thể do đã hết ngày hoặc cấu hình quá chặt).")
    else:
        # Gộp dữ liệu cũ và mới
        df_total = pd.concat([history_before, df_new], ignore_index=True)
        
        # --- TAB VIEW ---
        tab1, tab2, tab3 = st.tabs(["🗓️ Lịch Chi Tiết", "📈 Báo Cáo Tháng", "💾 Dữ liệu Thô"])
        
        with tab1:
            st.subheader("Lịch trực hiển thị")
            # Chuẩn bị Pivot Table đẹp
            df_view = df_total[df_total["Ngày"].dt.date >= start_date].copy()
            df_view["Ngày Str"] = df_view["Ngày"].apply(lambda x: f"{get_vietnamese_weekday(x)} ({x.strftime('%d/%m')})")
            
            df_group = df_view.groupby(["Ngày Str", "Ca", "Ngày"], as_index=False)["Nhân viên"].apply(lambda x: ", ".join(x))
            
            df_pivot = df_group.pivot(index=["Ngày", "Ngày Str"], columns="Ca", values="Nhân viên").reset_index()
            # Sort lại theo ngày thực
            df_pivot = df_pivot.sort_values("Ngày")
            # Bỏ cột ngày thực, chỉ giữ ngày hiển thị
            df_display = df_pivot.drop(columns=["Ngày"]).set_index("Ngày Str")
            
            # Đảm bảo cột theo thứ tự
            cols_order = [c for c in ["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"] if c in df_display.columns]
            st.table(df_display[cols_order].fillna("-"))

        with tab2:
            st.subheader("Báo cáo tổng giờ làm theo tháng")
            
            # Chuyển đổi dict final_monthly_status sang DataFrame
            report_data = []
            for name, months in final_monthly_status.items():
                for m_key, hours in months.items():
                    report_data.append({
                        "Tháng": f"{m_key[1]}/{m_key[0]}",
                        "Nhân viên": name,
                        "Tổng giờ": hours
                    })
            
            df_report = pd.DataFrame(report_data)
            
            # Lọc các tháng liên quan đến đợt xếp lịch này
            relevant_months = set([(d.year, d.month) for d in pd.date_range(start_date, end_date)])
            df_report = df_report[df_report["Tháng"].isin([f"{m}/{y}" for y, m in relevant_months])]
            
            # Pivot để so sánh
            if not df_report.empty:
                rp_pivot = df_report.pivot(index="Nhân viên", columns="Tháng", values="Tổng giờ").fillna(0)
                # Tô màu để thấy ai thấp/cao
                st.dataframe(rp_pivot.style.background_gradient(cmap="RdYlGn", axis=0))
                
                st.write(f"*Lưu ý: Giới hạn tối đa là {max_hours_per_month} giờ/tháng.*")
            else:
                st.info("Chưa có dữ liệu giờ cho khoảng thời gian này.")

        with tab3:
            st.dataframe(df_total)

        # --- SAVE TO SHEETS ---
        # Chuẩn bị định dạng lưu
        df_save_raw = df_total.copy()
        if "MonthKey" in df_save_raw.columns:
            del df_save_raw["MonthKey"]
        if "Loại Ca" in df_save_raw.columns:
            del df_save_raw["Loại Ca"]
            
        df_save_raw["Ngày"] = df_save_raw["Ngày"].dt.strftime("%d/%m/%Y")
        
        # Ghi đè Data_Log
        conn.update(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Data_Log",
            data=df_save_raw
        )
        
        # Tạo bản view cho Sheet Lich_Truc
        df_sheet_view = df_pivot.drop(columns=["Ngày"]).rename(columns={"Ngày Str": "Ngày"})
        conn.update(
            spreadsheet=SPREADSHEET_URL,
            worksheet="Lich_Truc",
            data=df_sheet_view
        )
        
        st.success("✅ Đã cập nhật lịch lên Google Sheets thành công!")

# ==================================================
# HIỂN THỊ TRẠNG THÁI HIỆN TẠI
# ==================================================
st.divider()
st.subheader("📊 Trạng thái lũy kế (Lifetime) trước khi chạy")
st.caption("Thuật toán sẽ ưu tiên người có giờ thấp để cân bằng.")
df_lifetime = pd.DataFrame(list(lifetime_hours.items()), columns=["Nhân viên", "Tổng giờ (All time)"])
st.dataframe(df_lifetime.sort_values("Tổng giờ (All time)"))
