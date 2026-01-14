import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import numpy as np # 引入 numpy 計算平均線

st.set_page_config(page_title="台股AI標股神探 (真實策略版)", layout="wide")

# --- 0. 初始化：股票清單 ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {
        "2330.TW": "台積電", "2454.TW": "聯發科", "2317.TW": "鴻海", "2603.TW": "長榮",
        "2609.TW": "陽明",   "2303.TW": "聯電",   "2881.TW": "富邦金", "2882.TW": "國泰金",
        "1605.TW": "華新",   "3231.TW": "緯創",   "2382.TW": "廣達",   "2357.TW": "華碩",
        "3008.TW": "大立光", "1101.TW": "台泥",   "3034.TW": "聯詠",   "6669.TW": "緯穎",
        "2379.TW": "瑞昱",   "3037.TW": "欣興",   "2345.TW": "智邦",   "2412.TW": "中華電",
        "2308.TW": "台達電", "5871.TW": "中租-KY", "2395.TW": "研華",  "1513.TW": "中興電",
        "2912.TW": "統一超", "1216.TW": "統一",   "6505.TW": "台塑化", "1301.TW": "台塑",
        "2002.TW": "中鋼",   "2891.TW": "中信金"
    }

# --- 1. 核心邏輯：生成基於 MA (月線) 的分析 ---
def analyze_stock_strategy(current_price, ma20, ma60, trend_list):
    # 計算乖離率 (Bias)
    bias_20 = ((current_price - ma20) / ma20) * 100
    
    # 判斷趨勢 (簡單判斷：看最近 5 天是不是大概在漲)
    recent_trend = trend_list[-1] > trend_list[-5]
    
    reason = ""
    rating = "觀察"
    color_class = "tag-hold"
    predict_score = 0 # 這是我們用來排序的分數，不是預測漲幅
    
    # === 真實策略邏輯 ===
    
    if current_price > ma20 and current_price > ma60 and bias_20 > 5:
        # 股價 > 月線 > 季線，且乖離擴大 (強勢)
        rating = "強力推薦"
        color_class = "tag-strong"
        predict_score = 90
        reason = f"🔥 強力多頭：股價強勢站穩月線({ma20:.1f})與季線之上，乖離率 {bias_20:.1f}% 顯示動能強勁，均線發散向上。"
        
    elif current_price > ma20 and bias_20 > 0:
        # 股價剛站上月線
        rating = "買進"
        color_class = "tag-buy"
        predict_score = 70
        reason = f"📈 翻多訊號：股價站上月線支撐({ma20:.1f})，短線趨勢轉強，可嘗試佈局。"
        
    elif current_price < ma20 and current_price < ma60:
        # 股價 < 月線 < 季線 (空頭)
        rating = "避開"
        color_class = "tag-sell"
        predict_score = 10
        reason = f"⚠️ 空頭排列：股價跌破月線({ma20:.1f})與季線，上方壓力沈重，建議觀望或減碼。"
        
    elif current_price < ma20:
        # 跌破月線
        rating = "賣出"
        color_class = "tag-sell"
        predict_score = 30
        reason = f"📉 轉弱警示：股價跌破月線({ma20:.1f})，短線動能轉弱，留意修正風險。"
        
    else:
        rating = "觀察"
        color_class = "tag-hold"
        predict_score = 50
        reason = f"👀 區間震盪：股價在月線({ma20:.1f})附近徘徊，方向未明，等待表態。"
        
    return rating, color_class, reason, predict_score

# --- 2. 抓取資料 ---
@st.cache_data(ttl=300) 
def fetch_fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    # 抓取 4 個月資料，確保有足夠天數算季線 (60MA)
    return yf.download(tickers, period="6mo", group_by='ticker', progress=False)

def process_stock_data():
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    
    with st.spinner(f'AI 正在計算 {len(tickers)} 檔個股的月線與季線數據...'):
        data_download = fetch_fetch_stock_data_wrapper(tickers)
    
    rows = []
    if data_download is None or len(tickers) == 0:
        return []

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df_stock = data_download
            else:
                df_stock = data_download[ticker]
            
            closes = df_stock['Close']
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            
            # 清理數據
            closes_list = closes.dropna().tolist()
            if len(closes_list) < 60: continue # 資料不足算季線就跳過
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # === 計算真實技術指標 ===
            # 月線 (20MA)
            ma20 = sum(closes_list[-20:]) / 20
            # 季線 (60MA)
            ma60 = sum(closes_list[-60:]) / 60
            
            # 呼叫策略函式
            rating, color_class, reason, score = analyze_stock_strategy(
                current_price, ma20, ma60, closes_list[-10:]
            )

            rows.append({
                "code": ticker.replace(".TW", ""),
                "name": current_map[ticker],
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price,
                "change": daily_change_pct,
                "score": score, # 用來排序
                "ma20": ma20,   # 顯示月線價格
                "rating": rating,
                "rating_class": color_class,
                "reason": reason,
                "trend": closes_list[-30:]
            })
        except:
            continue
            
    # 依照分數排序 (強勢股在最上面)
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 3. 輔助功能 ---
def make_sparkline(data):
    if not data: return ""
    width, height = 100, 30
    min_val, max_val = min(data), max(data)
    if max_val == min_val: return ""
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        y = height - ((val - min_val) / (max_val - min_val)) * (height - 4) - 2
        points.append(f"{x},{y}")
    color = "#dc3545" if data[-1] > data[0] else "#28a745"
    return f'<svg width="{width}" height="{height}" style="overflow:visible"><polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/><circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="3" fill="{color}"/></svg>'

