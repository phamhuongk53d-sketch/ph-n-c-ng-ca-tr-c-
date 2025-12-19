import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH STREAMLIT
# ==================================================
st.set_page_config(page_title="Hệ thống Trực Công Bằng 2026", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM TIỆN ÍCH
# ==================================================
def get_vietnamese_weekday(d: pd.Timestamp) -> str:
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{weekdays[d.weekday()]}- {d.strftime('%d/%m')}"

# ==================================================
# ĐỌC VÀ XỬ LÝ DỮ LIỆU GỐC
# ==================================================
@st.cache_data(ttl=0)
def load_and_clean_data():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])
        
        # Xử lý lỗi KeyError: Chuẩn hóa tên cột (xóa khoảng trắng thừa, ẩn)
        df.columns = [str(col).strip() for col in df.columns]
        
        if "Ngày" in df.columns:
            df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Ngày"])
        return df
    except Exception as e:
        st.error(f"Không thể đọc dữ liệu: {e}")
        return pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

df_raw = load_and_clean_data()

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("👥 Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect("Chỉ trực ca ngày (T2-T6)", staff, default=["Trung", "Ngà"])

    st.header("📅 Thời gian phân lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

# ==================================================
# XỬ LÝ LŨY KẾ & THAY THẾ DỮ LIỆU
# ==================================================
# Giữ lại dữ liệu nằm ngoài khoảng thời gian đang chọn (Để thay thế dữ liệu cũ)
history_keep = df_raw[df_raw["Ngày"].dt.date < start_date].copy()
future_keep = df_raw[df_raw["Ngày"].dt.date > end_date].copy()

# Tính lũy kế giờ làm việc từ lịch sử để đảm bảo công bằng
luy_ke_hours = {s: history_keep.loc[history_keep["Nhân viên"] == s, "Giờ"].sum() for s in staff}

# ==================================================
# THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    work_hours = luy_ke_hours.copy()
    # Theo dõi thời gian nghỉ: Tránh trực ca quá gần nhau
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekend = curr.weekday() >= 5 

        # --- CA NGÀY (08:00 - 16:00) ---
        day_pool = [s for s in staff if available_at[s] <= base.replace(hour=8)]
        if is_weekend:
            day_pool = [s for s in day_pool if s not in special_staff]
        
        # Sắp xếp chọn người ít giờ nhất
        day_pool.sort(key=lambda x: work_hours.get(x, 0))
        selected_day = day_pool[:2]

        for s in selected_day:
            rows.append({"Ngày": curr, "Ca": "Ca: 8h00 - 16h00", "Nhân viên": s, "Giờ": 8})
            work_hours[s] = work_hours.get(s, 0) + 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # --- CA ĐÊM (16:00 - 08:00) ---
        night_pool = [s for s in staff if s not in special_staff and s not in selected_day and available_at[s] <= base.replace(hour=16)]
        night_pool.sort(key=lambda x: work_hours.get(x, 0))
        selected_night = night_pool[:2]

        for s in selected_night:
            rows.append({"Ngày": curr, "Ca": "Ca: 16h00 - 8h00", "Nhân viên": s, "Giờ": 16})
            work_hours[s] = work_hours.get(s, 0) + 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)
    return pd.DataFrame(rows)

# ==================================================
# THỰC THI & HIỂN THỊ
# ==================================================
if st.button("🚀 CẬP NHẬT LỊCH TRỰC (THAY THẾ DỮ LIỆU CŨ)"):
    df_new = generate_schedule()
    
    # Ghép dữ liệu: [Cũ] + [Mới tạo] + [Tương lai] -> Tạo cơ chế thay thế vùng dữ liệu trùng
    df_final = pd.concat([history_keep, df_new, future_keep], ignore_index=True)
    df_final = df_final.sort_values(by="Ngày")

    # HIỂN THỊ CHIA THEO THÁNG
    st.write("---")
    df_show = df_final.copy()
    df_show["Tháng"] = df_show["Ngày"].dt.month
    df_show["Năm"] = df_show["Ngày"].dt.year
    
    unique_months = df_show[["Năm", "Tháng"]].drop_duplicates().sort_values(["Năm", "Tháng"])

    all_pivots = []
    for _, row in unique_months.iterrows():
        y, m = row["Năm"], row["Tháng"]
        st.markdown(f"### 📅 LỊCH PHÂN CÔNG THÁNG {m} NĂM {y}")
        
        # Lọc dữ liệu tháng
        mask = (df_show["Năm"] == y) & (df_show["Tháng"] == m)
        m_data = df_show[mask].copy()
        
        # Pivot table
        m_pivot = m_data.groupby(["Ngày", "Ca"])["Nhân viên"].apply(lambda x: ", ".join(x)).unstack(fill_value="")
        
        # Kiểm tra đủ cột
        for col in ["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"]:
            if col not in m_pivot.columns: m_pivot[col] = ""
        
        m_pivot = m_pivot[["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"]].reset_index()
        m_pivot_display = m_pivot.copy()
        m_pivot_display["Ngày"] = m_pivot_display["Ngày"].apply(get_vietnamese_weekday)
        
        st.table(m_pivot_display)
        all_pivots.append(m_pivot_display)

    # GHI DỮ LIỆU
    df_save = df_final.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
    
    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_save)
        st.success("✅ Đã cập nhật Data_Log và thay thế dữ liệu trùng khớp thành công!")
        st.balloons()
    except Exception as e:
        st.error(f"Lỗi khi lưu dữ liệu: {e}")

else:
    st.info("Vui lòng cấu hình nhân sự ở Sidebar và nhấn nút để tạo lịch.")
