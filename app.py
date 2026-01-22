import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import requests
import re

st.set_page_config(page_title="台股AI標股神探 (終極修正版)", layout="wide")

# --- 1. 內建百大熱門股 (字典資料庫) ---
INIT_STOCKS = [
    # === 半導體與 AI (上市 .TW) ===
    ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2317.TW", "鴻海"), ("2303.TW", "聯電"), ("3711.TW", "日月光投控"),
    ("2308.TW", "台達電"), ("2382.TW", "廣達"), ("3231.TW", "緯創"), ("2357.TW", "華碩"), ("6669.TW", "緯穎"),
    ("2379.TW", "瑞昱"), ("3034.TW", "聯詠"), ("3035.TW", "智原"), ("3443.TW", "創意"), ("3661.TW", "世芯-KY"),
    ("3008.TW", "大立光"), ("2408.TW", "南亞科"), ("2376.TW", "技嘉"), ("2356.TW", "英業達"), ("2324.TW", "仁寶"),
    ("3017.TW", "奇鋐"), ("2301.TW", "光寶科"), ("2368.TW", "金像電"), ("3037.TW", "欣興"), ("3044.TW", "健鼎"),
    ("2313.TW", "華通"), ("2383.TW", "台光電"), ("2449.TW", "京元電子"),

    # === 半導體與 AI (上櫃 .TWO) ===
    ("5274.TWO", "信驊"), ("3529.TWO", "力旺"), ("8299.TWO", "群聯"), ("5347.TWO", "世界先進"),
    ("3293.TWO", "鈊象"), ("8069.TWO", "元太"), ("6147.TWO", "頎邦"), ("3105.TWO", "穩懋"),
    ("6488.TWO", "環球晶"), ("5483.TWO", "中美晶"), ("4966.TWO", "譜瑞-KY"), ("6223.TWO", "旺矽"),
    ("3324.TWO", "雙鴻"), ("6274.TWO", "台燿"), ("3260.TWO", "威剛"), ("6271.TWO", "凌群"),

    # === 金融股 (上市) ===
    ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("2891.TW", "中信金"), ("2886.TW", "兆豐金"), ("2884.TW", "玉山金"),
    ("2885.TW", "元大金"), ("2892.TW", "第一金"), ("2880.TW", "華南金"), ("2883.TW", "凱基金"), ("2890.TW", "永豐金"),
    ("5880.TW", "合庫金"), ("2887.TW", "台新新光金"),
    ("2834.TW", "臺企銀"), ("2801.TW", "彰銀"), ("5876.TW", "上海商銀"), ("2812.TW", "台中銀"), ("5871.TW", "中租-KY"),

    # === 傳產龍頭 (上市) ===
    ("1301.TW", "台塑"), ("1303.TW", "南亞"), ("1326.TW", "台化"), ("6505.TW", "台塑化"), ("1101.TW", "台泥"),
    ("1102.TW", "亞泥"), ("2002.TW", "中鋼"), ("2027.TW", "大成鋼"), ("1605.TW", "華新"), ("1402.TW", "遠東新"),
    ("1216.TW", "統一"), ("2912.TW", "統一超"), ("2207.TW", "和泰車"), ("9904.TW", "寶成"), ("9910.TW", "豐泰"),
    ("1313.TW", "聯成"), ("1218.TW", "泰山"),

    # === 航運與重電 (上市) ===
    ("2603.TW", "長榮"), ("2609.TW", "陽明"), ("2615.TW", "萬海"), ("2618.TW", "長榮航"), ("2610.TW", "華航"),
    ("2634.TW", "漢翔"), ("1513.TW", "中興電"), ("1519.TW", "華城"), ("1503.TW", "士電"), ("1504.TW", "東元"),
    ("1514.TW", "亞力"), ("1609.TW", "大亞"), ("1616.TW", "億泰"), ("6282.TW", "康舒"),

    # === 電信與面板 (上市) ===
    ("2412.TW", "中華電"), ("3045.TW", "台灣大"), ("4904.TW", "遠傳"), ("2409.TW", "友達"), ("3481.TW", "群創"),

    # === 熱門 ETF (上市) ===
    ("0050.TW", "元大台灣50"), ("0056.TW", "元大高股息"), ("00878.TW", "國泰永續高股息"), ("00919.TW", "群益台灣精選高息"),
    ("00929.TW", "復華台灣科技優息"), ("00940.TW", "元大台灣價值高息"), ("006208.TW", "富邦台50"), ("00713.TW", "元大高息低波"),
    ("00632R.TW", "元大台灣50反1"), 
    
    # === 債券 ETF (上櫃 .TWO) ===
    ("00679B.TWO", "元大美債20年"), ("00687B.TWO", "國泰20年美債"), ("00937B.TWO", "群益ESG投等債20+")
]

