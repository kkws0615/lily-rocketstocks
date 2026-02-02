import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="台股AI標股神探 (目標價版)", layout="wide")

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
    ("3324.TWO", "雙鴻"), ("6274.TWO", "台燿"), ("3260.TWO", "威剛"), ("6282.TW", "康舒"),
    
    ("0050.TW", "元大台灣50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息"),
    ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"), ("00679B.TWO", "元大美債20年")
]

# 索引建立
stock_map_code = {code: name for code, name in DEFAULT_STOCKS}
stock_map_name = {name: code for code, name in DEFAULT_STOCKS}
stock_map_simple = {code.split('.')[0]: code for code, name in DEFAULT_STOCKS}

# --- 0. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in DEFAULT_STOCKS}

for code, name in DEFAULT_STOCKS:
    if code in st.session_state.watch_list:
        st.session_state.watch_list[code] = name

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# --- 2. 搜尋與驗證 ---
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
                if res.get('exchange') in ['NMS', 'NYQ']: return res['symbol'], res['name']
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
        if name: return target, name, None
        elif probe_ticker(target): return target, f"{query} (上市)", None
            
        target = f"{query}.TWO"
        name = scrape_yahoo_name(target)
        if name: return target, name, None
        elif probe_ticker(target): return target, f"{query} (上櫃)", None

    return None, None, f"找不到「{query}」，請確認代號。"

# --- 3. 核心分析邏輯 (含目標價計算) ---

# 【策略 A】短線衝刺 (預測未來 30 天)
def analyze_short_term(ticker_code, current_price, ma20, ma60):
    if ma60 is None: return "觀察", "tag-hold", 40, "👀 資料不足", 2, current_price

    bias_20 = ((current_price - ma20) / ma20) * 100
    
    # 目標價邏輯：
    # 強力推薦 -> 氣勢正旺，目標看漲 10%
    # 買進 -> 轉強初期，目標看漲 5%
    # 避開/賣出 -> 趨勢向下，目標看跌 5%
    
    if current_price > ma20 and current_price > ma60 and bias_20 > 5:
        target_price = current_price * 1.10
        return "強力推薦", "tag-strong", 90, f"🔥 <b>噴出：</b>乖離 {bias_20:.1f}%，動能極強！", 4, target_price
    elif current_price > ma20 and bias_20 > 0:
        target_price = current_price * 1.05
        return "買進", "tag-buy", 70, f"📈 <b>轉強：</b>站上月線({ma20:.1f})，趨勢向上。", 3, target_price
    elif current_price < ma20 and current_price < ma60:
        target_price = current_price * 0.95
        return "避開", "tag-sell", 10, "⚠️ <b>空頭：</b>跌破月季線，壓力沉重。", 1, target_price
    elif current_price < ma20:
        target_price = current_price * 0.98
        return "賣出", "tag-sell", 30, f"📉 <b>轉弱：</b>跌破月線({ma20:.1f})。", 1, target_price
    else:
        target_price = current_price * 1.02
        return "觀察", "tag-hold", 50, "👀 <b>盤整：</b>月線附近震盪。", 2, target_price

# 【策略 B】長線存股 (預測未來 180 天)
def analyze_long_term(ticker_code, current_price, ma60, ma200):
    if ma200 is None: return "資料不足", "tag-hold", 0, "⚠️ 上市未滿一年", 0, current_price

    # 目標價邏輯：長線看年線乖離
    
    if current_price > ma200 and ma60 > ma200:
        bias_60 = ((current_price - ma60) / ma60) * 100
        if bias_60 < 10:
            target_price = current_price * 1.15 # 長多格局，看漲 15%
            return "強力推薦", "tag-strong", 95, f"💎 <b>長多：</b>年線之上且乖離低，穩健佈局點。", 4, target_price
        else:
            target_price = current_price * 1.05
            return "續抱", "tag-buy", 80, f"📈 <b>多頭：</b>長線趨勢強，但短線稍熱。", 3, target_price

    elif current_price > ma200 and current_price < ma60:
        target_price = ma60 # 回檔目標是彈回季線
        return "回檔佈局", "tag-buy", 85, f"💰 <b>機會：</b>回測年線({ma200:.1f})支撐，價值浮現。", 3.5, target_price

    elif current_price < ma200:
        target_price = current_price * 0.90 # 空頭看跌
        return "空頭走勢", "tag-sell", 20, f"🐻 <b>空頭：</b>股價低於年線({ma200:.1f})，勿接刀。", 1, target_price
    
    else:
        target_price = current_price
        return "觀察", "tag-hold", 50, "👀 <b>整理：</b>年線附近震盪。", 2, target_price

# --- 4. 資料處理 ---
@st.cache_data(ttl=300) 
def fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    return yf.download(tickers, period="1y", group_by='ticker', progress=False)

