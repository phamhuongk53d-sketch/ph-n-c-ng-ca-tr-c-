import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH HỆ THỐNG
# ==================================================
st.set_page_config(page_title="Lịch trực ca – Tối ưu hóa", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"
REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# 2. HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    return f"{days[d.weekday()]} - {d.strftime('%d/%m/%Y')}"

def ensure_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[REQUIRED_COLS]

def parse_date(df):
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Ngày"])

# ==================================================
# 3. ĐỌC DỮ LIỆU GỐC
# ==================================================
try:
    df_old = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_old = ensure_df(df_old)
    df_old = parse_date(df_old)
    df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)
except Exception:
    df_old = pd.DataFrame(columns=REQUIRED_COLS)

# ==================================================
# 4. SIDEBAR - CẤU HÌNH NHÂN SỰ & THỜI GIAN
# ==================================================
with st.sidebar:
    st.header("👥 Quản lý Nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = ["Trung", "Ngà"] # Nhóm luôn trực ca ngày T2-T6

    st.header("📅 Khoảng thời gian")
    start_date = st.date_input("Ngày bắt đầu lịch mới", datetime.now().date())
    end_date = st.date_input("Ngày kết thúc", start_date + timedelta(days=30))

    st.header("🔄 Thay đổi nhân sự")
    change_date = st.date_input("Áp dụng thay đổi từ ngày", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ / bận", staff)

# --- CHẶN THAO TÁC QUÁ KHỨ ---
today = datetime.now().date()
if start_date < today or change_date < today:
    st.error("❌ Không được phép tạo lịch hoặc thay đổi nhân sự cho các ngày trong quá khứ.")
    st.stop()

# ==================================================
# 5. THUẬT TOÁN PHÂN CA TỰ ĐỘNG
# ==================================================
def generate_schedule():
    df_fixed = df_old[df_old["Ngày"].dt.date < change_date].copy()
    hours = {s: df_fixed[df_fixed["Nhân viên"] == s]["Giờ"].sum() for s in staff}
    
    rows = []
    active_staff = [s for s in staff if s not in absent_staff]
    available_at = {s: datetime.min for s in active_staff}

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5 # T2 - T6

        # --- CA NGÀY (8h - 16h) ---
        day_shift_staff = []
        
        # Ưu tiên Trung, Ngà vào ca ngày nếu là ngày trong tuần và không nghỉ
        if is_weekday:
            for s in special_staff:
                if s in active_staff and available_at[s] <= base.replace(hour=8):
                    day_shift_staff.append(s)
        
        # Nếu thiếu người (cuối tuần hoặc Trung/Ngà nghỉ), lấy nhân viên khác luân phiên
        if len(day_shift_staff) < 2:
            candidates = [
                s for s in active_staff 
                if s not in special_staff and s not in day_shift_staff
                and available_at[s] <= base.replace(hour=8)
            ]
            candidates.sort(key=lambda x: hours[x])
            needed = 2 - len(day_shift_staff)
            day_shift_staff.extend(candidates[:needed])

        for s in day_shift_staff:
            rows.append({"Ngày": curr, "Ca": "Ca ngày", "Nhân viên": s, "Giờ": 8})
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # --- CA ĐÊM (16h - 8h) ---
        # Trung và Ngà KHÔNG BAO GIỜ trực ca đêm
        night_candidates = [
            s for s in active_staff 
            if s not in special_staff and s not in day_shift_staff
            and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda x: hours[x])
        
        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm", "Nhân viên": s, "Giờ": 16})
            hours[s] += 16
            available_at[s] = base + timedelta(days=2) # Nghỉ hồi phục sau ca đêm

        curr += timedelta(days=1)

    df_new = pd.DataFrame(rows)
    return pd.concat([df_fixed, df_new], ignore_index=True).sort_values("Ngày")

# ==================================================
# 6. HIỂN THỊ LỊCH TRỰC
# ==================================================
st.title("🗓️ Quản lý Lịch trực & Công tác")

if st.button("🚀 TẠO / CẬP NHẬT LỊCH TRỰC", type="primary"):
    with st.spinner("Đang tính toán lịch trực..."):
        df_all = generate_schedule()
        
        # Tạo bảng hiển thị
        display_data = []
        for d, g in df_all.groupby("Ngày", sort=False):
            display_data.append({
                "Ngày": vn_day(d),
                "Ca: 8h00 – 16h00": ", ".join(g[g["Ca"] == "Ca ngày"]["Nhân viên"]),
                "Ca: 16h00 – 8h00": ", ".join(g[g["Ca"] == "Ca đêm"]["Nhân viên"])
            })
        df_display = pd.DataFrame(display_data)
        
        st.subheader("📋 BẢNG PHÂN CA CHI TIẾT")
        st.dataframe(df_display, use_container_width=True)

        # Cập nhật lên Google Sheets
        df_save = df_all.copy()
        df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_display)
        st.success("✅ Đã lưu lịch mới vào hệ thống!")

st.write("---")

# ==================================================
# 7. TỔNG HỢP GIỜ TRỰC (THEO YÊU CẦU)
# ==================================================
st.subheader("📊 THỐNG KÊ TỔNG GIỜ CÔNG")

if st.button("🔢 TÍNH TỔNG SỐ GIỜ TRỰC"):
    if df_old.empty:
        st.warning("⚠️ Không có dữ liệu lịch sử trong Data_Log.")
    else:
        df_stats = df_old.copy()
        
        # Sắp xếp theo tháng/năm chuẩn xác
        df_stats['Sort_Key'] = df_stats['Ngày'].dt.to_period('M')
        df_stats['Tháng'] = df_stats['Sort_Key'].dt.strftime('Tháng %m/%Y')
        df_stats['Năm'] = df_stats['Ngày'].dt.year
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### 📅 Tổng giờ theo Tháng")
            summary_month = df_stats.groupby(['Nhân viên', 'Sort_Key', 'Tháng'])['Giờ'].sum().reset_index()
            pivot_month = summary_month.pivot(index='Nhân viên', columns='Tháng', values='Giờ').fillna(0)
            
            # Đảm bảo thứ tự cột theo thời gian
            sorted_months = summary_month.sort_values('Sort_Key')['Tháng'].unique()
            pivot_month = pivot_month[sorted_months]
            
            st.dataframe(pivot_month.style.format("{:.0f}"), use_container_width=True)

        with col2:
            st.markdown("#### 🗓️ Tổng giờ theo Năm")
            summary_year = df_stats.groupby(['Nhân viên', 'Năm'])['Giờ'].sum().reset_index()
            pivot_year = summary_year.pivot(index='Nhân viên', columns='Năm', values='Giờ').fillna(0)
            st.dataframe(pivot_year.style.format("{:.0f}"), use_container_width=True)
            
        st.info("💡 Số liệu được tính toán dựa trên toàn bộ dữ liệu hiện có trong sheet Data_Log.")