# 建立快速查詢字典
tw_stock_dict = {name: code for code, name in INIT_STOCKS}
for code, name in INIT_STOCKS:
    simple_code = code.split('.')[0]
    tw_stock_dict[simple_code] = code 

# --- 0. 初始化 Session State ---
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {code: name for code, name in INIT_STOCKS}

if 'last_added' not in st.session_state:
    st.session_state.last_added = ""

# 產業分類
ticker_sector_map = {"2330": "Semi", "2603": "Ship", "2618": "Trans"} 
sector_trends = {
    "Semi": {"bull": "AI 晶片需求強勁。", "bear": "消費電子復甦慢。"},
    "Ship": {"bull": "紅海危機推升運價。", "bear": "新船運力投放過剩。"},
    "Trans": {"bull": "客運復甦票價高檔。", "bear": "燃油成本上升。"},
    "Default": {"bull": "資金輪動健康，法人進駐。", "bear": "產業前景不明，面臨修正。"}
}

# --- 2. 搜尋與驗證邏輯 (三重保險機制) ---

# A. 網頁爬蟲 (最後手段：抓取 Yahoo 網頁標題)
def scrape_yahoo_title(symbol):
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            match = re.search(r'<title>(.*?)\(', r.text)
            if match:
                return match.group(1).strip()
    except: pass
    return None

