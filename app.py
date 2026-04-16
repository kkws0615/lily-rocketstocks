import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. 頁面基本設定 ---
st.set_page_config(
    page_title="台股 AI 趨勢雷達",
    page_icon="🚀",
    layout="wide"
)

# --- 2. 內建核心熱門股清單 (🌟 全新進化：百大熱門板塊分類) ---
DEFAULT_STOCKS = [
    # --- 半導體與 IC 設計 ---
    ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2303.TW", "聯電"), ("3711.TW", "日月光投控"),
    ("2379.TW", "瑞昱"), ("3034.TW", "聯詠"), ("3661.TW", "世芯-KY"), ("3443.TW", "創意"),
    ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), ("5347.TWO", "世界先進"),
    ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"), ("3105.TWO", "穩懋"), ("4966.TW", "譜瑞-KY"),
    ("2408.TW", "南亞科"), ("2344.TW", "華邦電"), ("2337.TW", "旺宏"), ("3583.TW", "辛耘"),

    # --- AI 伺服器、代工與電腦周邊 ---
    ("2317.TW", "鴻海"), ("2382.TW", "廣達"), ("3231.TW", "緯創"), ("6669.TW", "緯穎"),
    ("2376.TW", "技嘉"), ("2356.TW", "英業達"), ("2357.TW", "華碩"), ("2324.TW", "仁寶"),
    ("4938.TW", "和碩"), ("8210.TW", "勤誠"), ("3017.TW", "奇鋐"), ("3324.TWO", "雙鴻"), 
    ("2421.TW", "建準"), ("3037.TW", "欣興"), ("2368.TW", "金像電"), ("2383.TW", "台光電"), 
    ("6274.TWO", "台燿"), ("4953.TWO", "緯軟"),

    # --- 零組件、光學與車用 ---
    ("2308.TW", "台達電"), ("3008.TW", "大立光"), ("3406.TW", "玉晶光"), ("2327.TW", "國巨"),
    ("2492.TW", "華新科"), ("2301.TW", "光寶科"), ("1560.TW", "中砂"), ("3533.TW", "嘉澤"),
    ("6271.TW", "同欣電"), ("5425.TWO", "台半"), ("8215.TW", "明基材"),

    # --- 重電、綠能與電纜 ---
    ("1519.TW", "華城"), ("1513.TW", "中興電"), ("1503.TW", "士電"), ("1514.TW", "亞力"),
    ("1504.TW", "東元"), ("1609.TW", "大亞"), ("1618.TW", "合機"), ("3708.TW", "上緯投控"),

    # --- 航運與傳產龍頭 ---
    ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("2618.TW", "長榮航"),
    ("2610.TW", "華航"), ("2002.TW", "中鋼"), ("1101.TW", "台泥"), ("1301.TW", "台塑"),
    ("1303.TW", "南亞"), ("2912.TW", "統一超"), ("1216.TW", "統一"), ("9914.TW", "美利達"),

    # --- 金融保險 ---
    ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2886.TW", "兆豐金"),
    ("2884.TW", "玉山金"), ("5880.TW", "合庫金"), ("2892.TW", "第一金"), ("2880.TW", "華南金"),
    ("2885.TW", "元大金"), ("2890.TW", "永豐金"), ("2883.TW", "凱基金"), ("2887.TW", "台新金"),

    # --- 軟體、遊戲與其他妖股 ---
    ("3293.TWO", "鈊象"), ("8069.TWO", "元太"), ("2453.TW", "凌群"), ("3130.TW", "一零四"),
    ("5904.TWO", "寶雅"), ("8454.TW", "富邦媒"),

    # --- 熱門高股息與市值型 ETF ---
    ("0050.TW", "元大台灣50"), ("006208.TW", "富邦台50"), ("0056.TW", "元大高股息"),
    ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息"), ("00929.TW", "復華台灣科技優息"),
    ("00940.TW", "元大台灣價值高息"), ("00713.TW", "元大台灣高息低波"), ("00915.TW", "凱基優選高股息30"),
    ("00679B.TWO", "元大美債20年"), ("00687B.TW", "國泰20年美債")
]

stock_map_code = {code: name for code, name in DEFAULT_STOCKS}
stock_map_name = {name: code for code, name in DEFAULT_STOCKS}
stock_map_simple = {code.split('.')[0]: code for code, name in DEFAULT_STOCKS}

# --- 3. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in DEFAULT_STOCKS}

# 強制更新既有清單，確保新的名字(如開發金改凱基金)能對齊
new_watch_list = {}
for code, name in DEFAULT_STOCKS:
    new_watch_list[code] = name
# 保留使用者自己手動新增的股票
for code, name in st.session_state.watch_list.items():
    if code not in new_watch_list:
        new_watch_list[code] = name
