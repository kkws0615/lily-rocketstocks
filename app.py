# --- 3. 大盤即時走勢圖 (確保鎖定台股大盤版) ---
def render_taiex_realtime_chart():
    # 這裡的 "symbol": "TWSE:TAIEX" 代表「台灣證券交易所：加權指數」
    html_code = """
    <div class="tradingview-widget-container" style="height: 500px; width: 100%;">
      <div id="tradingview_taiex" style="height: 100%; width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {
      "autosize": true,
      "symbol": "TWSE:TAIEX",     // 【關鍵修正】強制鎖定台灣加權指數
      "interval": "1",            // 1分鐘線
      "timezone": "Asia/Taipei",  // 鎖定台北時間
      "theme": "light",
      "style": "1",               // 1 = 專業 K 線圖
      "locale": "zh_TW",          // 鎖定繁體中文
      "enable_publishing": false,
      "backgroundColor": "#ffffff",
      "gridColor": "rgba(240, 243, 250, 0.5)",
      "hide_top_toolbar": true,   // 隱藏頂部工具列，畫面更乾淨
      "hide_legend": false,       // 顯示開高低收數值
      "save_image": false,
      "container_id": "tradingview_taiex",
      "withdateranges": true,     // 保留底部的時間切換 (1天, 5天, 1個月...)
      "studies": [
        "Volume@tv-basicstudies"  // 保留成交量
      ]
    }
      );
      </script>
    </div>
    """
    components.html(html_code, height=500)
