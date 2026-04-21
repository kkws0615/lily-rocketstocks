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

# --- 2. 動態抓取 0050 成分股 (🌟 本次核心升級) ---
@st.cache_data(ttl=86400) # 快取 24 小時 (ETF成分股不需要每分鐘抓)
def fetch_0050_constituents():
    # 完美備案：若 API 遭阻擋，使用最新一季的 50 大權值股保底
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
        # 嘗試串接投信公開 API 獲取 0050 (fundid=1066) 最新持股
        url = "https://www.yuantaetfs.com/api/StkWeights?date=&fundid=1066"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            dynamic_0050 = []
            for item in data:
                # 投信 API 通常會回傳 stkCd (代號) 與 stkNm (名稱)
                code = str(item.get("stkCd", "")).strip()
                name = str(item.get("stkNm", "")).strip()
                if code and name and code.isdigit():
                    dynamic_0050.append((f"{code}.TW", name))
            
            # 確保有成功抓到足夠數量的成分股 (至少 40 檔以上才算成功)
            if len(dynamic_0050) >= 40:
                return dynamic_0050
    except Exception as e:
        pass # 發生超時或阻擋時，靜默失敗並回傳備用清單
        
    return fallback_0050

# --- 3. 基礎中小型熱門股與 ETF 清單 ---
OTHER_HOT_STOCKS = [
    # 🔥 中小型熱門飆股 (上櫃/中型)
    ("4953.TWO", "緯軟"), ("3293.TWO", "鈊象"), ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), 
    ("5347.TWO", "世界先進"), ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"), ("3105.TWO", "穩懋"), ("3324.TWO", "雙鴻"), 
    ("6274.TWO", "台燿"), ("8069.TWO", "元太"), ("2453.TW", "凌群"), ("1618.TW", "合機"), ("1513.TW", "中興電"),
    ("1503.TW", "士電"), ("1514.TW", "亞力"), ("3583.TW", "辛耘"), ("8210.TW", "勤誠"), ("3533.TW", "嘉澤"),

    # 💰 熱門高股息與市值型 ETF
    ("0050.TW", "元大台灣50"), ("006208.TW", "富邦台50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), 
    ("00919.TW", "群益台灣精選高息"), ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"), 
    ("00713.TW", "元大台灣高息低波"), ("00915.TW", "凱基優選高股息30"), ("00679B.TWO", "元大美債20年"), ("00687B.TW", "國泰20年美債")
]

# 組合：動態 0050 成分股 + 其他熱門股
BASE_STOCKS = fetch_0050_constituents() + OTHER_HOT_STOCKS

# 建立搜尋字典
ALL_STOCKS_MAP = {c: n for c, n in BASE_STOCKS}

# --- 4. 動態抓取政府 API 邏輯 (百大成交量熱門股) ---
@st.cache_data(ttl=1800)
def fetch_dynamic_hot_stocks():
    stocks = []
    try:
        r_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=5)
        if r_twse.status_code == 200:
            for item in r_twse.json():
                code = str(item.get("Code", ""))
                if len(code) == 4 or code.startswith('00'):
                    vol_str = str(item.get("TradeVolume", "0")).replace(',', '')
                    if vol_str.isdigit():
                        stocks.append({"code": f"{code}.TW", "name": str(item.get("Name", "")), "vol": int(vol_str)})

        r_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=5)
        if r_tpex.status_code == 200:
            for item in r_tpex.json():
                code = str(item.get("SecuritiesCompanyCode", ""))
                if len(code) == 4 or code.startswith('00'):
                    vol_str = str(item.get("TradingVolume", "0")).replace(',', '')
                    if vol_str.isdigit():
                        stocks.append({"code": f"{code}.TWO", "name": str(item.get("CompanyName", "")), "vol": int(vol_str)})

        if not stocks: return None
        stocks = sorted(stocks, key=lambda x: x['vol'], reverse=True)[:100]
        return [(s["code"], s["name"]) for s in stocks]
    except:
        return None

# --- 5. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = ALL_STOCKS_MAP.copy()

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# 更新搜尋字典包含使用者自訂項目
ALL_STOCKS_MAP.update(st.session_state.watch_list)
stock_map_code = {code: name for code, name in ALL_STOCKS_MAP.items()}
stock_map_name = {name: code for code, name in ALL_STOCKS_MAP.items()}
stock_map_simple = {code.split('.')[0]: code for code, name in ALL_STOCKS_MAP.items()}

# --- 6. 大盤技術分析圖 ---
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
                x_max = df.index[-1] + x_offset
                
                fig.update_layout(
                    margin=dict(l=10, r=40, t=10, b=10), height=450,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_rangeslider_visible=False, showlegend=False, 
                    xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', range=[x_min, x_max], type="date"),
                    yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', side="right", tickformat=","),
                    hovermode="x unified" 
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 無法取得 Yahoo 報價。")
        except Exception as e:
            st.error(f"大盤圖表載入失敗，請確認網路連線。錯誤: {e}")

# --- 7. 搜尋邏輯 ---
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
    
    current_map = st.session_state.watch_list
    if query in current_map.values():
        for k, v in current_map.items():
            if v == query: return k, v, None
    if f"{query}.TW" in current_map: return f"{query}.TW", current_map[f"{query}.TW"], None
    if f"{query}.TWO" in current_map: return f"{query}.TWO", current_map[f"{query}.TWO"], None
    if query in stock_map_name: return stock_map_name[query], query, None
    if query in stock_map_code: return query, stock_map_code[query], None
    if query in stock_map_simple: return stock_map_simple[query], stock_map_code[stock_map_simple[query]], None
    
    s, n = search_yahoo_api(query)
