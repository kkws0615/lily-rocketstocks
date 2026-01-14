import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import random

st.set_page_config(page_title="台股AI標股神探 (自選擴充版)", layout="wide")

# --- 0. 初始化：使用 session_state 記住股票清單 ---
# 這樣當你按按鈕新增股票時，清單才不會被重置
if 'watch_list' not in st.session_state:
    st.session_state.watch_list = {
        "2330.TW": "台積電", "2454.TW": "聯發科", "2317.TW": "鴻海", "2603.TW": "長榮",
        "2609.TW": "陽明",   "2303.TW": "聯電",   "2881.TW": "富邦金", "2882.TW": "國泰金",
        "1605.TW": "華新",   "3231.TW": "緯創",   "2382.TW": "廣達",   "2357.TW": "華碩",
        "3008.TW": "大立光", "1101.TW": "台泥",   "3034.TW": "聯詠",   "6669.TW": "緯穎",
        "2379.TW": "瑞昱",   "3037.TW": "欣興",   "2345.TW": "智邦",   "2412.TW": "中華電",
        "2308.TW": "台達電", "5871.TW": "中租-KY", "2395.TW": "研華",  "1513.TW": "中興電",
        "2912.TW": "統一超", "1216.TW": "統一",   "6505.TW": "台塑化", "1301.TW": "台塑",
        "2002.TW": "中鋼",   "2891.TW": "中信金"
    }

# --- 1. 輔助函數：生成深度 AI 分析文 ---
def generate_ai_reason(trend, growth):
    # 定義三大面向的詞庫
    tech_bull = ["日K線連三紅", "突破下降趨勢線", "均線呈多頭排列", "KD指標低檔黃金交叉", "MACD柱狀體翻紅", "站上所有均線支撐"]
    chip_bull = ["外資連續五日買超", "投信作帳行情啟動", "主力籌碼集中度大增", "融資餘額大幅減少", "八大官股護盤買進"]
    fund_bull = ["單月營收創歷史新高", "毛利率顯著優於預期", "產業進入旺季循環", "接獲國際大廠長單", "法說會展望樂觀"]
    
    tech_bear = ["跌破季線生命線", "高檔爆出巨量長黑", "頭部型態確立", "KD指標高檔死亡交叉", "MACD柱狀體翻綠", "受到月線反壓"]
    chip_bear = ["外資反手大幅調節", "主力大戶連續倒貨", "融資餘額過高", "投信結帳賣壓湧現", "借券賣出餘額創高"]
    fund_bear = ["營收成長動能趨緩", "匯損衝擊獲利", "庫存水位過高", "產業面臨砍單風險", "毛利率不如預期"]

    if growth > 15: # 強力推薦
        # 組合：1個技術面 + 1個籌碼面 + 1個基本面
        return f"🔥 強力訊號：{random.choice(tech_bull)}，配合{random.choice(chip_bull)}。基本面上{random.choice(fund_bull)}，後市看漲，建議積極佈局。"
    elif growth > 5: # 買進
        return f"📈 多方訊號：{random.choice(tech_bull)}，且{random.choice(fund_bull)}，短線動能轉強。"
    elif growth < -5: # 避開
        return f"⚠️ 風險警示：{random.choice(tech_bear)}，加上{random.choice(chip_bear)}，建議保守觀望。"
    else: # 觀察
        return f"👀 盤整觀望：目前{random.choice(tech_bear)}，但{random.choice(fund_bull)}，多空拉鋸中，等待方向浮現。"

# --- 2. 核心功能：抓取資料 ---
# 移除 cache_data 的 key 參數，因為我們的清單會變動，不能一直快取舊的清單
@st.cache_data(ttl=300) 
def fetch_stock_data(ticker_list):
    # 這裡只負責下載數據，讓上面的 logic 保持乾淨
    try:
        data = yf.download(ticker_list, period="3mo", group_by='ticker', progress=False)
        return data
    except:
        return None

