import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="台股 AI 趨勢雷達", page_icon="🚀", layout="wide")

# --- 1. 內建百大熱門股 ---
DEFAULT_STOCKS = [
    ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2317.TW", "鴻海"), ("2303.TW", "聯電"), ("2308.TW", "台達電"),
    ("2382.TW", "廣達"), ("3231.TW", "緯創"), ("2357.TW", "華碩"), ("6669.TW", "緯穎"), ("3008.TW", "大立光"),
    ("2376.TW", "技嘉"), ("2356.TW", "英業達"), ("3017.TW", "奇鋐"), ("2301.TW", "光寶科"), ("3711.TW", "日月光投控"),
    ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("2618.TW", "長榮航"), ("2610.TW", "華航"),
    ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2886.TW", "兆豐金"), ("2884.TW", "玉山金"),
    ("5880.TW", "合庫金"), ("2892.TW", "第一金"), ("2880.TW", "華南金"), ("2885.TW", "元大金"), ("2890.TW", "永豐金"),
    ("1513.TW", "中興電"), ("1519.TW", "華城"), ("1503.TW", "士電"), ("1504.TW", "東元"), ("1514.TW", "亞力"),
    ("6271.TW", "同欣電"), ("2453.TW", "凌群"), ("1616.TW", "億泰"), ("1618.TW", "合機"), ("2344.TW", "華邦電"),

    ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), ("5347.TWO", "世界先進"), ("3293.TWO", "鈊象"),
    ("8069.TWO", "元太"), ("6147.TWO", "頎邦"), ("3105.TWO", "穩懋"), ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"),
    ("3324.TWO", "雙鴻"), ("6274.TWO", "台燿"), ("3260.TWO", "威剛"), ("6282.TW", "康舒"), ("4953.TWO", "緯軟"),
    
    ("0050.TW", "元大台灣50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息"),
    ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"), ("00679B.TWO", "元大美債20年")
]

stock_map_code = {code: name for code, name in DEFAULT_STOCKS}
stock_map_name = {name: code for code, name in DEFAULT_STOCKS}
stock_map_simple = {code.split('.')[0]: code for code, name in DEFAULT_STOCKS}

# --- 初始化 ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in DEFAULT_STOCKS}

for code, name in DEFAULT_STOCKS:
    if code in st.session_state.watch_list:
        st.session_state.watch_list[code] = name

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# --- 搜尋功能 ---
def search_yahoo_api(query):
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
    try:
        r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        data = r.json()
        results = data.get('data', {}).get('result', [])
        for res in results:
            if query in res.get('symbol') or query in res.get('name'):
                if res.get('exchange') == 'TAI': return f"{res['symbol']}.TW", res['name']
                if res.get('exchange') == 'TWO': return f"{res['symbol']}.TWO", res['name']
    except: pass
    return None, None

def scrape_yahoo_name(symbol):
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            match = re.search(r'<title>(.*?)[\(（]', r.text)
            if match: return match.group(1).strip()
    except: pass
    return None

def probe_ticker(symbol):
    try:
        t = yf.Ticker(symbol)
        if not t.history(period="1d").empty: return True
    except: pass
    return False

def validate_and_add(query):
    query = query.strip()
    if query in stock_map_name: return stock_map_name[query], query, None
    if query in stock_map_code: return query, stock_map_code[query], None
    if query in stock_map_simple:
        code = stock_map_simple[query]
        return code, stock_map_code[code], None
    
    symbol, name = search_yahoo_api(query)
    if symbol and name: return symbol, name, None

    if query.isdigit():
        target = f"{query}.TW"
        name = scrape_yahoo_name(target)
        if name and name != "Yahoo奇摩股市": return target, name, None
        elif probe_ticker(target): return target, f"{query} (上市)", None
            
        target = f"{query}.TWO"
        name = scrape_yahoo_name(target)
        if name and name != "Yahoo奇摩股市": return target, name, None
        elif probe_ticker(target): return target, f"{query} (上櫃)", None

    return None, None, f"找不到「{query}」，請確認代號。"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 核心分析策略 ---

