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
        background: #161b22; border: 1px solid #21262d;
        border-radius: 8px; padding: 16px 20px; text-align: center;
    }
    .metric-card .label { font-size: 11px; color: #7d8590; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-card .value { font-family: 'JetBrains Mono', monospace; font-size: 26px; font-weight: 600; margin-top: 4px; }
    .score-high { color: #3fb950; }
    .score-mid  { color: #d29922; }
    .score-low  { color: #f85149; }
    .stDataFrame { border: 1px solid #21262d !important; border-radius: 8px; overflow: hidden; }
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; border-radius: 6px;
        padding: 10px 28px; font-size: 15px; font-weight: 600;
        width: 100%; transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button:hover { opacity: 0.85; }
    .section-title {
        font-size: 13px; font-weight: 600; color: #7d8590;
        text-transform: uppercase; letter-spacing: 0.1em;
        border-bottom: 1px solid #21262d; padding-bottom: 8px; margin: 24px 0 12px 0;
    }
    .tv-link {
        display: inline-block; background: #1c2333; border: 1px solid #2d81ff;
        color: #2d81ff; padding: 8px 18px; border-radius: 6px;
        font-size: 13px; font-weight: 600; text-decoration: none; margin: 4px 4px 4px 0;
    }
    .tv-link:hover { background: #2d81ff; color: white; }
    .confirm-badge {
        display: inline-block; background: #1a3a22; border: 1px solid #3fb950;
        color: #3fb950; padding: 3px 10px; border-radius: 12px;
        font-size: 12px; font-weight: 700;
    }
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

# ─── SKOR FONKSİYONU ───────────────────────────────────────────────────────────
def compute_composite_score(rsi, rvol, macd_hist, ema_cross, atr_pct, above_sma200, daily_change):
    score = 0
    if 30 <= rsi <= 55:      score += 25
    elif 55 < rsi <= 65:     score += 12
    elif rsi < 30:           score += 8
    if ema_cross:            score += 25
    if macd_hist > 0:        score += 20
    elif macd_hist > -0.3:   score += 8
    if atr_pct >= 2.5:       score += 15
    elif atr_pct >= 1.8:     score += 10
    elif atr_pct >= 1.2:     score += 5
    if rvol >= 2.0:          score += 15
    elif rvol >= 1.5:        score += 10
    elif rvol >= 1.2:        score += 5
    if above_sma200:         score = min(100, score + 5)
    if daily_change <= -5:   score = max(0, score - 20)
    return score


# ─── TradingView KONTROL FONKSİYONU ────────────────────────────────────────────
def check_tradingview_filters(df, close, high, low):
    """
    TradingView'daki filtrelerle aynı mantığı hesapla:
    ADX > 20, SMA200 altında fiyat yok (fiyat > SMA200),
    Aroon Up yüksek & Down düşük, DMI+ > DMI-,
    Parabolic SAR < Fiyat, Hull MA < Fiyat, CMF > 0
    """
    results = {}

    try:
        # ADX > 20
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None:
            adx_col = [c for c in adx_df.columns if c.startswith('ADX_')]
            dmp_col = [c for c in adx_df.columns if c.startswith('DMP_')]
            dmn_col = [c for c in adx_df.columns if c.startswith('DMN_')]
            results['ADX>20']    = float(adx_df[adx_col[0]].iloc[-1]) > 20 if adx_col else False
            results['DMI+>DMI-'] = float(adx_df[dmp_col[0]].iloc[-1]) > float(adx_df[dmn_col[0]].iloc[-1]) if (dmp_col and dmn_col) else False
        else:
            results['ADX>20'] = False
            results['DMI+>DMI-'] = False
    except:
        results['ADX>20'] = False
        results['DMI+>DMI-'] = False

    try:
        # Aroon Up yüksek (>70), Down düşük (<30)
        aroon_df = ta.aroon(high, low, length=14)
        if aroon_df is not None:
            up_col   = [c for c in aroon_df.columns if 'UP' in c.upper() or 'up' in c]
            down_col = [c for c in aroon_df.columns if 'DOWN' in c.upper() or 'dn' in c.lower()]
            aroon_up   = float(aroon_df[up_col[0]].iloc[-1])   if up_col   else 0
            aroon_down = float(aroon_df[down_col[0]].iloc[-1]) if down_col else 100
            results['Aroon↑']   = aroon_up > 70
            results['Aroon↑>↓'] = aroon_up > aroon_down
        else:
            results['Aroon↑']   = False
            results['Aroon↑>↓'] = False
    except:
        results['Aroon↑']   = False
        results['Aroon↑>↓'] = False

    try:
        # Parabolic SAR < Fiyat
        psar_df = ta.psar(high, low, close)
        if psar_df is not None:
            # Düşen SAR kolonu (long pozisyon için)
            psar_col = [c for c in psar_df.columns if 'PSARl' in c or 'long' in c.lower()]
            if psar_col:
                psar_val = psar_df[psar_col[0]].iloc[-1]
                results['SAR<Fiyat'] = (not pd.isna(psar_val)) and (float(psar_val) < float(close.iloc[-1]))
            else:
                results['SAR<Fiyat'] = False
        else:
            results['SAR<Fiyat'] = False
    except:
        results['SAR<Fiyat'] = False

    try:
        # Hull MA < Fiyat
        hma = ta.hma(close, length=9)
        results['HMA<Fiyat'] = float(hma.iloc[-1]) < float(close.iloc[-1]) if hma is not None else False
    except:
        results['HMA<Fiyat'] = False

    try:
        # CMF > 0
        cmf = ta.cmf(high, low, close, df['Volume'].squeeze(), length=20)
        results['CMF>0'] = float(cmf.iloc[-1]) > 0 if cmf is not None else False
    except:
        results['CMF>0'] = False

    # Kaç TV filtresi geçti?
    tv_filters = ['ADX>20', 'DMI+>DMI-', 'Aroon↑', 'Aroon↑>↓', 'SAR<Fiyat', 'HMA<Fiyat', 'CMF>0']
    passed = sum(1 for f in tv_filters if results.get(f, False))
    results['TV_Skor'] = passed  # 0-7 arası
    results['TV_Onay'] = passed >= 5  # 7'den 5'i geçerse TV onaylı say

    return results


# ─── VERİ ÇEKME FONKSİYONU ─────────────────────────────────────────────────────
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

            close  = df['Close'].squeeze()
            high   = df['High'].squeeze()
            low    = df['Low'].squeeze()
            volume = df['Volume'].squeeze()

            # Temel göstergeler
            rsi_s    = ta.rsi(close, length=14)
            ema20_s  = ta.ema(close, length=20)
            ema50_s  = ta.ema(close, length=50)
            sma200_s = ta.sma(close, length=200)
            atr_s    = ta.atr(high, low, close, length=14)
            macd_df  = ta.macd(close, fast=12, slow=26, signal=9)

            if rsi_s is None or ema20_s is None or ema50_s is None:
                progress_bar.progress((idx + 1) / len(ticker_list))
                continue

            last_close  = float(close.iloc[-1])
            prev_close  = float(close.iloc[-2])
            last_rsi    = float(rsi_s.iloc[-1])
            last_ema20  = float(ema20_s.iloc[-1])
            last_ema50  = float(ema50_s.iloc[-1])
            last_atr    = float(atr_s.iloc[-1]) if atr_s is not None else 0

            above_sma200 = False
            if sma200_s is not None and not sma200_s.dropna().empty:
                last_sma200  = float(sma200_s.dropna().iloc[-1])
                above_sma200 = last_close > last_sma200

            macd_hist = 0.0
            if macd_df is not None:
                hist_col = [c for c in macd_df.columns if 'h' in c.lower()]
                if hist_col:
                    macd_hist = float(macd_df[hist_col[0]].iloc[-1])

            vol_mean     = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else float(volume.mean())
            rvol         = float(volume.iloc[-1]) / vol_mean if vol_mean > 0 else 0
            daily_change = ((last_close - prev_close) / prev_close) * 100
            atr_pct      = (last_atr / last_close) * 100 if last_close > 0 else 0
            ema_cross    = last_ema20 > last_ema50

            score = compute_composite_score(last_rsi, rvol, macd_hist, ema_cross, atr_pct, above_sma200, daily_change)

            # TradingView filtreleri
            tv = check_tradingview_filters(df, close, high, low)

            trend = "↑ Yükseliş" if above_sma200 else "↓ Düşüş"

            if last_rsi > 65 or daily_change <= -5:
                signal = "⛔ Geç (Koşmuş)" if last_rsi > 65 else "⛔ Geç (Düşen Bıçak)"
            elif score >= 70:
                signal = "🔥 GÜÇLÜ AL"
            elif score >= 50:
                signal = "🟢 AL"
            elif score >= 35:
                signal = "⏳ İzle"
            else:
                signal = "⛔ Geç"

            results.append({
                "Hisse"       : ticker.replace(".IS", ""),
                "Fiyat"       : round(last_close, 2),
                "Günlük %"    : round(daily_change, 2),
                "RSI"         : round(last_rsi, 1),
                "RVOL"        : round(rvol, 2),
                "MACD Hist"   : round(macd_hist, 3),
                "EMA 20>50"   : "✅" if ema_cross else "❌",
                "ATR %"       : round(atr_pct, 2),
                "Trend"       : trend,
                "Skor /100"   : score,
                # TradingView sütunları
                "ADX>20"      : "✅" if tv['ADX>20']    else "❌",
                "DMI+>DMI-"   : "✅" if tv['DMI+>DMI-'] else "❌",
                "Aroon↑"      : "✅" if tv['Aroon↑']    else "❌",
                "SAR<Fiyat"   : "✅" if tv['SAR<Fiyat'] else "❌",
                "HMA<Fiyat"   : "✅" if tv['HMA<Fiyat'] else "❌",
                "CMF>0"       : "✅" if tv['CMF>0']     else "❌",
                "TV /7"       : tv['TV_Skor'],
                "TV Onay"     : "⭐ ONAY" if tv['TV_Onay'] else "—",
                "Sinyal"      : signal,
            })

        except Exception:
            pass

        progress_bar.progress((idx + 1) / len(ticker_list))

    return pd.DataFrame(results)


# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Filtreler")
    min_score      = st.slider("Minimum Skor", 0, 100, 50, step=5)
    min_rvol       = st.slider("Min. RVOL", 0.5, 3.0, 1.2, step=0.1)
    min_atr        = st.slider("Min. ATR %", 0.0, 4.0, 1.2, step=0.1)
    max_daily_drop = st.slider("Maks. Günlük Düşüş %", -10.0, 0.0, -5.0, step=0.5)
    only_trend     = st.checkbox("Sadece SMA200 üstü", value=True)
    only_tv        = st.checkbox("Sadece TV Onaylı (≥5/7)", value=False,
                                  help="TradingView filtrelerinin en az 5'ini geçen hisseler")

    st.markdown("---")
    st.markdown("### ℹ️ Gösterge Rehberi")
    st.markdown("""
**RSI 30–55** → İdeal giriş bölgesi  
**RSI > 65** → Koşmuş, girme  
**RVOL ≥ 1.5** → Hacim onaylı  
**MACD Hist > 0** → Yukarı momentum  
**EMA 20 > 50** → Kısa vade trend  
**ATR % ≥ 1.8** → %2 hedefe ulaşır  
**Günlük < -5%** → Düşen bıçak  
**TV /7** → TradingView filtre skoru  
**TV Onay ⭐** → Her iki tarayıcı onayladı  
**Skor ≥ 70** → Güçlü al sinyali
    """)

# ─── BUTON ─────────────────────────────────────────────────────────────────────
col_btn, col_empty = st.columns([1, 3])
with col_btn:
    run = st.button("🔍 Piyasayı Tara")

if run:
    pb = st.progress(0, text="Hisseler analiz ediliyor…")
    data = fetch_data(DEFAULT_TICKERS, pb)
    pb.empty()

    if data.empty:
        st.error("Hiç veri alınamadı.")
        st.stop()

    # ── Özet metrikler ──────────────────────────────────────────────────────
    total     = len(data)
    guclu     = len(data[data['Sinyal'] == '🔥 GÜÇLÜ AL'])
    al        = len(data[data['Sinyal'] == '🟢 AL'])
    tv_onay   = len(data[data['TV Onay'] == '⭐ ONAY'])
    avg_score = int(data['Skor /100'].mean())

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, value, css in [
        (c1, "Taranan Hisse", total,     ""),
        (c2, "Güçlü AL",      guclu,     "score-high"),
        (c3, "AL Sinyali",    al,        "score-mid"),
        (c4, "TV Onaylı ⭐",  tv_onay,   "score-high"),
        (c5, "Ort. Skor",     avg_score, "score-high" if avg_score >= 50 else "score-low"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="label">{label}</div>
                <div class="value {css}">{value}</div>
            </div>""", unsafe_allow_html=True)

    # ── Filtre uygula ───────────────────────────────────────────────────────
    filtered = data[
        (data['Skor /100']  >= min_score) &
        (data['RVOL']       >= min_rvol) &
        (data['ATR %']      >= min_atr) &
        (data['Günlük %']   >= max_daily_drop) &
        (~data['Sinyal'].str.contains('Geç'))
    ]
    if only_trend:
        filtered = filtered[filtered['Trend'] == '↑ Yükseliş']
    if only_tv:
        filtered = filtered[filtered['TV Onay'] == '⭐ ONAY']

    filtered = filtered.sort_values(['TV Onay', 'Skor /100'], ascending=[False, False]).reset_index(drop=True)

    # ── Her iki tarayıcıda da çıkanlar — ALTIN LİSTE ────────────────────────
    st.markdown('<div class="section-title">⭐ ALTIN LİSTE — Her İki Tarayıcı Onayladı</div>', unsafe_allow_html=True)

    altin = filtered[filtered['TV Onay'] == '⭐ ONAY']

    if altin.empty:
        st.info("Bugün her iki tarayıcıdan da geçen hisse yok. Filtreler gevşetilebilir.")
    else:
        st.success(f"✅ {len(altin)} hisse hem Streamlit hem TradingView filtrelerini geçti!")

        # TradingView'da tek tıkla aç
        tv_symbols = ",".join([f"BIST:{h}" for h in altin['Hisse'].tolist()])
        tv_url = f"https://tr.tradingview.com/chart/?symbol=BIST:{altin['Hisse'].iloc[0]}"
        st.markdown(f'<a href="{tv_url}" target="_blank" class="tv-link">📊 TradingView\'da Aç →</a>', unsafe_allow_html=True)

        def style_altin(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            for i, row in df.iterrows():
                for col in df.columns:
                    styles.at[i, col] = 'background-color:#0d2016'
                styles.at[i, 'Skor /100'] = 'background-color:#1a3a22; color:#3fb950; font-weight:700'
                styles.at[i, 'TV Onay']   = 'background-color:#1a3a22; color:#f0c040; font-weight:700'
                styles.at[i, 'Sinyal']    = 'background-color:#1a3a22; color:#3fb950'
                if row['Günlük %'] > 0: styles.at[i, 'Günlük %'] = 'color:#3fb950; background-color:#0d2016'
                elif row['Günlük %'] < 0: styles.at[i, 'Günlük %'] = 'color:#f85149; background-color:#0d2016'
                if row['RVOL'] >= 1.5: styles.at[i, 'RVOL'] = 'color:#3fb950; font-weight:600; background-color:#0d2016'
            return styles

        st.dataframe(
            altin.style.apply(style_altin, axis=None),
            use_container_width=True,
            height=min(400, 36 * (len(altin) + 1) + 20)
        )

        # Her hisse için ayrı TradingView linki
        st.markdown("**Grafikleri aç:**")
        link_cols = st.columns(min(len(altin), 6))
        for i, (_, row) in enumerate(altin.iterrows()):
            with link_cols[i % len(link_cols)]:
                tv_link = f"https://tr.tradingview.com/chart/?symbol=BIST:{row['Hisse']}"
                st.markdown(f'<a href="{tv_link}" target="_blank" class="tv-link">📈 {row["Hisse"]}</a>', unsafe_allow_html=True)

    # ── Filtreli tüm sonuçlar ───────────────────────────────────────────────
    st.markdown('<div class="section-title">🎯 Bugünkü Fırsatlar (Tüm Filtreler)</div>', unsafe_allow_html=True)

    if filtered.empty:
        st.warning("Eşleşen hisse yok. Sol panelden filtreleri gevşet.")
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
                if row['TV Onay'] == '⭐ ONAY':
                    styles.at[i, 'TV Onay'] = 'background-color:#2a2000; color:#f0c040; font-weight:700'
                    styles.at[i, 'TV /7']   = 'color:#f0c040; font-weight:700'
                if row['Günlük %'] > 0: styles.at[i, 'Günlük %'] = 'color:#3fb950'
                elif row['Günlük %'] < 0: styles.at[i, 'Günlük %'] = 'color:#f85149'
                if row['RVOL'] >= 1.5: styles.at[i, 'RVOL'] = 'color:#3fb950; font-weight:600'
                if row['ATR %'] >= 1.8: styles.at[i, 'ATR %'] = 'color:#3fb950'
                elif row['ATR %'] < 1.2: styles.at[i, 'ATR %'] = 'color:#f85149'
            return styles

        st.dataframe(
            filtered.style.apply(style_table, axis=None),
            use_container_width=True,
            height=min(600, 36 * (len(filtered) + 1) + 20)
        )

    # ── Tüm sonuçlar ───────────────────────────────────────────────────────
    with st.expander("📊 Tüm Tarama Sonuçları", expanded=False):
        st.dataframe(
            data.sort_values(['TV Onay', 'Skor /100'], ascending=[False, False]),
            use_container_width=True
        )

    st.markdown("---")
    st.markdown("""
> **⚠️ Risk Notu:** Bu araç yalnızca teknik analiz filtresi sunar.  
> Her işlemde stop-loss kullan (%1.5 önerilir). Yatırım tavsiyesi değildir.
    """)
