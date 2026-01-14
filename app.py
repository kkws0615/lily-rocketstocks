import streamlit as st
import pandas as pd
import numpy as np
import random

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI選股系統", layout="wide")

# --- 1. 核心功能：生成模擬數據 (含走勢圖數據) ---
@st.cache_data
def get_stock_data():
    data = []
    
    # 擴充真實台股代碼與名稱樣本 (約 40 檔熱門股)
    real_stocks = [
        ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"), ("2603", "長榮"),
        ("2609", "陽明"), ("2615", "萬海"), ("3231", "緯創"), ("2382", "廣達"),
        ("2357", "華碩"), ("3008", "大立光"), ("2881", "富邦金"), ("2882", "國泰金"),
        ("2891", "中信金"), ("1101", "台泥"), ("1605", "華新"), ("2303", "聯電"),
        ("3034", "聯詠"), ("6669", "緯穎"), ("2379", "瑞昱"), ("3037", "欣興"),
        ("2345", "智邦"), ("2412", "中華電"), ("2308", "台達電"), ("5871", "中租"),
        ("2395", "研華"), ("1513", "中興電"), ("1519", "華城"), ("3711", "日月光"),
        ("4904", "遠傳"), ("2409", "友達"), ("3481", "群創"), ("2002", "中鋼"),
        ("2912", "統一超"), ("1216", "統一"), ("6505", "台塑化"), ("1301", "台塑")
    ]
    
    # 產生 100 筆資料
    for i in range(100):
        # 名稱處理：優先使用真實名單，用完後自動生成「像真的」名稱
        if i < len(real_stocks):
            code, name = real_stocks[i]
        else:
            # 自動生成像樣的名稱，例如：62xx 宏達科技
            code = str(random.randint(4000, 9999))
            suffix = random.choice(["科技", "電子", "半導體", "生技", "工業", "金控", "建設"])
            prefix = random.choice(["宏", "華", "台", "新", "國", "富", "聯", "亞"])
            mid = random.choice(["達", "訊", "通", "鼎", "盛", "光", "微"])
            name = f"{prefix}{mid}{suffix}"
            
        stock_display = f"{code} {name}"
            
        # 模擬股價
        current_price = round(random.uniform(50, 1000), 1)
        
        # 模擬走勢圖數據 (List of float)
        # 隨機生成過去 52 週的價格走勢，讓最後一個價格接近目前股價
        # np.random.randn 生成常態分佈亂數，cumsum 累加變成走勢
        history_trend = (np.random.randn(50).cumsum() + 20).tolist()
        
        # 模擬預測數據
        predicted_growth = round(random.uniform(-10, 30), 2)
        daily_change_pct = round(random.uniform(-5, 5), 2)
        
        # 評級邏輯 (純文字，不加 icon)
        rating = "一般"
        if predicted_growth > 15:
            rating = "強力推薦"
        elif predicted_growth > 5:
            rating = "買進"
            
        data.append({
            "股票名稱": stock_display,
            "目前股價": current_price,
            "今日漲跌": daily_change_pct, # 數值欄位，顯示時加上 %
            "AI預測月漲幅": predicted_growth,
            "評級": rating,
            "近一年走勢": history_trend # 這是給走勢圖用的列表數據
        })
    
    return pd.DataFrame(data)

# --- 2. 介面設計 ---

st.title("台股 AI 飆股快篩系統")

# 上方控制區
col1, col2 = st.columns([1, 5])

with col1:
    # 篩選開關
    show_strong_only = st.checkbox("只顯示強力推薦", value=False)

with col2:
    if show_strong_only:
        st.caption("目前顯示：AI 預測漲幅 > 15% 之標的")
    else:
        st.caption("目前顯示：所有監控標的")

# 獲取資料
df = get_stock_data()

# --- 3. 篩選與排序 ---

if show_strong_only:
    display_df = df[df["評級"] == "強力推薦"]
else:
    display_df = df

display_df = display_df.sort_values(by="AI預測月漲幅", ascending=False)

# --- 4. 表格樣式設定 (關鍵修改) ---

# 設定顏色邏輯 (針對數值欄位)
def color_numbers(row):
    # 預設文字顏色
    styles = []
    
    # 定義漲跌顏色 (紅漲綠跌)
    # 根據「今日漲跌」來決定整行的核心顏色邏輯
    trend_color = 'red' if row['今日漲跌'] > 0 else 'green'
    
    for col in row.index:
        if col == '目前股價':
            styles.append(f'color: {trend_color}; font-weight: bold;')
        elif col == 'AI預測月漲幅':
             # 預測部分獨立判斷顏色
            p_color = 'red' if row[col] > 0 else 'green'
            styles.append(f'color: {p_color}')
        elif col == '今日漲跌':
            styles.append(f'color: {trend_color}')
        else:
            styles.append('') # 其他欄位不變色
            
    return styles

# 顯示 Dataframe，使用 column_config 來畫圖
st.dataframe(
    display_df.style.apply(color_numbers, axis=1),
    use_container_width=True,
    height=800,
    # 這裡隱藏原本的 index 欄位
    hide_index=True, 
    column_config={
        "股票名稱": st.column_config.TextColumn("股票名稱", width="medium"),
        "目前股價": st.column_config.NumberColumn("目前股價", format="$%.2f"),
        "今日漲跌": st.column_config.NumberColumn("今日漲跌", format="%.2f%%"),
        "AI預測月漲幅": st.column_config.NumberColumn("預測月漲幅", format="%.2f%%"),
        "近一年走勢": st.column_config.LineChartColumn(
            "近一年走勢",
            width="medium",
            y_min=0, # 設定 Y 軸下限，避免圖形太誇張
            y_max=None
        ),
        "評級": st.column_config.TextColumn("AI 評級"),
    }
)
