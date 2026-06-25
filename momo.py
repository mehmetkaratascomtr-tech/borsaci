import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time

st.set_page_config(page_title="BIST Analiz Pro", layout="wide")

st.title("🚀 BIST Genişletilmiş Analiz Paneli")
st.markdown("""
*Bu panel BIST 100 ve popüler hisseleri tarar. **SMA 200** üzerindeki hisseler daha güvenli kabul edilir.*
""")

# Daha geniş bir liste (BIST 100 ve popülerler)
# Not: Hepsini (500) eklemek istersen listeyi genişletebilirsin.
tickers = [
    'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 'ENKAI.IS', 'EREGL.IS', 'FROTO.IS', 'GARAN.IS', 'HEKTS.IS',
    'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KARDM.IS', 'PETKM.IS', 'PGSUS.IS', 'SAHOL.IS', 'SISE.IS', 'TAVHL.IS', 'THYAO.IS',
    'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'SISE.IS', 'SASA.IS', 'GUBRF.IS', 'KONTROL.IS', 'YEOTK.IS', 'ASTOR.IS', 'ALARK.IS',
    'CANTE.IS', 'DOHOL.IS', 'ENJSİ.IS', 'ODAS.IS', 'OYAKC.IS', 'SKBNK.IS', 'TSKB.IS', 'TTKOM.IS', 'TCELL.IS', 'VESTL.IS',
    'ZOREN.IS', 'KONTR.IS', 'MIATK.IS', 'REEDR.IS', 'EUPWR.IS', 'SMRTG.IS', 'ALFAS.IS', 'BRYAT.IS', 'QUAGR.IS'
    # Buraya istediğin kadar hisse ekleyebilirsin...
]

def fetch_comprehensive_data(ticker_list):
    results = []
    progress_text = "Hisseler analiz ediliyor..."
    my_bar = st.progress(0, text=progress_text)
    
    for idx, ticker in enumerate(ticker_list):
        try:
            # 1 yıllık veri çek (SMA 200 için gerekli)
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Teknik Göstergeler
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA200'] = ta.sma(df['Close'], length=200)
            
            last_price = float(df['Close'].iloc[-1])
            last_rsi = float(df['RSI'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1])
            change = ((last_price - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100
            
            # Güvenlik Puanı: SMA200 üstündeyse daha güvenli
            trend = "YÜKSELİŞ" if last_price > sma200 else "DÜŞÜŞ"
            
            # Sinyal Mantığı
            if last_rsi < 35 and trend == "YÜKSELİŞ":
                signal = "🔥 GÜÇLÜ AL (Trend Üstü Ucuz)"
            elif last_rsi < 30:
                signal = "🟢 AL (Aşırı Satım)"
            elif last_rsi > 70:
                signal = "🔴 SAT (Aşırı Alım)"
            else:
                signal = "⏳ BEKLE"

            results.append({
                "Hisse": ticker.replace(".IS", ""),
                "Fiyat": round(last_price, 2),
                "Günlük %": round(change, 2),
                "RSI": round(last_rsi, 1),
                "Trend (SMA200)": trend,
                "Sinyal": signal
            })
        except:
            continue
        
        my_bar.progress((idx + 1) / len(ticker_list))
    
    return pd.DataFrame(results)

if st.button('Piyasayı Tara (Geniş Tarama)'):
    data = fetch_comprehensive_data(tickers)
    
    if not data.empty:
        # 1. En Güvenli Alım Fırsatları (SMA200 üstü ve RSI düşük)
        st.subheader("🛡️ En Güvenli Alım Fırsatları (Trendi Sağlam)")
        safe_buys = data[(data['Trend (SMA200)'] == 'YÜKSELİŞ') & (data['RSI'] < 45)]
        st.dataframe(safe_buys.sort_values(by="RSI"), use_container_width=True)

        # 2. Tüm Liste
        st.subheader("📊 Tüm Tarama Sonuçları")
        
        def color_logic(val):
            if "AL" in str(val): return 'background-color: #2ecc71; color: white'
            if "SAT" in str(val): return 'background-color: #e74c3c; color: white'
            return ''

        st.dataframe(data.style.map(color_logic, subset=['Sinyal']), use_container_width=True)
    else:
        st.error("Veri alınamadı.")

st.info("💡 İpucu: 'Trend' sütunu YÜKSELİŞ olan hisseler, uzun vadede daha az risk taşır.")
