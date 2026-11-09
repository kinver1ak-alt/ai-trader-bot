import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = "9288839638:AAEuUm8Tmeh7LscyYQIZxgM-Gb0pvx_CgkI"
CHAT_ID = "8724154941"
LOG_FILE = "trading_history.csv"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"خطأ في إرسال التنبيه: {e}")

def save_trade_to_log(asset, action, price, sl, tp, rsi):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_row = pd.DataFrame([{
        'الوقت': current_time,
        'الأصل': asset,
        'الإجراء': action,
        'السعر': price,
        'وقف الخسارة': sl,
        'هدف الربح': tp,
        'RSI': rsi
    }])
    
    if not os.path.exists(LOG_FILE):
        new_row.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
    else:
        new_row.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

class AutonomousTradingScanner:
    def __init__(self):
        self.tickers = {
            'EURUSD': 'EURUSD=X',
            'GBPUSD': 'GBPUSD=X',
            'USDJPY': 'USDJPY=X',
            'GOLD': 'GC=F',
            'SILVER': 'SI=F',
            'BTCUSD': 'BTC-USD',
            'ETHUSD': 'ETH-USD',
            'SPX (S&P 500)': '^GSPC',
            'US 100 (NDQ)': '^IXIC',
            'US30 (Dow Jones)': '^DJI'
        }

    def scan_once(self):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{current_time}] 🔄 جاري فحص الأسواق اللحظية على فريم 15M...")
        
        for name, ticker in self.tickers.items():
            try:
                df = yf.download(ticker, period='60d', interval='15m', auto_adjust=True, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                if df.empty or len(df) < 50 or 'Close' not in df.columns:
                    continue
                    
                close_prices = df['Close'].squeeze()
                high_prices = df['High'].squeeze() if 'High' in df.columns else close_prices
                low_prices = df['Low'].squeeze() if 'Low' in df.columns else close_prices

                analysis_df = pd.DataFrame({'Close': close_prices})

                delta = analysis_df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                analysis_df['RSI'] = 100 - (100 / (1 + rs))
                
                exp1 = analysis_df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = analysis_df['Close'].ewm(span=26, adjust=False).mean()
                analysis_df['MACD'] = exp1 - exp2
                analysis_df['Signal_Line'] = analysis_df['MACD'].ewm(span=9, adjust=False).mean()
                
                analysis_df['EMA_50'] = analysis_df['Close'].ewm(span=50, adjust=False).mean()
                analysis_df['EMA_200'] = analysis_df['Close'].ewm(span=200, adjust=False).mean()
                
                high_low = high_prices - low_prices
                high_close = np.abs(high_prices - close_prices.shift())
                low_close = np.abs(low_prices - close_prices.shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                analysis_df['ATR'] = true_range.rolling(14).mean()
                
                analysis_df.dropna(inplace=True)
                if analysis_df.empty:
                    continue

                last_row = analysis_df.iloc[-1]
                close = float(last_row['Close'])
                rsi = float(last_row['RSI'])
                macd = float(last_row['MACD'])
                signal_line = float(last_row['Signal_Line'])
                ema50 = float(last_row['EMA_50'])
                ema200 = float(last_row['EMA_200'])
                atr = float(last_row['ATR']) if not np.isnan(last_row['ATR']) else close * 0.005
                
                decision = "HOLD"
                
                if rsi < 40 and macd > signal_line and close > ema200:
                    decision = "BUY"
                elif rsi > 60 and macd < signal_line and close < ema200:
                    decision = "SELL"

                if decision != "HOLD":
                    stop_loss = round(close - (1.2 * atr) if decision == "BUY" else close + (1.2 * atr), 2)
                    take_profit = round(close + (2.5 * atr) if decision == "BUY" else close - (2.5 * atr), 2)
                    
                    save_trade_to_log(name, decision, round(close, 2), stop_loss, take_profit, round(rsi, 2))
                    
                    emoji = "🟢" if decision == "BUY" else "🔴"
                    msg = (
                        f"{emoji} **تنبيه صفقة حية ({decision})**\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"📊 الأصل: `{name}`\n"
                        f"💲 السعر الحالي: `{round(close, 2)}`\n"
                        f"📈 RSI: `{round(rsi, 2)}`\n"
                        f"🛑 وقف الخسارة: `{stop_loss}`\n"
                        f"🎯 هدف الربح: `{take_profit}`"
                    )
                    send_telegram_alert(msg)
                    print(f"🎯 تم تسجيل وإرسال إشعار صفقة {decision} للأصل {name}!")
            except Exception:
                pass
        print("✅ انتهت دورة الفحص. البوت في انتظار الشمعة القادمة...")

scanner = AutonomousTradingScanner()
print("🤖 البوت يعمل الآن ويراقب الأسواق ويسجل الصفقات أوتوماتيكياً...")
send_telegram_alert("🚀 **تم تفعيل حارس التداول السحابي!** البوت يراقب ويسجل الصفقات 24/7.")

while True:
    scanner.scan_once()
    time.sleep(900)