# B. Yahoo API 搜尋
def search_yahoo_and_get_name(query):
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"
    try:
        r = requests.get(url, params={"query": query, "limit": 5}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        data = r.json()
        results = data.get('data', {}).get('result', [])
        for res in results:
            if (res.get('name') == query or res.get('symbol') == query) and res.get('exchange') in ['TAI', 'TWO']:
                suffix = ".TW" if res['exchange'] == 'TAI' else ".TWO"
                return f"{res['symbol']}{suffix}", res['name']
        for res in results:
            if res.get('exchange') in ['TAI', 'TWO']:
                suffix = ".TW" if res['exchange'] == 'TAI' else ".TWO"
                return f"{res['symbol']}{suffix}", res['name']
    except Exception as e: pass
    return None, None

# C. 主驗證入口
def validate_and_add(query):
    query = query.strip()
    
    # === 第一道防線：內建字典 (最快、最準) ===
    # 這行保證 6271 直接命中，不會去問不穩定的 API
    if query in tw_stock_dict:
        full_code = tw_stock_dict[query]
        # 取得正確名稱
        name = query if not query.replace('.','').isdigit() else st.session_state.watch_list.get(full_code, "未知")
        # 再次確認 session_state 裡有沒有這個名字，沒有的話從 INIT_STOCKS 找
        if name == "未知":
             for c, n in INIT_STOCKS:
                 if c == full_code: name = n
        return full_code, name, None

    # 反向查找 (Input: 6271 -> 6271.TWO)
    for name, code in tw_stock_dict.items():
        if query == code.split('.')[0]: return code, name, None

    # === 第二道防線：Yahoo API ===
    symbol, real_name = search_yahoo_and_get_name(query)
    if symbol and real_name:
        return symbol, real_name, None
    
    # === 第三道防線：爬蟲 (針對 API 失效但輸入正確代號的情況) ===
    if query.isdigit():
        # 試試看上市
        name = scrape_yahoo_title(f"{query}.TW")
        if name: return f"{query}.TW", name, None
        # 試試看上櫃
        name = scrape_yahoo_title(f"{query}.TWO")
        if name: return f"{query}.TWO", name, None
        
        # 真的沒辦法才顯示自選股 (但至少代號是對的)
        # 這裡可以再擋一次，避免亂碼
        # return f"{query}.TW", f"自選股-{query}", None 

    return None, None, f"Yahoo 找不到「{query}」，請確認名稱或代號。"

# --- 3. 分析邏輯 ---
def analyze_stock_strategy(ticker_code, current_price, ma20, ma60):
    rating, color_class, predict_score = "觀察", "tag-hold", 50
    sort_order = 2 
    sector_key = ticker_sector_map.get(ticker_code, "Default")
    
    if current_price is None: return "N/A", "tag-sell", 0, "無報價", 0

    if ma60 is None:
        if ma20 and current_price > ma20: 
            return "短多", "tag-buy", 60, f"🚀 <b>短線：</b>站上月線({ma20:.1f})，動能強。", 3
        else: 
            return "觀察", "tag-hold", 40, "👀 <b>整理：</b>資料不足或盤整中。", 2

    bias_20 = ((current_price - ma20) / ma20) * 100
    
    if current_price > ma20 and current_price > ma60 and bias_20 > 5:
        rating, color_class, predict_score, sort_order = "強力推薦", "tag-strong", 90, 4
        trend = sector_trends.get(sector_key, sector_trends["Default"])["bull"]
        reason = f"🔥 <b>技術：</b>站穩月季線，乖離 {bias_20:.1f}%。<br>🌍 <b>產業：</b>{trend}"
    elif current_price > ma20 and bias_20 > 0:
        rating, color_class, predict_score, sort_order = "買進", "tag-buy", 70, 3
        trend = sector_trends.get(sector_key, sector_trends["Default"])["bull"]
        reason = f"📈 <b>技術：</b>站上月線({ma20:.1f})，轉強。<br>🌍 <b>產業：</b>{trend}"
    elif current_price < ma20 and current_price < ma60:
        rating, color_class, predict_score, sort_order = "避開", "tag-sell", 10, 1
        trend = sector_trends.get(sector_key, sector_trends["Default"])["bear"]
        reason = f"⚠️ <b>技術：</b>跌破月季線，壓力大。<br>🌍 <b>產業：</b>{trend}"
    elif current_price < ma20:
        rating, color_class, predict_score, sort_order = "賣出", "tag-sell", 30, 1
        trend = sector_trends.get(sector_key, sector_trends["Default"])["bear"]
        reason = f"📉 <b>技術：</b>跌破月線({ma20:.1f})。<br>🌍 <b>產業：</b>{trend}"
    else:
        reason = "👀 <b>技術：</b>月線附近震盪。<br>🌍 <b>產業：</b>方向未明。"
        
    return rating, color_class, predict_score, reason, sort_order

# --- 4. 資料處理 ---
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
    
    for ticker in tickers:
        clean_code = ticker.replace(".TW", "").replace(".TWO", "")
        stock_name = current_map.get(ticker, ticker)
        
        try:
            if len(tickers) == 1: df_stock = data_download
            else: df_stock = data_download[ticker] if data_download is not None else pd.DataFrame()
            
            closes = df_stock['Close'] if not df_stock.empty else pd.Series()
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            closes_list = closes.dropna().tolist()
            
            if len(closes_list) < 1:
                is_new = (ticker == st.session_state.last_added)
                sort_key = 9999 if is_new else 0
                rows.append({
                    "code": clean_code, "name": stock_name,
                    "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                    "price": 0, "change": 0, "score": sort_key, "sort_order": 0,
                    "ma20_disp": "-", "rating": "資料N/A", "rating_class": "tag-sell",
                    "reason": "⚠️ API 暫無數據。", "trend": []
                })
                continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2] if len(closes_list) > 1 else current_price
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            ma20 = sum(closes_list[-20:]) / 20 if len(closes_list) >= 20 else None
            ma60 = sum(closes_list[-60:]) / 60 if len(closes_list) >= 60 else None
            
            rating, color_class, score, reason, sort_order = analyze_stock_strategy(clean_code, current_price, ma20, ma60)
            
            is_new = (ticker == st.session_state.last_added)
            final_sort_key = 9999 if is_new else score 
            ma20_disp = f"{ma20:.1f}" if ma20 else "-"
            safe_reason = reason.replace("'", "&#39;")

            rows.append({
                "code": clean_code, "name": stock_name,
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price, "change": change_pct, 
                "score": final_sort_key, "sort_order": sort_order,
                "ma20_disp": ma20_disp, "rating": rating, "rating_class": color_class,
                "reason": safe_reason, 
                "trend": closes_list[-30:]
            })
        except Exception as e:
            rows.append({
                "code": clean_code, "name": stock_name,
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": 0, "change": 0, "score": 0, "sort_order": 0,
                "ma20_disp": "-", "rating": "讀取錯誤", "rating_class": "tag-sell",
                "reason": f"錯誤: {str(e)}", "trend": []
            })
            continue
    
    return sorted(rows, key=lambda x: x['score'], reverse=True)

