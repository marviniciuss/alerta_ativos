import yfinance as yf
import requests
import json
import os
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ==============================================================================

import os

# Agora o script busca as informações nas variáveis de ambiente do servidor
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Descobre a pasta exata onde este arquivo .py está salvo
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

# Força o Python a salvar o JSON dentro dessa mesma pasta
ARQUIVO_LOG = os.path.join(DIRETORIO_ATUAL, "log_alertas.json")

# Ativos e parâmetros personalizados
ATIVOS_PARA_MONITORAR = {
    "IVVB11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "DIVO11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "NSDV11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "HGLG11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "VISC11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "RBRR11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "KNCR11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "KNSC11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "RBVA11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "WEGE3.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "ALUP11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "KLBN4.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "HASH11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10},
    "HODL11.SA": {"rsi_compra": 30, "rsi_venda": 75, "drawdown_max": -0.10}
}

# ==============================================================================
# 2. FUNÇÕES DE APOIO
# ==============================================================================

def carregar_log():
    if not os.path.exists(ARQUIVO_LOG): return {}
    with open(ARQUIVO_LOG, 'r') as f: return json.load(f)

def salvar_log(log):
    with open(ARQUIVO_LOG, 'w') as f: json.dump(log, f)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def formatar_distancia(dist):
    """Formata a diferença percentual com cor e sinal"""
    icone = "🟢" if dist > 0 else "🔴"
    # O :+.1% força o Python a colocar o sinal de + ou - antes do número
    return f"{icone} {dist:+.1%}"

# ==============================================================================
# 3. NÚCLEO DE INTELIGÊNCIA (ANÁLISE DE TENDÊNCIA)
# ==============================================================================

def calcular_rsi(data, window=14):
    delta = data.diff()
    ganho = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    perda = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = ganho / perda
    return 100 - (100 / (1 + rs))

def analisar():
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    log = carregar_log()
    alertas_enviados = []

    for ticker, config in ATIVOS_PARA_MONITORAR.items():
        if log.get(ticker) == hoje_str: continue

        try:
            acao = yf.Ticker(ticker)
            df = acao.history(period="2y") 
            if df.empty or len(df) < 200: continue

            # --- CÁLCULO DAS MÉTRICAS (HOJE E ONTEM) ---
            preco_atual = df['Close'].iloc[-1]
            maxima_ano = df['High'].max()
            queda_da_maxima = (preco_atual / maxima_ano) - 1
            
            # Médias de hoje
            sma21_hoje = df['Close'].rolling(window=21).mean().iloc[-1]
            sma50_hoje = df['Close'].rolling(window=50).mean().iloc[-1]
            sma200_hoje = df['Close'].rolling(window=200).mean().iloc[-1]
            
            # Médias de ontem
            sma50_ontem = df['Close'].rolling(window=50).mean().iloc[-2]
            sma200_ontem = df['Close'].rolling(window=200).mean().iloc[-2]

            df['RSI'] = calcular_rsi(df['Close'])
            rsi_atual = df['RSI'].iloc[-1]

            # --- LÓGICA DE DISTÂNCIA E TENDÊNCIA ---
            dist_21 = (preco_atual / sma21_hoje) - 1
            dist_50 = (preco_atual / sma50_hoje) - 1
            dist_200 = (preco_atual / sma200_hoje) - 1
            
            tendencia_atual = "📈 ALTA" if sma50_hoje > sma200_hoje else "📉 BAIXA"

            # --- LÓGICA DE CRUZAMENTO (GATILHOS) ---
            cruzamento_msg = ""
            tipo_alerta = ""
            icone = "🔍"

            if sma50_ontem <= sma200_ontem and sma50_hoje > sma200_hoje:
                cruzamento_msg = "🌟 *GOLDEN CROSS DETECTADO!* (Tendência de Alta confirmada)"
                tipo_alerta = "COMPRA FORTE"
                icone = "🚀"

            elif sma50_ontem >= sma200_ontem and sma50_hoje < sma200_hoje:
                cruzamento_msg = "💀 *DEATH CROSS DETECTADO!* (Tendência de Baixa iniciada)"
                tipo_alerta = "VENDA/ALERTA"
                icone = "⚠️"

            # 3. Gatilhos Auxiliares (RSI e Drawdown)
            gatilhos = []
            if rsi_atual <= config['rsi_compra']: gatilhos.append(f"RSI Baixo ({rsi_atual:.1f})")
            if queda_da_maxima <= config['drawdown_max']: gatilhos.append(f"Queda Real ({queda_da_maxima:.1%})")

            # --- DISPARO DO ALERTA ---
            if cruzamento_msg or gatilhos:
                status = cruzamento_msg if cruzamento_msg else f"Gatilho: {' e '.join(gatilhos)}"
                if not tipo_alerta: tipo_alerta = "OPORTUNIDADE"
                
                msg = (f"{icone} *ALERTA DE {tipo_alerta}: {ticker}*\n"
                       f"📢 {status}\n\n"
                       f"💵 *Preço Atual:* R$ {preco_atual:.2f}\n"
                       f"---------------------------\n"
                       f"🧭 *Tendência Primária:* {tendencia_atual}\n"
                       f"📊 *Raio-X de Médias:*\n"
                       f"🔹 21d (Curto): R$ {sma21_hoje:.2f} [{formatar_distancia(dist_21)}]\n"
                       f"🔹 50d (Médio): R$ {sma50_hoje:.2f} [{formatar_distancia(dist_50)}]\n"
                       f"🔹 200d (Longo): R$ {sma200_hoje:.2f} [{formatar_distancia(dist_200)}]\n"
                       f"---------------------------\n"
                       f"📉 *Distância do Topo:* {queda_da_maxima:.1%}")

                enviar_telegram(msg)
                log[ticker] = hoje_str
                alertas_enviados.append(ticker)

        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")

    salvar_log(log)
    return alertas_enviados

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Analisando tendências...")
    analisados = analisar()
    print(f"Processo finalizado. Alertas: {analisados}")