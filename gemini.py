import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# 1. CẤU HÌNH TRANG & KẾT NỐI
# ==================================================
st.set_page_config(page_title="Lịch trực ca – FINAL", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit"
SHEET_DATA = "Data_Log"
SHEET_VIEW = "Lich_Truc"

REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]
conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# 2. HÀM TIỆN ÍCH
# ==================================================
def vn_day(d):
    """Định dạng ngày tiếng Việt: T2 - 01/01/2024"""
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
# 3. ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
try:
    df_old = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_old = ensure_df(df_old)
    df_old = parse_date(df_old)
    df_old["Giờ"] = pd.to_numeric(df_old["Giờ"], errors="coerce").fillna(0)
except Exception:
    df_old = pd.DataFrame(columns=REQUIRED_COLS)

# ==================================================
# 4. SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("👥 Nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, HươngB"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = ["Trung", "Ngà"]

    st.header("📅 Khoảng thời gian")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

    st.header("🔄 Thay đổi nhân sự")
    change_date = st.date_input("Áp dụng từ ngày", start_date)
    absent_staff = st.multiselect("Nhân sự nghỉ / bận từ ngày này", staff)

# Kiểm tra ngày quá khứ
today = datetime.now().date()
if start_date < today or change_date < today:
    st.error("❌ Không được thay đổi hoặc tạo lịch ở thời gian quá khứ.")
    st.stop()

# ==================================================
# 5. THUẬT TOÁN PHÂN CA
# ==================================================
def generate_schedule():
    df_fixed = df_old[df_old["Ngày"].dt.date < change_date].copy()
    
    # Tính giờ lũy kế
    hours = {s: df_fixed[df_fixed["Nhân viên"] == s]["Giờ"].sum() for s in staff}
    
    rows = []
    active_staff = [s for s in staff if s not in absent_staff]
    available_at = {s: datetime.min for s in active_staff}

    curr = change_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekday = curr.weekday() < 5

        # CA NGÀY
        day_candidates = []
        for s in active_staff:
            if available_at[s] <= base.replace(hour=8):
                if s in special_staff:
                    if is_weekday: day_candidates.append(s)
                else:
                    day_candidates.append(s)

        day_candidates.sort(key=lambda s: hours[s])
        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca ngày", "Nhân viên": s, "Giờ": 8})
            hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)

        # CA ĐÊM
        night_candidates = [
            s for s in active_staff
            if s not in special_staff and available_at[s] <= base.replace(hour=16)
        ]
        night_candidates.sort(key=lambda s: hours[s])

        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca đêm", "Nhân viên": s, "Giờ": 16})
            hours[s] += 16
            available_at[s] = base + timedelta(days=2)

        curr += timedelta(days=1)

    df_new = pd.DataFrame(rows)
    df_result = pd.concat([df_fixed, df_new], ignore_index=True)
    return parse_date(df_result).sort_values("Ngày")

# ==================================================
# 6. HIỂN THỊ GIAO DIỆN CHÍNH
# ==================================================
st.title(" Hệ thống Quản lý Lịch trực")

if st.button(" TẠO / CẬP NHẬT LỊCH"):
    df_all = generate_schedule()
    
    # Hiển thị bảng lịch trực
    rows_display = []
    for d, g in df_all.groupby("Ngày", sort=False):
        rows_display.append({
            "Ngày": vn_day(d),
            "Ca: 8h00 – 16h00": ", ".join(g[g["Ca"] == "Ca ngày"]["Nhân viên"]),
            "Ca: 16h00 – 8h00": ", ".join(g[g["Ca"] == "Ca đêm"]["Nhân viên"])
        })
    df_display = pd.DataFrame(rows_display)
    
    st.subheader("📋 LỊCH TRỰC CHI TIẾT")
    st.dataframe(df_display, use_container_width=True)

    # Lưu Google Sheets
    df_save = df_all.copy()
    df_save["Ngày"] = df_save["Ngày"].dt.strftime("%d/%m/%Y")
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, data=df_save)
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_VIEW, data=df_display)
    st.success("✅ Đã cập nhật lịch thành công!")

st.write("---")

# ==================================================
# 7. THỐNG KÊ TỔNG GIỜ (YÊU CẦU MỚI)
# ==================================================
st.subheader("📊 THỐNG KÊ CÔNG TRỰC")

if st.button("🔢 TỔNG SỐ GIỜ TRỰC"):
    if df_old.empty:
        st.warning("⚠️ Không có dữ liệu trong Data_Log để thống kê.")
    else:
        # Xử lý dữ liệu thống kê
        df_stats = df_old.copy()
        
        # Tạo cột trung gian để sắp xếp thời gian chuẩn
        df_stats['Tháng_Năm_Sort'] = df_stats['Ngày'].dt.to_period('M')
        df_stats['Năm'] = df_stats['Ngày'].dt.year
        
        # --- BẢNG THÁNG ---
        st.markdown("### 📅 Tổng giờ theo Tháng")
        
        # Tính tổng theo nhân viên và tháng
        summary_month = df_stats.groupby(['Nhân viên', 'Tháng_Năm_Sort'])['Giờ'].sum().reset_index()
        summary_month['Thời gian'] = summary_month['Tháng_Năm_Sort'].dt.strftime('Tháng %m/%Y')
        
        # Xoay bảng (Pivot)
        pivot_month = summary_month.pivot(index='Nhân viên', columns='Thời gian', values='Giờ').fillna(0)
        
        # Sắp xếp các cột theo thời gian tăng dần (không phải Alphabet)
        sorted_month_cols = sorted(pivot_month.columns, key=lambda x: datetime.strptime(x, 'Tháng %m/%Y'))
        pivot_month = pivot_month[sorted_month_cols]
        
        # Định dạng hiển thị số nguyên và tô màu
        st.dataframe(
            pivot_month.style.format("{:.0f}")
            .highlight_max(axis=0, color="#90ee90"),
            use_container_width=True
        )

        # --- BẢNG NĂM ---
        st.write("")
        st.markdown("### 🗓️ Tổng giờ theo Năm")
        
        summary_year = df_stats.groupby(['Nhân viên', 'Năm'])['Giờ'].sum().reset_index()
        pivot_year = summary_year.pivot(index='Nhân viên', columns='Năm', values='Giờ').fillna(0)
        
        st.dataframe(
            pivot_year.style.format("{:.0f} giờ")
            .highlight_max(axis=0, color="#ffebcc"),
            use_container_width=True
        )
        
        st.success("✅ Đã trích xuất dữ liệu tổng hợp thành công!")

