import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from google.oauth2 import service_account
import gspread

# --- 策略參數常數 ---
VOL_SURGE_THRESHOLD = 1.2
BIAS_STRONG_PCT     = 5.0
NEAR_MA_RANGE       = 0.05
SHORT_TARGET_MULT   = 1.10
MEDIUM_TARGET_MULT  = 1.15
LONG_TARGET_MULT    = 1.30

# --- 1. 頁面基本設定 ---
st.set_page_config(
    page_title="台股 AI 趨勢雷達",
    page_icon="🚀",
    layout="wide"
)

# --- 2. 靜態保底百大清單 ---
MEGA_STOCKS = [
    ("2330.TW", "台積電"), ("2317.TW", "鴻海"), ("2454.TW", "聯發科"), ("2382.TW", "廣達"), ("2308.TW", "台達電"),
    ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2303.TW", "聯電"), ("3711.TW", "日月光投控"),
    ("2886.TW", "兆豐金"), ("3231.TW", "緯創"), ("2884.TW", "玉山金"), ("2357.TW", "華碩"), ("2892.TW", "第一金"),
    ("5880.TW", "合庫金"), ("2885.TW", "元大金"), ("2880.TW", "華南金"), ("2890.TW", "永豐金"), ("2883.TW", "凱基金"),
    ("2887.TW", "台新金"), ("2801.TW", "彰銀"), ("2834.TW", "臺企銀"), ("2412.TW", "中華電"), ("3045.TW", "台灣大"),
    ("4904.TW", "遠傳"), ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("1216.TW", "統一"),
    ("2002.TW", "中鋼"), ("1303.TW", "南亞"), ("1301.TW", "台塑"), ("1326.TW", "台化"), ("3008.TW", "大立光"),
    ("2327.TW", "國巨"), ("2379.TW", "瑞昱"), ("3034.TW", "聯詠"), ("2376.TW", "技嘉"), ("2356.TW", "英業達"),
    ("6669.TW", "緯穎"), ("3661.TW", "世芯-KY"), ("3443.TW", "創意"), ("2207.TW", "和泰車"), ("2912.TW", "統一超"),
    ("1519.TW", "華城"), ("5871.TW", "中租-KY"), ("2301.TW", "光寶科"), ("3017.TW", "奇鋐"), ("2383.TW", "台光電"),
    ("4953.TWO", "緯軟"), ("3293.TWO", "鈊象"), ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"),
    ("5347.TWO", "世界先進"), ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"), ("3105.TWO", "穩懋"), ("3324.TWO", "雙鴻"),
    ("6274.TWO", "台燿"), ("8069.TWO", "元太"), ("2453.TW", "凌群"), ("1618.TW", "合機"), ("1513.TW", "中興電"),
    ("1503.TW", "士電"), ("1514.TW", "亞力"), ("3583.TW", "辛耘"), ("8210.TW", "勤誠"), ("3533.TW", "嘉澤"),
    ("0050.TW", "元大台灣50"), ("006208.TW", "富邦台50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"),
    ("00919.TW", "群益台灣精選高息"), ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"),
    ("00713.TW", "元大台灣高息低波"), ("00915.TW", "凱基優選高股息30"), ("00679B.TWO", "元大美債20年")
]

LOCAL_NAME_DICT = {n: (c, n) for c, n in MEGA_STOCKS}
LOCAL_DICT = {c.split('.')[0]: (c, n) for c, n in MEGA_STOCKS}

# =====================================================================
# --- Google Sheets 持久化層 ---
# 每個使用者以暱稱為 key，自選股存在 Sheet 的 "watchlist" 分頁。
# 資料格式：每列 = [user_id, ticker, name]
# =====================================================================

@st.cache_resource
def get_gsheet_client():
    """建立並快取 Google Sheets 連線（整個 app 生命週期只連一次）"""
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def get_worksheet():
    """取得工作表，若分頁不存在則自動建立並加上標題列"""
    client = get_gsheet_client()
    sheet = client.open_by_key(st.secrets["gcp_service_account"]["SHEET_ID"])
    try:
        ws = sheet.worksheet("watchlist")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="watchlist", rows=5000, cols=3)
        ws.append_row(["user_id", "ticker", "name"])
    return ws

def load_user_watchlist(user_id: str) -> dict:
    """從 Google Sheets 讀取指定使用者的自選股，回傳 {ticker: name}"""
    try:
        ws = get_worksheet()
        records = ws.get_all_records()
        return {
            row["ticker"]: row["name"]
            for row in records
            if str(row.get("user_id", "")).strip() == user_id
        }
    except Exception as e:
        st.warning(f"⚠️ 讀取雲端自選失敗，改用本地暫存：{e}")
        return {}

def save_stock_to_sheet(user_id: str, ticker: str, name: str):
    """新增一筆自選股到 Google Sheets（先檢查是否重複）"""
    try:
        ws = get_worksheet()
        existing = ws.get_all_records()
        for row in existing:
            if str(row.get("user_id", "")) == user_id and str(row.get("ticker", "")) == ticker:
                return  # 已存在，不重複寫入
        ws.append_row([user_id, ticker, name])
    except Exception as e:
        st.warning(f"⚠️ 儲存至雲端失敗：{e}")

def delete_stock_from_sheet(user_id: str, ticker: str):
    """從 Google Sheets 刪除指定使用者的指定股票"""
    try:
        ws = get_worksheet()
        cell_list = ws.findall(ticker)
        for cell in cell_list:
            row_vals = ws.row_values(cell.row)
            if len(row_vals) >= 1 and row_vals[0] == user_id:
                ws.delete_rows(cell.row)
                break
    except Exception as e:
        st.warning(f"⚠️ 從雲端刪除失敗：{e}")

def delete_all_user_stocks(user_id: str):
    """清空指定使用者的所有自選股"""
    try:
        ws = get_worksheet()
        records = ws.get_all_records()
        # 從最後一列往前刪，避免刪除時 row index 跑掉
        rows_to_delete = [
            i + 2  # +2：第1列是 header（1-indexed），所以資料從第2列開始
            for i, row in enumerate(records)
            if str(row.get("user_id", "")) == user_id
        ]
        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)
    except Exception as e:
        st.warning(f"⚠️ 清空雲端自選失敗：{e}")