# --- 5. 畫圖與介面 ---
def make_sparkline(data):
    if not data or len(data) < 2: return '<span style="color:#ccc;font-size:12px">無走勢圖</span>'
    w, h = 100, 30
    min_v, max_v = min(data), max(data)
    if max_v == min_v: return ""
    
    pts = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * w
        y = h - ((val - min_v) / (max_v - min_v)) * (h - 4) - 2
        pts.append(f"{x},{y}")
    c = "#dc3545" if data[-1] > data[0] else "#28a745"
    
    last_pt = pts[-1]
    last_x, last_y = last_pt.split(",")
    
    return f'<svg width="{w}" height="{h}" style="overflow:visible"><polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="2"/><circle cx="{last_x}" cy="{last_y}" r="3" fill="{c}"/></svg>'

st.title("🚀 台股 AI 飆股神探")
with st.container():
    col_add, col_info = st.columns([2, 3])
    with col_add:
        with st.form(key='add_stock_form', clear_on_submit=True):
            col_in, col_btn = st.columns([3, 1])
            with col_in: query = st.text_input("新增監控", placeholder="輸入：6271 或 凌群")
            with col_btn: submitted = st.form_submit_button("新增")
            
            if submitted and query:
                # 呼叫三重驗證功能
                symbol, name, err = validate_and_add(query)
                
                if symbol:
                    if symbol in st.session_state.watch_list:
                        st.warning(f"「{name}」已在清單中")
                    else:
                        st.session_state.watch_list[symbol] = name
                        st.session_state.last_added = symbol
                        st.success(f"✅ 成功加入：{name} ({symbol})")
                        st.rerun()
                else:
                    st.error(f"❌ {err}")

    with col_info:
        st.info("💡 **完美搜尋**：內建 100+ 熱門股字典，並支援 Yahoo API 自動抓名與網頁爬蟲補位。6271 凌群可正確顯示！")
        filter_strong = st.checkbox("🔥 只看強力推薦", value=False)

data_rows = process_stock_data()
if filter_strong: data_rows = [d for d in data_rows if d['rating'] == "強力推薦"]