# --- 4. 介面設計 ---

st.title("🚀 台股 AI 飆股神探 (真實策略版)")

# 上方輸入區
with st.container():
    col_add, col_info = st.columns([2, 3])
    with col_add:
        with st.form(key='add_stock_form', clear_on_submit=True):
            col_input, col_btn = st.columns([3, 1])
            with col_input:
                new_ticker = st.text_input("輸入代號", placeholder="輸入代號 (如 2330)")
            with col_btn:
                submitted = st.form_submit_button("新增")
            if submitted and new_ticker:
                full_ticker = f"{new_ticker}.TW"
                if full_ticker not in st.session_state.watch_list:
                    try:
                        stock_info = yf.Ticker(full_ticker)
                        if not stock_info.history(period='1d').empty:
                            st.session_state.watch_list[full_ticker] = f"自選股-{new_ticker}"
                            st.success(f"已加入 {new_ticker}")
                            st.rerun()
                        else: st.error("代號錯誤")
                    except: st.error("連線錯誤")
    with col_info:
        st.info("💡 評級依據：**真實股價與月線(20MA)、季線(60MA) 之乖離率**。")
        filter_strong = st.checkbox("🔥 只看強力推薦", value=False)

data_rows = process_stock_data()
if filter_strong:
    data_rows = [d for d in data_rows if d['rating'] == "強力推薦"]

# --- 5. HTML 渲染 ---
html_content = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: "Microsoft JhengHei", sans-serif; margin: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 15px; }
    th { background: #f2f2f2; padding: 12px; text-align: left; position: sticky; top: 0; z-index: 10; border-bottom: 2px solid #ddd; }
    td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
    tr:hover { background: #f8f9fa; }
    
    .up { color: #d62728; font-weight: bold; }
    .down { color: #2ca02c; font-weight: bold; }
    a { text-decoration: none; color: #0066cc; font-weight: bold; background: #f0f7ff; padding: 2px 6px; border-radius: 4px; }

    .tooltip-container { position: relative; display: inline-block; cursor: help; padding: 5px 10px; border-radius: 20px; font-weight: bold; font-size: 13px; transition: all 0.2s; }
    .tooltip-container:hover { transform: scale(1.05); }
    
    .tooltip-text { 
        visibility: hidden; width: 300px; background-color: #2c3e50; color: #fff; 
        text-align: left; border-radius: 8px; padding: 12px; position: absolute; z-index: 999; 
        bottom: 140%; left: 50%; margin-left: -150px; opacity: 0; transition: opacity 0.3s; 
        font-weight: normal; font-size: 13px; line-height: 1.6; pointer-events: none; 
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    .tooltip-text::after { content: ""; position: absolute; top: 100%; left: 50%; margin-left: -6px; border-width: 6px; border-style: solid; border-color: #2c3e50 transparent transparent transparent; }
    .tooltip-container:hover .tooltip-text { visibility: visible; opacity: 1; }
    
    .tag-strong { background: #ffebeb; color: #d62728; border: 1px solid #ffcccc; }
    .tag-buy { background: #e6ffe6; color: #2ca02c; border: 1px solid #ccffcc; }
    .tag-sell { background: #f1f3f5; color: #495057; border: 1px solid #dee2e6; }
    .tag-hold { background: #fff; color: #868e96; border: 1px solid #eee; }
    
    .sub-text { font-size: 12px; color: #888; margin-left: 5px; font-weight: normal; }
</style>
</head>
<body>
<table>
    <thead>
        <tr>
            <th>代號</th><th>股名</th><th>現價 <span style="font-size:12px;color:#888">(月線)</span></th><th>漲跌</th><th>AI 評級 (懸停看原因)</th><th>近三月走勢</th>
        </tr>
    </thead>
    <tbody>
"""

for row in data_rows:
    p_cls = "up" if row['change'] > 0 else "down"
    
    html_content += f"""
        <tr>
            <td><a href="{row['url']}" target="_blank">{row['code']}</a></td>
            <td>{row['name']}</td>
            <td class="{p_cls}">{row['price']:.1f} <span class="sub-text">({row['ma20']:.1f})</span></td>
            <td class="{p_cls}">{row['change']:.2f}%</td>
            <td>
                <div class="tooltip-container {row['rating_class']}">
                    {row['rating']}
                    <span class="tooltip-text">{row['reason']}</span>
                </div>
            </td>
            <td>{make_sparkline(row['trend'])}</td>
        </tr>
    """

html_content += "</tbody></table></body></html>"
components.html(html_content, height=800, scrolling=True)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API | 評級依據：月線(20MA)與季線(60MA)趨勢分析")
