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

# --- 2. 動態抓取 0050 成分股 ---
@st.cache_data(ttl=86400)
def fetch_0050_constituents():
    fallback_0050 = [
        ("2330.TW", "台積電"), ("2317.TW", "鴻海"), ("2454.TW", "聯發科"), ("2382.TW", "廣達"), ("2308.TW", "台達電"),
        ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2303.TW", "聯電"), ("3711.TW", "日月光投控"),
        ("2886.TW", "兆豐金"), ("3231.TW", "緯創"), ("2884.TW", "玉山金"), ("2357.TW", "華碩"), ("2892.TW", "第一金"),
        ("5880.TW", "合庫金"), ("2885.TW", "元大金"), ("2880.TW", "華南金"), ("2890.TW", "永豐金"), ("2883.TW", "凱基金"), 
        ("2887.TW", "台新金"), ("2801.TW", "彰銀"), ("2834.TW", "臺企銀"), ("2412.TW", "中華電"), ("3045.TW", "台灣大"), 
        ("4904.TW", "遠傳"), ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("1216.TW", "統一"), 
        ("2002.TW", "中鋼"), ("1303.TW", "南亞"), ("1301.TW", "台塑"), ("1326.TW", "台化"), ("3008.TW", "大立光"), 
        ("2327.TW", "國巨"), ("2379.TW", "瑞昱"), ("3034.TW", "聯詠"), ("2376.TW", "技嘉"), ("2356.TW", "英業達"), 
        ("6669.TW", "緯穎"), ("3661.TW", "世芯-KY"), ("3443.TW", "創意"), ("2207.TW", "和泰車"), ("2912.TW", "統一超"), 
        ("1519.TW", "華城"), ("5871.TW", "中租-KY"), ("2301.TW", "光寶科"), ("3017.TW", "奇鋐"), ("2383.TW", "台光電")
    ]
    try:
        url = "https://www.yuantaetfs.com/api/StkWeights?date=&fundid=1066"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            dynamic_0050 = []
            for item in data:
                code = str(item.get("stkCd", "")).strip()
                name = str(item.get("stkNm", "")).strip()
                if code.isdigit(): dynamic_0050.append((f"{code}.TW", name))
            if len(dynamic_0050) >= 40: return dynamic_0050
    except: pass
    return fallback_0050

# --- 3. 基礎其他熱門股 ---
OTHER_HOT_STOCKS = [
    ("4953.TWO", "緯軟"), ("3293.TWO", "鈊象"), ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), 
    ("0050.TW", "元大台灣50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息")
]

# --- 4. 初始化 Session State ---
# watch_list 放系統推薦的百大股
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {c: n for c, n in (fetch_0050_constituents() + OTHER_HOT_STOCKS)}

# custom_list 專門放使用者手動加入的股票
if 'custom_list' not in st.session_state:
    st.session_state.custom_list = {}

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
                change, change_pct = current - prev_close, ((current - prev_close) / prev_close) * 100
                cur_ma = {ma: df[f'MA{ma}'].iloc[-1] for ma in mas}
                with col_metric:
                    st.metric(label=f"台灣加權指數 ({period_opt})", value=f"{current:,.0f}", delta=f"{change:,.0f} ({change_pct:.2f}%)", delta_color="inverse")
                
                ma_html = "".join([f'<span style="color: {ma_colors[i]}; margin-right: 15px;">MA{mas[i]}: {cur_ma[mas[i]]:,.0f}</span>' for i in range(len(mas))])
                st.markdown(f'<div style="font-family: sans-serif; font-size: 14px; margin-bottom: 5px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-weight: bold;">{ma_html}</div>', unsafe_allow_html=True)
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color='#dc3545', increasing_fillcolor='#dc3545', decreasing_line_color='#28a745', decreasing_fillcolor='#28a745'))
                for ma, color in zip(mas, ma_colors):
                    fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], mode='lines', name=f'MA{ma}', line=dict(color=color, width=1.2), hoverinfo='y'))
                
                visible_points = 150
                x_min = df.index[-visible_points] if len(df) > visible_points else df.index[0]
                fig.update_layout(margin=dict(l=10, r=40, t=10, b=10), height=450, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_rangeslider_visible=False, showlegend=False, xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', range=[x_min, df.index[-1] + timedelta(days=5)], type="date"), yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', side="right", tickformat=","), hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        except Exception as e: st.error(f"圖表載入失敗: {e}")

