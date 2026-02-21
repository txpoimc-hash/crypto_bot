# crypto_bot.py - Bot per crypto trading e alert (Versione Telegram Completa)

import asyncio
import aiohttp
import pandas as pd
import numpy as np
import uuid
import talib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from enum import Enum

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Platform(Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"
    BOTH = "both"

class CryptoTradingBot:
    """Bot per monitoraggio crypto, alert e trading automation"""
    
    def __init__(self, bot_core):
        self.core = bot_core
        self.logger = logging.getLogger(__name__)
        
        # Exchange connections
        self.exchanges = {
            'binance': {
                'api_url': 'https://api.binance.com/api/v3',
                'ws_url': 'wss://stream.binance.com:9443/ws',
                'api_key': self.core.config.get('binance_api_key', ''),
                'api_secret': self.core.config.get('binance_api_secret', '')
            },
            'coinbase': {
                'api_url': 'https://api.pro.coinbase.com',
                'ws_url': 'wss://ws-feed.pro.coinbase.com',
                'api_key': self.core.config.get('coinbase_api_key', ''),
                'api_secret': self.core.config.get('coinbase_api_secret', '')
            },
            'kraken': {
                'api_url': 'https://api.kraken.com/0/public',
                'ws_url': 'wss://ws.kraken.com',
                'api_key': self.core.config.get('kraken_api_key', ''),
                'api_secret': self.core.config.get('kraken_api_secret', '')
            }
        }
        
        # Market data cache
        self.price_cache = {}
        self.ohlcv_cache = {}
        self.indicators_cache = {}
        
        # User alerts
        self.alerts = {}
        
        # Trading signals
        self.signals = {}
        
        # Popular coins list
        self.popular_coins = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
            'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT',
            'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'BCHUSDT'
        ]
        
    async def register_commands(self):
        """Registra comandi crypto per Telegram"""
        
        from telegram.ext import CommandHandler, CallbackQueryHandler
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Handler per comandi principali
        self.core.telegram_app.add_handler(CommandHandler("price", self.telegram_price))
        self.core.telegram_app.add_handler(CommandHandler("crypto", self.telegram_crypto_list))
        self.core.telegram_app.add_handler(CommandHandler("alert", self.telegram_alert))
        self.core.telegram_app.add_handler(CommandHandler("alerts", self.telegram_list_alerts))
        self.core.telegram_app.add_handler(CommandHandler("rsi", self.telegram_rsi))
        self.core.telegram_app.add_handler(CommandHandler("macd", self.telegram_macd))
        self.core.telegram_app.add_handler(CommandHandler("trend", self.telegram_trend))
        self.core.telegram_app.add_handler(CommandHandler("signal", self.telegram_signal))
        self.core.telegram_app.add_handler(CommandHandler("portfolio", self.telegram_portfolio))
        self.core.telegram_app.add_handler(CommandHandler("addcoin", self.telegram_add_coin))
        self.core.telegram_app.add_handler(CommandHandler("removecoin", self.telegram_remove_coin))
        self.core.telegram_app.add_handler(CommandHandler("market", self.telegram_market_overview))
        self.core.telegram_app.add_handler(CommandHandler("feargreed", self.telegram_fear_greed))
        self.core.telegram_app.add_handler(CommandHandler("dominance", self.telegram_dominance))
        self.core.telegram_app.add_handler(CommandHandler("gas", self.telegram_gas_fees))
        
        logger.info("Crypto bot commands registered for Telegram")
    
    async def telegram_price(self, update, context):
        """Handler per comando /price"""
        symbol = context.args[0].upper() if context.args else "BTCUSDT"
        await self.get_price(update, symbol, Platform.TELEGRAM)
    
    async def telegram_crypto_list(self, update, context):
        """Handler per comando /crypto"""
        await self.list_cryptos(update, Platform.TELEGRAM)
    
    async def telegram_alert(self, update, context):
        """Handler per comando /alert [simbolo] [prezzo] [above/below]"""
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Formato: /alert <simbolo> <prezzo> [above/below]\n"
                "Esempio: /alert BTCUSDT 50000 above"
            )
            return
        
        symbol = context.args[0].upper()
        try:
            target_price = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Prezzo non valido")
            return
        
        condition = context.args[2].lower() if len(context.args) > 2 else "above"
        if condition not in ["above", "below"]:
            condition = "above"
        
        await self.set_alert(update, symbol, target_price, condition, Platform.TELEGRAM)
    
    async def telegram_list_alerts(self, update, context):
        """Handler per comando /alerts"""
        await self.list_alerts(update, Platform.TELEGRAM)
    
    async def telegram_rsi(self, update, context):
        """Handler per comando /rsi [simbolo] [periodo]"""
        symbol = context.args[0].upper() if context.args else "BTCUSDT"
        period = int(context.args[1]) if len(context.args) > 1 else 14
        await self.calculate_rsi(update, symbol, period, Platform.TELEGRAM)
    
    async def telegram_macd(self, update, context):
        """Handler per comando /macd [simbolo]"""
        symbol = context.args[0].upper() if context.args else "BTCUSDT"
        await self.calculate_macd(update, symbol, Platform.TELEGRAM)
    
    async def telegram_trend(self, update, context):
        """Handler per comando /trend [simbolo]"""
        symbol = context.args[0].upper() if context.args else "BTCUSDT"
        await self.analyze_trend(update, symbol, Platform.TELEGRAM)
    
    async def telegram_signal(self, update, context):
        """Handler per comando /signal [simbolo]"""
        symbol = context.args[0].upper() if context.args else "BTCUSDT"
        await self.generate_signal(update, symbol, Platform.TELEGRAM)
    
    async def telegram_portfolio(self, update, context):
        """Handler per comando /portfolio - mostra il portfolio dell'utente"""
        await self.show_portfolio(update, Platform.TELEGRAM)
    
    async def telegram_add_coin(self, update, context):
        """Handler per comando /addcoin [simbolo] [quantità] [prezzo_acquisto]"""
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Formato: /addcoin <simbolo> <quantità> <prezzo_acquisto>\n"
                "Esempio: /addcoin BTCUSDT 0.5 45000"
            )
            return
        
        symbol = context.args[0].upper()
        try:
            quantity = float(context.args[1])
            buy_price = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Quantità o prezzo non validi")
            return
        
        await self.add_to_portfolio(update, symbol, quantity, buy_price, Platform.TELEGRAM)
    
    async def telegram_remove_coin(self, update, context):
        """Handler per comando /removecoin [simbolo]"""
        if not context.args:
            await update.message.reply_text("❌ Formato: /removecoin <simbolo>")
            return
        
        symbol = context.args[0].upper()
        await self.remove_from_portfolio(update, symbol, Platform.TELEGRAM)
    
    async def telegram_market_overview(self, update, context):
        """Handler per comando /market - overview mercato crypto"""
        await self.market_overview(update, Platform.TELEGRAM)
    
    async def telegram_fear_greed(self, update, context):
        """Handler per comando /feargreed - indice paura/avidità"""
        await self.fear_greed_index(update, Platform.TELEGRAM)
    
    async def telegram_dominance(self, update, context):
        """Handler per comando /dominance - dominance BTC/ETH"""
        await self.market_dominance(update, Platform.TELEGRAM)
    
    async def telegram_gas_fees(self, update, context):
        """Handler per comando /gas - gas fees Ethereum"""
        await self.eth_gas_fees(update, Platform.TELEGRAM)
    
    async def get_price(self, update, symbol: str, platform: Platform):
        """Ottiene prezzo attuale e variazioni"""
        
        try:
            # Tenta cache
            if symbol in self.price_cache:
                cached = self.price_cache[symbol]
                if datetime.now().timestamp() - cached['timestamp'] < 30:
                    price_data = cached
                else:
                    price_data = await self.fetch_price(symbol)
            else:
                price_data = await self.fetch_price(symbol)
            
            # Formatta output
            change_emoji = "📈" if price_data['change_24h'] > 0 else "📉" if price_data['change_24h'] < 0 else "➡️"
            
            message = (
                f"**{symbol} Price Info** {change_emoji}\n\n"
                f"💰 **Prezzo:** ${price_data['price']:,.2f}\n"
                f"📊 **24h Change:** {price_data['change_24h']:+.2f}%\n"
                f"📈 **24h High:** ${price_data['high_24h']:,.2f}\n"
                f"📉 **24h Low:** ${price_data['low_24h']:,.2f}\n"
                f"📦 **24h Volume:** {price_data['volume']:,.0f} {symbol.replace('USDT', '')}\n"
                f"🏆 **Rank:** #{price_data.get('rank', 'N/A')}\n"
                f"🌐 **Market Cap:** ${price_data.get('market_cap', 0):,.0f}\n\n"
                f"🕒 Last Update: {datetime.fromtimestamp(price_data['timestamp']).strftime('%H:%M:%S')}"
            )
            
            await self.send_message(update, message, platform)
            
        except Exception as e:
            self.logger.error(f"Error in get_price: {e}")
            await self.send_message(update, f"❌ Errore: {str(e)}", platform)
    
    async def fetch_price(self, symbol: str) -> Dict:
        """Fetch prezzo da exchange multipli"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # Binance
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        price_data = {
                            'symbol': symbol,
                            'price': float(data['lastPrice']),
                            'change_24h': float(data['priceChangePercent']),
                            'high_24h': float(data['highPrice']),
                            'low_24h': float(data['lowPrice']),
                            'volume': float(data['volume']),
                            'quote_volume': float(data['quoteVolume']),
                            'timestamp': datetime.now().timestamp(),
                            'rank': None,
                            'market_cap': 0
                        }
                        
                        # Aggiungi market cap da CoinGecko
                        coin = symbol.replace('USDT', '').lower()
                        gecko_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true"
                        async with session.get(gecko_url) as gecko_resp:
                            if gecko_resp.status == 200:
                                gecko_data = await gecko_resp.json()
                                if coin in gecko_data:
                                    price_data['market_cap'] = gecko_data[coin].get('usd_market_cap', 0)
                        
                        # Cache
                        self.price_cache[symbol] = price_data
                        return price_data
                        
            except Exception as e:
                self.logger.warning(f"Binance fetch failed for {symbol}: {e}")
                # Fallback a CoinGecko
                coin = symbol.replace('USDT', '').lower()
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true"
                
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if coin in data:
                            coin_data = data[coin]
                            return {
                                'symbol': symbol,
                                'price': coin_data['usd'],
                                'change_24h': coin_data.get('usd_24h_change', 0),
                                'high_24h': 0,
                                'low_24h': 0,
                                'volume': coin_data.get('usd_24h_vol', 0),
                                'quote_volume': 0,
                                'market_cap': coin_data.get('usd_market_cap', 0),
                                'timestamp': datetime.now().timestamp(),
                                'rank': None
                            }
            
            raise Exception(f"Symbol {symbol} not found")
    
    async def list_cryptos(self, update, platform: Platform):
        """Mostra lista criptovalute popolari con prezzi"""
        
        message = "**📊 TOP CRYPTOCURRENCIES**\n\n"
        
        tasks = []
        for symbol in self.popular_coins[:10]:  # Limita a 10
            tasks.append(self.fetch_price(symbol))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                change_emoji = "🟢" if result['change_24h'] > 0 else "🔴" if result['change_24h'] < 0 else "⚪"
                message += (
                    f"{change_emoji} **{result['symbol']}**\n"
                    f"   💰 ${result['price']:,.2f} | {result['change_24h']:+.2f}%\n"
                )
        
        message += "\n💡 Usa /price <simbolo> per dettagli"
        
        await self.send_message(update, message, platform)
    
    async def set_alert(self, update, symbol: str, target_price: float, condition: str, platform: Platform):
        """Imposta alert di prezzo"""
        
        user_id = str(update.effective_user.id)
        
        # Verifica prezzo attuale
        try:
            price_data = await self.fetch_price(symbol)
            current_price = price_data['price']
        except Exception as e:
            await self.send_message(update, f"❌ Symbol {symbol} non trovato", platform)
            return
        
        # Crea alert
        alert_id = str(uuid.uuid4())[:8]
        
        alert = {
            'id': alert_id,
            'user_id': user_id,
            'symbol': symbol,
            'target_price': target_price,
            'condition': condition,
            'current_price': current_price,
            'created_at': datetime.now().isoformat(),
            'triggered': False,
            'platform': platform.value,
            'chat_id': str(update.effective_chat.id)
        }
        
        # Salva
        if user_id not in self.alerts:
            self.alerts[user_id] = []
        self.alerts[user_id].append(alert)
        
        await self.send_message(update,
            f"🔔 **Alert impostato!**\n"
            f"ID: `{alert_id}`\n"
            f"{symbol}: ti avviserò quando il prezzo sarà {condition} ${target_price:,.2f}\n"
            f"Prezzo attuale: ${current_price:,.2f}",
            platform
        )
        
        # Avvia monitoraggio
        asyncio.create_task(self.monitor_alert(alert))
    
    async def list_alerts(self, update, platform: Platform):
        """Mostra lista alert attivi"""
        
        user_id = str(update.effective_user.id)
        
        if user_id not in self.alerts or not self.alerts[user_id]:
            await self.send_message(update, "🔔 Nessun alert attivo", platform)
            return
        
        message = "**🔔 I TUOI ALERT ATTIVI**\n\n"
        
        for alert in self.alerts[user_id]:
            if not alert['triggered']:
                status = "🟢 Attivo"
                message += (
                    f"`{alert['id']}` **{alert['symbol']}**\n"
                    f"   Target: {alert['condition']} ${alert['target_price']:,.2f}\n"
                    f"   Attuale: ${alert['current_price']:,.2f}\n"
                    f"   Status: {status}\n\n"
                )
        
        await self.send_message(update, message, platform)
    
    async def monitor_alert(self, alert: Dict):
        """Monitora alert in background"""
        
        while not alert['triggered']:
            try:
                price_data = await self.fetch_price(alert['symbol'])
                current_price = price_data['price']
                
                # Verifica condizione
                triggered = False
                if alert['condition'] == 'above' and current_price >= alert['target_price']:
                    triggered = True
                elif alert['condition'] == 'below' and current_price <= alert['target_price']:
                    triggered = True
                
                if triggered:
                    alert['triggered'] = True
                    
                    # Invia notifica Telegram
                    from telegram import Bot
                    bot = Bot(token=self.core.config['telegram_token'])
                    
                    await bot.send_message(
                        chat_id=int(alert['chat_id']),
                        text=(
                            f"🔔 **ALERT ATTIVATO!**\n"
                            f"{alert['symbol']} ha raggiunto ${current_price:,.2f}\n"
                            f"Target: {alert['condition']} ${alert['target_price']:,.2f}"
                        ),
                        parse_mode='Markdown'
                    )
                    
                    break
                
            except Exception as e:
                self.logger.error(f"Alert monitor error: {e}")
            
            await asyncio.sleep(60)  # Controlla ogni minuto
    
    async def fetch_ohlcv(self, symbol: str, interval: str = '1h', limit: int = 100) -> List:
        """Fetch OHLCV data da Binance"""
        
        cache_key = f"{symbol}_{interval}_{limit}"
        if cache_key in self.ohlcv_cache:
            cached = self.ohlcv_cache[cache_key]
            if datetime.now().timestamp() - cached['timestamp'] < 300:  # 5 min cache
                return cached['data']
        
        async with aiohttp.ClientSession() as session:
            try:
                url = f"https://api.binance.com/api/v3/klines"
                params = {
                    'symbol': symbol,
                    'interval': interval,
                    'limit': limit
                }
                
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Cache
                        self.ohlcv_cache[cache_key] = {
                            'data': data,
                            'timestamp': datetime.now().timestamp()
                        }
                        
                        return data
                        
            except Exception as e:
                self.logger.error(f"OHLCV fetch error for {symbol}: {e}")
                return []
    
    async def calculate_rsi(self, update, symbol: str, period: int, platform: Platform):
        """Calcola RSI (Relative Strength Index)"""
        
        # Ottieni dati OHLCV
        ohlcv = await self.fetch_ohlcv(symbol, '1h', 100)
        
        if not ohlcv or len(ohlcv) < period:
            await self.send_message(update, f"❌ Dati insufficienti per calcolare RSI", platform)
            return
        
        # Estrai prezzi di chiusura
        closes = np.array([float(c[4]) for c in ohlcv])
        
        # Calcola RSI
        rsi_values = talib.RSI(closes, timeperiod=period)
        
        # Filtra NaN
        rsi_values = rsi_values[~np.isnan(rsi_values)]
        
        if len(rsi_values) == 0:
            await self.send_message(update, f"❌ Impossibile calcolare RSI", platform)
            return
        
        current_rsi = rsi_values[-1]
        
        # Calcola RSI precedenti per trend
        rsi_1h_ago = rsi_values[-2] if len(rsi_values) > 1 else current_rsi
        rsi_24h_ago = rsi_values[-24] if len(rsi_values) > 24 else current_rsi
        
        # Interpretazione
        if current_rsi >= 70:
            signal = "🔴 **SOVRACOMPRATO** - Possibile inversione al ribasso"
            emoji = "⚠️"
        elif current_rsi <= 30:
            signal = "🟢 **SOVRAVENDUTO** - Possibile inversione al rialzo"
            emoji = "💎"
        else:
            signal = "⚪ Neutro"
            emoji = "➡️"
        
        # Trend
        trend_1h = "↗️ in salita" if current_rsi > rsi_1h_ago else "↘️ in discesa"
        trend_24h = "↗️ in salita" if current_rsi > rsi_24h_ago else "↘️ in discesa"
        
        message = (
            f"**📊 RSI - {symbol}** {emoji}\n"
            f"Periodo: {period}\n\n"
            f"**RSI Attuale:** {current_rsi:.2f}\n"
            f"**Segnale:** {signal}\n\n"
            f"**Trend:**\n"
            f"• 1h: {trend_1h}\n"
            f"• 24h: {trend_24h}\n\n"
            f"💡 RSI >70 = ipercomprato, <30 = ipervenduto"
        )
        
        await self.send_message(update, message, platform)
    
    async def calculate_macd(self, update, symbol: str, platform: Platform):
        """Calcola MACD (Moving Average Convergence Divergence)"""
        
        # Ottieni dati OHLCV
        ohlcv = await self.fetch_ohlcv(symbol, '1h', 100)
        
        if not ohlcv or len(ohlcv) < 26:
            await self.send_message(update, f"❌ Dati insufficienti per calcolare MACD", platform)
            return
        
        # Estrai prezzi di chiusura
        closes = np.array([float(c[4]) for c in ohlcv])
        
        # Calcola MACD
        macd, signal, hist = talib.MACD(
            closes,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )
        
        # Filtra NaN
        macd = macd[~np.isnan(macd)]
        signal = signal[~np.isnan(signal)]
        hist = hist[~np.isnan(hist)]
        
        if len(macd) == 0:
            await self.send_message(update, f"❌ Impossibile calcolare MACD", platform)
            return
        
        current_macd = macd[-1]
        current_signal = signal[-1]
        current_hist = hist[-1]
        
        # Interpretazione
        if current_macd > current_signal:
            if current_hist > 0:
                signal_text = "🟢 **SEGNALE BULLISH** - Momentum positivo in aumento"
                emoji = "🚀"
            else:
                signal_text = "🟡 **SEGNALE DEBOLE** - MACD sopra Signal ma istogramma negativo"
                emoji = "⚠️"
        else:
            if current_hist < 0:
                signal_text = "🔴 **SEGNALE BEARISH** - Momentum negativo in aumento"
                emoji = "📉"
            else:
                signal_text = "🟡 **SEGNALE DEBOLE** - MACD sotto Signal ma istogramma positivo"
                emoji = "⚠️"
        
        # Crossover recente
        if len(hist) >= 2:
            if hist[-1] > 0 and hist[-2] <= 0:
                crossover = "🟢 Crossover rialzista recente!"
            elif hist[-1] < 0 and hist[-2] >= 0:
                crossover = "🔴 Crossover ribassista recente!"
            else:
                crossover = "Nessun crossover recente"
        else:
            crossover = "Dati insufficienti"
        
        message = (
            f"**📈 MACD - {symbol}** {emoji}\n\n"
            f"**MACD Line:** {current_macd:.4f}\n"
            f"**Signal Line:** {current_signal:.4f}\n"
            f"**Histogram:** {current_hist:.4f}\n\n"
            f"**Segnale:** {signal_text}\n"
            f"**Crossover:** {crossover}\n\n"
            f"💡 MACD > Signal = rialzista, MACD < Signal = ribassista"
        )
        
        await self.send_message(update, message, platform)
    
    async def analyze_trend(self, update, symbol: str, platform: Platform):
        """Analisi trend completa"""
        
        # Ottieni dati OHLCV
        ohlcv = await self.fetch_ohlcv(symbol, '1h', 200)
        
        if not ohlcv or len(ohlcv) < 50:
            await self.send_message(update, f"❌ Dati insufficienti per analisi trend", platform)
            return
        
        # Estrai prezzi
        closes = np.array([float(c[4]) for c in ohlcv])
        highs = np.array([float(c[2]) for c in ohlcv])
        lows = np.array([float(c[3]) for c in ohlcv])
        
        # Calcola medie mobili
        sma_20 = talib.SMA(closes, timeperiod=20)
        sma_50 = talib.SMA(closes, timeperiod=50)
        sma_200 = talib.SMA(closes, timeperiod=200)
        
        # Calcola Bollinger Bands
        upper, middle, lower = talib.BBANDS(closes, timeperiod=20, nbdevup=2, nbdevdn=2)
        
        # Calcola supporto e resistenza
        recent_high = np.max(highs[-20:])
        recent_low = np.min(lows[-20:])
        
        # Trend direction
        current_price = closes[-1]
        
        # Trend a breve termine (20 SMA)
        if not np.isnan(sma_20[-1]):
            if current_price > sma_20[-1]:
                short_trend = "🟢 RIALZISTA"
                short_emoji = "↗️"
            else:
                short_trend = "🔴 RIBASSISTA"
                short_emoji = "↘️"
        else:
            short_trend = "⚪ ND"
            short_emoji = "➡️"
        
        # Trend a medio termine (50 SMA)
        if not np.isnan(sma_50[-1]):
            if current_price > sma_50[-1]:
                medium_trend = "🟢 RIALZISTA"
            else:
                medium_trend = "🔴 RIBASSISTA"
        else:
            medium_trend = "⚪ ND"
        
        # Trend a lungo termine (200 SMA)
        if not np.isnan(sma_200[-1]):
            if current_price > sma_200[-1]:
                long_trend = "🟢 RIALZISTA"
            else:
                long_trend = "🔴 RIBASSISTA"
        else:
            long_trend = "⚪ ND"
        
        # Golden/Death Cross
        if not np.isnan(sma_50[-1]) and not np.isnan(sma_200[-1]):
            if sma_50[-1] > sma_200[-1] and sma_50[-2] <= sma_200[-2]:
                cross_signal = "🟢 **GOLDEN CROSS** - Forte segnale rialzista!"
            elif sma_50[-1] < sma_200[-1] and sma_50[-2] >= sma_200[-2]:
                cross_signal = "🔴 **DEATH CROSS** - Forte segnale ribassista!"
            else:
                cross_signal = "⚪ Nessun crossover"
        else:
            cross_signal = "⚪ Dati insufficienti"
        
        # Bollinger position
        if not np.isnan(upper[-1]) and not np.isnan(lower[-1]):
            if current_price >= upper[-1]:
                bb_position = "🔴 Sopra Banda Superiore (ipercomprato)"
            elif current_price <= lower[-1]:
                bb_position = "🟢 Sotto Banda Inferiore (ipervenduto)"
            else:
                bb_position = "⚪ Dentro le Bande"
        else:
            bb_position = "⚪ ND"
        
        message = (
            f"**📊 ANALISI TREND - {symbol}**\n\n"
            f"**Prezzo Attuale:** ${current_price:,.2f}\n\n"
            f"**Trend:**\n"
            f"• Breve (20 SMA): {short_trend} {short_emoji}\n"
            f"• Medio (50 SMA): {medium_trend}\n"
            f"• Lungo (200 SMA): {long_trend}\n\n"
            f"**Indicatori:**\n"
            f"• {cross_signal}\n"
            f"• Bollinger: {bb_position}\n"
            f"• Supporto: ${recent_low:,.2f}\n"
            f"• Resistenza: ${recent_high:,.2f}\n\n"
            f"💡 Usa /rsi e /macd per analisi più dettagliate"
        )
        
        await self.send_message(update, message, platform)
    
    async def generate_signal(self, update, symbol: str, platform: Platform):
        """Genera segnale di trading combinato"""
        
        # Ottieni dati
        ohlcv = await self.fetch_ohlcv(symbol, '1h', 200)
        
        if not ohlcv or len(ohlcv) < 50:
            await self.send_message(update, f"❌ Dati insufficienti per generare segnale", platform)
            return
        
        closes = np.array([float(c[4]) for c in ohlcv])
        
        # Calcola indicatori
        rsi = talib.RSI(closes, timeperiod=14)
        macd, signal, hist = talib.MACD(closes)
        upper, middle, lower = talib.BBANDS(closes, timeperiod=20)
        sma_20 = talib.SMA(closes, timeperiod=20)
        sma_50 = talib.SMA(closes, timeperiod=50)
        
        current_price = closes[-1]
        current_rsi = rsi[-1] if not np.isnan(rsi[-1]) else 50
        current_macd = macd[-1] if not np.isnan(macd[-1]) else 0
        current_signal = signal[-1] if not np.isnan(signal[-1]) else 0
        current_hist = hist[-1] if not np.isnan(hist[-1]) else 0
        
        # Calcolo punteggio
        score = 50  # Base
        
        signals = []
        
        # RSI
        if current_rsi < 30:
            score += 15
            signals.append("🟢 RSI ipervenduto (+15)")
        elif current_rsi > 70:
            score -= 15
            signals.append("🔴 RSI ipercomprato (-15)")
        
        # MACD
        if current_macd > current_signal:
            if current_hist > 0:
                score += 10
                signals.append("🟢 MACD bullish (+10)")
            else:
                score += 5
                signals.append("🟡 MACD debolmente bullish (+5)")
        else:
            if current_hist < 0:
                score -= 10
                signals.append("🔴 MACD bearish (-10)")
            else:
                score -= 5
                signals.append("🟡 MACD debolmente bearish (-5)")
        
        # Bollinger
        if not np.isnan(upper[-1]) and not np.isnan(lower[-1]):
            if current_price <= lower[-1]:
                score += 10
                signals.append("🟢 Sotto Bollinger inferiore (+10)")
            elif current_price >= upper[-1]:
                score -= 10
                signals.append("🔴 Sopra Bollinger superiore (-10)")
        
        # Medie mobili
        if not np.isnan(sma_20[-1]):
            if current_price > sma_20[-1]:
                score += 5
                signals.append("🟢 Sopra SMA20 (+5)")
            else:
                score -= 5
                signals.append("🔴 Sotto SMA20 (-5)")
        
        if not np.isnan(sma_50[-1]):
            if current_price > sma_50[-1]:
                score += 5
                signals.append("🟢 Sopra SMA50 (+5)")
            else:
                score -= 5
                signals.append("🔴 Sotto SMA50 (-5)")
        
        # Determina segnale finale
        if score >= 70:
            final_signal = "🟢 **FORTEMENTE RIALZISTA** 🚀"
            action = "💰 **AZIONE:** Considera ENTRATA LONG"
            emoji = "🚀"
        elif score >= 60:
            final_signal = "🟢 **RIALZISTA**"
            action = "💰 **AZIONE:** Opportunità di acquisto"
            emoji = "📈"
        elif score >= 40:
            final_signal = "⚪ **NEUTRO**"
            action = "⏳ **AZIONE:** Attesa, monitorare"
            emoji = "⏳"
        elif score >= 30:
            final_signal = "🔴 **RIBASSISTA**"
            action = "💸 **AZIONE:** Considera VENDITA"
            emoji = "📉"
        else:
            final_signal = "🔴 **FORTEMENTE RIBASSISTA** 💀"
            action = "💸 **AZIONE:** USCITA O SHORT"
            emoji = "💀"
        
        # Costruisci messaggio
        message = (
            f"**📊 SEGNALE TRADING - {symbol}** {emoji}\n\n"
            f"**Prezzo:** ${current_price:,.2f}\n"
            f"**RSI:** {current_rsi:.1f}\n"
            f"**MACD Hist:** {current_hist:.4f}\n\n"
            f"**Punteggio:** {score}/100\n"
            f"**Segnale:** {final_signal}\n"
            f"{action}\n\n"
            f"**Fattori:**\n"
        )
        
        for s in signals[:5]:  # Mostra massimo 5 segnali
            message += f"• {s}\n"
        
        message += f"\n💡 Usa /trend per analisi completa"
        
        await self.send_message(update, message, platform)
    
    async def show_portfolio(self, update, platform: Platform):
        """Mostra portfolio dell'utente"""
        
        user_id = str(update.effective_user.id)
        
        # Recupera portfolio dal database
        portfolio = await self.get_user_portfolio(user_id)
        
        if not portfolio or len(portfolio) == 0:
            await self.send_message(update, 
                "📊 **Portfolio vuoto**\n\n"
                "Aggiungi crypto con /addcoin <simbolo> <quantità> <prezzo_acquisto>",
                platform
            )
            return
        
        message = "**📊 IL TUO PORTFOLIO CRYPTO**\n\n"
        
        total_value = 0
        total_cost = 0
        
        for coin in portfolio:
            try:
                price_data = await self.fetch_price(coin['symbol'])
                current_price = price_data['price']
                
                current_value = coin['quantity'] * current_price
                cost_basis = coin['quantity'] * coin['buy_price']
                profit_loss = current_value - cost_basis
                profit_loss_pct = (profit_loss / cost_basis) * 100 if cost_basis > 0 else 0
                
                total_value += current_value
                total_cost += cost_basis
                
                # Emoji per P/L
                if profit_loss > 0:
                    pl_emoji = "🟢"
                elif profit_loss < 0:
                    pl_emoji = "🔴"
                else:
                    pl_emoji = "⚪"
                
                message += (
                    f"**{coin['symbol']}**\n"
                    f"   Quantità: {coin['quantity']:.4f}\n"
                    f"   Prezzo attuale: ${current_price:,.2f}\n"
                    f"   Prezzo acquisto: ${coin['buy_price']:,.2f}\n"
                    f"   Valore: ${current_value:,.2f}\n"
                    f"   {pl_emoji} P/L: ${profit_loss:,.2f} ({profit_loss_pct:+.1f}%)\n\n"
                )
                
            except Exception as e:
                self.logger.error(f"Portfolio error for {coin['symbol']}: {e}")
                continue
        
        # Totali
        total_pl = total_value - total_cost
        total_pl_pct = (total_pl / total_cost) * 100 if total_cost > 0 else 0
        
        if total_pl > 0:
            total_emoji = "🟢"
        elif total_pl < 0:
            total_emoji = "🔴"
        else:
            total_emoji = "⚪"
        
        message += (
            f"**📈 TOTALI**\n"
            f"   Valore totale: ${total_value:,.2f}\n"
            f"   Costo totale: ${total_cost:,.2f}\n"
            f"   {total_emoji} P/L Totale: ${total_pl:,.2f} ({total_pl_pct:+.1f}%)\n"
        )
        
        await self.send_message(update, message, platform)
    
    async def add_to_portfolio(self, update, symbol: str, quantity: float, buy_price: float, platform: Platform):
        """Aggiunge crypto al portfolio"""
        
        user_id = str(update.effective_user.id)
        
        # Verifica che il simbolo esista
        try:
            await self.fetch_price(symbol)
        except:
            await self.send_message(update, f"❌ Symbol {symbol} non valido", platform)
            return
        
        # Salva nel database
        success = await self.save_portfolio_item(user_id, symbol, quantity, buy_price)
        
        if success:
            await self.send_message(update,
                f"✅ **Aggiunto al portfolio**\n"
                f"{quantity} {symbol} a ${buy_price:,.2f}",
                platform
            )
        else:
            await self.send_message(update, "❌ Errore nel salvare il portfolio", platform)
    
    async def remove_from_portfolio(self, update, symbol: str, platform: Platform):
        """Rimuove crypto dal portfolio"""
        
        user_id = str(update.effective_user.id)
        
        # Rimuovi dal database
        success = await self.delete_portfolio_item(user_id, symbol)
        
        if success:
            await self.send_message(update, f"✅ {symbol} rimosso dal portfolio", platform)
        else:
            await self.send_message(update, f"❌ {symbol} non trovato nel portfolio", platform)
    
    async def market_overview(self, update, platform: Platform):
        """Mostra overview del mercato crypto"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # Global data da CoinGecko
                url = "https://api.coingecko.com/api/v3/global"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        global_data = data['data']
                        
                        message = (
                            f"**🌍 MARKET OVERVIEW**\n\n"
                            f"**Market Cap:** ${global_data['total_market_cap']['usd']:,.0f}\n"
                            f"**24h Volume:** ${global_data['total_volume']['usd']:,.0f}\n"
                            f"**BTC Dominance:** {global_data['market_cap_percentage']['btc']:.1f}%\n"
                            f"**ETH Dominance:** {global_data['market_cap_percentage']['eth']:.1f}%\n"
                            f"**Active Cryptos:** {global_data['active_cryptocurrencies']:,}\n"
                            f"**Active Markets:** {global_data['active_markets']:,}\n"
                            f"**Active Exchanges:** {global_data['active_exchanges']:,}\n\n"
                        )
                        
                        # Top gainers/losers (simulato)
                        message += "**📈 Top Gainers/Losers 24h:**\n"
                        
                        # Prendi prezzi di alcune crypto
                        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
                        tasks = [self.fetch_price(s) for s in symbols]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        for result in results:
                            if isinstance(result, dict):
                                arrow = "🟢" if result['change_24h'] > 0 else "🔴"
                                message += f"{arrow} {result['symbol']}: {result['change_24h']:+.1f}%\n"
                        
                        await self.send_message(update, message, platform)
                        
            except Exception as e:
                self.logger.error(f"Market overview error: {e}")
                await self.send_message(update, "❌ Errore nel recuperare dati di mercato", platform)
    
    async def fear_greed_index(self, update, platform: Platform):
        """Mostra indice paura/avidità"""
        
        async with aiohttp.ClientSession() as session:
            try:
                url = "https://api.alternative.me/fng/"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fng = data['data'][0]
                        
                        value = int(fng['value'])
                        classification = fng['value_classification']
                        
                        # Emoji
                        if value <= 25:
                            emoji = "😱"
                        elif value <= 45:
                            emoji = "😨"
                        elif value <= 55:
                            emoji = "😐"
                        elif value <= 75:
                            emoji = "😊"
                        else:
                            emoji = "🤑"
                        
                        message = (
                            f"**📊 CRYPTO FEAR & GREED INDEX** {emoji}\n\n"
                            f"**Valore:** {value}/100\n"
                            f"**Stato:** {classification}\n\n"
                            f"**Interpretazione:**\n"
                        )
                        
                        if value <= 25:
                            message += "• Estrema paura - Possibile opportunità di acquisto"
                        elif value <= 45:
                            message += "• Paura - Mercato in fase di selling"
                        elif value <= 55:
                            message += "• Neutrale - Mercato in equilibrio"
                        elif value <= 75:
                            message += "• Avidità - Mercato in fase di buying"
                        else:
                            message += "• Estrema avidità - Possibile bolla, attenzione"
                        
                        await self.send_message(update, message, platform)
                        
            except Exception as e:
                self.logger.error(f"Fear & Greed error: {e}")
                await self.send_message(update, "❌ Errore nel recuperare Fear & Greed Index", platform)
    
    async def market_dominance(self, update, platform: Platform):
        """Mostra dominance BTC/ETH"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # Global data
                url = "https://api.coingecko.com/api/v3/global"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        percentages = data['data']['market_cap_percentage']
                        
                        # Prezzi BTC e ETH
                        btc_data = await self.fetch_price('BTCUSDT')
                        eth_data = await self.fetch_price('ETHUSDT')
                        
                        message = (
                            f"**📊 MARKET DOMINANCE**\n\n"
                            f"**Bitcoin (BTC)**\n"
                            f"   Dominance: {percentages['btc']:.1f}%\n"
                            f"   Prezzo: ${btc_data['price']:,.2f}\n"
                            f"   24h: {btc_data['change_24h']:+.1f}%\n\n"
                            f"**Ethereum (ETH)**\n"
                            f"   Dominance: {percentages['eth']:.1f}%\n"
                            f"   Prezzo: ${eth_data['price']:,.2f}\n"
                            f"   24h: {eth_data['change_24h']:+.1f}%\n\n"
                            f"**Altcoin Dominance:** {100 - percentages['btc'] - percentages['eth']:.1f}%\n\n"
                            f"💡 Alta dominance BTC = flight to safety\n"
                            f"💡 Bassa dominance BTC = altseason"
                        )
                        
                        await self.send_message(update, message, platform)
                        
            except Exception as e:
                self.logger.error(f"Dominance error: {e}")
                await self.send_message(update, "❌ Errore nel recuperare dominance", platform)
    
    async def eth_gas_fees(self, update, platform: Platform):
        """Mostra gas fees Ethereum"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # Etherscan Gas Tracker API (gratuita)
                url = "https://api.etherscan.io/api"
                params = {
                    'module': 'gastracker',
                    'action': 'gasoracle',
                    'apikey': self.core.config.get('etherscan_api_key', 'YourApiKeyToken')
                }
                
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['status'] == '1':
                            result = data['result']
                            
                            message = (
                                f"**⛽ ETH GAS FEES**\n\n"
                                f"**Low:** {result['SafeGasPrice']} Gwei\n"
                                f"**Average:** {result['ProposeGasPrice']} Gwei\n"
                                f"**High:** {result['FastGasPrice']} Gwei\n\n"
                                f"**Recommended:**\n"
                                f"• Standard TX: {result['ProposeGasPrice']} Gwei\n"
                                f"• Urgent TX: {result['FastGasPrice']} Gwei\n\n"
                                f"💡 Basse gas fees = buon momento per transazioni"
                            )
                            
                            await self.send_message(update, message, platform)
                        else:
                            # Fallback a valori simulati
                            await self.send_message(update,
                                "**⛽ ETH GAS FEES**\n\n"
                                "Low: 15 Gwei\n"
                                "Average: 25 Gwei\n"
                                "High: 40 Gwei\n\n"
                                "💡 Dati stimati - usa API key per dati reali",
                                platform
                            )
                            
            except Exception as e:
                self.logger.error(f"Gas fees error: {e}")
                await self.send_message(update,
                    "**⛽ ETH GAS FEES**\n\n"
                    "Low: 15 Gwei\n"
                    "Average: 25 Gwei\n"
                    "High: 40 Gwei\n\n"
                    "💡 Dati stimati - servizio temporaneamente non disponibile",
                    platform
                )
    
    async def get_user_portfolio(self, user_id: str) -> List:
        """Recupera portfolio dal database"""
        # TODO: Implementare con database reale
        # Per ora ritorna dati di esempio
        return [
            {'symbol': 'BTCUSDT', 'quantity': 0.1, 'buy_price': 45000},
            {'symbol': 'ETHUSDT', 'quantity': 1.5, 'buy_price': 3000},
            {'symbol': 'SOLUSDT', 'quantity': 10, 'buy_price': 100}
        ]
    
    async def save_portfolio_item(self, user_id: str, symbol: str, quantity: float, buy_price: float) -> bool:
        """Salva item nel portfolio"""
        # TODO: Implementare con database reale
        self.logger.info(f"Saving portfolio item for {user_id}: {symbol} {quantity} @ {buy_price}")
        return True
    
    async def delete_portfolio_item(self, user_id: str, symbol: str) -> bool:
        """Rimuove item dal portfolio"""
        # TODO: Implementare con database reale
        self.logger.info(f"Deleting portfolio item for {user_id}: {symbol}")
        return True
    
    async def send_message(self, update, message: str, platform: Platform):
        """Invia messaggio su Telegram"""
        if platform == Platform.TELEGRAM:
            await update.message.reply_text(message, parse_mode='Markdown')
