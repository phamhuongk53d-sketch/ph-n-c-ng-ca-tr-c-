import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Hệ thống Trực Công Bằng 2025", layout="wide")

# ================== CẤU HÌNH ==================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IQg-gXpWWL14FjpiPNAaNAOpsRlXv6BWnm9_GOSLOEE/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ================== HÀM TIỆN ÍCH ==================
def get_vietnamese_weekday(d):
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    # Trả về định dạng: T2- 1/12 (bỏ số 0 ở ngày để giống mẫu h1.jpg)
    return f"{weekdays[d.weekday()]}- {d.day}/{d.month}"

# ================== ĐỌC DỮ LIỆU ==================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
except Exception:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

if not df_raw.empty:
    df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce").dt.date
    df_raw = df_raw.dropna(subset=["Ngày"])
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("Cấu hình nhân sự")
    staff_input = st.text_area("Danh sách nhân viên", "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B")
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]
    special_staff = st.multiselect("Chỉ trực ca ngày", staff, default=["Trung", "Ngà"])
    
    st.header("Thời gian phân lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

# ================== TÍNH LŨY KẾ ==================
history_before = df_raw[df_raw["Ngày"] < start_date].copy()
luy_ke_hours = {s: history_before.loc[history_before["Nhân viên"] == s, "Giờ"].sum() for s in staff}

st.subheader(f"📊 Tổng giờ lũy kế đến hết ngày {start_date - timedelta(days=1)}")
st.dataframe(pd.DataFrame([luy_ke_hours]))

# ================== THUẬT TOÁN PHÂN LỊCH ==================
def generate_schedule():
    rows = []
    work_hours = luy_ke_hours.copy()
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}
    
    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        # --- CA NGÀY ---
        day_candidates = [s for s in staff if available_at[s] <= base.replace(hour=8)]
        day_candidates.sort(key=lambda s: (0 if s in special_staff else 1, work_hours[s]))
        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 8h00 - 16h00", "Nhân viên": s, "Giờ": 8})
            work_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16)
        # --- CA ĐÊM ---
        night_candidates = [s for s in staff if s not in special_staff and available_at[s] <= base.replace(hour=16)]
        night_candidates.sort(key=lambda s: work_hours[s])
        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 16h00 - 8h00", "Nhân viên": s, "Giờ": 16})
            work_hours[s] += 16
            available_at[s] = base + timedelta(days=2)
        curr += timedelta(days=1)
    return pd.DataFrame(rows)

# ================== TẠO & LƯU LỊCH ==================
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT"):
    df_new = generate_schedule()
    # Gộp lịch sử cũ và lịch mới
    df_total = pd.concat([history_before, df_new], ignore_index=True)
    
    # 1. Sắp xếp theo ngày thực tế (datetime) trước khi pivot
    df_total = df_total.sort_values(by="Ngày")

    # 2. Xử lý gộp tên nhân viên cho bản hiển thị
    df_view = df_total.copy()
    # Gộp tên nhân viên theo Ngày và Ca (Ví dụ: "Trung Ngà")
    df_pivot = df_view.groupby(["Ngày", "Ca"])["Nhân viên"].apply(lambda x: " ".join(x)).reset_index()
    
    # 3. Pivot bảng (Xoay bảng)
    df_pivot = df_pivot.pivot(index="Ngày", columns="Ca", values="Nhân viên").reset_index()
    
    # 4. Đảm bảo luôn hiển thị đủ 2 cột ca trực và đúng thứ tự cột
    ca_ngay = "Ca: 8h00 - 16h00"
    ca_dem = "Ca: 16h00 - 8h00"
    for c in [ca_ngay, ca_dem]:
        if c not in df_pivot.columns: df_pivot[c] = ""
    
    # 5. Chuyển cột Ngày sang định dạng văn bản sau khi đã sắp xếp xong xuôi
    df_pivot["Ngày_HT"] = df_pivot["Ngày"].apply(get_vietnamese_weekday)
    
    # Chỉ lấy các cột cần thiết theo thứ tự ảnh h1.jpg
    df_final_display = df_pivot[["Ngày_HT", ca_ngay, ca_dem]].fillna("")
    df_final_display.columns = ["Ngày", ca_ngay, ca_dem]

    st.subheader("🗓️ Lịch trực mới (Sắp xếp theo thời gian)")
    st.table(df_final_view = df_final_display)

    # ---- GHI GOOGLE SHEETS ----
    # Chuyển ngày về dạng chuỗi VN để lưu trữ trong Data_Log
    df_save_raw = df_total.copy()
    df_save_raw["Ngày"] = pd.to_datetime(df_save_raw["Ngày"]).dt.strftime("%d/%m/%Y")

    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_save_raw)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_final_display)
        st.success("✅ Đã cập nhật lịch trực thành công!")
    except Exception as e:
        st.error(f"Lỗi khi lưu Sheets: {e}")