st.session_state.watch_list = new_watch_list

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# --- 4. 大盤技術分析圖 (日/週/月 K線與多空均線) ---
def render_taiex_ta_chart():
    col_metric, col_controls = st.columns([2, 3])
    
    with col_controls:
        period_opt = st.radio("選擇週期", ["日線", "週線", "月線"], horizontal=True, label_visibility="collapsed")
    
    with st.container():
        try:
            if period_opt == "日線":
                df = yf.download("^TWII", period="2y", interval="1d", progress=False)
            elif period_opt == "週線":
                df = yf.download("^TWII", period="10y", interval="1wk", progress=False)
            else: 
                df = yf.download("^TWII", period="20y", interval="1mo", progress=False)
            
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                
                mas = [5, 10, 20, 60, 120, 240]
                ma_colors = ['#f39c12', '#3498db', '#9b59b6', '#2ecc71', '#e74c3c', '#7f8c8d']
                
                for ma in mas:
                    df[f'MA{ma}'] = df['Close'].rolling(window=ma).mean()
                
                current = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                change = current - prev_close
                change_pct = (change / prev_close) * 100
                
                cur_ma = {ma: df[f'MA{ma}'].iloc[-1] for ma in mas}
                
                with col_metric:
                    st.metric(
                        label=f"台灣加權指數 ({period_opt})", 
                        value=f"{current:,.0f}", 
                        delta=f"{change:,.0f} ({change_pct:.2f}%)",
                        delta_color="inverse"
                    )
                
                ma_html = f"""
                <div style="font-family: 'Microsoft JhengHei', sans-serif; font-size: 14px; margin-bottom: 5px; padding: 10px; background-color: #f8f9fa; border-radius: 8px; font-weight: bold;">
                    <span style="color: {ma_colors[0]}; margin-right: 15px;">MA5: {cur_ma[5]:,.0f}</span>
                    <span style="color: {ma_colors[1]}; margin-right: 15px;">MA10: {cur_ma[10]:,.0f}</span>
                    <span style="color: {ma_colors[2]}; margin-right: 15px;">MA20: {cur_ma[20]:,.0f}</span>
                    <span style="color: {ma_colors[3]}; margin-right: 15px;">MA60: {cur_ma[60]:,.0f}</span>
                    <span style="color: {ma_colors[4]}; margin-right: 15px;">MA120: {cur_ma[120]:,.0f}</span>
                    <span style="color: {ma_colors[5]};">MA240: {cur_ma[240]:,.0f}</span>
                </div>
                """
                st.markdown(ma_html, unsafe_allow_html=True)
                
                fig = go.Figure()
                
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='K線',
                    increasing_line_color='#dc3545', increasing_fillcolor='#dc3545', 
                    decreasing_line_color='#28a745', decreasing_fillcolor='#28a745'  
                ))
                
                for ma, color in zip(mas, ma_colors):
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df[f'MA{ma}'],
                        mode='lines', name=f'MA{ma}',
                        line=dict(color=color, width=1.2),
                        hoverinfo='y' 
                    ))
                
                visible_points = 150 
                if len(df) > visible_points:
                    x_min = df.index[-visible_points]
                else:
                    x_min = df.index[0]
                
                if period_opt == "日線": x_offset = timedelta(days=5)
                elif period_opt == "週線": x_offset = timedelta(days=21)
                else: x_offset = timedelta(days=90)
                x_max = df.index[-1] + x_offset
                
                fig.update_layout(
                    margin=dict(l=10, r=40, t=10, b=10),
                    height=450,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_rangeslider_visible=False, 
                    showlegend=False, 
                    xaxis=dict(
                        showgrid=True, gridcolor='rgba(200,200,200,0.2)',
                        range=[x_min, x_max],
                        type="date"
                    ),
                    yaxis=dict(
                        showgrid=True, gridcolor='rgba(200,200,200,0.2)',
                        side="right", 
                        tickformat=","
                    ),
                    hovermode="x unified" 
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
            else:
                st.warning("⚠️ 無法取得 Yahoo 報價。")
        except Exception as e:
            st.error(f"大盤圖表載入失敗，請確認網路連線。錯誤: {e}")

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
            
            ma20, ma60 = closes.rolling(20).mean().iloc[-1], closes.rolling(60).mean().iloc[-1]
            ma120 = closes.rolling(120).mean().iloc[-1] if len(closes) >= 120 else None
            ma240 = closes.rolling(240).mean().iloc[-1] if len(closes) >= 240 else None
            
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
    w, h = 180, 50 
    mn, mx = min(data), max(data)
    if mx == mn: return ""
    pts = " ".join([f"{(i/(len(data)-1))*w},{h-((v-mn)/(mx-mn))*(h-10)-5}" for i, v in enumerate(data)])
    color = "#dc3545" if data[-1] > data[0] else "#28a745"
    return f'<svg width="{w}" height="{h}" style="display:block;margin:auto;"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'

def render_table(rows, date_label, trend_label):
    html = f"""
    <style>
        body {{ font-family: sans-serif; margin: 0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f2f2f2; padding: 10px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #ddd; z-index: 10; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }}
        .up {{ color: #d62728; font-weight: bold; }} .down {{ color: #2ca02c; font-weight: bold; }}
        .tag-strong {{ background: #ffebeb; color: #d62728; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-buy {{ background: #e6ffe6; color: #2ca02c; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-sell {{ background: #f1f3f5; color: #495057; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-hold {{ background: #fff; border: 1px solid #eee; color: #868e96; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        #tt {{ position: fixed; display: none; width: 280px; background: #2c3e50; color: #fff; padding: 12px; border-radius: 8px; z-index: 999; font-size: 13px; line-height: 1.5; pointer-events: none;}}
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

render_taiex_ta_chart()
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

d1 = (datetime.now() + timedelta(days=30)).strftime("%m/%d")
d2 = (datetime.now() + timedelta(days=180)).strftime("%m/%d")
d3 = (datetime.now() + timedelta(days=365)).strftime("%m/%d")

with t1:
    rows = process_stock_data("short")
    components.html(render_table(rows, d1, "近3月"), height=600, scrolling=True)
with t2:
    rows = process_stock_data("medium")
    components.html(render_table(rows, d2, "近半年"), height=600, scrolling=True)
with t3:
    rows = process_stock_data("year")
    components.html(render_table(rows, d3, "近1年"), height=600, scrolling=True)
