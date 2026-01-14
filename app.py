import streamlit as st
import pandas as pd
import yfinance as yf
import random

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI選股系統 (即時版)", layout="wide")

# --- 1. 核心功能：抓取真實股價 & 生成連結 ---
@st.cache_data(ttl=600)
def get_real_stock_data():
    tickers_list = [
        "2330.TW", "2454.TW", "2317.TW", "2603.TW", "2609.TW", "2303.TW", 
        "2881.TW", "2882.TW", "1605.TW", "3231.TW", "2382.TW", "2357.TW",
        "3008.TW", "1101.TW", "3034.TW", "6669.TW", "2379.TW", "3037.TW",
        "2345.TW", "2412.TW", "2308.TW", "5871.TW", "2395.TW", "1513.TW",
        "2912.TW", "1216.TW", "6505.TW", "1301.TW", "2002.TW", "2891.TW"
    ]
    
    data = []
    progress_text = "正在連線 Yahoo Finance 抓取最新股價，請稍候..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(tickers_list)
    
    for i, ticker in enumerate(tickers_list):
        my_bar.progress((i + 1) / total, text=f"正在分析: {ticker} ({i+1}/{total})")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y") 
            
            if hist.empty:
                continue

            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            history_trend = hist['Close'].tolist()
            
            # 模擬 AI 預測部分
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            rating = "一般"
            if predicted_growth > 15:
                rating = "強力推薦"
            elif predicted_growth > 5:
                rating = "買進"
            
            # 建立 Yahoo 股市連結
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{ticker}"

            data.append({
                "URL": yahoo_url,   # 這是我們要顯示的欄位 (內含連結)
                "目前股價": round(current_price, 2),
                "今日漲跌": daily_change_pct,
                "AI預測月漲幅": predicted_growth,
                "評級": rating,
                "近一年走勢": history_trend
            })
            
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
            
    my_bar.empty()
    return pd.DataFrame(data)

# --- 2. 介面設計 ---

st.title("📈 台股 AI 飆股快篩 (即時連線版)")

col1, col2 = st.columns([1, 5])
with col1:
    show_strong_only = st.checkbox("只顯示強力推薦", value=False)
with col2:
    if show_strong_only:
        st.caption("🔥 篩選模式：僅顯示 AI 預測高爆發股")
    else:
        st.caption("📋 監控模式：顯示熱門觀察名單 (資料來源：Yahoo Finance)")

df = get_real_stock_data()

# --- 3. 篩選與排序 ---

if show_strong_only:
    display_df = df[df["評級"] == "強力推薦"]
else:
    display_df = df

display_df = display_df.sort_values(by="AI預測月漲幅", ascending=False)

# --- 4. 表格顯示 (修正代號顯示問題) ---

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
        else:
            styles.append('')
    return styles

st.dataframe(
    display_df.style.apply(color_numbers, axis=1),
    use_container_width=True,
    height=800,
    hide_index=True,
    column_config={
        # === 修正重點在這裡 ===
        "URL": st.column_config.LinkColumn(
            "股票代號", 
            # 這個語法意思是：從網址中抓取 /quote/ 後面，直到 .TW 前面的文字來顯示
            # 網址範例：https://tw.stock.yahoo.com/quote/2330.TW -> 顯示 2330
            display_text="https://tw\.stock\.yahoo\.com/quote/(.*?)\.TW",
            help="點擊前往 Yahoo 股市",
            width="small"
        ),
        "目前股價": st.column_config.NumberColumn("目前股價", format="$%.2f"),
        "今日漲跌": st.column_config.NumberColumn("今日漲跌", format="%.2f%%"),
        "AI預測月漲幅": st.column_config.NumberColumn("預測月漲幅", format="%.2f%%"),
        "近一年走勢": st.column_config.LineChartColumn("近一年走勢", y_min=0, y_max=None),
    },
    # 這裡指定欄位順序
    column_order=("URL", "目前股價", "今日漲跌", "AI預測月漲幅", "評級", "近一年走勢") 
)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API (延遲報價)")
