import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re
import numpy as np
from datetime import datetime, timedelta

# --- 1. 頁面基本設定 ---
st.set_page_config(
    page_title="台股 AI 趨勢雷達",
    page_icon="🚀",
    layout="wide"
)

# --- 2. 內建核心熱門股清單 (確保代號與名稱正確匹配) ---
DEFAULT_STOCKS = [
    # 上市權值 (.TW)
    ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2317.TW", "鴻海"), ("2303.TW", "聯電"), ("2308.TW", "台達電"),
    ("2382.TW", "廣達"), ("3231.TW", "緯創"), ("2357.TW", "華碩"), ("6669.TW", "緯穎"), ("3008.TW", "大立光"),
    ("2376.TW", "技嘉"), ("2356.TW", "英業達"), ("3017.TW", "奇鋐"), ("2301.TW", "光寶科"), ("3711.TW", "日月光投控"),
    ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("2618.TW", "長榮航"), ("2610.TW", "華航"),
    ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2886.TW", "兆豐金"), ("2884.TW", "玉山金"),
    ("5880.TW", "合庫金"), ("2892.TW", "第一金"), ("2880.TW", "華南金"), ("2885.TW", "元大金"), ("2890.TW", "永豐金"),
    ("1513.TW", "中興電"), ("1519.TW", "華城"), ("1503.TW", "士電"), ("1504.TW", "東元"), ("1514.TW", "亞力"),
    ("6271.TW", "同欣電"), ("2453.TW", "凌群"), ("1616.TW", "億泰"), ("1618.TW", "合機"), ("2344.TW", "華邦電"),

    # 上櫃熱門 (.TWO)
    ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), ("5347.TWO", "世界先進"), ("3293.TWO", "鈊象"),
    ("8069.TWO", "元太"), ("6147.TWO", "頎邦"), ("3105.TWO", "穩懋"), ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"),
    ("3324.TWO", "雙鴻"), ("6274.TWO", "台燿"), ("3260.TWO", "威剛"), ("6282.TW", "康舒"), ("4953.TWO", "緯軟"),
    
    # 熱門 ETF
    ("0050.TW", "元大台灣50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息"),
    ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"), ("00679B.TWO", "元大美債20年")
]

# 快速查詢字典
stock_map_code = {code: name for code, name in DEFAULT_STOCKS}
stock_map_name = {name: code for code, name in DEFAULT_STOCKS}
stock_map_simple = {code.split('.')[0]: code for code, name in DEFAULT_STOCKS}

# --- 3. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in DEFAULT_STOCKS}

for code, name in DEFAULT_STOCKS:
    if code in st.session_state.watch_list:
        st.session_state.watch_list[code] = name

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# --- 4. 大盤即時走勢圖 (專業版 K 線圖) ---
def render_taiex_realtime_chart():
    # 鎖定台灣加權指數，高度優化為 500px 並貼合邊界
    html_code = """
    <div class="tradingview-widget-container" style="height: 500px; width: 100%;">
      <div id="tradingview_taiex" style="height: 100%; width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {
      "autosize": true,
      "symbol": "TWSE:TAIEX",
      "interval": "1",
      "timezone": "Asia/Taipei",
      "theme": "light",
      "style": "1",
      "locale": "zh_TW",
      "enable_publishing": false,
      "backgroundColor": "#ffffff",
      "gridColor": "rgba(240, 243, 250, 0.5)",
      "hide_top_toolbar": true,
      "hide_legend": false,
      "save_image": false,
      "container_id": "tradingview_taiex",
      "withdateranges": true,
      "studies": [
        "Volume@tv-basicstudies"
      ]
    }
      );
      </script>
    </div>
    """
    components.html(html_code, height=500)

# --- 5. 搜尋與驗證邏輯 ---
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
        for ext in [".TW", ".TWO"]:
            target = f"{query}{ext}"
            name = scrape_yahoo_name(target)
            if name and name != "Yahoo奇摩股市": return target, name, None
            elif probe_ticker(target): return target, f"{query} ({'上市' if ext=='.TW' else '上櫃'})", None

    return None, None, f"找不到「{query}」，請確認代號。"

# --- 6. 技術指標計算 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 7. 三大核心分析策略 ---

