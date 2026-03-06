import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "8643172698:AAFlLKjA-uRrS2iawjWifCGz5H_JYlS-mcM")
SITE_URL = "https://stend.netlify.app/"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = "receipts"
os.makedirs(UPLOAD_DIR, exist_ok=True)

orders = {}

@app.get("/")
def home():
    return "OK"

@app.post("/api/receipt")
def api_receipt():
    ref = request.form.get("ref", "").strip()
    ticket = request.form.get("ticket", "").strip()
    price = request.form.get("price", "").strip()
    count = request.form.get("count", "1").strip()
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    receipt = request.files.get("receipt")

    if not ref:
        return jsonify({"ok": False, "error": "no ref"}), 400

    if not ticket or not price or not count or not name or not phone:
        return jsonify({"ok": False, "error": "missing fields"}), 400

    if not receipt:
        return jsonify({"ok": False, "error": "no receipt"}), 400

    try:
        chat_id = int(ref)
    except:
        return jsonify({"ok": False, "error": "bad ref"}), 400

    order_id = uuid.uuid4().hex[:10]
    ticket_code = uuid.uuid4().hex[:8].upper()

    ext = os.path.splitext(receipt.filename or "")[1].lower() or ".jpg"
    filepath = os.path.join(UPLOAD_DIR, f"{order_id}{ext}")
    receipt.save(filepath)

    orders[order_id] = {
        "status": "pending",
        "chat_id": chat_id,
        "ticket": ticket,
        "price": price,
        "count": count,
        "name": name,
        "phone": phone,
        "ticket_code": ticket_code
    }

    caption = (
        "🎟 НОВА ПОКУПКА ПО ТВОЇЙ ССИЛЦІ\n\n"
        f"Квиток: {ticket}\n"
        f"Кількість: {count}\n"
        f"Сума: {price} грн\n"
        f"Ім'я: {name}\n"
        f"Телефон: +380{phone}\n"
        f"ID: {order_id}"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Прийняти", "callback_data": f"accept_{order_id}"},
            {"text": "❌ Відхилити", "callback_data": f"decline_{order_id}"}
        ]]
    }

    with open(filepath, "rb") as f:
        response = requests.post(
            f"{TELEGRAM_API}/sendPhoto",
            data={
                "chat_id": chat_id,
                "caption": caption,
                "reply_markup": str(keyboard).replace("'", '"')
            },
            files={"photo": f}
        )

    result = response.json()
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result}), 500

    return jsonify({"ok": True, "order_id": order_id})

@app.get("/api/status/<order_id>")
def api_status(order_id):
    if order_id not in orders:
        return jsonify({"status": "unknown"})

    order = orders[order_id]

    return jsonify({
        "status": order["status"],
        "ticket": {
            "event": "Стендап вечір у Харкові",
            "date": "7 березня 2026",
            "time": "20:00",
            "address": "Холодногірська вулиця, 11",
            "type": order["ticket"],
            "count": order["count"],
            "price": order["price"],
            "name": order["name"],
            "phone": f"+380{order['phone']}",
            "code": order["ticket_code"]
        }
    })

@app.post("/telegram/webhook")
def telegram_webhook():
    update = request.json or {}

    if "message" in update:
        message = update["message"]
        text = message.get("text", "")
        chat_id = message["chat"]["id"]

        if text.startswith("/start"):
            personal_link = f"{SITE_URL}/?ref={chat_id}"
            reply_text = (
                "Твоя особиста реф ссилка на сайт:\n\n"
                f"{personal_link}\n\n"
                "Надішли її іншій людині\n"
                "Якщо купить квиток, ти будеш дивитися за оплатою та підтвердити ЇЇ, чи ні"
            )

            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": reply_text
                }
            )

        return "ok"

    if "callback_query" in update:
        callback = update["callback_query"]
        data = callback.get("data", "")
        callback_id = callback.get("id")

        if data.startswith("accept_"):
            order_id = data.replace("accept_", "")
            if order_id in orders:
                orders[order_id]["status"] = "accepted"

        elif data.startswith("decline_"):
            order_id = data.replace("decline_", "")
            if order_id in orders:
                orders[order_id]["status"] = "declined"

        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": "Статус оновлено"
            }
        )

        return "ok"

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