# A. 短線 (1個月目標)
def analyze_short_term(current_price, ma20, ma60, vol_ratio, rsi):
    if ma60 is None: return "觀察", "tag-hold", 40, "👀 資料不足", 2, current_price
    bias_20 = ((current_price - ma20) / ma20) * 100
    
    reason_list = []
    if current_price > ma20: reason_list.append(f"📈 站上月線({ma20:.1f})")
    else: reason_list.append(f"📉 跌破月線")
    if vol_ratio > 1.5: reason_list.append(f"🔥 爆量({vol_ratio:.1f}倍)")
    if rsi > 80: reason_list.append(f"⚠️ RSI過熱({rsi:.0f})")
    elif rsi > 50: reason_list.append(f"💪 RSI強勢({rsi:.0f})")
    
    full_reason = "<br>".join(reason_list)

    if current_price > ma20 and current_price > ma60 and bias_20 > 5 and vol_ratio > 1.2:
        return "強力推薦", "tag-strong", 90, full_reason, 4, current_price * 1.10
    elif current_price > ma20 and bias_20 > 0:
        return "買進", "tag-buy", 70, full_reason, 3, current_price * 1.05
    elif current_price < ma20:
        return "賣出", "tag-sell", 30, full_reason, 1, current_price * 0.98
    else:
        return "觀察", "tag-hold", 50, full_reason, 2, current_price * 1.02

# B. 中線 (半年目標) - 改看季線(60)與半年線(120)
def analyze_medium_term(current_price, ma60, ma120):
    if ma120 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足半年", 0, current_price
    
    reason_list = []
    if current_price > ma60: reason_list.append(f"📈 站上季線({ma60:.1f})")
    else: reason_list.append(f"📉 跌破季線")

    full_reason = "<br>".join(reason_list)

    if current_price > ma120 and ma60 > ma120:
        bias_60 = ((current_price - ma60) / ma60) * 100
        if bias_60 < 10:
            return "強力推薦", "tag-strong", 95, f"💎 中長多格局，乖離適中。<br>{full_reason}", 4, current_price * 1.15
        else:
            return "續抱", "tag-buy", 80, f"📈 多頭排列。<br>{full_reason}", 3, current_price * 1.05
    elif current_price > ma120 and current_price < ma60:
        return "回檔佈局", "tag-buy", 85, f"💰 回測半年線支撐。<br>{full_reason}", 3.5, ma60
    elif current_price < ma120:
        return "空頭走勢", "tag-sell", 20, f"🐻 股價低於半年線。<br>{full_reason}", 1, current_price * 0.90
    else:
        return "觀察", "tag-hold", 50, full_reason, 2, current_price

# C. 長線 (1年目標) - 看年線(240)
def analyze_year_term(current_price, ma240, rsi):
    if ma240 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足一年", 0, current_price
    
    bias_240 = ((current_price - ma240) / ma240) * 100
    reason_list = [f"🐢 年線位置: {ma240:.1f}"]
    
    if bias_240 > 30:
        return "風險過高", "tag-sell", 40, f"⚠️ 乖離年線 {bias_240:.1f}% 太高<br>小心長線回調", 2, current_price * 0.9
    
    if -5 < bias_240 < 10:
        if rsi > 45: return "長線買點", "tag-strong", 95, f"💎 回測年線不破<br>長線價值浮現", 4, ma240 * 1.3
        else: return "打底觀察", "tag-buy", 70, f"👀 年線附近整理<br>等待RSI轉強", 3, ma240 * 1.2

    if bias_240 < -5:
        if rsi < 30: return "超跌搶反彈", "tag-buy", 60, f"📉 嚴重跌破年線<br>RSI超賣({rsi:.0f})", 3, ma240
        else: return "長線轉空", "tag-sell", 10, f"🐻 有效跌破年線<br>趨勢翻空", 1, current_price * 0.8

    if bias_240 >= 10:
        return "長多續抱", "tag-buy", 80, f"📈 站穩年線之上<br>長線趨勢向上", 3, current_price * 1.1

    return "觀察", "tag-hold", 50, "年線附近震盪", 2, current_price

# --- 資料處理 ---
@st.cache_data(ttl=300) 
def fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    return yf.download(tickers, period="2y", group_by='ticker', progress=False)