# A. 短線 (1個月) - 月線 20MA
def analyze_short_term(current_price, ma20, ma60, vol_ratio, rsi):
    if ma60 is None: return "觀察", "tag-hold", 40, "👀 資料不足", 2, current_price
    bias_20 = ((current_price - ma20) / ma20) * 100
    
    reasons = [f"📈 趨勢：{'站上' if current_price > ma20 else '低於'}月線"]
    if vol_ratio > 1.5: reasons.append(f"🔥 量能：爆量攻擊({vol_ratio:.1f}倍)")
    if rsi > 80: reasons.append(f"⚠️ 指標：RSI過熱({rsi:.0f})")
    elif rsi < 30: reasons.append(f"✨ 指標：RSI超賣({rsi:.0f})")

    if current_price > ma20 and current_price > ma60 and bias_20 > 5 and vol_ratio > 1.2:
        return "強力推薦", "tag-strong", 90, "<br>".join(reasons), 4, current_price * 1.10
    elif current_price > ma20 and bias_20 > 0:
        return "買進", "tag-buy", 70, "<br>".join(reasons), 3, current_price * 1.05
    else:
        return "觀察", "tag-hold", 50, "<br>".join(reasons), 2, current_price * 1.02

# B. 中線 (半年) - 季線 60MA 與 半年線 120MA
def analyze_medium_term(current_price, ma60, ma120):
    if ma120 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足半年", 0, current_price
    
    if current_price > ma120 and ma60 > ma120:
        bias_60 = ((current_price - ma60) / ma60) * 100
        if bias_60 < 10:
            return "強力推薦", "tag-strong", 95, "💎 中長多格局，位階適中。", 4, current_price * 1.15
        return "續抱", "tag-buy", 80, "📈 多頭排列中。", 3, current_price * 1.05
    elif current_price > ma120 and current_price < ma60:
        return "回檔佈局", "tag-buy", 85, "💰 回測半年線支撐。", 3.5, ma60
    return "觀察", "tag-hold", 50, "目前橫盤整理中。", 2, current_price

# C. 長線 (1年) - 年線 240MA
def analyze_year_term(current_price, ma240, rsi):
    if ma240 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足一年", 0, current_price
    
    bias_240 = ((current_price - ma240) / ma240) * 100
    if -5 < bias_240 < 10 and rsi > 45:
        return "長線買點", "tag-strong", 95, "💎 回測年線不破，價值浮現。", 4, ma240 * 1.3
    if bias_240 > 30:
        return "風險過高", "tag-sell", 40, "⚠️ 乖離年線過大，小心修正。", 2, current_price * 0.9
    return "長多續抱", "tag-buy", 80, "📈 趨勢穩健向上。", 3, current_price * 1.1

# --- 8. 資料獲取與處理 ---
@st.cache_data(ttl=300) 
def fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    return yf.download(tickers, period="2y", group_by='ticker', progress=False)

def process_stock_data(strategy_type="short"):
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    if not tickers: return []

    data_download = fetch_stock_data_wrapper(tickers)
    rows = []
    
    for ticker in tickers:
        try:
            df = data_download[ticker] if len(tickers) > 1 else data_download
            closes = df['Close'].dropna()
            if len(closes) < 20: continue
            
            cur_p = closes.iloc[-1]
            change = ((cur_p - closes.iloc[-2]) / closes.iloc[-2]) * 100
            
            # 均線計算
            ma20, ma60 = closes.rolling(20).mean().iloc[-1], closes.rolling(60).mean().iloc[-1]
            ma120 = closes.rolling(120).mean().iloc[-1] if len(closes) >= 120 else None
            ma240 = closes.rolling(240).mean().iloc[-1] if len(closes) >= 240 else None
            
            # 指標與量能
            rsi = calculate_rsi(closes).iloc[-1]
            vols = df['Volume'].dropna()
            vol_ratio = vols.iloc[-1] / vols.rolling(5).mean().iloc[-1] if len(vols) >= 5 else 1.0

            if strategy_type == "short":
                rating, cls, score, reason, sort, target = analyze_short_term(cur_p, ma20, ma60, vol_ratio, rsi)
                trend_list = closes.iloc[-60:].tolist()
            elif strategy_type == "medium":
                rating, cls, score, reason, sort, target = analyze_medium_term(cur_p, ma60, ma120)
                trend_list = closes.iloc[-120:].tolist()
            else:
                rating, cls, score, reason, sort, target = analyze_year_term(cur_p, ma240, rsi)
                trend_list = closes.iloc[-240:].tolist()

            rows.append({
                "code": ticker.split('.')[0], "name": current_map[ticker],
                "price": cur_p, "change": change, "target": target,
                "rating": rating, "cls": cls, "reason": reason.replace("'", "&#39;"),
                "trend": trend_list, "score": 9999 if ticker == st.session_state.last_added else score,
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}"
            })
        except: continue
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 9. 視覺化組件 ---
def make_sparkline(data):
    if not data: return ""
    w, h = 180, 50 # 走勢圖拉高至 50px，寬度 180px
    mn, mx = min(data), max(data)
    pts = " ".join([f"{(i/(len(data)-1))*w},{h-((v-mn)/(mx-mn))*(h-10)-5}" for i, v in enumerate(data)])
    color = "#dc3545" if data[-1] > data[0] else "#28a745"
    return f'<svg width="{w}" height="{h}" style="display:block;margin:auto;"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'

