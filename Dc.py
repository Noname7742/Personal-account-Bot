from discord import app_commands
import datetime
import os
from dotenv import load_dotenv
import discord
import schedule
import time
import sqlite3
import asyncio

load_dotenv()
TOKEN = os.getenv('TOKEN')

token = os.getenv('TOKEN')
print(token)

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def server_on():
    t = Thread(target=run)
    t.daemon = True
    t.start()

if TOKEN is None:
    print("Error: TOKEN is not set in environment variables or .env file.")
    exit()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def create_table(database_name):
    try:
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount REAL,
            description TEXT,
            date TEXT,
            image_path TEXT
        )""")
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาดในการสร้างตาราง: {e}")

def add_transaction(transaction, database_name):
    try:
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, amount, description, date, image_path) VALUES (?, ?, ?, ?, ?)",
                    (transaction["type"], transaction["amount"], transaction["description"], transaction["date"], transaction["image_path"]))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาดในการเพิ่มข้อมูล: {e}")

def get_transactions(database_name):
    try:
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions")
        rows = c.fetchall()
        conn.close()
        transactions = []
        for row in rows:
            if len(row) >= 5:  # ตรวจสอบว่ามีอย่างน้อย 5 คอลัมน์
                transaction = {
                    "id": row[0],
                    "type": row[1],
                    "amount": row[2],   
                    "description": row[3],
                    "date": row[4]
                }
                if len(row) >= 6:  # ตรวจสอบว่ามีคอลัมน์ image_path
                    transaction["image_path"] = row[5]
                else:
                    transaction["image_path"] = None  # กำหนด image_path เป็น None ถ้าไม่มีข้อมูล
                transactions.append(transaction)
            else:
                print(f"พบแถวข้อมูลที่ไม่ถูกต้อง: {row}")
        return transactions
    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาด: {e}")
        return []

@client.event
async def on_message(message):
    if message.content.startswith('!add_data'):
        user_id = str(message.author.id)  # ใช้ ID ผู้ใช้เป็นชื่อฐานข้อมูล
        database_name = f"{user_id}.db"

        conn = sqlite3.connect(database_name)
        c = conn.cursor()

        # สร้างตาราง (ถ้ายังไม่มี)
        c.execute('''CREATE TABLE IF NOT EXISTS data
                     (item TEXT)''')

        # เพิ่มข้อมูล
        item = message.content.split(' ')[1]
        c.execute("INSERT INTO data (item) VALUES (?)", (item,))

        conn.commit()
        conn.close()

        await message.channel.send("เพิ่มข้อมูลแล้ว!")

@client.event
async def on_ready():
    await tree.sync()
    print(f'{client.user} is ready!')
    schedule.every().day.at("00:00").do(send_daily_summary)
    client.loop.create_task(run_schedule())

async def run_schedule():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def send_daily_summary():
    now = datetime.datetime.now()
    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)
    end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # เช็คช่องที่ต้องการส่งข้อความ
    channel_id = 1351031050301739070
    channel = client.get_channel(channel_id)

    if channel:
        user_id = str(channel.guild.owner_id)
        database_name = f"{user_id}.db"
        try:
            create_table(database_name)
            transactions = get_transactions(database_name)

            filtered_transactions = [t for t in transactions if start_date <= datetime.datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S") < end_date]
            total_income = sum(t["amount"] for t in filtered_transactions if t["type"] == "income")
            total_expenses = sum(t["amount"] for t in filtered_transactions if t["type"] == "expenses")
            balance = total_income - total_expenses

            # ส่งข้อความสรุปรายการ
            await channel.send(f"สรุปรายรับ-รายจ่ายประจำวัน:\n"
                               f"รายรับ: {total_income} บาท\n"
                               f"รายจ่าย: {total_expenses} บาท\n"
                               f"คงเหลือ: {balance} บาท")
        except sqlite3.Error as e:
            print(f"เกิดข้อผิดพลาดในการทำงานกับฐานข้อมูล: {e}")
    else:
        print(f"ไม่พบช่อง Discord ที่มี ID: {channel_id}")

    print_summary({
        "date": now.date(),
        "total_income": total_income,
        "total_expense": total_expenses,
        "balance": balance,
        "income_details": [t for t in filtered_transactions if t["type"] == "income"],
        "expense_details": [t for t in filtered_transactions if t["type"] == "expenses"]
    })

def print_summary(summary):
    print(f"วันที่: {summary['date']}")
    print(f"ยอดรายรับ: {summary['total_income']} บาท")
    print(f"ยอดรายจ่าย: {summary['total_expense']} บาท")
    print(f"ยอดคงเหลือ: {summary['balance']} บาท")

    print("\nรายละเอียดรายรับ:")
    for income in summary["income_details"]:
        print(f"- {income['description']}: {income['amount']} บาท")

    print("\nรายละเอียดรายจ่าย:")
    for expense in summary["expense_details"]:
        print(f"- {expense['description']}: {expense['amount']} บาท")

@tree.command(name="income", description="เพิ่มรายรับ")
async def income(interaction: discord.Interaction, amount: float, description: str):
    transaction = {
        "type": "income",
        "amount": amount,
        "description": description,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image_path": None
    }
    user_id = str(interaction.user.id)
    database_name = f"{user_id}.db"
    add_transaction(transaction, database_name)
    await interaction.response.send_message(f"เพิ่มรายรับ: {amount} บาท ({description})")

@tree.command(name="expenses", description="เพิ่มรายจ่าย (แนบรูปภาพได้)")
async def expenses(interaction: discord.Interaction, amount: float, description: str, image: discord.Attachment = None):
    image_path = None
    if image:
        if image.content_type.startswith("image/"):
            filename = f"images/{image.filename}"
            await image.save(filename)
            image_path = filename
        else:
            await interaction.response.send_message("ไฟล์ที่อัปโหลดไม่ใช่รูปภาพ")
            return

    transaction = {
        "type": "expenses",
        "amount": amount,
        "description": description,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image_path": image_path
    }
    user_id = str(interaction.user.id)
    database_name = f"{user_id}.db"
    add_transaction(transaction, database_name)  # เรียกใช้ add_transaction ครั้งเดียว

    if image and image_path:
        try:
            await interaction.response.send_message(f"เพิ่มรายจ่าย: {amount} บาท ({description})", file=image)
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการส่งไฟล์: {e}")
            await interaction.response.send_message(f"เพิ่มรายจ่าย: {amount} บาท ({description}) (แต่มีปัญหาในการส่งรูปภาพ)")
    else:
        await interaction.response.send_message(f"เพิ่มรายจ่าย: {amount} บาท ({description})")

@tree.command(name="summary", description="สรุปรายรับ-รายจ่าย")
async def summary(interaction: discord.Interaction, period: str):
    await interaction.response.defer()

    now = datetime.datetime.now()
    if period == "สัปดาห์":
        start_date = now - datetime.timedelta(days=7)
    elif period == "เดือน":
        start_date = now - datetime.timedelta(days=30)
    elif period == "ปี":
        start_date = now - datetime.timedelta(days=365)
    else:
        await interaction.followup.send("กรุณาเลือก period: สัปดาห์, เดือน, ปี")
        return

    user_id = str(interaction.user.id)
    database_name = f"{user_id}.db"
    transactions = get_transactions(database_name)

    filtered_transactions = [t for t in transactions if datetime.datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S") >= start_date]
    total_income = sum(t["amount"] for t in filtered_transactions if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in filtered_transactions if t["type"] == "expenses")
    balance = total_income - total_expenses

    summary_message = f"สรุปรายรับ-รายจ่าย ({period}):\n"
    summary_message += f"รายรับ: {total_income} บาท\n"
    summary_message += f"รายจ่าย: {total_expenses} บาท\n"
    summary_message += f"คงเหลือ: {balance} บาท\n\n"

    summary_message += "รายละเอียด:\n"
    for transaction in filtered_transactions:
        summary_message += f"- {transaction['description']}: {transaction['amount']} บาท ({transaction['type']})\n"

    await interaction.followup.send(summary_message)  # ส่งข้อความสรุปเพียงครั้งเดียว

    files = []
    for expense in filtered_transactions:
        if expense["type"] == "expenses":
            if expense["image_path"]:
                file = discord.File(expense["image_path"])
                files.append(file)

    if files:
        await interaction.followup.send(files=files)  # ส่งไฟล์ภาพ (ถ้ามี)
    
    transactions = database_name
    filtered_transactions = [t for t in transactions if datetime.datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S") >= start_date]
    total_income = sum(t["amount"] for t in filtered_transactions if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in filtered_transactions if t["type"] == "expenses")
    balance = total_income - total_expenses
server_on()

client.run(TOKEN)

# รัน schedule
while True:
    schedule.run_pending()
    time.sleep(1)
