import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import numpy as np
import random

st.set_page_config(page_title="台股AI標股神探 (中文修正版)", layout="wide")

# --- 0. 初始化 ---
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

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# 產業資料庫
ticker_sector_map = {
    "2330": "Semi", "2454": "Semi", "2303": "Semi", "3034": "Semi", "2379": "Semi",
    "2317": "AI_Hw", "3231": "AI_Hw", "2382": "AI_Hw", "6669": "AI_Hw", "2357": "AI_Hw",
    "2603": "Ship", "2609": "Ship",
    "2881": "Fin", "2882": "Fin", "5871": "Fin", "2891": "Fin",
    "3008": "Optic",
    "1605": "Wire", "1513": "Power", "2308": "Power",
    "1101": "Cement", "2002": "Steel", "6505": "Plastic", "1301": "Plastic",
    "2412": "Tel", "4904": "Tel"
}

sector_trends = {
    "Semi": {"bull": "AI 晶片需求強勁，先進製程產能滿載。", "bear": "消費性電子復甦緩慢，成熟製程競爭加劇。"},
    "AI_Hw": {"bull": "雲端伺服器資本支出擴大，出貨動能強勁。", "bear": "缺料問題緩解後，市場擔憂毛利遭到壓縮。"},
    "Ship": {"bull": "紅海危機推升運價，SCFI 指數維持高檔。", "bear": "全球新船運力大量投放，供需失衡壓力大。"},
    "Fin": {"bull": "投資收益回升，銀行利差維持穩健。", "bear": "避險成本居高不下，降息預期反覆干擾。"},
    "Power": {"bull": "強韌電網計畫持續釋單，綠能需求長線看好。", "bear": "原物料價格波動，短線漲多面臨估值修正。"},
    "Default": {"bull": "資金輪動健康，具備題材吸引法人進駐。", "bear": "產業前景不明朗，資金撤出，面臨修正壓力。"}
}

# --- 1. 核心邏輯 ---
def analyze_stock_strategy(ticker_code, current_price, ma20, ma60, trend_list):
    bias_20 = ((current_price - ma20) / ma20) * 100
    rating, color_class, predict_score, reason = "觀察", "tag-hold", 50, ""
    
    sector_key = ticker_sector_map.get(ticker_code, "Default")
    
    if current_price > ma20 and current_price > ma60 and bias_20 > 5:
        rating, color_class, predict_score = "強力推薦", "tag-strong", 90
        trend_desc = sector_trends.get(sector_key, sector_trends["Default"])["bull"]
        reason = f"🔥 <b>技術面：</b>強勢站穩月線({ma20:.1f})，乖離率 {bias_20:.1f}%。<br>🌍 <b>產業面：</b>{trend_desc}"
    elif current_price > ma20 and bias_20 > 0:
        rating, color_class, predict_score = "買進", "tag-buy", 70
        trend_desc = sector_trends.get(sector_key, sector_trends["Default"])["bull"]
        reason = f"📈 <b>技術面：</b>站上月線支撐({ma20:.1f})，短線轉強。<br>🌍 <b>產業面：</b>{trend_desc}"
    elif current_price < ma20 and current_price < ma60:
        rating, color_class, predict_score = "避開", "tag-sell", 10
        trend_desc = sector_trends.get(sector_key, sector_trends["Default"])["bear"]
        reason = f"⚠️ <b>技術面：</b>跌破月季線，上方壓力大。<br>🌍 <b>產業面：</b>{trend_desc}"
    elif current_price < ma20:
        rating, color_class, predict_score = "賣出", "tag-sell", 30
        trend_desc = sector_trends.get(sector_key, sector_trends["Default"])["bear"]
        reason = f"📉 <b>技術面：</b>跌破月線({ma20:.1f})，動能轉弱。<br>🌍 <b>產業面：</b>{trend_desc}"
    else:
        reason = f"👀 <b>技術面：</b>月線({ma20:.1f})附近震盪。<br>🌍 <b>產業面：</b>多空消息紛雜，等待方向。"
        
    return rating, color_class, reason, predict_score

# --- 2. 資料處理 ---
@st.cache_data(ttl=300) 
def fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    return yf.download(tickers, period="6mo", group_by='ticker', progress=False)

def process_stock_data():
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    with st.spinner(f'AI 正在計算 {len(tickers)} 檔個股數據...'):
        data_download = fetch_stock_data_wrapper(tickers)
    
    rows = []
    if data_download is None or len(tickers) == 0: return []
    for ticker in tickers:
        try:
            if len(tickers) == 1: df_stock = data_download
            else: df_stock = data_download[ticker]
            closes = df_stock['Close']
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            closes_list = closes.dropna().tolist()
            if len(closes_list) < 60: continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            ma20 = sum(closes_list[-20:]) / 20
            ma60 = sum(closes_list[-60:]) / 60
            clean_code = ticker.replace(".TW", "")
            
            rating, color_class, reason, score = analyze_stock_strategy(
                clean_code, current_price, ma20, ma60, closes_list[-10:]
            )
            
            # 置頂邏輯
            is_new = (ticker == st.session_state.last_added)
            final_sort_key = 9999 if is_new else score 

            rows.append({
                "code": clean_code, "name": current_map[ticker],
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price, "change": daily_change_pct, 
                "score": final_sort_key,
                "ma20": ma20, "rating": rating, "rating_class": color_class,
                "reason": reason, "trend": closes_list[-30:]
            })
        except: continue
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 3. 畫圖 ---
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