def render_table(rows, date_label, trend_label):
    html = f"""
    <style>
        body {{ font-family: sans-serif; margin: 0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f2f2f2; padding: 10px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #ddd; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }}
        .up {{ color: #d62728; font-weight: bold; }} .down {{ color: #2ca02c; font-weight: bold; }}
        .tag-strong {{ background: #ffebeb; color: #d62728; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .tag-buy {{ background: #e6ffe6; color: #2ca02c; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .tag-hold {{ background: #f8f9fa; color: #666; padding: 4px 8px; border-radius: 4px; }}
        #tt {{ position: fixed; display: none; width: 280px; background: #2c3e50; color: #fff; padding: 12px; border-radius: 8px; z-index: 999; font-size: 13px; line-height: 1.5; }}
    </style>
    <div id="tt"></div>
    <table>
        <thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>目標價({date_label})</th><th>AI評級</th><th>走勢({trend_label})</th></tr></thead>
        <tbody>
    """
    for r in rows:
        color = "up" if r['change'] > 0 else "down"
        html += f"""
        <tr onmouseover="document.getElementById('tt').innerHTML='{r['reason']}';document.getElementById('tt').style.display='block';" 
            onmousemove="document.getElementById('tt').style.left=(event.clientX+15)+'px';document.getElementById('tt').style.top=(event.clientY+15)+'px';" 
            onmouseout="document.getElementById('tt').style.display='none';">
            <td><a href="{r['url']}" target="_blank" style="text-decoration:none;color:#0066cc;">{r['code']}</a></td>
            <td>{r['name']}</td>
            <td class="{color}">{r['price']:.1f}</td>
            <td class="{color}">{r['change']:.2f}%</td>
            <td style="font-weight:bold;">{r['target']:.1f}</td>
            <td><span class="{r['cls']}">{r['rating']}</span></td>
            <td>{make_sparkline(r['trend'])}</td>
        </tr>"""
    return html + "</tbody></table>"

# --- 10. 主介面 ---
st.title("🚀 台股 AI 趨勢雷達")
st.markdown("### 📊 台灣加權指數 (即時走勢)")
render_taiex_realtime_chart()
st.markdown("---")

with st.container():
    with st.form(key='add', clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        with c1: query = st.text_input("新增監控", placeholder="輸入代號或名稱 (例如: 2330, 緯軟)")
        with c2: 
            if st.form_submit_button("加入") and query:
                s, n, e = validate_and_add(query)
                if s: 
                    st.session_state.watch_list[s] = n
                    st.session_state.last_added = s
                    st.rerun()
                else: st.error(e)

t1, t2, t3 = st.tabs(["🚀 短線飆股 (1個月)", "🌊 中線波段 (半年)", "📅 長線價值 (1年)"])
d1, d2, d3 = (datetime.now() + timedelta(days=x)).strftime("%m/%d") for x in [30, 180, 365]

with t1:
    rows = process_stock_data("short")
    components.html(render_table(rows, d1, "近3月"), height=600, scrolling=True)
with t2:
    rows = process_stock_data("medium")
    components.html(render_table(rows, d2, "近半年"), height=600, scrolling=True)
with t3:
    rows = process_stock_data("year")
    components.html(render_table(rows, d3, "近1年"), height=600, scrolling=True)
