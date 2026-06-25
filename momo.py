import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

st.set_page_config(page_title="BIST İntraday Tarayıcı", layout="wide", page_icon="📈")

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #0d1117; color: #e6edf3; }

    .metric-card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-card .label { font-size: 11px; color: #7d8590; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-card .value { font-family: 'JetBrains Mono', monospace; font-size: 26px; font-weight: 600; margin-top: 4px; }

    .score-high  { color: #3fb950; }
    .score-mid   { color: #d29922; }
    .score-low   { color: #f85149; }

    .stDataFrame { border: 1px solid #21262d !important; border-radius: 8px; overflow: hidden; }

    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 28px;
        font-size: 15px;
        font-weight: 600;
        width: 100%;
        transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button:hover { opacity: 0.85; }

    .section-title {
        font-size: 13px;
        font-weight: 600;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border-bottom: 1px solid #21262d;
        padding-bottom: 8px;
        margin: 24px 0 12px 0;
    }

    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-green { background: #1a3a22; color: #3fb950; border: 1px solid #2ea043; }
    .badge-red   { background: #3a1a1a; color: #f85149; border: 1px solid #da3633; }
    .badge-yellow{ background: #3a2f0a; color: #d29922; border: 1px solid #9e6a03; }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("## 📈 BIST İntraday Tarayıcı")
st.markdown("**10:30 – 11:00 girişi · %+2 hedef · Aynı gün çıkış** — Sabah taramasını 09:50'de çalıştır.")

# ─── HİSSE LİSTESİ ─────────────────────────────────────────────────────────────
DEFAULT_TICKERS = [
    'AKBNK.IS','ARCLK.IS','ASELS.IS','BIMAS.IS','EKGYO.IS','ENKAI.IS','EREGL.IS',
    'FROTO.IS','GARAN.IS','HEKTS.IS','ISCTR.IS','KCHOL.IS','KOZAL.IS','PETKM.IS',
    'PGSUS.IS','SAHOL.IS','SISE.IS','TAVHL.IS','THYAO.IS','TOASO.IS','TUPRS.IS',
    'YKBNK.IS','SASA.IS','GUBRF.IS','ASTOR.IS','ALARK.IS','DOHOL.IS','ODAS.IS',
    'OYAKC.IS','SKBNK.IS','TSKB.IS','TTKOM.IS','TCELL.IS','VESTL.IS','ZOREN.IS',
    'KONTR.IS','MIATK.IS','EUPWR.IS','BRYAT.IS','ALFAS.IS','KRDMD.IS','AGHOL.IS',
    'CEMTS.IS','KOZAA.IS','MGROS.IS','SOKM.IS','BERA.IS','ISMEN.IS','LOGO.IS'
]

# ─── FONKSİYON ─────────────────────────────────────────────────────────────────
def compute_composite_score(rsi, rvol, macd_hist, ema_cross, atr_pct, above_sma200, daily_change):
    """
    Composite skor 0–100 arası.
    Ağırlıklar: RSI 25 | EMA Cross 25 | MACD 20 | ATR 15 | RVOL 15 | SMA200 bonus 5
    """
    score = 0

    # 1) RSI (25 puan): 30-55 arası ideal intraday giriş bölgesi
    if 30 <= rsi <= 55:
        score += 25
    elif 55 < rsi <= 65:
        score += 12   # koşmaya başlamış, dikkat
    elif rsi < 30:
        score += 8    # aşırı satım, dip avı riski var
    # RSI > 65 → 0 puan (zaten koşmuş, geç kalınmış)

    # 2) EMA Cross (25 puan): EMA20 > EMA50 → kısa vade trend sağlıklı
    if ema_cross:
        score += 25

    # 3) MACD Histogram (20 puan): momentum yönü
    if macd_hist > 0:
        score += 20
    elif macd_hist > -0.3:
        score += 8    # nötr bölge

    # 4) ATR% (15 puan): gün içi %2 hedefe ulaşabilecek volatilite
    if atr_pct >= 2.5:
        score += 15
    elif atr_pct >= 1.8:
        score += 10
    elif atr_pct >= 1.2:
        score += 5

    # 5) RVOL (15 puan): hacim onayı — tek başına skoru patlatmamalı
    if rvol >= 2.0:
        score += 15
    elif rvol >= 1.5:
        score += 10
    elif rvol >= 1.2:
        score += 5

    # Bonus: SMA200 üstündeyse +5
    if above_sma200:
        score = min(100, score + 5)

    # Ceza: Günlük -%5'ten fazla düşmüşse -20 (düşen bıçak riski)
    if daily_change <= -5:
        score = max(0, score - 20)

    return score


def fetch_data(ticker_list, progress_bar):
    results = []

    for idx, ticker in enumerate(ticker_list):
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
            if df.empty or len(df) < 55:
                progress_bar.progress((idx + 1) / len(ticker_list))
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df['Close'].squeeze()
            volume = df['Volume'].squeeze()

            # ── Göstergeler ──────────────────────────────────────────────────
            rsi_s    = ta.rsi(close, length=14)
            ema20_s  = ta.ema(close, length=20)
            ema50_s  = ta.ema(close, length=50)
            sma200_s = ta.sma(close, length=200)
            atr_s    = ta.atr(df['High'].squeeze(), df['Low'].squeeze(), close, length=14)
            macd_df  = ta.macd(close, fast=12, slow=26, signal=9)

            if rsi_s is None or ema20_s is None or ema50_s is None:
                progress_bar.progress((idx + 1) / len(ticker_list))
                continue

            last_close   = float(close.iloc[-1])
            prev_close   = float(close.iloc[-2])
            last_rsi     = float(rsi_s.iloc[-1])
            last_ema20   = float(ema20_s.iloc[-1])
            last_ema50   = float(ema50_s.iloc[-1])
            last_atr     = float(atr_s.iloc[-1]) if atr_s is not None else 0

            # SMA200 — sadece yeterli veri varsa
            above_sma200 = False
            if sma200_s is not None and not sma200_s.dropna().empty and len(sma200_s.dropna()) >= 1:
                last_sma200  = float(sma200_s.dropna().iloc[-1])
                above_sma200 = last_close > last_sma200

            # MACD histogram
            macd_hist = 0.0
            if macd_df is not None:
                hist_col = [c for c in macd_df.columns if 'h' in c.lower()]
                if hist_col:
                    macd_hist = float(macd_df[hist_col[0]].iloc[-1])

            # RVOL: son gün hacmi / 20 günlük ortalama hacim
            vol_mean = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else float(volume.mean())
            rvol = float(volume.iloc[-1]) / vol_mean if vol_mean > 0 else 0

            # Günlük değişim
            daily_change = ((last_close - prev_close) / prev_close) * 100

            # ATR%
            atr_pct = (last_atr / last_close) * 100 if last_close > 0 else 0

            # EMA cross
            ema_cross = last_ema20 > last_ema50

            # Composite skor
            score = compute_composite_score(last_rsi, rvol, macd_hist, ema_cross, atr_pct, above_sma200, daily_change)

            # Trend
            trend = "↑ Yükseliş" if above_sma200 else "↓ Düşüş"

            # Sinyal — RSI > 65 veya günlük düşüş > %5 → otomatik Geç
            if last_rsi > 65 or daily_change <= -5:
                if last_rsi > 65:
                    signal = "⛔ Geç (Koşmuş)"
                else:
                    signal = "⛔ Geç (Düşen Bıçak)"
            elif score >= 70:
                signal = "🔥 GÜÇLÜ AL"
            elif score >= 50:
                signal = "🟢 AL"
            elif score >= 35:
                signal = "⏳ İzle"
            else:
                signal = "⛔ Geç"

            results.append({
                "Hisse"        : ticker.replace(".IS", ""),
                "Fiyat"        : round(last_close, 2),
                "Günlük %"     : round(daily_change, 2),
                "RSI"          : round(last_rsi, 1),
                "RVOL"         : round(rvol, 2),
                "MACD Hist"    : round(macd_hist, 3),
                "EMA 20>50"    : "✅" if ema_cross else "❌",
                "ATR %"        : round(atr_pct, 2),
                "Trend"        : trend,
                "Skor /100"    : score,
                "Sinyal"       : signal,
            })

        except Exception:
            pass

        progress_bar.progress((idx + 1) / len(ticker_list))

    return pd.DataFrame(results)


# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Filtreler")
    min_score    = st.slider("Minimum Skor", 0, 100, 50, step=5)
    min_rvol     = st.slider("Min. RVOL", 0.5, 3.0, 1.2, step=0.1)
    min_atr      = st.slider("Min. ATR %", 0.0, 4.0, 1.2, step=0.1)
    max_daily_drop = st.slider("Maks. Günlük Düşüş %", -10.0, 0.0, -5.0, step=0.5,
                                help="Bu değerden fazla düşmüş hisseler elenir (düşen bıçak koruması)")
    only_trend   = st.checkbox("Sadece SMA200 üstü", value=True)

    st.markdown("---")
    st.markdown("### ℹ️ Gösterge Rehberi")
    st.markdown("""
**RSI 30–55** → İdeal giriş bölgesi  
**RSI > 65** → Koşmuş, girme  
**RVOL ≥ 1.5** → Hacim onaylı hareket  
**MACD Hist > 0** → Yukarı momentum  
**EMA 20 > 50** → Kısa vade trend sağlıklı  
**ATR % ≥ 1.8** → %2 hedefe ulaşabilir  
**Günlük < -5%** → Düşen bıçak, atla  
**Skor ≥ 70** → Güçlü al sinyali
    """)

# ─── ANA BUTON ─────────────────────────────────────────────────────────────────
col_btn, col_empty = st.columns([1, 3])
with col_btn:
    run = st.button("🔍 Piyasayı Tara")

if run:
    pb = st.progress(0, text="Hisseler analiz ediliyor…")
    data = fetch_data(DEFAULT_TICKERS, pb)
    pb.empty()

    if data.empty:
        st.error("Hiç veri alınamadı. İnternet bağlantısını veya ticker listesini kontrol et.")
        st.stop()

    # ── Özet metrikler ──────────────────────────────────────────────────────
    total      = len(data)
    guclu      = len(data[data['Sinyal'] == '🔥 GÜÇLÜ AL'])
    al         = len(data[data['Sinyal'] == '🟢 AL'])
    avg_score  = int(data['Skor /100'].mean())

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value, css in [
        (c1, "Taranan Hisse",   total,      ""),
        (c2, "Güçlü AL",        guclu,      "score-high"),
        (c3, "AL Sinyali",      al,         "score-mid"),
        (c4, "Ortalama Skor",   avg_score,  "score-high" if avg_score >= 50 else "score-low"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="label">{label}</div>
                <div class="value {css}">{value}</div>
            </div>""", unsafe_allow_html=True)

    # ── Filtre uygula ───────────────────────────────────────────────────────
    filtered = data[
        (data['Skor /100'] >= min_score) &
        (data['RVOL']      >= min_rvol) &
        (data['ATR %']     >= min_atr) &
        (data['Günlük %']  >= max_daily_drop) &
        (~data['Sinyal'].str.contains('Geç'))
    ]
    if only_trend:
        filtered = filtered[filtered['Trend'] == '↑ Yükseliş']

    filtered = filtered.sort_values('Skor /100', ascending=False).reset_index(drop=True)

    # ── Top fırsatlar tablosu ───────────────────────────────────────────────
    st.markdown('<div class="section-title">🎯 Bugünkü Fırsatlar (Filtre Uygulandı)</div>', unsafe_allow_html=True)

    if filtered.empty:
        st.warning("Bu filtrelerle eşleşen hisse yok. Sol panelden filtreleri gevşet.")
    else:
        def style_table(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)

            for i, row in df.iterrows():
                s = row['Skor /100']
                if s >= 70:
                    styles.at[i, 'Skor /100'] = 'background-color:#1a3a22; color:#3fb950; font-weight:700'
                    styles.at[i, 'Sinyal']    = 'background-color:#1a3a22; color:#3fb950'
                elif s >= 50:
                    styles.at[i, 'Skor /100'] = 'background-color:#3a2f0a; color:#d29922; font-weight:700'
                    styles.at[i, 'Sinyal']    = 'background-color:#3a2f0a; color:#d29922'
                else:
                    styles.at[i, 'Skor /100'] = 'color:#7d8590'

                if row['Günlük %'] > 0:
                    styles.at[i, 'Günlük %'] = 'color:#3fb950'
                elif row['Günlük %'] < 0:
                    styles.at[i, 'Günlük %'] = 'color:#f85149'

                if row['RVOL'] >= 1.5:
                    styles.at[i, 'RVOL'] = 'color:#3fb950; font-weight:600'

                if row['ATR %'] >= 1.8:
                    styles.at[i, 'ATR %'] = 'color:#3fb950'
                elif row['ATR %'] < 1.2:
                    styles.at[i, 'ATR %'] = 'color:#f85149'

            return styles

        st.dataframe(
            filtered.style.apply(style_table, axis=None),
            use_container_width=True,
            height=min(600, 36 * (len(filtered) + 1) + 20)
        )

    # ── Tüm sonuçlar ───────────────────────────────────────────────────────
    with st.expander("📊 Tüm Tarama Sonuçları", expanded=False):
        st.dataframe(
            data.sort_values('Skor /100', ascending=False),
            use_container_width=True
        )

    # ── Not ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
> **⚠️ Risk Notu:** Bu araç yalnızca teknik analiz filtresi sunar.  
> Her işlemde stop-loss kullan (%1.5 önerilir). Yatırım tavsiyesi değildir.
    """)
