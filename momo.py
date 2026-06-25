import streamlit as st
import yfinance as download
import pandas as pd
import pandas_ta as ta

# Başlık ve Açıklama
st.set_page_config(page_title="BIST Hisse Öneri Paneli", layout="wide")
st.title("📈 BIST Hisse Analiz ve Sinyal Paneli")
st.markdown("""
Bu uygulama BIST 30 hisselerini analiz eder ve **RSI (Göreceli Güç Endeksi)** göstergesine göre basit sinyaller üretir.
*Not: Bu bir yatırım tavsiyesi değildir!*
""")

# BIST 30 Listesi (Örnek olarak bir kısmı)
bist30_tickers = [
    'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 
    'ENKAI.IS', 'EREGL.IS', 'FROTO.IS', 'GARAN.IS', 'HEKTS.IS',
    'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KARDM.IS', 'PETKM.IS',
    'PGSUS.IS', 'SAHOL.IS', 'SISE.IS', 'TAVHL.IS', 'THYAO.IS',
    'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS'
]

def get_signal(rsi):
    if rsi < 30:
        return "AŞIRI SATIM (ALIM FIRSATI OLABİLİR)"
    elif rsi > 70:
        return "AŞIRI ALIM (DİKKATLİ OLUNMALI)"
    else:
        return "NÖTR"

def fetch_data():
    results = []
    with st.spinner('Veriler güncelleniyor, lütfen bekleyin...'):
        for ticker in bist30_tickers:
            try:
                # Son 60 günlük veriyi çek
                df = download.download(ticker, period="60d", interval="1d", progress=False)
                if df.empty: continue
                
                # RSI Hesapla
                df['RSI'] = ta.rsi(df['Close'], length=14)
                
                last_price = df['Close'].iloc[-1]
                last_rsi = df['RSI'].iloc[-1]
                change = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                
                results.append({
                    "Hisse": ticker.replace(".IS", ""),
                    "Fiyat": round(last_price, 2),
                    "Günlük Değişim (%)": round(change, 2),
                    "RSI (14)": round(last_rsi, 2),
                    "Sinyal": get_signal(last_rsi)
                })
            except Exception as e:
                continue
    return pd.DataFrame(results)

# Verileri Getir Butonu
if st.button('Hisseleri Tara ve Analiz Et'):
    data = fetch_data()
    
    # Görselleştirme
    st.subheader("BIST 30 Teknik Analiz Özeti")
    
    # Renklendirme fonksiyonu
    def color_signal(val):
        color = 'white'
        if "ALIM" in val: color = 'lightgreen'
        elif "DİKKAT" in val: color = 'red'
        return f'background-color: {color}; color: black'

    st.dataframe(data.style.applymap(color_signal, subset=['Sinyal']))

    # Öne Çıkanlar
    col1, col2 = st.columns(2)
    with col1:
        st.success("🟢 Alım Bölgesine Yakın (RSI Düşük)")
        st.table(data.sort_values(by="RSI (14)").head(3))
    
    with col2:
        st.error("🔴 Satış Bölgesine Yakın (RSI Yüksek)")
        st.table(data.sort_values(by="RSI (14)", ascending=False).head(3))
else:
    st.info("Analizi başlatmak için yukarıdaki butona tıklayın.")
