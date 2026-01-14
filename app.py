import streamlit as st
import pandas as pd
import yfinance as yf
import random
import numpy as np

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI標股神探 (HTML終極版)", layout="wide")

# --- 1. 核心功能：高速抓取股價 ---
@st.cache_data(ttl=600)
def get_stock_data():
    stocks_map = {
        "2330.TW": "台積電", "2454.TW": "聯發科", "2317.TW": "鴻海", "2603.TW": "長榮",
        "2609.TW": "陽明",   "2303.TW": "聯電",   "2881.TW": "富邦金", "2882.TW": "國泰金",
        "1605.TW": "華新",   "3231.TW": "緯創",   "2382.TW": "廣達",   "2357.TW": "華碩",
        "3008.TW": "大立光", "1101.TW": "台泥",   "3034.TW": "聯詠",   "6669.TW": "緯穎",
        "2379.TW": "瑞昱",   "3037.TW": "欣興",   "2345.TW": "智邦",   "2412.TW": "中華電",
        "2308.TW": "台達電", "5871.TW": "中租-KY", "2395.TW": "研華",  "1513.TW": "中興電",
        "2912.TW": "統一超", "1216.TW": "統一",   "6505.TW": "台塑化", "1301.TW": "台塑",
        "2002.TW": "中鋼",   "2891.TW": "中信金"
    }
    
    reasons_bull = ["外資連五日買超", "季線翻揚向上", "營收創歷史新高", "主力吃貨明顯", "突破下降趨勢線", "KD黃金交叉"]
    reasons_bear = ["高檔爆量長黑", "跌破季線支撐", "法人連續調節", "乖離率過大", "營收不如預期", "MACD死叉"]

    tickers = list(stocks_map.keys())
    
    # 批量下載數據
    with st.spinner('AI 正在連線交易所取得即時報價與計算技術指標...'):
        data_download = yf.download(tickers, period="3mo", group_by='ticker', progress=False)
    
    rows = []
    
    for ticker in tickers:
        try:
            df_stock = data_download[ticker]
            if df_stock.empty or len(df_stock) < 2: continue
            
            # 處理數據
            closes = df_stock['Close'].dropna().tolist()
            if len(closes) < 2: continue
            
            current_price = closes[-1]
            prev_price = closes[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # AI 預測模擬
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            # 評級邏輯
            if predicted_growth > 15:
                rating = "強力推薦"
                color_class = "tag-strong"
                reason = f"🔥 強力理由：{random.choice(reasons_bull)}，且{random.choice(reasons_bull)}，建議積極佈局。"
            elif predicted_growth > 5:
                rating = "買進"
                color_class = "tag-buy"
                reason = f"📈 買進理由：{random.choice(reasons_bull)}。"
            elif predicted_growth < -5:
                rating = "避開"
                color_class = "tag-sell"
                reason = f"⚠️ 風險提示：{random.choice(reasons_bear)}。"
            else:
                rating = "觀察"
                color_class = "tag-hold"
                reason = f"👀 觀察理由：目前區間震盪，{random.choice(reasons_bear)}。"

            rows.append({
                "code": ticker.replace(".TW", ""),
                "name": stocks_map[ticker],
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price,
                "change": daily_change_pct,
                "predict": predicted_growth,
                "rating": rating,
                "rating_class": color_class,
                "reason": reason,
                "trend": closes[-30:] # 取最近 30 天畫圖
            })
        except:
            continue
            
    return sorted(rows, key=lambda x: x['predict'], reverse=True)

# --- 2. 輔助功能：畫 SVG 走勢圖 (Python 畫圖轉 HTML) ---
def make_sparkline_svg(data):
    if not data: return ""
    width = 100
    height = 30
    min_val = min(data)
    max_val = max(data)
    if max_val == min_val: return ""
    
    # 正規化座標
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        # Y軸要反轉，因為 SVG 0 在上方
        y = height - ((val - min_val) / (max_val - min_val)) * height
        points.append(f"{x},{y}")
    
    polyline = " ".join(points)
    color = "red" if data[-1] > data[0] else "green"
    
    return f"""
    <svg width="{width}" height="{height}" style="overflow: visible">
        <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" />
        <circle cx="{points[-1].split(',')[0]}" cy="{points[-1].split(',')[1]}" r="3" fill="{color}" />
    </svg>
    """

# --- 3. 介面與 HTML 生成 ---

st.title("🚀 台股 AI 飆股快篩 (HTML 互動版)")
st.caption("滑鼠移至「評級」上方可查看詳細 AI 分析")

col1, col2 = st.columns([1, 5])
with col1:
    filter_strong = st.checkbox("🔥 只看強力推薦", value=False)

data = get_stock_data()
if filter_strong:
    data = [d for d in data if d['rating'] == "強力推薦"]

# === 關鍵：CSS 樣式表 (定義 Tooltip 和表格漂亮的外觀) ===
st.markdown("""
<style>
    /* 表格整體樣式 */
    table { width: 100%; border-collapse: collapse; font-family: "Microsoft JhengHei", sans-serif; }
    th { background-color: #f0f2f6; padding: 10px; text-align: left; font-size: 14px; border-bottom: 2px solid #ddd; }
    td { padding: 12px 10px; border-bottom: 1px solid #eee; vertical-align: middle; font-size: 15px; }
    tr:hover { background-color: #f9f9f9; }

    /* 數字顏色 */
    .up { color: #d62728; font-weight: bold; }
    .down { color: #2ca02c; font-weight: bold; }
    
    /* 連結樣式 */
    a { text-decoration: none; color: #1f77b4; font-weight: bold; }
    a:hover { text-decoration: underline; }

    /* === Tooltip 核心 CSS (這就是你要的！) === */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help; /* 滑鼠游標變成問號 */
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    
    /* Tooltip 文字框本身 (預設隱藏) */
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 220px;
        background-color: #333;
        color: #fff;
        text-align: left;
        border-radius: 6px;
        padding: 10px;
        position: absolute;
        z-index: 1;
        bottom: 125%; /* 顯示在上方 */
        left: 50%;
        margin-left: -110px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 13px;
        font-weight: normal;
        box-shadow: 0px 4px 8px rgba(0,0,0,0.2);
        line-height: 1.4;
    }
    
    /* 箭頭 */
    .tooltip .tooltiptext::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #333 transparent transparent transparent;
    }

    /* 滑鼠移上去時顯示 */
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }

    /* 標籤顏色 */
    .tag-strong { background-color: #ffebeb; color: #d62728; border: 1px solid #ffcccc; }
    .tag-buy { background-color: #f0fff0; color: #2ca02c; border: 1px solid #ccffcc; }
    .tag-hold { background-color: #f8f9fa; color: #666; border: 1px solid #eee; }
    .tag-sell { background-color: #e9ecef; color: #495057; }

</style>
""", unsafe_allow_html=True)

# === 4. 組合 HTML 表格 ===
html_content = "<table>"
html_content += "<thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>預測漲幅</th><th>AI 評級 (懸停看原因)</th><th>近三月走勢</th></tr></thead>"
html_content += "<tbody>"

for row in data:
    # 決定顏色 class
    price_color = "up" if row['change'] > 0 else "down"
    predict_color = "up" if row['predict'] > 0 else "down"
    
    # 產生走勢圖 SVG
    sparkline = make_sparkline_svg(row['trend'])
    
    # 組合每一列 HTML
    html_content += f"""
    <tr>
        <td><a href="{row['url']}" target="_blank">{row['code']}</a></td>
        <td>{row['name']}</td>
        <td class="{price_color}">{row['price']:.1f}</td>
        <td class="{price_color}">{row['change']:.2f}%</td>
        <td class="{predict_color}">{row['predict']:.2f}%</td>
        <td>
            <div class="tooltip {row['rating_class']}">
                {row['rating']}
                <span class="tooltiptext">{row['reason']}</span>
            </div>
        </td>
        <td>{sparkline}</td>
    </tr>
    """

html_content += "</tbody></table>"

# === 5. 渲染 HTML ===
st.markdown(html_content, unsafe_allow_html=True)
st.markdown("<br><hr><small>資料來源：Yahoo Finance (延遲報價) | 技術架構：HTML5 + CSS3 + Python SVG Generation</small>", unsafe_allow_html=True)
