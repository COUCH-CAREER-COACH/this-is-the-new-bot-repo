import asyncio
import logging
import aiohttp
import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import json
from tenacity import retry, stop_after_attempt, wait_exponential

class NotificationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationChannel:
    async def send_message(self, message: str, priority: NotificationPriority) -> bool:
        raise NotImplementedError

class TelegramNotifier(NotificationChannel):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def send_message(self, message: str, priority: NotificationPriority) -> bool:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/sendMessage"
            params = {
                "chat_id": self.chat_id,
                "text": f"[{priority.value.upper()}] {message}",
                "parse_mode": "HTML"
            }
            async with session.post(url, params=params) as response:
                return response.status == 200

class DiscordNotifier(NotificationChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def send_message(self, message: str, priority: NotificationPriority) -> bool:
        async with aiohttp.ClientSession() as session:
            payload = {
                "content": f"**[{priority.value.upper()}]** {message}"
            }
            async with session.post(self.webhook_url, json=payload) as response:
                return response.status == 204

class EmailNotifier(NotificationChannel):
    def __init__(self, smtp_config: Dict):
        self.smtp_server = smtp_config["server"]
        self.smtp_port = smtp_config["port"]
        self.sender_email = smtp_config["sender"]
        self.password = smtp_config["password"]
        self.recipient_email = smtp_config["recipient"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def send_message(self, message: str, priority: NotificationPriority) -> bool:
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.sender_email, self.password)
                msg = MIMEText(message)
                msg['Subject'] = f'[{priority.value.upper()}] Arbitrage Bot Notification'
                msg['From'] = self.sender_email
                msg['To'] = self.recipient_email
                server.send_message(msg)
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {str(e)}")
            return False

class NotificationManager:
    def __init__(self, config_path: str):
        self.channels: List[NotificationChannel] = []
        self.logger = logging.getLogger(__name__)
        self._initialize_from_config(config_path)

    def _initialize_from_config(self, config_path: str):
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            notifications_config = config.get("notifications", {})
            
            if telegram_config := notifications_config.get("telegram"):
                self.channels.append(TelegramNotifier(
                    telegram_config["bot_token"],
                    telegram_config["chat_id"]
                ))
            
            if discord_config := notifications_config.get("discord"):
                self.channels.append(DiscordNotifier(
                    discord_config["webhook_url"]
                ))
            
            if email_config := notifications_config.get("email"):
                self.channels.append(EmailNotifier(email_config))
                
        except Exception as e:
            self.logger.error(f"Failed to initialize notification channels: {str(e)}")

    async def notify(self, message: str, priority: NotificationPriority = NotificationPriority.MEDIUM) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        tasks = [
            channel.send_message(formatted_message, priority)
            for channel in self.channels
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for channel, result in zip(self.channels, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to send notification via {channel.__class__.__name__}: {str(result)}")

    async def notify_trade(self, trade_info: Dict) -> None:
        message = (
            f"🎯 Trade Executed\n"
            f"Profit: {trade_info['profit']:.6f} ETH\n"
            f"Route: {' → '.join(trade_info['path'])}\n"
            f"Gas Used: {trade_info['gas_used']}\n"
            f"TX Hash: {trade_info['tx_hash']}"
        )
        await self.notify(message, NotificationPriority.HIGH)

    async def notify_error(self, error: str, context: Optional[Dict] = None) -> None:
        message = f"❌ Error: {error}"
        if context:
            message += f"\nContext: {json.dumps(context, indent=2)}"
        await self.notify(message, NotificationPriority.CRITICAL)

    async def notify_opportunity(self, opportunity: Dict) -> None:
        message = (
            f"💰 Arbitrage Opportunity\n"
            f"Expected Profit: {opportunity['expected_profit']:.6f} ETH\n"
            f"Route: {' → '.join(opportunity['path'])}\n"
            f"Current Gas Price: {opportunity['gas_price']} gwei"
        )
        await self.notify(message, NotificationPriority.MEDIUM)
