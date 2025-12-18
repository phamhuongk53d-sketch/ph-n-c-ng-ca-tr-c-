import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH HỆ THỐNG
# ==================================================
st.set_page_config(
    page_title="Hệ thống Trực Công Bằng 2025",
    layout="wide",
    page_icon="📅"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# 2. HÀM HỖ TRỢ
# ==================================================
def get_vietnamese_weekday(d):
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return weekdays[d.weekday()]

# ==================================================
# 3. TẢI VÀ CHUẨN HÓA DỮ LIỆU
# ==================================================
@st.cache_data(ttl=2)
def load_and_clean_data():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
        df.columns = df.columns.str.strip()
        if not df.empty:
            # Ép kiểu ngày tháng và xử lý lỗi định dạng
            df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Ngày"])
            df["Giờ"] = pd.to_numeric(df["Giờ"], errors="coerce").fillna(0)
        return df
    except:
        return pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

df_raw = load_and_clean_data()

# ==================================================
# 4. CẤU HÌNH NHÂN SỰ (SIDEBAR)
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    
    special_staff = st.multiselect("Nhân viên chỉ trực ngày (Nghỉ T7/CN)", staff, default=["Trung", "Ngà"])
    
    st.divider()
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))
    max_hours = st.number_input("Giới hạn giờ/tháng", value=176)

# ==================================================
# 5. TÍNH TOÁN LŨY KẾ & CÔNG BẰNG
# ==================================================
# Tính tổng giờ lịch sử để phân bổ công bằng
history_before = df_raw[df_raw["Ngày"].dt.date < start_date].copy()
lifetime_hours = {s: history_before[history_before["Nhân viên"] == s]["Giờ"].sum() for s in staff}

# Theo dõi giờ theo tháng để không quá 176h
monthly_history = {}
if not history_before.empty:
    history_before["MonthKey"] = history_before["Ngày"].dt.to_period('M')
    for idx, row in history_before.iterrows():
        key = (row["Nhân viên"], row["MonthKey"])
        monthly_history[key] = monthly_history.get(key, 0) + row["Giờ"]

# ==================================================
# 6. THUẬT TOÁN PHÂN CA TỐI ƯU
# ==================================================
def generate_schedule():
    rows = []
    current_lifetime = lifetime_hours.copy()
    current_monthly = monthly_history.copy()
    # Theo dõi thời gian rảnh của mỗi người
    available_at = {s: datetime.combine(start_date, time(0,0)) for s in staff}

    curr = start_date
    while curr <= end_date:
        d_start = datetime.combine(curr, time(8, 0))
        d_night = datetime.combine(curr, time(16, 0))
        m_key = pd.Period(curr, freq='M')
        is_weekend = curr.weekday() >= 5

        # --- PHÂN CA NGÀY (8h-16h) ---
        day_pool = [s for s in staff if available_at[s] <= d_start and current_monthly.get((s, m_key), 0) + 8 <= max_hours]
        if s in special_staff and is_weekend: day_pool = [s for s in day_pool if s not in special_staff]
        
        # Ưu tiên người ít giờ nhất
        day_pool.sort(key=lambda x: (0 if x in special_staff and not is_weekend else 1, current_lifetime[x]))
        for s in day_pool[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 8h00 - 16h00", "Nhân viên": s, "Giờ": 8})
            current_lifetime[s] += 8
            current_monthly[(s, m_key)] = current_monthly.get((s, m_key), 0) + 8
            available_at[s] = d_start + timedelta(hours=8 + 16) # Nghỉ 16h sau ca ngày

        # --- PHÂN CA ĐÊM (16h-8h sáng mai) ---
        night_pool = [s for s in staff if s not in special_staff and available_at[s] <= d_night and current_monthly.get((s, m_key), 0) + 16 <= max_hours]
        night_pool.sort(key=lambda x: current_lifetime[x])
        for s in night_pool[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 16h00 - 8h00", "Nhân viên": s, "Giờ": 16})
            current_lifetime[s] += 16
            current_monthly[(s, m_key)] = current_monthly.get((s, m_key), 0) + 16
            available_at[s] = d_night + timedelta(hours=16 + 24) # Nghỉ 24h sau ca đêm

        curr += timedelta(days=1)
    return pd.DataFrame(rows)

# ==================================================
# 7. XỬ LÝ GIAO DIỆN & CẬP NHẬT
# ==================================================
st.title("⚖️ Hệ thống Trực Công Bằng 2025")

if st.button("🚀 CHẠY PHÂN LỊCH & CẬP NHẬT GOOGLE SHEETS"):
    df_new = generate_schedule()
    if not df_new.empty:
        # Hợp nhất và chuẩn hóa ngày tháng ĐÚNG CÁCH để tránh lỗi .dt
        df_total = pd.concat([history_before, df_new], ignore_index=True)
        df_total["Ngày"] = pd.to_datetime(df_total["Ngày"]) 

        # Hiển thị lịch mới
        st.subheader("🗓️ Lịch trực dự kiến")
        df_view = df_new.copy()
        df_view["Ngày Hiển Thị"] = df_view["Ngày"].apply(lambda x: f"{get_vietnamese_weekday(x)} ({x.strftime('%d/%m')})")
        df_pivot = df_view.groupby(["Ngày Hiển Thị", "Ca"])["Nhân viên"].apply(", ".join).unstack().fillna("-")
        st.table(df_pivot)

        # Báo cáo tổng giờ
        st.subheader("📊 Tổng kết giờ làm trong tháng")
        df_new["Tháng"] = df_new["Ngày"].dt.strftime('%m/%Y')
        summary = df_new.groupby(["Nhân viên", "Tháng"])["Giờ"].sum().unstack().fillna(0)
        st.dataframe(summary) # Sử dụng dataframe cơ bản nếu thiếu matplotlib

        # Ghi dữ liệu
        with st.spinner("Đang lưu dữ liệu..."):
            # Lưu Data Log
            df_save = df_total.copy()
            df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_save)
            
            # Lưu bản xem cho người dùng
            df_export = df_pivot.reset_index()
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_export)
            
        st.success("✅ Đã cập nhật thành công lên Google Sheets!")
    else:
        st.error("Không thể tạo lịch. Vui lòng kiểm tra lại cấu hình nhân sự.")

# Hiển thị bảng giờ lũy kế hiện tại
st.divider()
st.write("📌 **Giờ trực tích lũy hiện tại (All-time):**")
st.bar_chart(pd.Series(lifetime_hours))