# =====================================================================
# --- 使用者身份識別（側邊欄暱稱輸入）---
# user_id 存在 session_state。
# reload 後 session_state 清空，使用者重新輸入暱稱，即可從雲端還原自選。
# =====================================================================

def render_user_login():
    with st.sidebar:
        st.markdown("### 👤 我的帳號")
        st.caption("輸入暱稱來識別你的自選清單。每次 reload 重新輸入暱稱，自選股就會自動還原。")
        uid = st.text_input(
            "暱稱",
            value=st.session_state.get("user_id", ""),
            placeholder="例如：阿明、trader01",
            key="uid_input"
        )
        if st.button("確認暱稱", use_container_width=True):
            if uid.strip():
                st.session_state.user_id = uid.strip()
                # 切換使用者時，重新從雲端載入該使用者的自選
                st.session_state.custom_list = load_user_watchlist(st.session_state.user_id)
                st.rerun()
            else:
                st.error("暱稱不能為空白")

        if st.session_state.get("user_id"):
            st.success(f"✅ 目前：**{st.session_state.user_id}**")
        else:
            st.info("尚未設定暱稱，自選股將不會被儲存。")

    return st.session_state.get("user_id", None)

# --- 3. 動態抓取 0050 成分股 ---
@st.cache_data(ttl=86400)
def fetch_0050_constituents():
    fallback_0050 = MEGA_STOCKS[:50]
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
                if code.isdigit():
                    dynamic_0050.append((f"{code}.TW", name))
            if len(dynamic_0050) >= 40:
                return dynamic_0050
    except Exception as e:
        print(f"[fetch_0050_constituents] 失敗: {e}")
    return fallback_0050

# --- 4. 動態抓取百大熱門股 ---
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

        if not stocks:
            return None
        stocks = sorted(stocks, key=lambda x: x['vol'], reverse=True)[:100]
        return [(s["code"], s["name"]) for s in stocks]
    except Exception as e:
        print(f"[fetch_dynamic_hot_stocks] 失敗: {e}")
        return None

# --- 5. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {c: n for c, n in fetch_0050_constituents() + MEGA_STOCKS[50:]}

if 'custom_list' not in st.session_state:
    st.session_state.custom_list = {}

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

# reload 後如果已有 user_id 但 custom_list 是空的，從雲端重新載入
if st.session_state.user_id and not st.session_state.custom_list:
    st.session_state.custom_list = load_user_watchlist(st.session_state.user_id)

