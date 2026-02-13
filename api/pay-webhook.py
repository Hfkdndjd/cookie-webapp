import json
import os
import asyncpg
import httpx
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_HOST = os.environ.get("DB_HOST", "")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "cookie_bot")
DB_USER = os.environ.get("DB_USER", "cookie_user")
DB_PASS = os.environ.get("DB_PASS", "")
PAYMENT_AMOUNT = 99


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            # CloudPayments шлёт form-encoded или JSON
            try:
                data = json.loads(body)
            except Exception:
                from urllib.parse import parse_qs
                parsed = parse_qs(body.decode("utf-8"))
                data = {k: v[0] for k, v in parsed.items()}

            # Получаем данные платежа
            status = data.get("Status", "")
            invoice_id = data.get("InvoiceId", "")
            custom_data = data.get("Data", {})

            if isinstance(custom_data, str):
                try:
                    custom_data = json.loads(custom_data)
                except Exception:
                    custom_data = {}

            completion_id = custom_data.get("completion_id")
            owner_id = custom_data.get("user_id")

            # Только успешные платежи
            if status == "Completed" and completion_id and owner_id:
                import asyncio
                asyncio.run(self._handle_payment(int(completion_id), int(owner_id)))

            # CloudPayments ждёт {"code": 0} для успеха
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"code": 0}).encode())

        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"code": 0}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    async def _handle_payment(self, completion_id: int, owner_id: int):
        try:
            conn = await asyncpg.connect(
                host=DB_HOST, port=DB_PORT,
                database=DB_NAME, user=DB_USER, password=DB_PASS
            )

            # Помечаем как оплаченное
            await conn.execute(
                "UPDATE completions SET paid = TRUE WHERE id = $1",
                completion_id
            )

            # Получаем данные о прохождении
            row = await conn.fetchrow(
                """SELECT c.taker_name, c.score, c.taker_id
                   FROM completions c
                   WHERE c.id = $1""",
                completion_id
            )
            await conn.close()

            if not row:
                return

            taker_name = row["taker_name"]
            score = row["score"]
            taker_id = row["taker_id"]

            # Определяем уровень дружбы
            if score <= 30:
                relation = "Знакомые"
            elif score <= 55:
                relation = "Приятели"
            elif score <= 75:
                relation = "Друзья"
            elif score <= 90:
                relation = "Хорошие друзья"
            else:
                relation = "Лучшие друзья"

            # Отправляем владельцу через Telegram Bot API
            tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            text = (
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"Твой тест прошёл: <b>{taker_name}</b>\n"
                f"Результат: <b>{score}%</b>\n"
                f"Уровень дружбы: <b>{relation}</b>"
            )

            async with httpx.AsyncClient() as client:
                await client.post(tg_url, json={
                    "chat_id": owner_id,
                    "text": text,
                    "parse_mode": "HTML"
                })

        except Exception as e:
            print(f"Error in _handle_payment: {e}")
