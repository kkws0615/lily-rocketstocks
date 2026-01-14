import streamlit as st
import pandas as pd
import random

# --- 設定網頁標題與排版 ---
st.set_page_config(page_title="台股 AI 飆股快篩", layout="wide")

# --- 1. 核心功能：製造更像真實的模擬數據 ---
@st.cache_data
def get_stock_data():
    data = []
    
    # 準備一些真實的台股名稱樣本，讓畫面看起來更專業
    stock_samples = [
        ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"), ("2603", "長榮"),
        ("2609", "陽明"), ("3231", "緯創"), ("2382", "廣達"), ("2357", "華碩"),
        ("3008", "大立光"), ("2881", "富邦金"), ("2882", "國泰金"), ("1101", "台泥"),
        ("1605", "華新"), ("2303", "聯電"), ("3034", "聯詠"), ("6669", "緯穎")
    ]
    
    for i in range(100):
        # 隨機挑選一個樣本，為了湊滿100個，我們加上隨機後綴避免重複
        base_code, base_name = random.choice(stock_samples)
        
        # 為了產生100筆不同資料，這裡做一點隨機變化
        if i > 15: 
            fake_code = str(random.randint(1101, 9999))
            stock_display = f"{fake_code} 模擬股"
        else:
            stock_display = f"{base_code} {base_name}"
            
        price = round(random.uniform(50, 1000), 1)
        
        # 模擬「未來一個月預測漲幅」 (這是 AI 預測的)
        predicted_growth = round(random.uniform(-10, 30), 2)
        
        # 模擬「今日漲跌幅」 (這是用來決定股價顏色的！)
        # 台股漲跌幅限制約 10%，我們隨機生成
        daily_change_pct = round(random.uniform(-5, 5), 2)
        
        # 定義評級
        tag = "觀察"
        if predicted_growth > 15:
            tag = "🔥 強力推薦"
        elif predicted_growth > 5:
            tag = "💰 買進"
            
        data.append({
            "股票名稱": stock_display,
            "目前股價": price,
            "今日漲跌(%)": daily_change_pct, # 隱藏欄位，主要用於變色判斷
            "AI 預測月漲幅": predicted_growth,
            "評級": tag
        })
    
    return pd.DataFrame(data)

# --- 2. 介面設計 (上方控制區) ---

st.title("🚀 台股 AI 飆股快篩系統")

# 建立上方控制區塊 (使用 columns 來排列)
col1, col2 = st.columns([1, 4])

with col1:
    # 這是你要求的「上方按鈕」
    # 使用 checkbox 也可以，但在這裡我們用 toggle (切換開關) 或 按鈕邏輯
    # 為了直觀，我們用 checkbox 來做「篩選模式」的切換
    show_strong_only = st.checkbox("✅ 只顯示「強力推薦」股", value=False)

with col2:
    if show_strong_only:
        st.caption("🔥 目前模式：僅顯示 AI 預測漲幅 > 15% 的飆股")
    else:
        st.caption("📋 目前模式：顯示所有 100 檔監控個股")

# 讀取數據
df = get_stock_data()

# --- 3. 篩選邏輯 ---

if show_strong_only:
    display_df = df[df["評級"] == "🔥 強力推薦"]
else:
    display_df = df

# 排序：讓漲幅高的排前面
display_df = display_df.sort_values(by="AI 預測月漲幅", ascending=False)

# --- 4. 美化表格 (關鍵：股價紅綠變色) ---

# 定義樣式函數
def style_table(val):
    # 這個函數會對 dataframe 的每一個數值執行
    # 但我們比較難直接知道現在是哪一欄，所以通常用 apply 搭配 axis=1 (整列處理)
    return "" 

# 我們改用 Pandas 的 apply 方法來針對特定欄位上色
def highlight_rows(row):
    # 預設樣式
    price_color = 'black'
    
    # 根據「今日漲跌(%)」來決定「目前股價」的顏色
    if row['今日漲跌(%)'] > 0:
        price_color = 'red'
    elif row['今日漲跌(%)'] < 0:
        price_color = 'green'
    
    # 設定 CSS 樣式
    # 我們回傳一個列表，對應到每一欄的樣式
    styles = []
    for col in row.index:
        if col == '目前股價':
            styles.append(f'color: {price_color}; font-weight: bold;')
        elif col == 'AI 預測月漲幅':
            # 預測漲幅也順便上色 (大於0紅，小於0綠)
            color = 'red' if row[col] > 0 else 'green'
            styles.append(f'color: {color}')
        elif col == '今日漲跌(%)':
            color = 'red' if row[col] > 0 else 'green'
            styles.append(f'color: {color}')
        else:
            styles.append('')
    return styles

# 顯示表格
# 注意：為了不要顯示太雜亂，我們可以隱藏「今日漲跌」這一欄，或者顯示出來讓使用者參考
# 這裡我選擇顯示出來，讓你能看到為什麼股價是紅的或綠的
st.dataframe(
    display_df.style.apply(highlight_rows, axis=1) # axis=1 代表逐列處理
    .format({
        "目前股價": "{:.1f}", 
        "AI 預測月漲幅": "{:+.2f}%",
        "今日漲跌(%)": "{:+.2f}%"
    }),
    use_container_width=True,
    height=600,
    column_config={
        "評級": st.column_config.TextColumn("AI 評級", help="AI 根據漲幅預測給出的建議"),
    }
)

st.markdown("---")
st.caption("🔴 紅色代表上漲 | 🟢 綠色代表下跌 (依照台股慣例)")
