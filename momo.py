import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# Sayfa ayarları
st.set_page_config(page_title="BIST Hisse Öneri", layout="wide")
st.title("📈 BIST 30 Teknik Analiz Paneli")

# BIST 30 Listesi (Güncel Tickerlar)
bist30_tickers = [
    'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 
    'ENKAI.IS', 'EREGL.IS', 'FROTO.IS', 'GARAN.IS', 'HEKTS.IS',
    'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KARDM.IS', 'PETKM.IS',
    'PGSUS.IS', 'SAHOL.IS', 'SISE.IS', 'TAVHL.IS', 'THYAO.IS',
    'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS'
]

def get_signal(rsi):
    if rsi is None: return "Veri Yok"
    if rsi < 35: return "AŞIRI SATIM (AL)"
    elif rsi > 65: return "AŞIRI ALIM (SAT)"
    else: return "NÖTR"

def fetch_data():
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(bist30_tickers):
        try:
            # Veriyi çek (Son 3 aylık günlük veri)
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if len(df) < 20: # Yeterli veri yoksa atla
                continue
            
            # Sütun isimlerini düzelt (yfinance bazen karmaşık başlık verir)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # RSI Hesapla
            df['RSI'] = ta.rsi(df['Close'], length=14)
            
            last_price = float(df['Close'].iloc[-1])
            prev_price = float(df['Close'].iloc[-2])
            last_rsi = float(df['RSI'].iloc[-1])
            change = ((last_price - prev_price) / prev_price) * 100
            
            results.append({
                "Hisse": ticker.replace(".IS", ""),
                "Fiyat": round(last_price, 2),
                "Değişim %": round(change, 2),
                "RSI (14)": round(last_rsi, 2),
                "Sinyal": get_signal(last_rsi)
            })
        except Exception as e:
            print(f"Hata: {ticker} - {e}")
        
        progress_bar.progress((i + 1) / len(bist30_tickers))
    
    return pd.DataFrame(results)

# Arayüz Butonu
if st.button('Hisseleri Tara ve Analiz Et'):
    df_final = fetch_data()
    
    if not df_final.empty:
        st.subheader("BIST 30 Teknik Analiz Sonuçları")
        
        # Sinyale göre renklendirme fonksiyonu
        def color_signal(val):
            if "AL" in str(val): color = '#90ee90' # Açık yeşil
            elif "SAT" in str(val): color = '#ffcccb' # Açık kırmızı
            else: color = 'transparent'
            return f'background-color: {color}'

        # Tabloyu göster
        st.dataframe(df_final.style.map(color_signal, subset=['Sinyal']), use_container_width=True)

        # Öne çıkanları göster
        col1, col2 = st.columns(2)
        with col1:
            st.success("🟢 Alım Fırsatı Olabilir (Düşük RSI)")
            st.table(df_final.sort_values(by="RSI (14)").head(5))
        
        with col2:
            st.error("🔴 Dikkat: Aşırı Alım (Yüksek RSI)")
            st.table(df_final.sort_values(by="RSI (14)", ascending=False).head(5))
    else:
        st.error("Veri çekilemedi. Lütfen internet bağlantınızı kontrol edin veya biraz sonra tekrar deneyin.")
else:
    st.info("Piyasayı taramak için butona basın.")