# --- 6. HTML/JS 渲染 ---
html_content = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: "Microsoft JhengHei", sans-serif; margin: 0; padding-bottom: 50px; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 15px; }
    
    th { 
        background-color: #f2f2f2; padding: 12px; text-align: left; 
        position: sticky; top: 0; z-index: 10000; border-bottom: 2px solid #ddd; 
        cursor: pointer; user-select: none; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.1);
    }
    th:hover { background: #e6e6e6; }
    td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
    tr { position: relative; }
    tr:hover { background: #f8f9fa; } 
    
    .up { color: #d62728; font-weight: bold; }
    .down { color: #2ca02c; font-weight: bold; }
    a { text-decoration: none; color: #0066cc; font-weight: bold; background: #f0f7ff; padding: 2px 6px; border-radius: 4px; }
    
    #floating-tooltip {
        position: fixed; display: none; width: 300px; background-color: #2c3e50; color: #fff; 
        text-align: left; border-radius: 8px; padding: 15px; z-index: 99999; 
        font-size: 14px; line-height: 1.6; box-shadow: 0 5px 15px rgba(0,0,0,0.5); pointer-events: none;
    }
    
    .rating-cell { cursor: help; }
    .tag-strong { color: #d62728; background: #ffebeb; padding: 4px 8px; border-radius: 4px; border: 1px solid #ffcccc; display: inline-block; font-weight: bold;}
    .tag-buy { color: #2ca02c; background: #e6ffe6; padding: 4px 8px; border-radius: 4px; border: 1px solid #ccffcc; display: inline-block; font-weight: bold;}
    .tag-sell { color: #495057; background: #f1f3f5; padding: 4px 8px; border-radius: 4px; border: 1px solid #dee2e6; display: inline-block; font-weight: bold;}
    .tag-hold { color: #868e96; background: #fff; padding: 4px 8px; border-radius: 4px; border: 1px solid #eee; display: inline-block; font-weight: bold;}
    
    .sub-text { font-size: 12px; color: #888; margin-left: 5px; font-weight: normal; }
    .header-sub { font-size: 12px; font-weight: normal; color: #666; margin-left: 4px; }
</style>

<script>
function sortTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("stockTable");
  switching = true;
  dir = "desc"; 
  while (switching) {
    switching = false;
    rows = table.rows;
    for (i = 1; i < (rows.length - 1); i++) {
      shouldSwitch = false;
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i + 1].getElementsByTagName("TD")[n];
      var xVal = x.getAttribute("data-value") || (x.textContent || x.innerText);
      var yVal = y.getAttribute("data-value") || (y.textContent || y.innerText);
      var xNum = parseFloat(xVal.replace(/[^0-9.-]/g, ''));
      var yNum = parseFloat(yVal.replace(/[^0-9.-]/g, ''));

      if (dir == "asc") {
        if (!isNaN(xNum) && !isNaN(yNum)) { if (xNum > yNum) { shouldSwitch = true; break; } } 
        else { if (xVal.toLowerCase() > yVal.toLowerCase()) { shouldSwitch = true; break; } }
      } else if (dir == "desc") {
        if (!isNaN(xNum) && !isNaN(yNum)) { if (xNum < yNum) { shouldSwitch = true; break; } } 
        else { if (xVal.toLowerCase() < yVal.toLowerCase()) { shouldSwitch = true; break; } }
      }
    }
    if (shouldSwitch) {
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      switchcount ++;      
    } else {
      if (switchcount == 0 && dir == "desc") { dir = "asc"; switching = true; }
    }
  }
}

function showTooltip(e, content) {
    var tt = document.getElementById('floating-tooltip');
    tt.innerHTML = content;
    tt.style.display = 'block';
    moveTooltip(e);
}

function hideTooltip() {
    var tt = document.getElementById('floating-tooltip');
    tt.style.display = 'none';
}

function moveTooltip(e) {
    var tt = document.getElementById('floating-tooltip');
    var x = e.clientX + 15;
    var y = e.clientY + 15;
    if (x + 320 > window.innerWidth) { x = e.clientX - 315; }
    if (y + 100 > window.innerHeight) { y = e.clientY - 100; }
    tt.style.left = x + 'px';
    tt.style.top = y + 'px';
}
</script>
</head>
<body>

<div id="floating-tooltip"></div>

<table id="stockTable">
    <thead>
        <tr>
            <th onclick="sortTable(0)">代號 ⬍</th>
            <th onclick="sortTable(1)">股名 ⬍</th>
            <th onclick="sortTable(2)">現價 <span class="header-sub">(月線)</span> ⬍</th>
            <th onclick="sortTable(3)">漲跌 ⬍</th>
            <th onclick="sortTable(4)">AI 評級 ⬍</th>
            <th>近三月走勢</th>
        </tr>
    </thead>
    <tbody>
"""

for row in data_rows:
    p_cls = "up" if row['change'] > 0 else "down"
    
    if row['rating'] == "資料N/A" or row['rating'] == "讀取錯誤":
        price_display = "N/A"
        change_display = "-"
    else:
        price_display = f"{row['price']:.1f} <span class='sub-text'>({row['ma20_disp']})</span>"
        change_display = f"{row['change']:.2f}%"

    tooltip_events = f"onmouseover=\"showTooltip(event, '{row['reason']}')\" onmousemove=\"moveTooltip(event)\" onmouseout=\"hideTooltip()\""
    
    html_content += f"""
        <tr>
            <td data-value="{row['code']}"><a href="{row['url']}" target="_blank">{row['code']}</a></td>
            <td data-value="{row['name']}">{row['name']}</td>
            <td data-value="{row['price']}" class="{p_cls}">{price_display}</td>
            <td data-value="{row['change']}" class="{p_cls}">{change_display}</td>
            <td data-value="{row['sort_order']}" class="rating-cell" {tooltip_events}>
                <span class="{row['rating_class']}">{row['rating']}</span>
            </td>
            <td>{make_sparkline(row['trend'])}</td>
        </tr>
    """

html_content += "</tbody></table></body></html>"
components.html(html_content, height=800, scrolling=True)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API | 點擊表頭可進行排序")