def process_stock_data(strategy_type="short"):
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    
    if not tickers: return []

    with st.spinner(f'AI 正在計算 ({strategy_type}) 數據...'):
        data_download = fetch_stock_data_wrapper(tickers)
    
    rows = []
    
    for ticker in tickers:
        clean_code = ticker.replace(".TW", "").replace(".TWO", "")
        stock_name = current_map.get(ticker, ticker)
        
        try:
            if len(tickers) == 1: df_stock = data_download
            else: df_stock = data_download[ticker] if data_download is not None else pd.DataFrame()
            
            closes = df_stock['Close'] if not df_stock.empty else pd.Series()
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            closes_list = closes.dropna().tolist()
            
            if len(closes_list) < 1: continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2] if len(closes_list) > 1 else current_price
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            ma20 = sum(closes_list[-20:]) / 20 if len(closes_list) >= 20 else None
            ma60 = sum(closes_list[-60:]) / 60 if len(closes_list) >= 60 else None
            ma200 = sum(closes_list[-200:]) / 200 if len(closes_list) >= 200 else None
            
            if strategy_type == "short":
                rating, color_class, score, reason, sort_order, target_p = analyze_short_term(clean_code, current_price, ma20, ma60)
                ma_info = f"{ma20:.1f}" if ma20 else "-"
            else:
                rating, color_class, score, reason, sort_order, target_p = analyze_long_term(clean_code, current_price, ma60, ma200)
                ma_info = f"{ma200:.1f}" if ma200 else "-"

            is_new = (ticker == st.session_state.last_added)
            final_sort_key = 9999 if is_new else score 
            safe_reason = reason.replace("'", "&#39;")

            rows.append({
                "code": clean_code, "name": stock_name,
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price, "change": change_pct, 
                "score": final_sort_key, "sort_order": sort_order,
                "ma_disp": ma_info, "rating": rating, "rating_class": color_class,
                "reason": safe_reason, 
                "target_price": target_p, # 新增目標價
                "trend": closes_list[-30:]
            })
        except: continue
    
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 5. 畫圖與 HTML 生成 ---
def make_sparkline(data):
    if not data or len(data) < 2: return ""
    w, h = 100, 30
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

def render_html_table(rows, ma_label, target_date_str):
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
        #floating-tooltip {{ position: fixed; display: none; width: 300px; background-color: #2c3e50; color: #fff; border-radius: 8px; padding: 15px; z-index: 999; font-size: 14px; pointer-events: none; }}
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
        tt.style.left = (e.clientX + 15) + 'px'; tt.style.top = (e.clientY + 15) + 'px';
    }}
    function hideTooltip() {{ document.getElementById('floating-tooltip').style.display = 'none'; }}
    </script>
    </head>
    <body>
    <div id="floating-tooltip"></div>
    <table>
        <thead>
            <tr>
                <th>代號</th> <th>股名</th> <th>現價 <span class="sub-text">({ma_label})</span></th> <th>漲跌</th>
                <th>目標價 <span class="sub-text">({target_date_str})</span></th> 
                <th>AI 評級</th> <th>走勢</th>
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
            <td class="{p_cls}">{row['price']:.1f} <span class='sub-text'>({row['ma_disp']})</span></td>
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

# --- 6. 主程式介面 ---
st.title("🚀 台股 AI 標股神探 (目標價版)")

with st.container():
    with st.form(key='add_stock', clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1: query = st.text_input("新增", placeholder="輸入：6271、合機、華邦電")
        with col2: submit = st.form_submit_button("加入")
        if submit and query:
            s, n, e = validate_and_add(query)
            if s:
                st.session_state.watch_list[s] = n
                st.session_state.last_added = s
                st.success(f"已加入：{n}")
                st.rerun()
            else: st.error(e)

tab1, tab2 = st.tabs(["🚀 短線飆股 (1個月)", "🐢 長線存股 (6個月)"])

# 自動計算未來日期
date_1m = (datetime.now() + timedelta(days=30)).strftime("%m/%d")
date_6m = (datetime.now() + timedelta(days=180)).strftime("%m/%d")

with tab1:
    st.caption(f"🔥 **預測邏輯**：追逐動能，預估未來 30 天 ({date_1m}) 目標價。")
    filter_s = st.checkbox("只看強力推薦 (短線)", key="f1")
    rows = process_stock_data("short")
    if filter_s: rows = [r for r in rows if r['rating'] == "強力推薦"]
    components.html(render_html_table(rows, "月線", f"預計 {date_1m}"), height=600, scrolling=True)

with tab2:
    st.caption(f"💎 **預測邏輯**：尋找價值，預估未來半年 ({date_6m}) 目標價。")
    filter_l = st.checkbox("只看強力推薦 (長線)", key="f2")
    rows = process_stock_data("long")
    if filter_l: rows = [r for r in rows if r['rating'] == "強力推薦"]
    components.html(render_html_table(rows, "年線", f"預計 {date_6m}"), height=600, scrolling=True)