# --- 6. 搜尋與驗證 ---
def search_yahoo_api(query):
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
    try:
        r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        data = r.json()
        for res in data.get('data', {}).get('result', []):
            if query in res.get('symbol') or query in res.get('name'):
                suffix = ".TW" if res.get('exchange') == 'TAI' else ".TWO"
                return f"{res['symbol']}{suffix}", res['name']
    except: pass
    return None, None

def validate_and_add(query):
    query = query.strip()
    s, n = search_yahoo_api(query)
    if s and n: return s, n, None
    return None, None, f"找不到「{query}」，請檢查名稱或代號。"

# --- 7. 分析與繪圖組件 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    return 100 - (100 / (1 + gain / loss))

def analyze_logic(cur_p, ma20, ma60, ma120, ma240, vol_ratio, rsi, strategy="short"):
    if ma60 is None: return "觀察", "tag-hold", 40, "資料不足", cur_p
    bias_20 = ((cur_p - ma20) / ma20) * 100
    if strategy == "short":
        if cur_p > ma20 and bias_20 > 5 and vol_ratio > 1.2: return "強力推薦", "tag-strong", 90, "站上月線且爆量攻擊", cur_p*1.1
        return "買進" if cur_p > ma20 else "觀察", "tag-buy" if cur_p > ma20 else "tag-hold", 70 if cur_p > ma20 else 50, "月線附近震盪", cur_p*1.05
    elif strategy == "medium":
        if ma120 and cur_p > ma120 and ma60 > ma120: return "強力推薦", "tag-strong", 95, "中長多格局", cur_p*1.15
        return "回檔佈局", "tag-buy", 80, "季線支撐", ma60
    else:
        if ma240 and abs((cur_p - ma240)/ma240) < 0.05: return "長線買點", "tag-strong", 95, "年線價值區", ma240*1.3
        return "長多續抱", "tag-buy", 80, "站穩年線", cur_p*1.1

@st.cache_data(ttl=300)
def fetch_data(tickers):
    if not tickers: return None
    return yf.download(tickers, period="2y", group_by='ticker', progress=False)

def process_display(stock_dict, strategy="short"):
    tickers = list(stock_dict.keys())
    if not tickers: return []
    data = fetch_data(tickers)
    rows = []
    for t in tickers:
        try:
            df = data[t] if len(tickers) > 1 else data
            closes = df['Close'].dropna()
            if len(closes) < 20: continue
            cur_p, change = closes.iloc[-1], ((closes.iloc[-1]-closes.iloc[-2])/closes.iloc[-2])*100
            ma = [closes.rolling(window=m).mean().iloc[-1] for m in [20, 60, 120, 240]]
            rsi = calculate_rsi(closes).iloc[-1]
            vols = df['Volume'].dropna()
            v_ratio = vols.iloc[-1] / vols.rolling(5).mean().iloc[-1] if len(vols) >= 5 else 1.0
            
            rating, cls, score, reason, target = analyze_logic(cur_p, ma[0], ma[1], ma[2], ma[3], v_ratio, rsi, strategy)
            
            # 走勢圖資料
            hist_len = 60 if strategy=="short" else (120 if strategy=="medium" else 240)
            trend_data = closes.iloc[-hist_len:].tolist()
            
            rows.append({"code": t.split('.')[0], "name": stock_dict[t], "price": cur_p, "change": change, "target": target, "rating": rating, "cls": cls, "reason": reason, "trend": trend_data, "score": score, "url": f"https://tw.stock.yahoo.com/quote/{t}"})
        except: continue
    return sorted(rows, key=lambda x: x['score'], reverse=True)

