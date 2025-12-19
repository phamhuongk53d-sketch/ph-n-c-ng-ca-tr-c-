import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==================================================
# CẤU HÌNH
# ==================================================
st.set_page_config(page_title="Hệ thống phân công trực", layout="wide")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"
SHEET_DATA = "Data_Log"
REQUIRED_COLS = ["Ngày", "Ca", "Nhân viên", "Giờ"]

conn = st.connection("gsheets", type=GSheetsConnection)

# ==================================================
# HÀM HỖ TRỢ HIỂN THỊ
# ==================================================
def format_view_table(df):
    """Biến đổi bảng: Gộp nhân viên cùng ca vào 1 hàng"""
    if df.empty: return df
    
    # Tạo bản sao và format ngày
    df_view = df.copy()
    df_view['Thứ/Ngày'] = df_view['Ngày'].dt.strftime('%a %d/%m/%Y')
    
    # Gộp tên nhân viên trực cùng ca
    df_pivot = df_view.groupby(['Thứ/Ngày', 'Ca'])['Nhân viên'].apply(lambda x: ', '.join(x)).unstack()
    df_pivot = df_pivot.reset_index()
    return df_pivot

# ==================================================
# ĐỌC VÀ XỬ LÝ DỮ LIỆU
# ==================================================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_DATA, ttl=0)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    df_raw['Ngày'] = pd.to_datetime(df_raw['Ngày'], dayfirst=True)
    df_raw['Giờ'] = pd.to_numeric(df_raw['Giờ'], errors='coerce').fillna(0)
except:
    df_raw = pd.DataFrame(columns=REQUIRED_COLS)

# ==================================================
# TÍNH TOÁN TỔNG GIỜ (THÁNG/NĂM)
# ==================================================
now = datetime.now()
current_month = now.month
current_year = now.year

# Lọc dữ liệu theo năm hiện tại
df_year = df_raw[df_raw['Ngày'].dt.year == current_year]
# Lọc dữ liệu theo tháng hiện tại (từ ngày 01 đến nay)
df_month = df_year[df_year['Ngày'].dt.month == current_month]

# Tính tổng
sum_year = df_year.groupby('Nhân viên')['Giờ'].sum().reset_index().rename(columns={'Giờ': f'Tổng giờ năm {current_year}'})
sum_month = df_month.groupby('Nhân viên')['Giờ'].sum().reset_index().rename(columns={'Giờ': f'Tổng giờ tháng {current_month}'})

# Gộp bảng tổng kết
df_summary = pd.merge(sum_month, sum_year, on='Nhân viên', how='outer').fillna(0)

# ==================================================
# GIAO DIỆN HIỂN THỊ
# ==================================================
st.title("📊 BẢNG THEO DÕI TRỰC")

# --- PHẦN 1: TỔNG HỢP GIỜ CÔNG ---
st.subheader(f"⏱️ Tổng kết giờ trực (Tháng {current_month} & Năm {current_year})")
cols = st.columns(len(df_summary))
for i, row in df_summary.iterrows():
    with st.container():
        st.info(f"**{row['Nhân viên']}**\n\nTháng: {row[1]}h | Năm: {row[2]}h")

# --- PHẦN 2: LỊCH TRỰC CHI TIẾT ---
st.subheader("📅 Lịch trực chi tiết (Người trực cùng ca trên 1 hàng)")
if not df_raw.empty:
    # Hiển thị bảng đã được pivot
    view_table = format_view_table(df_raw.sort_values('Ngày', ascending=False))
    st.dataframe(view_table, use_container_width=True, hide_index=True)
else:
    st.write("Chưa có dữ liệu lịch trực.")

# ==================================================
# SIDEBAR - GIỮ NGUYÊN LOGIC TẠO LỊCH CỦA BẠN
# ==================================================
with st.sidebar:
    st.header("Cài đặt nhân sự & Tạo lịch")
    # ... (Giữ nguyên phần code xử lý nút bấm và thuật toán của bạn ở đây)
    # Lưu ý: Khi lưu xuống Google Sheets, hãy lưu df_total (dạng dọc) để dễ tính toán, 
    # còn hiển thị trên Streamlit thì dùng view_table.