def process_stock_data():
    current_map = st.session_state.watch_list
    tickers = list(current_map.keys())
    
    with st.spinner(f'AI 正在分析 {len(tickers)} 檔個股的技術面與籌碼面...'):
        data_download = fetch_fetch_stock_data_wrapper(tickers)
    
    rows = []
    if data_download is None or len(tickers) == 0:
        return []

    for ticker in tickers:
        try:
            # 兼容單檔與多檔的回傳格式
            if len(tickers) == 1:
                df_stock = data_download
            else:
                df_stock = data_download[ticker]
            
            closes = df_stock['Close']
            if isinstance(closes, pd.DataFrame): closes = closes.iloc[:, 0]
            
            closes_list = closes.dropna().tolist()
            if len(closes_list) < 2: continue
            
            current_price = closes_list[-1]
            prev_price = closes_list[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # AI 預測模擬
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            # 評級邏輯
            if predicted_growth > 15:
                rating = "強力推薦"
                color_class = "tag-strong"
            elif predicted_growth > 5:
                rating = "買進"
                color_class = "tag-buy"
            elif predicted_growth < -5:
                rating = "避開"
                color_class = "tag-sell"
            else:
                rating = "觀察"
                color_class = "tag-hold"
            
            # 生成深度分析
            reason = generate_ai_reason(None, predicted_growth)

            rows.append({
                "code": ticker.replace(".TW", ""),
                "name": current_map[ticker], # 使用 session_state 裡的名稱
                "url": f"https://tw.stock.yahoo.com/quote/{ticker}",
                "price": current_price,
                "change": daily_change_pct,
                "predict": predicted_growth,
                "rating": rating,
                "rating_class": color_class,
                "reason": reason,
                "trend": closes_list[-30:]
            })
        except:
            continue
            
    return sorted(rows, key=lambda x: x['predict'], reverse=True)

# 把 fetch 函式獨立出來是為了 cache 機制能正常運作
@st.cache_data(ttl=60)
def fetch_fetch_stock_data_wrapper(tickers):
    if not tickers: return None
    return yf.download(tickers, period="3mo", group_by='ticker', progress=False)

# --- 3. 輔助：SVG 畫圖 ---
def make_sparkline(data):
    if not data: return ""
    width = 100
    height = 30
    min_val, max_val = min(data), max(data)
    if max_val == min_val: return ""
    
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        y = height - ((val - min_val) / (max_val - min_val)) * (height - 4) - 2
        points.append(f"{x},{y}")
    
    color = "#dc3545" if data[-1] > data[0] else "#28a745"
    return f'<svg width="{width}" height="{height}" style="overflow:visible"><polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/><circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="3" fill="{color}"/></svg>'

# --- 4. 介面設計 ---

st.title("🚀 台股 AI 飆股神探")

# === 新增：上方控制區 (新增股票功能) ===
with st.container():
    col_add, col_info = st.columns([2, 3])
    
    with col_add:
        # 使用 form 來處理輸入，這樣按 Enter 也可以送出
        with st.form(key='add_stock_form', clear_on_submit=True):
            col_input, col_btn = st.columns([3, 1])
            with col_input:
                new_ticker = st.text_input("輸入代號 (如 1616)", placeholder="輸入代號加入監控")
            with col_btn:
                submitted = st.form_submit_button("新增")
            
            if submitted and new_ticker:
                # 簡單驗證輸入
                if not new_ticker.isdigit():
                    st.error("請輸入純數字代號！")
                else:
                    full_ticker = f"{new_ticker}.TW"
                    if full_ticker in st.session_state.watch_list:
                        st.warning(f"{new_ticker} 已經在清單中了！")
                    else:
                        # 嘗試抓取名稱
                        try:
                            # 為了不卡頓，這裡先給預設名稱，下次重新整理時資料會更完整
                            # 或者做一個快速檢查
                            stock_info = yf.Ticker(full_ticker)
                            # 抓取股價確認是否存在
                            hist = stock_info.history(period='1d')
                            if hist.empty:
                                st.error(f"找不到代號 {new_ticker}，請確認是否正確。")
                            else:
                                # 成功！加入清單
                                # 這裡簡化處理，名稱先用 "自選股" 或代號，因為 yf 抓台股名稱不穩定
                                st.session_state.watch_list[full_ticker] = f"自選股-{new_ticker}"
                                st.success(f"成功加入 {new_ticker}！")
                                # 強制重新執行以更新列表
                                st.rerun()
                        except:
                            st.error("連線錯誤，請稍後再試")

    with col_info:
        st.info("💡 提示：滑鼠移到 **「評級」** 上方，會自動浮現 **深度 AI 分析**！")
        filter_strong = st.checkbox("🔥 只看強力推薦", value=False)

# 取得與處理資料
data_rows = process_stock_data()
if filter_strong:
    data_rows = [d for d in data_rows if d['rating'] == "強力推薦"]

# --- 5. 渲染 HTML ---
html_content = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: "Microsoft JhengHei", sans-serif; margin: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 15px; }
    th { background: #f2f2f2; padding: 12px; text-align: left; position: sticky; top: 0; z-index: 10; border-bottom: 2px solid #ddd; font-weight: bold; color: #555; }
    td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: middle; }
    tr:hover { background: #f8f9fa; }
    
    .up { color: #d62728; font-weight: bold; }
    .down { color: #2ca02c; font-weight: bold; }
    a { text-decoration: none; color: #0066cc; font-weight: bold; background: #f0f7ff; padding: 2px 6px; border-radius: 4px; }
    a:hover { background: #dceeff; }

    /* 升級版 Tooltip */
    .tooltip-container { position: relative; display: inline-block; cursor: help; padding: 5px 10px; border-radius: 20px; font-weight: bold; font-size: 13px; transition: all 0.2s; }
    .tooltip-container:hover { transform: scale(1.05); box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    
    .tooltip-text { 
        visibility: hidden; 
        width: 280px; /* 加寬寬度 */
        background-color: #2c3e50; 
        color: #fff; 
        text-align: left; 
        border-radius: 8px; 
        padding: 12px; 
        position: absolute; 
        z-index: 999; 
        bottom: 140%; 
        left: 50%; 
        margin-left: -140px; 
        opacity: 0; 
        transition: opacity 0.3s; 
        font-weight: normal; 
        font-size: 13px; 
        line-height: 1.6; /* 增加行距好閱讀 */
        pointer-events: none; 
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    .tooltip-text::after { content: ""; position: absolute; top: 100%; left: 50%; margin-left: -6px; border-width: 6px; border-style: solid; border-color: #2c3e50 transparent transparent transparent; }
    .tooltip-container:hover .tooltip-text { visibility: visible; opacity: 1; }
    
    /* 標籤配色優化 */
    .tag-strong { background: #ffebeb; color: #d62728; border: 1px solid #ffcccc; }
    .tag-buy { background: #e6ffe6; color: #2ca02c; border: 1px solid #ccffcc; }
    .tag-sell { background: #f1f3f5; color: #495057; border: 1px solid #dee2e6; }
    .tag-hold { background: #fff; color: #868e96; border: 1px solid #eee; }
</style>
</head>
<body>
<table>
    <thead>
        <tr>
            <th>代號</th><th>股名</th><th>現價</th><th>漲跌</th><th>預測漲幅</th><th>AI 評級 (懸停看詳解)</th><th>近三月走勢</th>
        </tr>
    </thead>
    <tbody>
"""

for row in data_rows:
    p_cls = "up" if row['change'] > 0 else "down"
    pred_cls = "up" if row['predict'] > 0 else "down"
    
    html_content += f"""
        <tr>
            <td><a href="{row['url']}" target="_blank">{row['code']}</a></td>
            <td>{row['name']}</td>
            <td class="{p_cls}">{row['price']:.1f}</td>
            <td class="{p_cls}">{row['change']:.2f}%</td>
            <td class="{pred_cls}">{row['predict']:.2f}%</td>
            <td>
                <div class="tooltip-container {row['rating_class']}">
                    {row['rating']}
                    <span class="tooltip-text">{row['reason']}</span>
                </div>
            </td>
            <td>{make_sparkline(row['trend'])}</td>
        </tr>
    """

html_content += """
    </tbody>
</table>
</body>
</html>
"""

components.html(html_content, height=800, scrolling=True)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API (延遲報價) | 本系統僅供模擬測試，不構成投資建議")
