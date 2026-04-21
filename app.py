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

# --- 2. 備用清單 (當政府 API 斷線時的保命符) ---
FALLBACK_STOCKS = [
    ("2330.TW", "台積電"), ("2317.TW", "鴻海"), ("2454.TW", "聯發科"), ("2382.TW", "廣達"),
    ("3231.TW", "緯創"), ("2603.TW", "長榮"), ("1519.TW", "華城"), ("0050.TW", "元大台灣50")
]

# --- 3. 🌟 核心升級：串接證交所與櫃買中心 Open API 自動抓取真實熱門股 ---
@st.cache_data(ttl=3600) # 快取 1 小時，避免頻繁呼叫被鎖 IP
def fetch_dynamic_hot_stocks():
    stocks = []
    try:
        # 1. 抓取上市 (TWSE) 所有股票資訊
        r_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=5)
        if r_twse.status_code == 200:
            for item in r_twse.json():
                code = str(item.get("Code", ""))
                name = str(item.get("Name", ""))
                # 清理成交量字串並轉為整數
                vol_str = str(item.get("TradeVolume", "0")).replace(',', '')
                vol = int(vol_str) if vol_str.isdigit() else 0
                
                # 過濾掉奇怪的權證，保留一般股票(4碼)與ETF(00開頭)
                if len(code) == 4 or code.startswith('00'):
                    stocks.append({"code": f"{code}.TW", "name": name, "vol": vol})

        # 2. 抓取上櫃 (TPEx) 所有股票資訊
        r_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=5)
        if r_tpex.status_code == 200:
            for item in r_tpex.json():
                code = str(item.get("SecuritiesCompanyCode", ""))
                name = str(item.get("CompanyName", ""))
                vol_str = str(item.get("TradingVolume", "0")).replace(',', '')
                vol = int(vol_str) if vol_str.isdigit() else 0
                
                if len(code) == 4 or code.startswith('00'):
                    stocks.append({"code": f"{code}.TWO", "name": name, "vol": vol})

        # 如果 API 異常沒抓到資料，回傳備用清單
        if not stocks: 
            return FALLBACK_STOCKS
        
        # 3. 根據成交量 (vol) 由大到小排序，並精準攔截前 100 名！
        stocks = sorted(stocks, key=lambda x: x['vol'], reverse=True)[:100]
        return [(s["code"], s["name"]) for s in stocks]
        
    except Exception as e:
        return FALLBACK_STOCKS

# 取得當下最熱門的百大清單
HOT_STOCKS = fetch_dynamic_hot_stocks()

# 建立搜尋字典 (結合動態熱門股，確保搜尋驗證不會出錯)
stock_map_code = {code: name for code, name in HOT_STOCKS}
stock_map_name = {name: code for code, name in HOT_STOCKS}
stock_map_simple = {code.split('.')[0]: code for code, name in HOT_STOCKS}