# --- 6. 搜尋系統 ---
def probe_yfinance(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1d")
        if not hist.empty:
            return True
    except Exception as e:
        print(f"[probe_yfinance] {symbol} 失敗: {e}")
    return False

def search_yahoo_api(query):
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
    try:
        r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        data = r.json()
        for res in data.get('data', {}).get('result', []):
            sym = str(res.get('symbol', '')).strip().upper()
            name = str(res.get('name', '')).strip()
            if query in sym or query in name:
                if sym.endswith('.TW') or sym.endswith('.TWO'):
                    return sym, name
                exch = str(res.get('exchange', '')).upper()
                if exch == 'TAI':
                    return f"{sym}.TW", name
                if 'TWO' in exch or 'TPEX' in exch or 'GRE TAI' in exch:
                    return f"{sym}.TWO", name
    except Exception as e:
        print(f"[search_yahoo_api] 查詢 {query} 失敗: {e}")
    return None, None

def scrape_yahoo_name(symbol):
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            match = re.search(r'<title>(.*?)[\(（]', r.text)
            if match and "Yahoo" not in match.group(1):
                return match.group(1).strip()
    except Exception as e:
        print(f"[scrape_yahoo_name] {symbol} 失敗: {e}")
    return None

def validate_and_add(query):
    raw_query = query.strip()  # 保留原始輸入（含中文）
    query = raw_query.upper()  # 大寫版本用於英文/數字比對

    for c, n in st.session_state.custom_list.items():
        if query == c or raw_query == n or query == c.split('.')[0]:
            return c, n, None

    # 先用數字代碼查保底字典
    if query in LOCAL_DICT:
        return LOCAL_DICT[query][0], LOCAL_DICT[query][1], None

    # 再用中文名稱查保底字典（支援輸入「鴻海」、「台積電」等）
    if raw_query in LOCAL_NAME_DICT:
        return LOCAL_NAME_DICT[raw_query][0], LOCAL_NAME_DICT[raw_query][1], None

    s, n = search_yahoo_api(raw_query)
    if s and n:
        if probe_yfinance(s):
            return s, n, None
        alt_s = s.replace('.TW', '.TWO') if '.TW' in s else s.replace('.TWO', '.TW')
        if probe_yfinance(alt_s):
            return alt_s, n, None

    if query.isdigit():
        for ext in [".TW", ".TWO"]:
            target = f"{query}{ext}"
            if probe_yfinance(target):
                name = scrape_yahoo_name(target)
                if name:
                    return target, name, None
                return target, f"{query} (系統抓取)", None

    if probe_yfinance(query):
        return query, query, None

    return None, None, f"在所有市場資料庫中都找不到「{query}」。請確認股票代碼是否正確。"

# --- 7. 大盤技術分析圖 ---
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
                change_pct = ((current - prev_close) / prev_close) * 100
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
        except Exception as e:
            st.error(f"圖表載入失敗: {e}")

# --- 8. 分析與繪圖組件 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = np.where(loss == 0, np.inf, gain / loss)
    return pd.Series(np.where(loss == 0, 100, 100 - (100 / (1 + rs))), index=series.index)

def analyze_logic(cur_p, ma20, ma60, ma120, ma240, vol_ratio, rsi, strategy="short"):
    if ma60 is None:
        return "觀察", "tag-hold", 40, "資料不足", cur_p
    bias_20 = ((cur_p - ma20) / ma20) * 100
    if strategy == "short":
        if cur_p > ma20 and bias_20 > BIAS_STRONG_PCT and vol_ratio > VOL_SURGE_THRESHOLD:
            return "強力推薦", "tag-strong", 90, "站上月線且爆量攻擊", cur_p * SHORT_TARGET_MULT
        return ("買進", "tag-buy", 70, "月線附近震盪", cur_p * SHORT_TARGET_MULT) if cur_p > ma20 else ("觀察", "tag-hold", 50, "月線附近震盪", cur_p * SHORT_TARGET_MULT)
    elif strategy == "medium":
        if ma120 and cur_p > ma120 and ma60 > ma120:
            return "強力推薦", "tag-strong", 95, "中長多格局", cur_p * MEDIUM_TARGET_MULT
        return "回檔佈局", "tag-buy", 80, "季線支撐", ma60
    else:
        if ma240 and abs((cur_p - ma240) / ma240) < NEAR_MA_RANGE:
            return "長線買點", "tag-strong", 95, "年線價值區", ma240 * LONG_TARGET_MULT
        return "長多續抱", "tag-buy", 80, "站穩年線", cur_p * LONG_TARGET_MULT

@st.cache_data(ttl=300)
def fetch_data(tickers: tuple):
    if not tickers:
        return None
    return yf.download(list(tickers), period="2y", group_by='ticker', progress=False)

def process_display(stock_dict, strategy="short"):
    tickers = list(stock_dict.keys())
    if not tickers:
        return []
    data = fetch_data(tuple(sorted(tickers)))
    rows = []
    for t in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if t not in data.columns.get_level_values(0):
                    continue
                df = data[t]
            else:
                df = data

            closes = df['Close'].dropna()
            if len(closes) < 20:
                continue
            cur_p = closes.iloc[-1]
            change = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100
            ma = [closes.rolling(window=m).mean().iloc[-1] for m in [20, 60, 120, 240]]
            rsi = calculate_rsi(closes).iloc[-1]
            vols = df['Volume'].dropna()
            v_ratio = vols.iloc[-1] / vols.rolling(5).mean().iloc[-1] if len(vols) >= 5 else 1.0

            rating, cls, score, reason, target = analyze_logic(cur_p, ma[0], ma[1], ma[2], ma[3], v_ratio, rsi, strategy)
            hist_len = 60 if strategy == "short" else (120 if strategy == "medium" else 240)
            trend_data = closes.iloc[-hist_len:].tolist()

            rows.append({
                "code": t.split('.')[0], "name": stock_dict[t], "price": cur_p, "change": change,
                "target": target, "rating": rating, "cls": cls, "reason": reason,
                "trend": trend_data, "score": score,
                "url": f"https://tw.stock.yahoo.com/quote/{t}"
            })
        except Exception as e:
            print(f"[process_display] 處理 {t} 失敗: {e}")
            continue
    return sorted(rows, key=lambda x: x['score'], reverse=True)

def render_table(rows, date_label):
    html = f"""
    <style>
        table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }}
        th {{ background: #f2f2f2; padding: 10px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #ddd; z-index: 10; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }}
        .up {{ color: #d62728; font-weight: bold; }} .down {{ color: #2ca02c; font-weight: bold; }}
        .tag-strong {{ background: #ffebeb; color: #d62728; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-buy {{ background: #e6ffe6; color: #2ca02c; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-sell {{ background: #f1f3f5; color: #495057; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
        .tag-hold {{ background: #fff; border: 1px solid #eee; color: #868e96; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
    </style>
    <p style="font-family:sans-serif; font-size:12px; color:#888; margin:4px 0 8px;">
        ⚠️ 以下評級與目標價為演算法估算，非投資建議，投資人應自行判斷。
    </p>
    <table>
        <thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>目標價({date_label})</th><th>AI評級</th><th>趨勢</th></tr></thead>
        <tbody>
    """
    for r in rows:
        color = "up" if r['change'] > 0 else "down"
        mn, mx = min(r['trend']), max(r['trend'])
        if mx == mn:
            spark = '<svg width="150" height="40"><line x1="0" y1="20" x2="150" y2="20" stroke="#aaa" stroke-width="2"/></svg>'
        else:
            pts = " ".join([f"{(i / (len(r['trend']) - 1)) * 150},{40 - ((v - mn) / (mx - mn)) * 30 - 5}" for i, v in enumerate(r['trend'])])
            spark = f'<svg width="150" height="40"><polyline points="{pts}" fill="none" stroke="{"#d62728" if r["trend"][-1] > r["trend"][0] else "#2ca02c"}" stroke-width="2"/></svg>'

        html += f"<tr><td><a href='{r['url']}' target='_blank'>{r['code']}</a></td><td>{r['name']}</td><td class='{color}'>{r['price']:.1f}</td><td class='{color}'>{r['change']:.2f}%</td><td>{r['target']:.1f}</td><td><span class='{r['cls']}'>{r['rating']}</span><br><small>{r['reason']}</small></td><td>{spark}</td></tr>"
    return html + "</tbody></table>"

# =====================================================================
# --- 主介面佈局 ---
# =====================================================================

st.title("🚀 台股 AI 趨勢雷達")

# 側邊欄使用者登入（必須在所有其他 UI 之前呼叫）
current_user = render_user_login()

render_taiex_ta_chart()
st.markdown("---")

with st.container():
    col_form, col_btn = st.columns([4, 1])
    with col_form:
        with st.form(key='add_form', clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                query = st.text_input("新增自選股", placeholder="可輸入多筆代號，請用逗號分隔。例如: 2330, 8040, 6789")
            with c2:
                if st.form_submit_button("加入自選") and query:
                    if not current_user:
                        st.error("❌ 請先在左側欄設定暱稱，才能儲存自選股。")
                    else:
                        queries = [q.strip() for q in query.replace('，', ',').split(',') if q.strip()]
                        has_new = False
                        for q in queries:
                            s, n, e = validate_and_add(q)
                            if s:
                                st.session_state.custom_list[s] = n
                                st.session_state.watch_list[s] = n
                                st.session_state.last_added = s
                                save_stock_to_sheet(current_user, s, n)  # 同步寫入雲端
                                has_new = True
                                st.success(f"✅ 已將 {n} 加入自選並儲存至雲端！")
                            else:
                                st.error(f"❌ {q}：{e}")
                        if has_new:
                            st.rerun()

    with col_btn:
        with st.container():
            if st.button("🔄 刷新大盤熱門股", help="更新前三個 Tab 的百大熱門名單", use_container_width=True):
                fetch_dynamic_hot_stocks.clear()
                new_hot = fetch_dynamic_hot_stocks()
                if new_hot:
                    st.session_state.watch_list = {c: n for c, n in new_hot}
                    st.success("✅ 已更新為當下百大熱門股！")
                else:
                    base_system = fetch_0050_constituents() + MEGA_STOCKS[50:]
                    st.session_state.watch_list = {c: n for c, n in base_system}
                    st.warning("⚠️ 網路阻擋，維持現有 0050 與熱門清單。")
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
    rows = process_display(st.session_state.watch_list, "long")
    components.html(render_table(rows, d3), height=600, scrolling=True)

with t4:
    if not current_user:
        st.info("💡 請先在左側欄輸入暱稱，才能使用雲端自選功能。")
    elif not st.session_state.custom_list:
        st.info("💡 目前沒有自選股。請在上方輸入股票代碼（例如 2888, 8040），即可馬上加入！")
    else:
        col_header, col_clear = st.columns([5, 1])
        with col_header:
            st.caption(f"👤 {current_user} 的自選清單｜共 {len(st.session_state.custom_list)} 支")
        with col_clear:
            if st.button("🗑️ 清空自選", help="清空我的自選清單（雲端同步刪除）", use_container_width=True):
                delete_all_user_stocks(current_user)
                st.session_state.custom_list = {}
                st.success("已清空自選清單！")
                st.rerun()

        # 個別刪除按鈕
        with st.expander("✏️ 個別刪除股票", expanded=False):
            cols = st.columns(4)
            for i, (ticker, name) in enumerate(list(st.session_state.custom_list.items())):
                with cols[i % 4]:
                    if st.button(f"✕ {ticker.split('.')[0]} {name}", key=f"del_{ticker}", use_container_width=True):
                        delete_stock_from_sheet(current_user, ticker)
                        del st.session_state.custom_list[ticker]
                        st.rerun()

        rows = process_display(st.session_state.custom_list, "short")
        components.html(render_table(rows, d1), height=600, scrolling=True)













# import streamlit as st
# import streamlit.components.v1 as components
# import pandas as pd
# import yfinance as yf
# import requests
# import re
# import numpy as np
# from datetime import datetime, timedelta
# import plotly.graph_objects as go
# from google.oauth2 import service_account
# import gspread

# # --- 策略參數常數 ---
# VOL_SURGE_THRESHOLD = 1.2
# BIAS_STRONG_PCT     = 5.0
# NEAR_MA_RANGE       = 0.05
# SHORT_TARGET_MULT   = 1.10
# MEDIUM_TARGET_MULT  = 1.15
# LONG_TARGET_MULT    = 1.30

# # --- 1. 頁面基本設定 ---
# st.set_page_config(
#     page_title="台股 AI 趨勢雷達",
#     page_icon="🚀",
#     layout="wide"
# )

# # --- 2. 靜態保底百大清單 ---
# MEGA_STOCKS = [
#     ("2330.TW", "台積電"), ("2317.TW", "鴻海"), ("2454.TW", "聯發科"), ("2382.TW", "廣達"), ("2308.TW", "台達電"),
#     ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2303.TW", "聯電"), ("3711.TW", "日月光投控"),
#     ("2886.TW", "兆豐金"), ("3231.TW", "緯創"), ("2884.TW", "玉山金"), ("2357.TW", "華碩"), ("2892.TW", "第一金"),
#     ("5880.TW", "合庫金"), ("2885.TW", "元大金"), ("2880.TW", "華南金"), ("2890.TW", "永豐金"), ("2883.TW", "凱基金"),
#     ("2887.TW", "台新金"), ("2801.TW", "彰銀"), ("2834.TW", "臺企銀"), ("2412.TW", "中華電"), ("3045.TW", "台灣大"),
#     ("4904.TW", "遠傳"), ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("1216.TW", "統一"),
#     ("2002.TW", "中鋼"), ("1303.TW", "南亞"), ("1301.TW", "台塑"), ("1326.TW", "台化"), ("3008.TW", "大立光"),
#     ("2327.TW", "國巨"), ("2379.TW", "瑞昱"), ("3034.TW", "聯詠"), ("2376.TW", "技嘉"), ("2356.TW", "英業達"),
#     ("6669.TW", "緯穎"), ("3661.TW", "世芯-KY"), ("3443.TW", "創意"), ("2207.TW", "和泰車"), ("2912.TW", "統一超"),
#     ("1519.TW", "華城"), ("5871.TW", "中租-KY"), ("2301.TW", "光寶科"), ("3017.TW", "奇鋐"), ("2383.TW", "台光電"),
#     ("4953.TWO", "緯軟"), ("3293.TWO", "鈊象"), ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"),
#     ("5347.TWO", "世界先進"), ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"), ("3105.TWO", "穩懋"), ("3324.TWO", "雙鴻"),
#     ("6274.TWO", "台燿"), ("8069.TWO", "元太"), ("2453.TW", "凌群"), ("1618.TW", "合機"), ("1513.TW", "中興電"),
#     ("1503.TW", "士電"), ("1514.TW", "亞力"), ("3583.TW", "辛耘"), ("8210.TW", "勤誠"), ("3533.TW", "嘉澤"),
#     ("0050.TW", "元大台灣50"), ("006208.TW", "富邦台50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"),
#     ("00919.TW", "群益台灣精選高息"), ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"),
#     ("00713.TW", "元大台灣高息低波"), ("00915.TW", "凱基優選高股息30"), ("00679B.TWO", "元大美債20年")
# ]

# LOCAL_DICT = {c.split('.')[0]: (c, n) for c, n in MEGA_STOCKS}

# # =====================================================================
# # --- Google Sheets 持久化層 ---
# # 每個使用者以暱稱為 key，自選股存在 Sheet 的 "watchlist" 分頁。
# # 資料格式：每列 = [user_id, ticker, name]
# # =====================================================================

# @st.cache_resource
# def get_gsheet_client():
#     """建立並快取 Google Sheets 連線（整個 app 生命週期只連一次）"""
#     creds = service_account.Credentials.from_service_account_info(
#         st.secrets["gcp_service_account"],
#         scopes=["https://www.googleapis.com/auth/spreadsheets"]
#     )
#     return gspread.authorize(creds)

# def get_worksheet():
#     """取得工作表，若分頁不存在則自動建立並加上標題列"""
#     client = get_gsheet_client()
#     sheet = client.open_by_key(st.secrets["gcp_service_account"]["SHEET_ID"])
#     try:
#         ws = sheet.worksheet("watchlist")
#     except gspread.WorksheetNotFound:
#         ws = sheet.add_worksheet(title="watchlist", rows=5000, cols=3)
#         ws.append_row(["user_id", "ticker", "name"])
#     return ws

# def load_user_watchlist(user_id: str) -> dict:
#     """從 Google Sheets 讀取指定使用者的自選股，回傳 {ticker: name}"""
#     try:
#         ws = get_worksheet()
#         records = ws.get_all_records()
#         return {
#             row["ticker"]: row["name"]
#             for row in records
#             if str(row.get("user_id", "")).strip() == user_id
#         }
#     except Exception as e:
#         st.warning(f"⚠️ 讀取雲端自選失敗，改用本地暫存：{e}")
#         return {}

# def save_stock_to_sheet(user_id: str, ticker: str, name: str):
#     """新增一筆自選股到 Google Sheets（先檢查是否重複）"""
#     try:
#         ws = get_worksheet()
#         existing = ws.get_all_records()
#         for row in existing:
#             if str(row.get("user_id", "")) == user_id and str(row.get("ticker", "")) == ticker:
#                 return  # 已存在，不重複寫入
#         ws.append_row([user_id, ticker, name])
#     except Exception as e:
#         st.warning(f"⚠️ 儲存至雲端失敗：{e}")

# def delete_stock_from_sheet(user_id: str, ticker: str):
#     """從 Google Sheets 刪除指定使用者的指定股票"""
#     try:
#         ws = get_worksheet()
#         cell_list = ws.findall(ticker)
#         for cell in cell_list:
#             row_vals = ws.row_values(cell.row)
#             if len(row_vals) >= 1 and row_vals[0] == user_id:
#                 ws.delete_rows(cell.row)
#                 break
#     except Exception as e:
#         st.warning(f"⚠️ 從雲端刪除失敗：{e}")

# def delete_all_user_stocks(user_id: str):
#     """清空指定使用者的所有自選股"""
#     try:
#         ws = get_worksheet()
#         records = ws.get_all_records()
#         # 從最後一列往前刪，避免刪除時 row index 跑掉
#         rows_to_delete = [
#             i + 2  # +2：第1列是 header（1-indexed），所以資料從第2列開始
#             for i, row in enumerate(records)
#             if str(row.get("user_id", "")) == user_id
#         ]
#         for row_idx in reversed(rows_to_delete):
#             ws.delete_rows(row_idx)
#     except Exception as e:
#         st.warning(f"⚠️ 清空雲端自選失敗：{e}")

# # =====================================================================
# # --- 使用者身份識別（側邊欄暱稱輸入）---
# # user_id 存在 session_state。
# # reload 後 session_state 清空，使用者重新輸入暱稱，即可從雲端還原自選。
# # =====================================================================

# def render_user_login():
#     with st.sidebar:
#         st.markdown("### 👤 我的帳號")
#         st.caption("輸入暱稱來識別你的自選清單。每次 reload 重新輸入暱稱，自選股就會自動還原。")
#         uid = st.text_input(
#             "暱稱",
#             value=st.session_state.get("user_id", ""),
#             placeholder="例如：阿明、trader01",
#             key="uid_input"
#         )
#         if st.button("確認暱稱", use_container_width=True):
#             if uid.strip():
#                 st.session_state.user_id = uid.strip()
#                 # 切換使用者時，重新從雲端載入該使用者的自選
#                 st.session_state.custom_list = load_user_watchlist(st.session_state.user_id)
#                 st.rerun()
#             else:
#                 st.error("暱稱不能為空白")

#         if st.session_state.get("user_id"):
#             st.success(f"✅ 目前：**{st.session_state.user_id}**")
#         else:
#             st.info("尚未設定暱稱，自選股將不會被儲存。")

#     return st.session_state.get("user_id", None)

# # --- 3. 動態抓取 0050 成分股 ---
# @st.cache_data(ttl=86400)
# def fetch_0050_constituents():
#     fallback_0050 = MEGA_STOCKS[:50]
#     try:
#         url = "https://www.yuantaetfs.com/api/StkWeights?date=&fundid=1066"
#         headers = {'User-Agent': 'Mozilla/5.0'}
#         r = requests.get(url, headers=headers, timeout=5)
#         if r.status_code == 200:
#             data = r.json()
#             dynamic_0050 = []
#             for item in data:
#                 code = str(item.get("stkCd", "")).strip()
#                 name = str(item.get("stkNm", "")).strip()
#                 if code.isdigit():
#                     dynamic_0050.append((f"{code}.TW", name))
#             if len(dynamic_0050) >= 40:
#                 return dynamic_0050
#     except Exception as e:
#         print(f"[fetch_0050_constituents] 失敗: {e}")
#     return fallback_0050

# # --- 4. 動態抓取百大熱門股 ---
# @st.cache_data(ttl=1800)
# def fetch_dynamic_hot_stocks():
#     stocks = []
#     try:
#         r_twse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=5)
#         if r_twse.status_code == 200:
#             for item in r_twse.json():
#                 code = str(item.get("Code", ""))
#                 if len(code) == 4 or code.startswith('00'):
#                     vol_str = str(item.get("TradeVolume", "0")).replace(',', '')
#                     if vol_str.isdigit():
#                         stocks.append({"code": f"{code}.TW", "name": str(item.get("Name", "")), "vol": int(vol_str)})

#         r_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=5)
#         if r_tpex.status_code == 200:
#             for item in r_tpex.json():
#                 code = str(item.get("SecuritiesCompanyCode", ""))
#                 if len(code) == 4 or code.startswith('00'):
#                     vol_str = str(item.get("TradingVolume", "0")).replace(',', '')
#                     if vol_str.isdigit():
#                         stocks.append({"code": f"{code}.TWO", "name": str(item.get("CompanyName", "")), "vol": int(vol_str)})

#         if not stocks:
#             return None
#         stocks = sorted(stocks, key=lambda x: x['vol'], reverse=True)[:100]
#         return [(s["code"], s["name"]) for s in stocks]
#     except Exception as e:
#         print(f"[fetch_dynamic_hot_stocks] 失敗: {e}")
#         return None

# # --- 5. 初始化 Session State ---
# if 'watch_list' not in st.session_state:
#     st.session_state.watch_list = {c: n for c, n in fetch_0050_constituents() + MEGA_STOCKS[50:]}

# if 'custom_list' not in st.session_state:
#     st.session_state.custom_list = {}

# if 'last_added' not in st.session_state:
#     st.session_state.last_added = ""

# if 'user_id' not in st.session_state:
#     st.session_state.user_id = ""

# # reload 後如果已有 user_id 但 custom_list 是空的，從雲端重新載入
# if st.session_state.user_id and not st.session_state.custom_list:
#     st.session_state.custom_list = load_user_watchlist(st.session_state.user_id)

# # --- 6. 搜尋系統 ---
# def probe_yfinance(symbol):
#     try:
#         t = yf.Ticker(symbol)
#         hist = t.history(period="1d")
#         if not hist.empty:
#             return True
#     except Exception as e:
#         print(f"[probe_yfinance] {symbol} 失敗: {e}")
#     return False

# def search_yahoo_api(query):
#     url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
#     try:
#         r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
#         data = r.json()
#         for res in data.get('data', {}).get('result', []):
#             sym = str(res.get('symbol', '')).strip().upper()
#             name = str(res.get('name', '')).strip()
#             if query in sym or query in name:
#                 if sym.endswith('.TW') or sym.endswith('.TWO'):
#                     return sym, name
#                 exch = str(res.get('exchange', '')).upper()
#                 if exch == 'TAI':
#                     return f"{sym}.TW", name
#                 if 'TWO' in exch or 'TPEX' in exch or 'GRE TAI' in exch:
#                     return f"{sym}.TWO", name
#     except Exception as e:
#         print(f"[search_yahoo_api] 查詢 {query} 失敗: {e}")
#     return None, None

# def scrape_yahoo_name(symbol):
#     url = f"https://tw.stock.yahoo.com/quote/{symbol}"
#     try:
#         headers = {'User-Agent': 'Mozilla/5.0'}
#         r = requests.get(url, headers=headers, timeout=3)
#         if r.status_code == 200:
#             match = re.search(r'<title>(.*?)[\(（]', r.text)
#             if match and "Yahoo" not in match.group(1):
#                 return match.group(1).strip()
#     except Exception as e:
#         print(f"[scrape_yahoo_name] {symbol} 失敗: {e}")
#     return None

# def validate_and_add(query):
#     query = query.strip().upper()

#     for c, n in st.session_state.custom_list.items():
#         if query == c or query == n or query == c.split('.')[0]:
#             return c, n, None

#     if query in LOCAL_DICT:
#         return LOCAL_DICT[query][0], LOCAL_DICT[query][1], None

#     s, n = search_yahoo_api(query)
#     if s and n:
#         if probe_yfinance(s):
#             return s, n, None
#         alt_s = s.replace('.TW', '.TWO') if '.TW' in s else s.replace('.TWO', '.TW')
#         if probe_yfinance(alt_s):
#             return alt_s, n, None

#     if query.isdigit():
#         for ext in [".TW", ".TWO"]:
#             target = f"{query}{ext}"
#             if probe_yfinance(target):
#                 name = scrape_yahoo_name(target)
#                 if name:
#                     return target, name, None
#                 return target, f"{query} (系統抓取)", None

#     if probe_yfinance(query):
#         return query, query, None

#     return None, None, f"在所有市場資料庫中都找不到「{query}」。請確認股票代碼是否正確。"

# # --- 7. 大盤技術分析圖 ---
# def render_taiex_ta_chart():
#     col_metric, col_controls = st.columns([2, 3])
#     with col_controls:
#         period_opt = st.radio("選擇週期", ["日線", "週線", "月線"], horizontal=True, label_visibility="collapsed")
#     with st.container():
#         try:
#             if period_opt == "日線":
#                 df = yf.download("^TWII", period="2y", interval="1d", progress=False)
#             elif period_opt == "週線":
#                 df = yf.download("^TWII", period="10y", interval="1wk", progress=False)
#             else:
#                 df = yf.download("^TWII", period="20y", interval="1mo", progress=False)

#             if not df.empty:
#                 if isinstance(df.columns, pd.MultiIndex):
#                     df.columns = df.columns.droplevel(1)
#                 mas = [5, 10, 20, 60, 120, 240]
#                 ma_colors = ['#f39c12', '#3498db', '#9b59b6', '#2ecc71', '#e74c3c', '#7f8c8d']
#                 for ma in mas:
#                     df[f'MA{ma}'] = df['Close'].rolling(window=ma).mean()
#                 current = df['Close'].iloc[-1]
#                 prev_close = df['Close'].iloc[-2]
#                 change = current - prev_close
#                 change_pct = ((current - prev_close) / prev_close) * 100
#                 cur_ma = {ma: df[f'MA{ma}'].iloc[-1] for ma in mas}
#                 with col_metric:
#                     st.metric(label=f"台灣加權指數 ({period_opt})", value=f"{current:,.0f}", delta=f"{change:,.0f} ({change_pct:.2f}%)", delta_color="inverse")

#                 ma_html = "".join([f'<span style="color: {ma_colors[i]}; margin-right: 15px;">MA{mas[i]}: {cur_ma[mas[i]]:,.0f}</span>' for i in range(len(mas))])
#                 st.markdown(f'<div style="font-family: sans-serif; font-size: 14px; margin-bottom: 5px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-weight: bold;">{ma_html}</div>', unsafe_allow_html=True)

#                 fig = go.Figure()
#                 fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線', increasing_line_color='#dc3545', increasing_fillcolor='#dc3545', decreasing_line_color='#28a745', decreasing_fillcolor='#28a745'))
#                 for ma, color in zip(mas, ma_colors):
#                     fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], mode='lines', name=f'MA{ma}', line=dict(color=color, width=1.2), hoverinfo='y'))

#                 visible_points = 150
#                 x_min = df.index[-visible_points] if len(df) > visible_points else df.index[0]
#                 fig.update_layout(margin=dict(l=10, r=40, t=10, b=10), height=450, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_rangeslider_visible=False, showlegend=False, xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', range=[x_min, df.index[-1] + timedelta(days=5)], type="date"), yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)', side="right", tickformat=","), hovermode="x unified")
#                 st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
#         except Exception as e:
#             st.error(f"圖表載入失敗: {e}")

# # --- 8. 分析與繪圖組件 ---
# def calculate_rsi(series, period=14):
#     delta = series.diff()
#     gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
#     loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
#     rs = np.where(loss == 0, np.inf, gain / loss)
#     return pd.Series(np.where(loss == 0, 100, 100 - (100 / (1 + rs))), index=series.index)

# def analyze_logic(cur_p, ma20, ma60, ma120, ma240, vol_ratio, rsi, strategy="short"):
#     if ma60 is None:
#         return "觀察", "tag-hold", 40, "資料不足", cur_p
#     bias_20 = ((cur_p - ma20) / ma20) * 100
#     if strategy == "short":
#         if cur_p > ma20 and bias_20 > BIAS_STRONG_PCT and vol_ratio > VOL_SURGE_THRESHOLD:
#             return "強力推薦", "tag-strong", 90, "站上月線且爆量攻擊", cur_p * SHORT_TARGET_MULT
#         return ("買進", "tag-buy", 70, "月線附近震盪", cur_p * SHORT_TARGET_MULT) if cur_p > ma20 else ("觀察", "tag-hold", 50, "月線附近震盪", cur_p * SHORT_TARGET_MULT)
#     elif strategy == "medium":
#         if ma120 and cur_p > ma120 and ma60 > ma120:
#             return "強力推薦", "tag-strong", 95, "中長多格局", cur_p * MEDIUM_TARGET_MULT
#         return "回檔佈局", "tag-buy", 80, "季線支撐", ma60
#     else:
#         if ma240 and abs((cur_p - ma240) / ma240) < NEAR_MA_RANGE:
#             return "長線買點", "tag-strong", 95, "年線價值區", ma240 * LONG_TARGET_MULT
#         return "長多續抱", "tag-buy", 80, "站穩年線", cur_p * LONG_TARGET_MULT

# @st.cache_data(ttl=300)
# def fetch_data(tickers: tuple):
#     if not tickers:
#         return None
#     return yf.download(list(tickers), period="2y", group_by='ticker', progress=False)

# def process_display(stock_dict, strategy="short"):
#     tickers = list(stock_dict.keys())
#     if not tickers:
#         return []
#     data = fetch_data(tuple(sorted(tickers)))
#     rows = []
#     for t in tickers:
#         try:
#             if isinstance(data.columns, pd.MultiIndex):
#                 if t not in data.columns.get_level_values(0):
#                     continue
#                 df = data[t]
#             else:
#                 df = data

#             closes = df['Close'].dropna()
#             if len(closes) < 20:
#                 continue
#             cur_p = closes.iloc[-1]
#             change = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100
#             ma = [closes.rolling(window=m).mean().iloc[-1] for m in [20, 60, 120, 240]]
#             rsi = calculate_rsi(closes).iloc[-1]
#             vols = df['Volume'].dropna()
#             v_ratio = vols.iloc[-1] / vols.rolling(5).mean().iloc[-1] if len(vols) >= 5 else 1.0

#             rating, cls, score, reason, target = analyze_logic(cur_p, ma[0], ma[1], ma[2], ma[3], v_ratio, rsi, strategy)
#             hist_len = 60 if strategy == "short" else (120 if strategy == "medium" else 240)
#             trend_data = closes.iloc[-hist_len:].tolist()

#             rows.append({
#                 "code": t.split('.')[0], "name": stock_dict[t], "price": cur_p, "change": change,
#                 "target": target, "rating": rating, "cls": cls, "reason": reason,
#                 "trend": trend_data, "score": score,
#                 "url": f"https://tw.stock.yahoo.com/quote/{t}"
#             })
#         except Exception as e:
#             print(f"[process_display] 處理 {t} 失敗: {e}")
#             continue
#     return sorted(rows, key=lambda x: x['score'], reverse=True)

# def render_table(rows, date_label):
#     html = f"""
#     <style>
#         table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }}
#         th {{ background: #f2f2f2; padding: 10px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #ddd; z-index: 10; }}
#         td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: middle; }}
#         .up {{ color: #d62728; font-weight: bold; }} .down {{ color: #2ca02c; font-weight: bold; }}
#         .tag-strong {{ background: #ffebeb; color: #d62728; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
#         .tag-buy {{ background: #e6ffe6; color: #2ca02c; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
#         .tag-sell {{ background: #f1f3f5; color: #495057; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
#         .tag-hold {{ background: #fff; border: 1px solid #eee; color: #868e96; padding: 4px 8px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; min-width: 60px;}}
#     </style>
#     <p style="font-family:sans-serif; font-size:12px; color:#888; margin:4px 0 8px;">
#         ⚠️ 以下評級與目標價為演算法估算，非投資建議，投資人應自行判斷。
#     </p>
#     <table>
#         <thead><tr><th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>目標價({date_label})</th><th>AI評級</th><th>趨勢</th></tr></thead>
#         <tbody>
#     """
#     for r in rows:
#         color = "up" if r['change'] > 0 else "down"
#         mn, mx = min(r['trend']), max(r['trend'])
#         if mx == mn:
#             spark = '<svg width="150" height="40"><line x1="0" y1="20" x2="150" y2="20" stroke="#aaa" stroke-width="2"/></svg>'
#         else:
#             pts = " ".join([f"{(i / (len(r['trend']) - 1)) * 150},{40 - ((v - mn) / (mx - mn)) * 30 - 5}" for i, v in enumerate(r['trend'])])
#             spark = f'<svg width="150" height="40"><polyline points="{pts}" fill="none" stroke="{"#d62728" if r["trend"][-1] > r["trend"][0] else "#2ca02c"}" stroke-width="2"/></svg>'

#         html += f"<tr><td><a href='{r['url']}' target='_blank'>{r['code']}</a></td><td>{r['name']}</td><td class='{color}'>{r['price']:.1f}</td><td class='{color}'>{r['change']:.2f}%</td><td>{r['target']:.1f}</td><td><span class='{r['cls']}'>{r['rating']}</span><br><small>{r['reason']}</small></td><td>{spark}</td></tr>"
#     return html + "</tbody></table>"

# # =====================================================================
# # --- 主介面佈局 ---
# # =====================================================================

# st.title("🚀 台股 AI 趨勢雷達")

# # 側邊欄使用者登入（必須在所有其他 UI 之前呼叫）
# current_user = render_user_login()

# render_taiex_ta_chart()
# st.markdown("---")

# with st.container():
#     col_form, col_btn = st.columns([4, 1])
#     with col_form:
#         with st.form(key='add_form', clear_on_submit=True):
#             c1, c2 = st.columns([4, 1])
#             with c1:
#                 query = st.text_input("新增自選股", placeholder="可輸入多筆代號，請用逗號分隔。例如: 2330, 8040, 6789")
#             with c2:
#                 if st.form_submit_button("加入自選") and query:
#                     if not current_user:
#                         st.error("❌ 請先在左側欄設定暱稱，才能儲存自選股。")
#                     else:
#                         queries = [q.strip() for q in query.replace('，', ',').split(',') if q.strip()]
#                         has_new = False
#                         for q in queries:
#                             s, n, e = validate_and_add(q)
#                             if s:
#                                 st.session_state.custom_list[s] = n
#                                 st.session_state.watch_list[s] = n
#                                 st.session_state.last_added = s
#                                 save_stock_to_sheet(current_user, s, n)  # 同步寫入雲端
#                                 has_new = True
#                                 st.success(f"✅ 已將 {n} 加入自選並儲存至雲端！")
#                             else:
#                                 st.error(f"❌ {q}：{e}")
#                         if has_new:
#                             st.rerun()

#     with col_btn:
#         with st.container():
#             if st.button("🔄 刷新大盤熱門股", help="更新前三個 Tab 的百大熱門名單", use_container_width=True):
#                 fetch_dynamic_hot_stocks.clear()
#                 new_hot = fetch_dynamic_hot_stocks()
#                 if new_hot:
#                     st.session_state.watch_list = {c: n for c, n in new_hot}
#                     st.success("✅ 已更新為當下百大熱門股！")
#                 else:
#                     base_system = fetch_0050_constituents() + MEGA_STOCKS[50:]
#                     st.session_state.watch_list = {c: n for c, n in base_system}
#                     st.warning("⚠️ 網路阻擋，維持現有 0050 與熱門清單。")
#                 st.rerun()

# # 分頁顯示
# t1, t2, t3, t4 = st.tabs(["🚀 短線飆股 (系統)", "🌊 中線波段 (系統)", "📅 長線價值 (系統)", "⭐ 我的自選"])

# d1 = (datetime.now() + timedelta(days=30)).strftime("%m/%d")
# d2 = (datetime.now() + timedelta(days=180)).strftime("%m/%d")
# d3 = (datetime.now() + timedelta(days=365)).strftime("%m/%d")

# with t1:
#     rows = process_display(st.session_state.watch_list, "short")
#     components.html(render_table(rows, d1), height=600, scrolling=True)
# with t2:
#     rows = process_display(st.session_state.watch_list, "medium")
#     components.html(render_table(rows, d2), height=600, scrolling=True)
# with t3:
#     rows = process_display(st.session_state.watch_list, "long")
#     components.html(render_table(rows, d3), height=600, scrolling=True)

# with t4:
#     if not current_user:
#         st.info("💡 請先在左側欄輸入暱稱，才能使用雲端自選功能。")
#     elif not st.session_state.custom_list:
#         st.info("💡 目前沒有自選股。請在上方輸入股票代碼（例如 2888, 8040），即可馬上加入！")
#     else:
#         col_header, col_clear = st.columns([5, 1])
#         with col_header:
#             st.caption(f"👤 {current_user} 的自選清單｜共 {len(st.session_state.custom_list)} 支")
#         with col_clear:
#             if st.button("🗑️ 清空自選", help="清空我的自選清單（雲端同步刪除）", use_container_width=True):
#                 delete_all_user_stocks(current_user)
#                 st.session_state.custom_list = {}
#                 st.success("已清空自選清單！")
#                 st.rerun()

#         # 個別刪除按鈕
#         with st.expander("✏️ 個別刪除股票", expanded=False):
#             cols = st.columns(4)
#             for i, (ticker, name) in enumerate(list(st.session_state.custom_list.items())):
#                 with cols[i % 4]:
#                     if st.button(f"✕ {ticker.split('.')[0]} {name}", key=f"del_{ticker}", use_container_width=True):
#                         delete_stock_from_sheet(current_user, ticker)
#                         del st.session_state.custom_list[ticker]
#                         st.rerun()

#         rows = process_display(st.session_state.custom_list, "short")
#         components.html(render_table(rows, d1), height=600, scrolling=True)
























