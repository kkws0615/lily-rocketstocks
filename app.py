import streamlit as st
import pandas as pd
import yfinance as yf
import random

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI選股系統 (即時版)", layout="wide")

# --- 1. 核心功能：抓取真實股價 & 生成分析 ---
@st.cache_data(ttl=600)
def get_real_stock_data():
    stocks_info = [
        ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2317.TW", "鴻海"), 
        ("2603.TW", "長榮"),   ("2609.TW", "陽明"),   ("2303.TW", "聯電"), 
        ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("1605.TW", "華新"), 
        ("3231.TW", "緯創"),   ("2382.TW", "廣達"),   ("2357.TW", "華碩"),
        ("3008.TW", "大立光"), ("1101.TW", "台泥"),   ("3034.TW", "聯詠"), 
        ("6669.TW", "緯穎"),   ("2379.TW", "瑞昱"),   ("3037.TW", "欣興"),
        ("2345.TW", "智邦"),   ("2412.TW", "中華電"), ("2308.TW", "台達電"), 
        ("5871.TW", "中租-KY"),("2395.TW", "研華"),   ("1513.TW", "中興電"),
        ("2912.TW", "統一超"), ("1216.TW", "統一"),   ("6505.TW", "台塑化"), 
        ("1301.TW", "台塑"),   ("2002.TW", "中鋼"),   ("2891.TW", "中信金")
    ]
    
    # 定義隨機的「推薦原因庫」 (模擬 AI 分析結果)
    bull_reasons = ["主力籌碼集中", "外資連續買超", "均線多頭排列", "營收創新高", "量能爆發", "底部型態完成"]
    bear_reasons = ["高檔震盪", "量縮整理", "乖離率過大", "面臨前波壓力", "法人調節", "跌破五日線"]
    
    data = []
    progress_text = "正在連線 Yahoo Finance 抓取最新股價..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(stocks_info)
    
    for i, (ticker, name) in enumerate(stocks_info):
        my_bar.progress((i + 1) / total, text=f"正在分析: {ticker} {name} ({i+1}/{total})")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y") 
            
            if hist.empty:
                continue

            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            history_trend = hist['Close'].tolist()
            
            # AI 預測模擬
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            rating = "一般"
            reason = "觀望"
            
            # 根據預測漲幅決定評級與原因
            if predicted_growth > 15:
                rating = "強力推薦"
                reason = f"🔥 {random.choice(bull_reasons)}"
            elif predicted_growth > 5:
                rating = "買進"
                reason = f"📈 {random.choice(bull_reasons)}"
            elif predicted_growth < -5:
                rating = "避開"
                reason = f"⚠️ {random.choice(bear_reasons)}"
            else:
                rating = "觀察"
                reason = f"👀 {random.choice(bear_reasons)}"
            
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{ticker}"

            data.append({
                "代號連結": yahoo_url,
                "股名": name,          # 修改 1: 簡稱 -> 股名
                "目前股價": round(current_price, 2),
                "今日漲跌": daily_change_pct,
                "AI預測月漲幅": predicted_growth,
                "評級": rating,
                "推薦短評": reason,     # 修改 2: 新增原因欄位
                "近一年走勢": history_trend
            })
            
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
            
    my_bar.empty()
    return pd.DataFrame(data)

# --- 2. 介面設計 ---

st.title("📈 台股 AI 飆股快篩 (即時版)")

col1, col2 = st.columns([1, 5])
with col1:
    show_strong_only = st.checkbox("只顯示強力推薦", value=False)
with col2:
    if show_strong_only:
        st.caption("🔥 篩選模式：僅顯示 AI 預測高爆發股")
    else:
        st.caption("📋 監控模式：顯示熱門觀察名單 (點擊代號可查看 Yahoo 個股詳情)")

df = get_real_stock_data()

# --- 3. 篩選與排序 ---

if show_strong_only:
    display_df = df[df["評級"] == "強力推薦"]
else:
    display_df = df

display_df = display_df.sort_values(by="AI預測月漲幅", ascending=False)

# --- 4. 表格顯示 ---

def color_numbers(row):
    styles = []
    trend_color = 'red' if row['今日漲跌'] > 0 else 'green'
    
    for col in row.index:
        if col == '目前股價':
            styles.append(f'color: {trend_color}; font-weight: bold;')
        elif col == 'AI預測月漲幅':
            p_color = 'red' if row[col] > 0 else 'green'
            styles.append(f'color: {p_color}')
        elif col == '今日漲跌':
            styles.append(f'color: {trend_color}')
        elif col == '推薦短評':
             # 讓短評文字小一點，顏色淡一點
            styles.append('color: gray; font-size: 0.9em;')
        else:
            styles.append('')
    return styles

st.dataframe(
    display_df.style.apply(color_numbers, axis=1),
    use_container_width=True,
    height=800,
    hide_index=True,
    column_config={
        "代號連結": st.column_config.LinkColumn(
            "代號", 
            display_text="https://tw\.stock\.yahoo\.com/quote/(.*?)\.TW",
            help="點擊前往 Yahoo 股市",
            width="small"
        ),
        "股名": st.column_config.TextColumn("股名", width="small"),
        "目前股價": st.column_config.NumberColumn("目前股價", format="$%.2f"),
        "今日漲跌": st.column_config.NumberColumn("今日漲跌", format="%.2f%%"),
        "AI預測月漲幅": st.column_config.NumberColumn("預測月漲幅", format="%.2f%%"),
        # 新增推薦短評欄位設定
        "推薦短評": st.column_config.TextColumn(
            "AI 分析短評", 
            width="medium",
            help="AI 演算法根據技術面與籌碼面生成的簡短評價" # 這是標題的浮動提示
        ),
        "評級": st.column_config.TextColumn("評級", width="small"),
        "近一年走勢": st.column_config.LineChartColumn("近一年走勢", y_min=0, y_max=None),
    },
    # 調整順序，把短評放在評級旁邊
    column_order=("代號連結", "股名", "目前股價", "今日漲跌", "AI預測月漲幅", "評級", "推薦短評", "近一年走勢") 
)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API (延遲報價) | 分析短評為模擬生成，僅供介面參考")
