import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH TRANG & KẾT NỐI
# ==================================================
st.set_page_config(page_title="Lịch trực & Thống kê giờ công", layout="wide")

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
    # Chuyển đổi ngày tháng và xử lý lỗi
    df["Ngày"] = pd.to_datetime(df["Ngày"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Ngày"])

# ==================================================
# 3. ĐỌC DỮ LIỆU
# ==================================================
try:
    df_old = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_old = ensure_df(df_old)
    df_old = parse_date(df_old)
    df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)
except Exception as e:
    st.error(f"Lỗi kết nối: {e}")
    df_old = pd.DataFrame(columns=REQUIRED_COLS)

# ==================================================
# 4. SIDEBAR - CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("⚙️ Cấu hình")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = ["Trung", "Ngà"]

    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))
    change_date = st.date_input("Ngày áp dụng thay đổi", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ", staff)

# ==================================================
# 5. THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    rows = []
    df_fixed = df_old[df_old["Ngày"].dt.date < change_date].copy()
    current_hours = {s: df_fixed[df_fixed["Nhân viên"] == s]["Giờ"].sum() for s in staff}
    active_staff = [s for s in staff if s not in absent_staff]
    available_at = {s: datetime.min for s in active_staff}

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5
        
        # Ca Ngày
        day_candidates = [s for s in active_staff if available_at[s] <= base.replace(hour=8)]
        day_candidates = [s for s in day_candidates if (s in special_staff and is_weekday) or (s not in special_staff)]
        day_candidates.sort(key=lambda s: current_hours[s])
        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca ngày", "Nhân viên": s, "Giờ": 8})
            current_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # Ca Đêm
        night_candidates = [s for s in active_staff if s not in special_staff and available_at[s] <= base.replace(hour=16)]
        night_candidates.sort(key=lambda s: current_hours[s])
        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm", "Nhân viên": s, "Giờ": 16})
            current_hours[s] += 16
            available_at[s] = base + timedelta(days=2)
        curr += timedelta(days=1)

    df_new = pd.DataFrame(rows)
    df_new["Ngày"] = pd.to_datetime(df_new["Ngày"])
    return pd.concat([df_fixed, df_new], ignore_index=True).sort_values("Ngày")

# ==================================================
# 6. GIAO DIỆN CHÍNH
# ==================================================
st.title("🗓️ Quản lý Lịch trực")

if st.button("🚀 TẠO / CẬP NHẬT LỊCH"):
    df_all = generate_schedule()
    rows_display = []
    for d, g in df_all.groupby("Ngày", sort=False):
        rows_display.append({
            "Ngày": vn_day(d),
            "Ca: 8h00 – 16h00": ", ".join(g[g["Ca"] == "Ca ngày"]["Nhân viên"]),
            "Ca: 16h00 – 8h00": ", ".join(g[g["Ca"] == "Ca đêm"]["Nhân viên"])
        })
    st.dataframe(pd.DataFrame(rows_display), use_container_width=True)
    
    # Lưu Sheets
    df_save = df_all.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
    st.success("✅ Đã cập nhật lên Google Sheets!")

st.write("---")

# ==================================================
# 7. PHẦN SỬA ĐỔI: THỐNG KÊ GIỜ CÔNG (ĐÃ FIX LỖI)
# ==================================================
st.subheader("📊 THỐNG KÊ TỔNG GIỜ TRỰC")

if st.button("🔢 TÍNH TỔNG SỐ GIỜ TRỰC"):
    if df_old.empty:
        st.warning("Dữ liệu trống.")
    else:
        df_stats = df_old.copy()
        
        # 1. Xử lý hiển thị theo Tháng
        st.markdown("#### 📅 Tổng giờ theo Tháng")
        
        # Tạo cột Period để sắp xếp chuẩn theo thời gian (không bị lỗi T1/2026 đứng trước T12/2025)
        df_stats['Month_Sort'] = df_stats['Ngày'].dt.to_period('M')
        
        summary_month = df_stats.groupby(['Nhân viên', 'Month_Sort'])['Giờ'].sum().reset_index()
        summary_month['Thời gian'] = summary_month['Month_Sort'].dt.strftime('T%m/%Y')
        
        # Pivot bảng
        pivot_month = summary_month.pivot(index='Nhân viên', columns='Thời gian', values='Giờ').fillna(0)
        
        # Sắp xếp lại các cột theo thứ tự thời gian tăng dần
        sorted_cols = sorted(pivot_month.columns, key=lambda x: datetime.strptime(x, 'T%m/%Y'))
        pivot_month = pivot_month[sorted_cols]

        # Hiển thị: ép kiểu về số nguyên và tô màu
        st.dataframe(
            pivot_month.style.format("{:.0f}")  # Hiển thị số nguyên, bỏ .000000
            .highlight_max(axis=0, color='#90ee90'), 
            use_container_width=True
        )

        # 2. Xử lý hiển thị theo Năm
        st.write("")
        st.markdown("#### 🗓️ Tổng giờ theo Năm")
        df_stats['Năm'] = df_stats['Ngày'].dt.year
        summary_year = df_stats.groupby(['Nhân viên', 'Năm'])['Giờ'].sum().reset_index()
        pivot_year = summary_year.pivot(index='Nhân viên', columns='Năm', values='Giờ').fillna(0)
        
        st.dataframe(
            pivot_year.style.format("{:.0f} giờ")
            .highlight_max(axis=0, color='#ffebcc'),
            use_container_width=True
        )
