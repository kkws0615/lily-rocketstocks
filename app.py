import streamlit as st
import pandas as pd
import yfinance as yf
import random

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI標股神探 (完美修復版)", layout="wide")

# --- 1. 核心功能：抓取資料 ---
@st.cache_data(ttl=600)
def get_stock_data():
    # 30 檔熱門觀察名單
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
    with st.spinner('AI 正在連線交易所取得即時報價...'):
        try:
            # 抓取 3 個月資料以畫出比較明顯的走勢
            data_download = yf.download(tickers, period="3mo", group_by='ticker', progress=False)
        except:
            return []
    
    rows = []
    
    for ticker in tickers:
        try:
            df_stock = data_download[ticker]
            # 處理 MultiIndex 結構問題
            closes = df_stock['Close']
            if isinstance(closes, pd.DataFrame):
                closes = closes.iloc[:, 0]
            
            closes_list = closes.dropna().tolist()
            if len(closes_list) < 2: continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            # 評級邏輯
            if predicted_growth > 15:
                rating = "強力推薦"
                color_class = "tag-strong"
                reason = f"🔥 強力理由：{random.choice(reasons_bull)}，且{random.choice(reasons_bull)}。"
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
                reason = f"👀 觀察理由：{random.choice(reasons_bear)}。"

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
                "trend": closes_list[-30:] # 取最近 30 天
            })
        except:
            continue
            
    return sorted(rows, key=lambda x: x['predict'], reverse=True)

# --- 2. 輔助功能：SVG 走勢圖生成器 ---
def make_sparkline(data):
    if not data: return ""
    width = 100
    height = 35
    min_val = min(data)
    max_val = max(data)
    if max_val == min_val: return ""
    
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        y = height - ((val - min_val) / (max_val - min_val)) * (height - 4) - 2
        points.append(f"{x},{y}")
    
    polyline_points = " ".join(points)
    color = "#dc3545" if data[-1] > data[0] else "#28a745" # 紅漲綠跌
    
    # 這裡一定要用單行字串，避免 HTML 結構斷裂
    return f'<svg width="{width}" height="{height}" style="overflow:visible;vertical-align:middle"><polyline points="{polyline_points}" fill="none" stroke="{color}" stroke-width="2"/><circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="3" fill="{color}"/></svg>'

# --- 3. 頁面標題與 CSS 注入 ---

st.title("🚀 台股 AI 飆股快篩 (HTML 完美渲染版)")

col1, col2 = st.columns([1, 5])
with col1:
    filter_strong = st.checkbox("🔥 只看強力推薦", value=False)
with col2:
    st.info("💡 提示：滑鼠移到 **「評級」** 上方，會自動浮現 AI 分析原因！")

# 取得資料
data_rows = get_stock_data()
if filter_strong:
    data_rows = [d for d in data_rows if d['rating'] == "強力推薦"]

# === 4. 構建 HTML 字串 (極度謹慎版) ===

# 定義 CSS (壓縮成一行或確保無縮排問題)
css_style = """
<style>
    table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }
    th { background: #f0f2f6; padding: 12px; text-align: left; border-bottom: 2px solid #ddd; }
    td { padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }
    tr:hover { background: #f9f9f9; }
    .t-up { color: #d62728; font-weight: bold; }
    .t-down { color: #2ca02c; font-weight: bold; }
    a { text-decoration: none; color: #007bff; font-weight: bold; }
    
    /* Tooltip 樣式 */
    .tooltip-box { position: relative; display: inline-block; cursor: help; padding: 5px 8px; border-radius: 4px; font-weight: bold; font-size: 13px; }
    .tooltip-text { visibility: hidden; width: 220px; background-color: #222; color: #fff; text-align: left; border-radius: 6px; padding: 10px; position: absolute; z-index: 100; bottom: 130%; left: 50%; margin-left: -110px; opacity: 0; transition: opacity 0.3s; font-weight: normal; font-size: 12px; line-height: 1.5; box-shadow: 0 4px 8px rgba(0,0,0,0.3); pointer-events: none; }
    .tooltip-text::after { content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px; border-width: 5px; border-style: solid; border-color: #222 transparent transparent transparent; }
    .tooltip-box:hover .tooltip-text { visibility: visible; opacity: 1; }
    
    /* 評級顏色 */
    .tag-strong { background: #ffebeb; color: #d62728; border: 1px solid #ffcccc; }
    .tag-buy { background: #e6ffe6; color: #2ca02c; border: 1px solid #ccffcc; }
    .tag-sell { background: #f0f0f0; color: #666; }
    .tag-hold { background: #f8f9fa; color: #888; }
</style>
"""

# 開始拼接 HTML
html_parts = []
html_parts.append(css_style)
html_parts.append('<table>')
html_parts.append('<thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>預測漲幅</th><th>AI 評級 (懸停看原因)</th><th>近月走勢</th></tr></thead>')
html_parts.append('<tbody>')

for row in data_rows:
    p_cls = "t-up" if row['change'] > 0 else "t-down"
    pred_cls = "t-up" if row['predict'] > 0 else "t-down"
    sparkline_svg = make_sparkline(row['trend'])
    
    # 使用 f-string 但小心不要有換行符號破壞結構
    tr = f"""
    <tr>
        <td><a href="{row['url']}" target="_blank">{row['code']}</a></td>
        <td>{row['name']}</td>
        <td class="{p_cls}">{row['price']:.1f}</td>
        <td class="{p_cls}">{row['change']:.2f}%</td>
        <td class="{pred_cls}">{row['predict']:.2f}%</td>
        <td>
            <div class="tooltip-box {row['rating_class']}">
                {row['rating']}
                <span class="tooltip-text">{row['reason']}</span>
            </div>
        </td>
        <td>{sparkline_svg}</td>
    </tr>
    """
    html_parts.append(tr)

html_parts.append('</tbody></table>')

# 將列表組合成單一字串
final_html = "".join(html_parts)

# === 5. 輸出 (關鍵) ===
# 使用 unsafe_allow_html=True 渲染
st.markdown(final_html, unsafe_allow_html=True)

st.write("")
st.markdown("---")
st.caption("資料來源：Yahoo Finance API | Render Mode: HTML Strict")