def render_table(rows, date_label):
    html = f"""
    <style>
        table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }}
        th {{ background: #f2f2f2; padding: 10px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #ddd; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }}
        .up {{ color: #d62728; font-weight: bold; }} .down {{ color: #2ca02c; font-weight: bold; }}
        .tag-strong {{ background: #ffebeb; color: #d62728; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .tag-buy {{ background: #e6ffe6; color: #2ca02c; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .tag-hold {{ background: #f8f9fa; color: #666; padding: 4px 8px; border-radius: 4px; }}
    </style>
    <table>
        <thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>目標價({date_label})</th><th>AI評級</th><th>趨勢</th></tr></thead>
        <tbody>
    """
    for r in rows:
        color = "up" if r['change'] > 0 else "down"
        mn, mx = min(r['trend']), max(r['trend'])
        pts = " ".join([f"{(i/(len(r['trend'])-1))*150},{40-((v-mn)/(mx-mn))*30-5}" for i, v in enumerate(r['trend'])])
        spark = f'<svg width="150" height="40"><polyline points="{pts}" fill="none" stroke="{"#d62728" if r["trend"][-1]>r["trend"][0] else "#2ca02c"}" stroke-width="2"/></svg>'
        html += f"<tr><td><a href='{r['url']}' target='_blank'>{r['code']}</a></td><td>{r['name']}</td><td class='{color}'>{r['price']:.1f}</td><td class='{color}'>{r['change']:.2f}%</td><td>{r['target']:.1f}</td><td><span class='{r['cls']}'>{r['rating']}</span><br><small>{r['reason']}</small></td><td>{spark}</td></tr>"
    return html + "</tbody></table>"

# --- 12. 主介面佈局 ---
st.title("🚀 台股 AI 趨勢雷達")
render_taiex_ta_chart()
st.markdown("---")

# 新增監控表單
with st.container():
    col_form, col_btn = st.columns([4, 1])
    with col_form:
        with st.form(key='add_form', clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            with c1: query = st.text_input("新增自選股", placeholder="輸入代號或名稱 (例如: 2330 或 台積電)")
            with c2: 
                if st.form_submit_button("加入自選"):
                    s, n, e = validate_and_add(query)
                    if s:
                        st.session_state.custom_list[s] = n
                        st.success(f"已加入自選：{n}")
                        st.rerun()
                    else: st.error(e)
    with col_btn:
        st.write("") ; st.write("")
        if st.button("🗑️ 清空自選股", use_container_width=True):
            st.session_state.custom_list = {}
            st.rerun()

# 分頁顯示
t1, t2, t3, t4 = st.tabs(["🚀 短線飆股 (系統)", "🌊 中線波段 (系統)", "📅 長線價值 (系統)", "⭐ 我的自選"])

d1 = (datetime.now() + timedelta(days=30)).strftime("%m/%d")
d2 = (datetime.now() + timedelta(days=180)).strftime("%m/%d")
d3 = (datetime.now() + timedelta(days=365)).strftime("%m/%d")

with t1:
    rows = process_display(st.session_state.watch_list, "short")
    components.html(render_table(rows, d1), height=600, scrolling=True)
with t2:
    rows = process_display(st.session_state.watch_list, "medium")
    components.html(render_table(rows, d2), height=600, scrolling=True)
with t3:
    rows = process_display(st.session_state.watch_list, "year")
    components.html(render_table(rows, d3), height=600, scrolling=True)
with t4:
    if not st.session_state.custom_list:
        st.info("目前沒有自選股，請從上方搜尋框加入標的。")
    else:
        # 自選股預設套用短線分析邏輯
        rows = process_display(st.session_state.custom_list, "short")
        components.html(render_table(rows, d1), height=600, scrolling=True)