# --- 4. 介面與新增功能 ---
st.title("🚀 台股 AI 飆股神探")

with st.container():
    col_add, col_info = st.columns([2, 3])
    with col_add:
        with st.form(key='add_stock_form', clear_on_submit=True):
            col_input, col_btn = st.columns([3, 1])
            with col_input: 
                # === 介面修改提示 ===
                new_ticker_input = st.text_input("輸入代號與名稱", placeholder="範例：1616 億泰 (自動命名) 或 1616")
            with col_btn: 
                submitted = st.form_submit_button("新增")
            
            if submitted and new_ticker_input:
                # === 關鍵邏輯修改：解析輸入 ===
                # 如果使用者輸入 "1616 億泰"，我們就直接用 "億泰"
                # 如果使用者只輸入 "1616"，我們才去抓 (可能會抓到英文)
                
                parts = new_ticker_input.strip().split()
                stock_code = parts[0]
                custom_name = parts[1] if len(parts) > 1 else None # 如果有第二部分，那就是名字
                
                if not stock_code.isdigit():
                    st.error("代號必須是數字！")
                else:
                    full_ticker = f"{stock_code}.TW"
                    
                    if full_ticker in st.session_state.watch_list:
                         st.warning(f"{stock_code} 已經在清單中了！")
                    else:
                        try:
                            # 先檢查是否存在
                            ticker_obj = yf.Ticker(full_ticker)
                            hist = ticker_obj.history(period='5d')
                            
                            if not hist.empty:
                                # 決定顯示名稱
                                if custom_name:
                                    final_name = custom_name # 使用者自己輸入的中文
                                else:
                                    # 嘗試抓取，抓不到就用代號
                                    final_name = ticker_obj.info.get('longName', f"自選股-{stock_code}")
                                
                                st.session_state.watch_list[full_ticker] = final_name
                                st.session_state.last_added = full_ticker
                                
                                st.success(f"成功加入：{stock_code} {final_name}")
                                st.rerun()
                            else:
                                st.error(f"找不到代號 {stock_code}，請確認。")
                        except Exception as e:
                            st.error(f"連線錯誤，請稍後再試。")

    with col_info:
        st.info("💡 **小撇步**：為了避免抓到英文名，建議輸入 **「代號+空格+中文名」** (如 `1616 億泰`)，系統會直接使用你輸入的名字！")
        filter_strong = st.checkbox("🔥 只看強力推薦", value=False)

data_rows = process_stock_data()
if filter_strong: data_rows = [d for d in data_rows if d['rating'] == "強力推薦"]

# --- 5. HTML 渲染 ---
html_content = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: "Microsoft JhengHei", sans-serif; margin: 0; padding-bottom: 50px; }
    table { width: 100%; border-collapse: collapse; font-size: 15px; }
    th { background: #f2f2f2; padding: 12px; text-align: left; position: sticky; top: 0; z-index: 10; border-bottom: 2px solid #ddd; }
    td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
    tr { position: relative; z-index: 1; }
    tr:hover { background: #f8f9fa; z-index: 100; position: relative; }
    
    .up { color: #d62728; font-weight: bold; }
    .down { color: #2ca02c; font-weight: bold; }
    a { text-decoration: none; color: #0066cc; font-weight: bold; background: #f0f7ff; padding: 2px 6px; border-radius: 4px; }
    
    .tooltip-container { position: relative; display: inline-block; cursor: help; padding: 5px 10px; border-radius: 20px; font-weight: bold; font-size: 13px; transition: all 0.2s; }
    .tooltip-container:hover { transform: scale(1.05); }
    .tooltip-text { 
        visibility: hidden; width: 350px; background-color: #2c3e50; color: #fff; 
        text-align: left; border-radius: 8px; padding: 15px; position: absolute; z-index: 9999; 
        bottom: 140%; left: 50%; margin-left: -175px; opacity: 0; transition: opacity 0.3s; 
        font-weight: normal; font-size: 14px; line-height: 1.6; pointer-events: none; 
        box-shadow: 0 5px 15px rgba(0,0,0,0.5);
    }
    .tooltip-text::after { content: ""; position: absolute; top: 100%; left: 50%; margin-left: -6px; border-width: 6px; border-style: solid; border-color: #2c3e50 transparent transparent transparent; }
    .tooltip-container:hover .tooltip-text { visibility: visible; opacity: 1; }

    tr:nth-child(-n+3) .tooltip-text { bottom: auto; top: 140%; }
    tr:nth-child(-n+3) .tooltip-text::after { top: auto; bottom: 100%; border-color: transparent transparent #2c3e50 transparent; }

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
            <th>代號</th><th>股名</th><th>現價 <span style="font-size:12px;color:#888">(月線)</span></th><th>漲跌</th><th>AI 評級 (懸停)</th><th>近三月走勢</th>
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
st.caption("資料來源：Yahoo Finance API")