def process_stock_data(strategy_type="short"):
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    if not tickers: return []

    with st.spinner(f'AI 正在計算 ({strategy_type}) 數據...'):
        data_download = fetch_stock_data_wrapper(tickers)
    
    rows = []
    invalid_tickers = []
    
    for ticker in tickers:
        clean_code = ticker.replace(".TW", "").replace(".TWO", "")
        stock_name = current_map.get(ticker, ticker)
        
        try:
            if len(tickers) == 1: df_stock = data_download
            else: df_stock = data_download[ticker] if data_download is not None else pd.DataFrame()
            
            closes = df_stock['Close'] if not df_stock.empty else pd.Series()
            volumes = df_stock['Volume'] if not df_stock.empty else pd.Series()
            
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            if isinstance(volumes, pd.DataFrame): volumes = volumes.iloc[:, 0]
            
            closes_list = closes.dropna().tolist()
            if len(closes_list) < 20: 
                invalid_tickers.append(ticker)
                continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2]
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # 計算台股標準均線
            ma20 = sum(closes_list[-20:]) / 20
            ma60 = sum(closes_list[-60:]) / 60 if len(closes_list) >= 60 else None
            ma120 = sum(closes_list[-120:]) / 120 if len(closes_list) >= 120 else None # 半年線
            ma240 = sum(closes_list[-240:]) / 240 if len(closes_list) >= 240 else None # 年線
            
            rsi_series = calculate_rsi(closes)
            current_rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
            
            vol_list = volumes.dropna().tolist()
            vol_ratio = 1.0
            if len(vol_list) >= 5:
                avg_vol_5 = sum(vol_list[-5:]) / 5
                if avg_vol_5 > 0: vol_ratio = vol_list[-1] / avg_vol_5

            # 根據策略決定走勢圖要抓取的天數
            if strategy_type == "short":
                rating, color_class, score, reason, sort_order, target_p = analyze_short_term(current_price, ma20, ma60, vol_ratio, current_rsi)
                trend_data = closes_list[-60:] # 短線畫近3個月
            elif strategy_type == "medium":
                rating, color_class, score, reason, sort_order, target_p = analyze_medium_term(current_price, ma60, ma120)
                trend_data = closes_list[-120:] # 中線畫近半年
            elif strategy_type == "year":
                rating, color_class, score, reason, sort_order, target_p = analyze_year_term(current_price, ma240, current_rsi)
                trend_data = closes_list[-240:] # 長線畫近1年

            is_new = (ticker == st.session_state.last_added)
            final_sort_key = 9999 if is_new else score 
            safe_reason = reason.replace("'", "&#39;")

            rows.append({
                "code": clean_code, "name": stock_name,
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price, "change": change_pct, 
                "score": final_sort_key, "sort_order": sort_order,
                "rating": rating, "rating_class": color_class,
                "reason": safe_reason, "target_price": target_p,
                "trend": trend_data # 動態走勢資料
            })
        except: 
            invalid_tickers.append(ticker)
            continue
            
    if invalid_tickers:
        for bad_ticker in invalid_tickers:
            if bad_ticker in st.session_state.watch_list:
                del st.session_state.watch_list[bad_ticker]
    
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 畫圖 (加大寬度以顯示長線趨勢) ---
def make_sparkline(data):
    if not data or len(data) < 2: return ""
    w, h = 180, 35 # 【重點修改】拉寬走勢圖，讓長線趨勢看得更清楚
    min_v, max_v = min(data), max(data)
    if max_v == min_v: return ""
    pts = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * w
        y = h - ((val - min_v) / (max_v - min_v)) * (h - 4) - 2
        pts.append(f"{x},{y}")
    c = "#dc3545" if data[-1] > data[0] else "#28a745"
    last_pt = pts[-1].split(",")
    return f'<svg width="{w}" height="{h}" style="overflow:visible"><polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="2"/><circle cx="{last_pt[0]}" cy="{last_pt[1]}" r="3" fill="{c}"/></svg>'

