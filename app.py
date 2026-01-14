import streamlit as st
import pandas as pd
import yfinance as yf
import random
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode # 引入進階表格套件

# --- 設定網頁配置 ---
st.set_page_config(page_title="台股AI選股系統 (AgGrid版)", layout="wide")

# --- 1. 抓取資料 (邏輯不變) ---
@st.cache_data(ttl=600)
def get_real_stock_data():
    stocks_info = [
        ("2330.TW", "台積電"), ("2454.TW", "聯發科"), ("2317.TW", "鴻海"), 
        ("2603.TW", "長榮"),   ("2609.TW", "陽明"),   ("2303.TW", "聯電"), 
        ("2881.TW", "富邦金"), ("2882.TW", "國泰金"), ("1605.TW", "華新"), 
        ("3231.TW", "緯創"),   ("2382.TW", "廣達"),   ("2357.TW", "華碩"),
        ("3008.TW", "大立光"), ("1101.TW", "台泥"),   ("3034.TW", "聯詠"), 
        ("6669.TW", "緯穎"),   ("2379.TW", "瑞昱"),   ("3037.TW", "欣興"),
        ("2345.TW", "智邦"),   ("2412.TW", "中華電"), ("2308.TW", "台達電"), 
        ("5871.TW", "中租-KY"),("2395.TW", "研華"),   ("1513.TW", "中興電"),
        ("2912.TW", "統一超"), ("1216.TW", "統一"),   ("6505.TW", "台塑化"), 
        ("1301.TW", "台塑"),   ("2002.TW", "中鋼"),   ("2891.TW", "中信金")
    ]
    
    bull_reasons = ["主力籌碼集中", "外資連續買超", "均線多頭排列", "營收創新高", "量能爆發", "底部型態完成", "投信作帳行情"]
    bear_reasons = ["高檔震盪", "量縮整理", "乖離率過大", "面臨前波壓力", "法人調節", "跌破五日線", "融資過高"]
    
    data = []
    progress_text = "正在連線 Yahoo Finance..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(stocks_info)
    
    for i, (ticker, name) in enumerate(stocks_info):
        my_bar.progress((i + 1) / total, text=f"正在分析: {ticker} {name}")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d") # 只需要最新價格，抓5天比較快
            
            if hist.empty:
                continue

            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            daily_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # AI 預測模擬
            predicted_growth = round(random.uniform(-10, 30), 2)
            
            rating = "一般"
            reason = "觀望"
            
            if predicted_growth > 15:
                rating = "強力推薦"
                reason = f"🔥 強力理由：{random.choice(bull_reasons)}"
            elif predicted_growth > 5:
                rating = "買進"
                reason = f"📈 買進理由：{random.choice(bull_reasons)}"
            elif predicted_growth < -5:
                rating = "避開"
                reason = f"⚠️ 風險提示：{random.choice(bear_reasons)}"
            else:
                reason = f"👀 觀察理由：{random.choice(bear_reasons)}"
            
            clean_code = ticker.replace(".TW", "")
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{ticker}"

            data.append({
                "代號": clean_code,
                "URL": yahoo_url, # 隱藏欄位，供連結使用
                "股名": name,
                "目前股價": round(current_price, 2),
                "今日漲跌": round(daily_change_pct, 2),
                "預測漲幅": predicted_growth,
                "評級": rating,
                "推薦短評": reason # 這欄位會變成 Tooltip，不直接顯示
            })
            
        except Exception:
            continue
            
    my_bar.empty()
    return pd.DataFrame(data)

# --- 2. 介面設計 ---

st.title("📈 台股 AI 飆股快篩 (AgGrid 進階版)")

col1, col2 = st.columns([1, 5])
with col1:
    show_strong_only = st.checkbox("只顯示強力推薦", value=False)
with col2:
    st.info("💡 操作提示：將滑鼠游標移到 **「評級」** 欄位上方，即可查看 AI 分析原因！")

df = get_real_stock_data()

# --- 3. 篩選與排序 ---

if show_strong_only:
    display_df = df[df["評級"] == "強力推薦"]
else:
    display_df = df

display_df = display_df.sort_values(by="預測漲幅", ascending=False)

# --- 4. AgGrid 表格設定 (關鍵！) ---

# 初始化設定器
gb = GridOptionsBuilder.from_dataframe(display_df)

# 設定表格一般樣式 (自動調整欄寬)
gb.configure_default_column(resizable=True, sortable=True)

# 隱藏不需要直接顯示的欄位 (但數據還在，給 Tooltip 用)
gb.configure_column("URL", hide=True)
gb.configure_column("推薦短評", hide=True)

# === 關鍵 1: 設定評級欄位的 Tooltip ===
# tooltipField="推薦短評" 意思就是：這格的提示內容，去抓「推薦短評」那一欄的文字
gb.configure_column("評級", tooltipField="推薦短評", headerName="AI 評級 (👆懸停看原因)", pinned="right")

# === 關鍵 2: 設定代號的超連結 ===
# 使用 JavaScript 讓點擊代號時開啟新視窗
link_renderer = JsCode("""
    class UrlCellRenderer {
      init(params) {
        this.eGui = document.createElement('a');
        this.eGui.innerText = params.value;
        this.eGui.setAttribute('href', params.data.URL);
        this.eGui.setAttribute('target', '_blank');
        this.eGui.style.color = '#3b82f6';
        this.eGui.style.textDecoration = 'none';
        this.eGui.style.fontWeight = 'bold';
      }
      getGui() {
        return this.eGui;
      }
    }
""")
gb.configure_column("代號", cellRenderer=link_renderer, width=100)

# 設定股價顏色 (紅漲綠跌)
price_style = JsCode("""
    function(params) {
        if (params.data.今日漲跌 > 0) {
            return {'color': 'red', 'fontWeight': 'bold'};
        } else if (params.data.今日漲跌 < 0) {
            return {'color': 'green', 'fontWeight': 'bold'};
        }
        return {'color': 'black'};
    }
""")
gb.configure_column("目前股價", cellStyle=price_style)
gb.configure_column("今日漲跌", cellStyle=price_style)
gb.configure_column("預測漲幅", cellStyle=price_style)

# 建立表格設定
gridOptions = gb.build()

# 顯示 AgGrid 表格
AgGrid(
    display_df,
    gridOptions=gridOptions,
    allow_unsafe_jscode=True, # 必須開啟才能用 JS 畫連結和顏色
    height=600,
    theme="streamlit", # 風格設定
    columns_auto_size_mode="FIT_CONTENTS"
)

st.markdown("---")
st.caption("資料來源：Yahoo Finance API | 使用 AgGrid 模組實作懸停提示")
