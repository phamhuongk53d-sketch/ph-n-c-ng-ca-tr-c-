import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

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

# ==================================================
# ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==================================================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", ttl=0)
except Exception:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

if not df_raw.empty:
    df_raw["Ngày"] = pd.to_datetime(df_raw["Ngày"], dayfirst=True, errors="coerce")
    df_raw = df_raw.dropna(subset=["Ngày"])
else:
    df_raw = pd.DataFrame(columns=["Ngày", "Ca", "Nhân viên", "Giờ"])

# ==================================================
# SIDEBAR – CẤU HÌNH
# ==================================================
with st.sidebar:
    st.header("👥 Cấu hình nhân sự")
    staff_input = st.text_area(
        "Danh sách nhân viên",
        "Trung, Ngà, Liên, Linh, Hà, Bình, Huyền, Thảo, Trang, Hương B"
    )
    staff = [s.strip() for s in staff_input.split(",") if s.strip()]

    special_staff = st.multiselect(
        "Chỉ trực ca ngày (T2-T6)",
        staff,
        default=["Trung", "Ngà"]
    )

    st.header("📅 Thời gian phân lịch")
    start_date = st.date_input("Từ ngày", datetime.now().date())
    end_date = st.date_input("Đến ngày", start_date + timedelta(days=30))

# ==================================================
# XỬ LÝ DỮ LIỆU CŨ VÀ LŨY KẾ
# ==================================================
# Lấy dữ liệu lịch sử TRƯỚC ngày bắt đầu chọn
history_keep = df_raw[df_raw["Ngày"].dt.date < start_date].copy()

# Lấy dữ liệu SAU ngày kết thúc chọn (nếu có để ghép lại sau)
future_keep = df_raw[df_raw["Ngày"].dt.date > end_date].copy()

# Tính giờ lũy kế dựa trên history_keep
luy_ke_hours = {s: history_keep.loc[history_keep["Nhân viên"] == s, "Giờ"].sum() for s in staff}

st.subheader(f"📊 Tổng giờ lũy kế (Tính đến hết {start_date - timedelta(days=1)})")
st.dataframe(pd.DataFrame([luy_ke_hours]), use_container_width=True)

# ==================================================
# THUẬT TOÁN PHÂN CA CÂN BẰNG
# ==================================================
def generate_schedule():
    rows = []
    work_hours = luy_ke_hours.copy()
    
    # Quy định thời gian có sẵn (tránh trực 2 ca liên tiếp)
    available_at = {s: datetime.combine(start_date - timedelta(days=1), datetime.min.time()) for s in staff}

    curr = start_date
    while curr <= end_date:
        base = datetime.combine(curr, datetime.min.time())
        is_weekend = curr.weekday() >= 5 # Thứ 7 (5) và CN (6)

        # 1. PHÂN CA NGÀY (08:00 - 16:00)
        # Ứng viên: Nếu cuối tuần thì loại nhân viên đặc biệt
        day_candidates = [s for s in staff if available_at[s] <= base.replace(hour=8)]
        if is_weekend:
            day_candidates = [s for s in day_candidates if s not in special_staff]
        
        # Sắp xếp: Ưu tiên người ít giờ nhất
        day_candidates.sort(key=lambda s: work_hours[s])

        for s in day_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 8h00 - 16h00", "Nhân viên": s, "Giờ": 8})
            work_hours[s] += 8
            available_at[s] = base.replace(hour=16) + timedelta(hours=16) # Nghỉ ít nhất 16h

        # 2. PHÂN CA ĐÊM (16:00 - 08:00)
        # Ứng viên: Không phải nhân viên đặc biệt, không đang trong ca ngày, đủ thời gian nghỉ
        night_candidates = [
            s for s in staff 
            if s not in special_staff 
            and available_at[s] <= base.replace(hour=16)
            and not any(r['Ngày'] == curr and r['Nhân viên'] == s for r in rows)
        ]
        night_candidates.sort(key=lambda s: work_hours[s])

        for s in night_candidates[:2]:
            rows.append({"Ngày": curr, "Ca": "Ca: 16h00 - 8h00", "Nhân viên": s, "Giờ": 16})
            work_hours[s] += 16
            available_at[s] = base + timedelta(days=2) # Trực đêm nghỉ 2 ngày

        curr += timedelta(days=1)
    return pd.DataFrame(rows)

# ==================================================
# XỬ LÝ XUẤT DỮ LIỆU
# ==================================================
if st.button("🚀 TẠO LỊCH MỚI & CẬP NHẬT HỆ THỐNG"):
    df_new = generate_schedule()
    
    # GHÉP DỮ LIỆU: Cũ + Mới (Thay thế phần trùng) + Tương lai
    df_total = pd.concat([history_keep, df_new, future_keep], ignore_index=True)
    df_total = df_total.sort_values(by=["Ngày", "Ca"])

    # CHUẨN BỊ HIỂN THỊ THEO THÁNG
    df_display = df_total.copy()
    df_display["Tháng_Năm"] = df_display["Ngày"].dt.strftime("Tháng %m năm %Y")
    df_display["Tháng_Sort"] = df_display["Ngày"].dt.year * 100 + df_display["Ngày"].dt.month
    
    st.write("---")
    st.header("📅 KẾ HOẠCH TRỰC CHI TIẾT")

    # Group dữ liệu để hiển thị Pivot
    all_pivots = []
    
    months = sorted(df_display["Tháng_Sort"].unique())
    for m_code in months:
        m_data = df_display[df_display["Tháng_Sort"] == m_code].copy()
        tieu_de = m_data["Tháng_Năm"].iloc[0]
        
        st.subheader(f"📍 {tieu_de.upper()}")
        
        # Pivot table cho từng tháng
        m_pivot = (
            m_data.groupby(["Ngày", "Ca"])["Nhân viên"]
            .apply(lambda x: " & ".join(x))
            .unstack(fill_value="")
            .reset_index()
        )
        
        # Đảm bảo đủ 2 cột ca
        for c in ["Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"]:
            if c not in m_pivot.columns: m_pivot[c] = ""
        
        m_pivot = m_pivot[["Ngày", "Ca: 8h00 - 16h00", "Ca: 16h00 - 8h00"]]
        
        # Format ngày hiển thị
        display_table = m_pivot.copy()
        display_table["Ngày"] = display_table["Ngày"].apply(get_vietnamese_weekday)
        
        st.table(display_table)
        all_pivots.append(display_table)

    # ================== GHI DỮ LIỆU LÊN GOOGLE SHEETS ==================
    # 1. Ghi Data_Log (Dạng thô để tính toán)
    df_save_log = df_total.copy()
    df_save_log["Ngày"] = df_save_log["Ngày"].dt.strftime("%d/%m/%Y")
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Data_Log", data=df_save_log)

    # 2. Ghi Lich_Truc (Dạng bảng đã pivot để in ấn/xem)
    df_final_pivot = pd.concat(all_pivots, ignore_index=True)
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Lich_Truc", data=df_final_pivot)

    st.success(f"✅ Đã cập nhật lịch từ {start_date} đến {end_date}. Các ngày trùng lặp đã được thay thế mới!")
    st.balloons()