def render_html_table(rows, target_date_str, sparkline_label):
    # 【重點修改】移除了表頭的 (月線/季線) 標籤，讓現價欄位變乾淨
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: "Microsoft JhengHei", sans-serif; margin: 0; padding-bottom: 50px; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: 15px; }}
        th {{ background-color: #f2f2f2; padding: 12px; text-align: left; position: sticky; top: 0; z-index: 100; border-bottom: 2px solid #ddd; cursor: pointer; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }}
        tr:hover {{ background: #f8f9fa; }} 
        .up {{ color: #d62728; font-weight: bold; }}
        .down {{ color: #2ca02c; font-weight: bold; }}
        a {{ text-decoration: none; color: #0066cc; font-weight: bold; background: #f0f7ff; padding: 2px 6px; border-radius: 4px; }}
        #floating-tooltip {{ position: fixed; display: none; width: 320px; background-color: #2c3e50; color: #fff; border-radius: 8px; padding: 15px; z-index: 9999; font-size: 14px; pointer-events: none; line-height: 1.6; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
        .tag-strong {{ color: #d62728; background: #ffebeb; padding: 4px 8px; border-radius: 4px; border: 1px solid #ffcccc; display: inline-block; font-weight: bold;}}
        .tag-buy {{ color: #2ca02c; background: #e6ffe6; padding: 4px 8px; border-radius: 4px; border: 1px solid #ccffcc; display: inline-block; font-weight: bold;}}
        .tag-sell {{ color: #495057; background: #f1f3f5; padding: 4px 8px; border-radius: 4px; border: 1px solid #dee2e6; display: inline-block; font-weight: bold;}}
        .tag-hold {{ color: #868e96; background: #fff; padding: 4px 8px; border-radius: 4px; border: 1px solid #eee; display: inline-block; font-weight: bold;}}
        .sub-text {{ font-size: 12px; color: #888; margin-left: 5px; font-weight: normal; }}
        .target-price {{ font-weight: bold; color: #555; }}
    </style>
    <script>
    function showTooltip(e, content) {{
        var tt = document.getElementById('floating-tooltip');
        tt.innerHTML = content; tt.style.display = 'block';
        var x = e.clientX + 15; var y = e.clientY + 15;
        if (x + 320 > window.innerWidth) {{ x = e.clientX - 330; }}
        if (y + 150 > window.innerHeight) {{ y = e.clientY - 150; }}
        tt.style.left = x + 'px'; tt.style.top = y + 'px';
    }}
    function hideTooltip() {{ document.getElementById('floating-tooltip').style.display = 'none'; }}
    </script>
    </head>
    <body>
    <div id="floating-tooltip"></div>
    <table>
        <thead>
            <tr>
                <th>代號</th> <th>股名</th> <th>現價</th> <th>漲跌</th>
                <th>目標價 <span class="sub-text">({target_date_str})</span></th> 
                <th>AI 評級</th> <th>走勢 <span class="sub-text">({sparkline_label})</span></th>
            </tr>
        </thead>
        <tbody>
    """
    for row in rows:
        p_cls = "up" if row['change'] > 0 else "down"
        html += f"""
        <tr>
            <td><a href="{row['url']}" target="_blank">{row['code']}</a></td>
            <td>{row['name']}</td>
            <td class="{p_cls}">{row['price']:.1f}</td>
            <td class="{p_cls}">{row['change']:.2f}%</td>
            <td class="target-price">{row['target_price']:.1f}</td>
            <td onmouseover="showTooltip(event, '{row['reason']}')" onmouseout="hideTooltip()" style="cursor:help">
                <span class="{row['rating_class']}">{row['rating']}</span>
            </td>
            <td>{make_sparkline(row['trend'])}</td>
        </tr>
        """
    html += "</tbody></table></body></html>"
    return html

# --- 8. 主程式介面 ---
st.title("🚀 台股 AI 趨勢雷達")

with st.container():
    with st.form(key='add_stock', clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1: query = st.text_input("新增監控", placeholder="輸入代號或名稱 (如: 4953, 緯軟)")
        with col2: submit = st.form_submit_button("加入")
        if submit and query:
            s, n, e = validate_and_add(query)
            if s:
                st.session_state.watch_list[s] = n
                st.session_state.last_added = s
                st.success(f"已加入：{n}")
                st.rerun()
            else: st.error(e)

tab1, tab2, tab3 = st.tabs(["🚀 短線飆股 (1個月)", "🌊 中線波段 (半年)", "📅 長線價值 (1年)"])

date_1m = (datetime.now() + timedelta(days=30)).strftime("%m/%d")
date_6m = (datetime.now() + timedelta(days=180)).strftime("%m/%d")
date_1y = (datetime.now() + timedelta(days=365)).strftime("%m/%d")

with tab1:
    st.caption("🔥 **短線**：追逐動能 (Price > MA20)，尋找爆發股。")
    filter_s = st.checkbox("只看強力推薦 (短)", key="f1")
    rows = process_stock_data("short")
    if filter_s: rows = [r for r in rows if r['rating'] == "強力推薦"]
    components.html(render_html_table(rows, f"預計 {date_1m}", "近3月"), height=600, scrolling=True)

with tab2:
    st.caption("🌊 **中線**：波段操作 (Price > 季線60MA)，尋找趨勢股。")
    filter_m = st.checkbox("只看強力推薦 (中)", key="f2")
    rows = process_stock_data("medium")
    if filter_m: rows = [r for r in rows if r['rating'] == "強力推薦"]
    components.html(render_html_table(rows, f"預計 {date_6m}", "近半年"), height=600, scrolling=True)

with tab3:
    st.caption("📅 **長線**：價值投資 (Price vs 年線240MA)，尋找年線支撐買點。")
    filter_y = st.checkbox("只看長線買點", key="f3")
    rows = process_stock_data("year")
    if filter_y: rows = [r for r in rows if r['rating'] == "長線買點"]
    components.html(render_html_table(rows, f"預計 {date_1y}", "近1年"), height=600, scrolling=True)