# --- 4. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in HOT_STOCKS}

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# --- 5. 大盤技術分析圖 ---
def render_taiex_ta_chart():
    col_metric, col_controls = st.columns([2, 3])
    with col_controls:
        period_opt = st.radio("選擇週期", ["日線", "週線", "月線"], horizontal=True, label_visibility="collapsed")
    
    with st.container():
        try:
            if period_opt == "日線": df = yf.download("^TWII", period="2y", interval="1d", progress=False)
            elif period_opt == "週線": df = yf.download("^TWII", period="10y", interval="1wk", progress=False)
            else: df = yf.download("^TWII", period="20y", interval="1mo", progress=False)
            
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
                
                mas = [5, 10, 20, 60, 120, 240]
                ma_colors = ['#f39c12', '#3498db', '#9b59b6', '#2ecc71', '#e74c3c', '#7f8c8d']
                
                for ma in mas: df[f'MA{ma}'] = df['Close'].rolling(window=ma).mean()
                
                current, prev_close = df['Close'].iloc[-1], df['Close'].iloc[-2]
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
                    x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                    name='K線', increasing_line_color='#dc3545', increasing_fillcolor='#dc3545', 
                    decreasing_line_color='#28a745', decreasing_fillcolor='#28a745'  
                ))
                
                for ma, color in zip(mas, ma_colors):
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df[f'MA{ma}'], mode='lines', name=f'MA{ma}',
                        line=dict(color=color, width=1.2), hoverinfo='y' 
                    ))
                
                visible_points = 150 
                x_min = df.index[-visible_points] if len(df) > visible_points else df.index[0]
                
                if period_opt == "日線": x_offset = timedelta(days=5)
                elif period_opt == "週線": x_offset = timedelta(days=21)
                else: x_offset = timedelta(days=90)
                
                fig.update_layout(
                    margin=dict(l=10, r=40, t=10, b=10), height=450,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_rangeslider_visible=False, showlegend=False, 
                    xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', range=[x_min, df.index[-1] + x_offset], type="date"),
                    yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', side="right", tickformat=","),
                    hovermode="x unified" 
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else: st.warning("⚠️ 無法取得 Yahoo 報價。")
        except Exception as e: st.error(f"大盤圖表載入失敗。錯誤: {e}")

# --- 6. 搜尋邏輯 ---
def search_yahoo_api(query):
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
    try:
        r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        data = r.json()
        for res in data.get('data', {}).get('result', []):
            if query in res.get('symbol') or query in res.get('name'):
                if res.get('exchange') == 'TAI': return f"{res['symbol']}.TW", res['name']
                if res.get('exchange') == 'TWO': return f"{res['symbol']}.TWO", res['name']
    except: pass
    return None, None

def validate_and_add(query):
    query = query.strip()
    if query in stock_map_name: return stock_map_name[query], query, None
    if query in stock_map_code: return query, stock_map_code[query], None
    if query in stock_map_simple: return stock_map_simple[query], stock_map_code[stock_map_simple[query]], None
    
    s, n = search_yahoo_api(query)
    if s and n: return s, n, None
    return None, None, f"找不到「{query}」，請確認代號。"

# --- 7. 技術指標與策略 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    return 100 - (100 / (1 + gain / loss))

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
    return "觀察", "tag-hold", 50, "<br>".join(reasons), 2, current_price * 1.02

def analyze_medium_term(current_price, ma60, ma120):
    if ma120 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足半年", 0, current_price
    if current_price > ma120 and ma60 > ma120:
        bias_60 = ((current_price - ma60) / ma60) * 100
        if bias_60 < 10: return "強力推薦", "tag-strong", 95, "💎 中長多格局，位階適中。", 4, current_price * 1.15
        return "續抱", "tag-buy", 80, "📈 多頭排列中。", 3, current_price * 1.05
    elif current_price > ma120 and current_price < ma60:
        return "回檔佈局", "tag-buy", 85, "💰 回測半年線支撐。", 3.5, ma60
    return "觀察", "tag-hold", 50, "目前橫盤整理中。", 2, current_price

def analyze_year_term(current_price, ma240, rsi):
    if ma240 is None: return "資料不足", "tag-hold", 0, "⚠️ 資料不足一年", 0, current_price
    bias_240 = ((current_price - ma240) / ma240) * 100
    if -5 < bias_240 < 10 and rsi > 45: return "長線買點", "tag-strong", 95, "💎 回測年線不破，價值浮現。", 4, ma240 * 1.3
    if bias_240 > 30: return "風險過高", "tag-sell", 40, "⚠️ 乖離年線過大，小心修正。", 2, current_price * 0.9
    return "長多續抱", "tag-buy", 80, "📈 趨勢穩健向上。", 3, current_price * 1.1

# --- 8. 資料處理 ---
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

# --- 9. 視覺化 HTML ---
def make_sparkline(data):
    if not data: return ""
    w, h, mn, mx = 180, 50, min(data), max(data)
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

# --- 【重點新增】：新增按鈕與表單排版 ---
with st.container():
    col_form, col_btn = st.columns([4, 1]) # 表單佔 4 份寬，按鈕佔 1 份
    
    with col_form:
        with st.form(key='add', clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            with c1: query = st.text_input("新增監控", placeholder="輸入代號或名稱 (例如: 2330, 緯軟)")
            with c2: 
                if st.form_submit_button("加入自選") and query:
                    s, n, e = validate_and_add(query)
                    if s: 
                        st.session_state.watch_list[s] = n
                        st.session_state.last_added = s
                        st.rerun()
                    else: st.error(e)
                    
    with col_btn:
        st.write("") # 為了與左邊對齊
        st.write("")
        # 點擊此按鈕，強制清除快取並重新抓取證交所最新資料
        if st.button("🔄 刷新百大熱門股", help="自動向證交所抓取當下成交量前100大股票", use_container_width=True):
            fetch_dynamic_hot_stocks.clear() # 清空 API 快取
            fetch_stock_data_wrapper.clear() # 清空 Yahoo 報價快取
            
            # 重新取得最新熱門股並覆蓋現有清單
            new_hot_list = fetch_dynamic_hot_stocks()
            st.session_state.watch_list = {code: name for code, name in new_hot_list}
            st.success("已成功更新至最新百大熱門股！")
            st.rerun()

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
