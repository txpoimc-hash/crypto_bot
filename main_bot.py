# main_bot.py - File principale per avviare il bot

import asyncio
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import redis.asyncio as redis

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotCore:
    """Core del bot condiviso"""
    
    def __init__(self, config: dict):
        self.config = config
        self.redis = None
        self.telegram_app = None
        
    async def initialize(self):
        """Inizializza componenti"""
        # Redis
        self.redis = await redis.from_url(self.config.get('redis_url', 'redis://localhost:6379/0'))
        
        # Telegram
        self.telegram_app = Application.builder().token(self.config['telegram_token']).build()
        
        logger.info("Bot core initialized")

async def main():
    """Funzione principale"""
    
    # Configurazione
    config = {
        'telegram_token': 'YOUR_TELEGRAM_BOT_TOKEN',
        'redis_url': 'redis://localhost:6379/0',
        'binance_api_key': '',
        'binance_api_secret': '',
        'etherscan_api_key': ''
    }
    
    # Inizializza core
    bot_core = BotCore(config)
    await bot_core.initialize()
    
    # Inizializza crypto bot
    from crypto_bot import CryptoTradingBot
    crypto_bot = CryptoTradingBot(bot_core)
    await crypto_bot.register_commands()
    
    # Inizializza casino bot
    from casino_bot import CasinoGameBot
    casino_bot = CasinoGameBot(bot_core)
    await casino_bot.register_commands()
    
    # Handler per Mines (comandi aggiuntivi)
    from telegram.ext import CommandHandler
    
    async def reveal_command(update, context):
        if len(context.args) < 2:
            await update.message.reply_text("❌ Formato: /reveal <game_id> <posizione>")
            return
        game_id = context.args[0]
        try:
            position = int(context.args[1])
            await casino_bot.reveal_mine(update, game_id, position, Platform.TELEGRAM)
        except ValueError:
            await update.message.reply_text("❌ Posizione non valida")
    
    async def cashout_command(update, context):
        if not context.args:
            await update.message.reply_text("❌ Formato: /cashout <game_id>")
            return
        game_id = context.args[0]
        await casino_bot.cashout_mines(update, game_id, Platform.TELEGRAM)
    
    async def hit_command(update, context):
        if not context.args:
            await update.message.reply_text("❌ Formato: /hit <game_id>")
            return
        game_id = context.args[0]
        await casino_bot.blackjack_hit(update, game_id, Platform.TELEGRAM)
    
    async def stand_command(update, context):
        if not context.args:
            await update.message.reply_text("❌ Formato: /stand <game_id>")
            return
        game_id = context.args[0]
        await casino_bot.blackjack_stand(update, game_id, Platform.TELEGRAM)
    
    async def double_command(update, context):
        if not context.args:
            await update.message.reply_text("❌ Formato: /double <game_id>")
            return
        game_id = context.args[0]
        await casino_bot.blackjack_double(update, game_id, Platform.TELEGRAM)
    
    bot_core.telegram_app.add_handler(CommandHandler("reveal", reveal_command))
    bot_core.telegram_app.add_handler(CommandHandler("cashout", cashout_command))
    bot_core.telegram_app.add_handler(CommandHandler("hit", hit_command))
    bot_core.telegram_app.add_handler(CommandHandler("stand", stand_command))
    bot_core.telegram_app.add_handler(CommandHandler("double", double_command))
    
    # Avvia bot
    logger.info("Starting bot...")
    await bot_core.telegram_app.initialize()
    await bot_core.telegram_app.start()
    await bot_core.telegram_app.updater.start_polling()
    
    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    try:
        # Mantieni in esecuzione
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        await bot_core.telegram_app.updater.stop()
        await bot_core.telegram_app.stop()
        await bot_core.telegram_app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
