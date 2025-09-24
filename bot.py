import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from discord import app_commands
import datetime
import json
import os
import re
import sys
import importlib
from pathlib import Path
import traceback
from typing import Optional
import gspread
from oauth2client.service_account import ServiceAccountCredentials





# Константы по умолчанию
BOT_ADMIN_ID = 297265099444322315
MIN_RANK_FOR_HR = "Капитан внутренней службы"
REQUESTS_CHANNEL = 1401272012185276599
DISMISSAL_CHANNEL = 1401272012185276599  # По умолчанию тот же канал
LOG_CHANNEL = 1401276964366712912
REQUEST_STATUS_CHANNEL = REQUESTS_CHANNEL

RANK_HIERARCHY = [
    "Рядовой внутренней службы",
    "Младший сержант внутренней службы",
    "Сержант внутренней службы",
    "Старший сержант внутренней службы",
    "Старшина внутренней службы",
    "Прапорщик внутренней службы",
    "Старший Прапорщик внутренней службы",
    "Младший Лейтенант внутренней службы",
    "Лейтенант внутренней службы",
    "Старший Лейтенант внутренней службы",
    "Капитан внутренней службы",
    "Майор внутренней службы",
    "Подполковник внутренней службы",
    "Полковник внутренней службы",
    "Генерал-Майор внутренней службы"
]

POSITIONS = [
    "Без должности",
    "Командир отделения",
    "Зам. командира отделения"
]

DIVISIONS = ["Академия ФСИН", "ОСБ", "ООиН", "ОК", "СЧ", "ОСН"]

DATA_FILE = "personnel_data.json"
SETTINGS_FILE = "bot_settings.json"
GOOGLE_CREDS_FILE = "google_credentials.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

class RequestData:
    def __init__(self):
        self.recruitment_requests = {}
        self.dismissal_requests = {}

request_data = RequestData()


from aiohttp import web
import threading
import asyncio

class BotWebServer:
    def __init__(self, bot, host='0.0.0.0', port=5000):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.setup_routes()
        
    def setup_routes(self):
        self.app.router.add_post('/google-sheets-audit', self.handle_google_sheets_audit)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.root_handler)
    
    async def handle_google_sheets_audit(self, request):
        try:
            # Проверяем авторизацию
            auth_token = request.headers.get('Authorization')
            if not self.validate_token(auth_token):
                return web.json_response({"status": "error", "message": "Unauthorized"}, status=401)
            
            data = await request.json()
            
            if data.get('action') == 'google_sheets_audit':
                audit_data = data['data']
                
                # Обрабатываем аудит в основном потоке бота
                success = await self.process_audit(audit_data)
                
                if success:
                    return web.json_response({
                        "status": "success", 
                        "message": "Аудит успешно обработан и отправлен в Discord"
                    })
                else:
                    return web.json_response({
                        "status": "error", 
                        "message": "Ошибка обработки аудита"
                    }, status=500)
            else:
                return web.json_response({
                    "status": "error", 
                    "message": "Неверный формат запроса"
                }, status=400)
                
        except Exception as e:
            print(f"Ошибка обработки аудита: {e}")
            return web.json_response({
                "status": "error", 
                "message": str(e)
            }, status=500)
    
    def validate_token(self, token):
        """Простая проверка токена"""
        expected_token = "Bearer your-secret-token-here"
        return token == expected_token
    
    async def health_check(self, request):
        return web.json_response({
            "status": "online", 
            "bot": str(self.bot.user),
            "guilds": len(self.bot.guilds)
        })
    
    async def root_handler(self, request):
        return web.json_response({
            "message": "UVDBot Web Server",
            "endpoints": {
                "POST /google-sheets-audit": "Прием аудитов из Google Таблиц",
                "GET /health": "Проверка статуса бота",
                "GET /": "Информация о сервере"
            }
        })
    
    async def process_audit(self, audit_data):
        """Обработка аудита из Google Таблиц"""
        try:
            # Создаем embed такой же как у бота
            action_colors = {
                "Принят": 0x00FF00,    # Зеленый
                "Уволен": 0xFF0000,    # Красный
                "Повышен": 0xFFA500,   # Оранжевый
                "Понижен": 0xFFFF00,   # Желтый
                "Переведен": 0xFFFF00  # Желтый
            }
            
            color = action_colors.get(audit_data['action'], 0x2E73F0)
            
            embed = discord.Embed(
                title="📝 Кадровый аудит ФСИН",
                color=color,
                timestamp=datetime.datetime.now()
            )
            
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/1407347004400472176/1419651513311170641/Gerb_FSIN.png?ex=68d28900&is=68d13780&hm=14dd51a0315adcf62c7c9c52d04d5d220340ee9ab037dfc55678ecfc4791b9b5&=&format=webp&quality=lossless&width=911&height=960")
            
            # Добавляем поля
            target_mention = f"<@{audit_data['discord_id']}>" if audit_data['discord_id'] else audit_data['full_name']
            
            embed.add_field(
                name="Кадровую отписал", 
                value="Google Таблица",
                inline=False
            )
            
            embed.add_field(
                name="Имя Фамилия | 6 цифр статика", 
                value=f"{audit_data['full_name']} | {audit_data['static']}", 
                inline=False
            )

            embed.add_field(name="Дата Действия", value=datetime.datetime.now().strftime("%d-%m-%Y"), inline=False)
            embed.add_field(name="Действие", value=audit_data['action'], inline=False)
            
            if audit_data['discord_id']:
                embed.add_field(name="Сотрудник", value=target_mention, inline=False)
            
            embed.add_field(name="Звание", value=audit_data['rank'], inline=True)
            embed.add_field(name="Подразделение", value=audit_data['division'], inline=True)
            embed.add_field(name="Источник", value="Google Таблица", inline=True)

            # Отправляем в канал аудита
            settings = load_settings()
            audit_channel_id = settings["channels"].get("logs", LOG_CHANNEL)
            channel = self.bot.get_channel(audit_channel_id)
            
            if channel:
                await channel.send(embed=embed)
                
                # Обновляем лист кадрового аудита
                await self.update_audit_sheet(audit_data)
                
                # Обновляем личный состав если нужно
                if audit_data['action'] in ['Принят', 'Уволен']:
                    await self.update_personnel_sheet(audit_data)
                
                return True
            else:
                print("Канал для аудита не найден")
                return False
                
        except Exception as e:
            print(f"Ошибка обработки аудита: {e}")
            return False
    
    async def update_audit_sheet(self, audit_data):
        """Обновить лист кадрового аудита"""
        try:
            settings = load_settings()
            if not settings["google_sheets"].get("enabled", False):
                return
            
            spreadsheet = google_sheets.client.open_by_key(
                settings["google_sheets"]["spreadsheet_id"]
            )
            
            try:
                audit_sheet = spreadsheet.worksheet("Кадровый аудит")
            except gspread.WorksheetNotFound:
                audit_sheet = spreadsheet.add_worksheet(title="Кадровый аудит", rows="1000", cols="10")
                headers = ["Дата", "Сотрудник", "Статик", "Действие", "Звание", "Подразделение", "Источник"]
                audit_sheet.insert_row(headers, 1)
            
            row_data = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                audit_data['full_name'],
                audit_data['static'],
                audit_data['action'],
                audit_data['rank'],
                audit_data['division'],
                "Google Таблица"
            ]
            
            audit_sheet.append_row(row_data)
            
        except Exception as e:
            print(f"Ошибка обновления аудита: {e}")
    
    async def update_personnel_sheet(self, audit_data):
        """Обновить личный состав"""
        try:
            settings = load_settings()
            if not settings["google_sheets"].get("enabled", False):
                return
            
            spreadsheet = google_sheets.client.open_by_key(
                settings["google_sheets"]["spreadsheet_id"]
            )
            
            try:
                personnel_sheet = spreadsheet.worksheet("Личный состав")
                
                if audit_data['action'] == 'Принят':
                    # Добавляем нового сотрудника
                    row_data = [
                        audit_data['discord_id'] or '',
                        audit_data['full_name'],
                        audit_data['static'],
                        audit_data['rank'],
                        audit_data['division'],
                        '',
                        datetime.datetime.now().strftime("%Y-%m-%d"),
                        "Активен"
                    ]
                    personnel_sheet.append_row(row_data)
                    
                elif audit_data['action'] == 'Уволен' and audit_data['discord_id']:
                    # Ищем сотрудника по Discord ID
                    try:
                        cell = personnel_sheet.find(audit_data['discord_id'])
                        if cell:
                            personnel_sheet.update_cell(cell.row, 8, "Уволен")
                            personnel_sheet.update_cell(cell.row, 9, datetime.datetime.now().strftime("%Y-%m-%d"))
                    except gspread.CellNotFound:
                        print("Сотрудник не найден в личном составе")
                        
            except gspread.WorksheetNotFound:
                print("Лист 'Личный состав' не найден")
                
        except Exception as e:
            print(f"Ошибка обновления состава: {e}")
    
    def start_server(self):
        """Запуск HTTP сервера в отдельном потоке"""
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def start():
                self.runner = web.AppRunner(self.app)
                await self.runner.setup()
                
                self.site = web.TCPSite(self.runner, self.host, self.port)
                await self.site.start()
                
                print(f"🌐 HTTP сервер запущен на http://{self.host}:{self.port}")
                print("📋 Endpoints:")
                print("   POST /google-sheets-audit - Прием аудитов из Google Таблиц")
                print("   GET  /health - Проверка статуса бота")
                print("   GET  / - Информация о сервере")
            
            loop.run_until_complete(start())
            loop.run_forever()
        
        # Запускаем сервер в отдельном потоке
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        return server_thread
    
    async def stop_server(self):
        """Остановка HTTP сервера"""
        if self.runner:
            await self.runner.cleanup()



async def handle_recruitment_approve(interaction: discord.Interaction):
    try:
        if not has_recruitment_permissions(interaction.user):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ У вас нет прав для одобрения заявок!", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        user_id = int(embed.fields[0].value[2:-1])
        member = interaction.guild.get_member(user_id)
        
        if not member:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Пользователь не найден на сервере!", ephemeral=True)
            return

        full_name = None
        static = None
        reason = None
        
        for field in embed.fields:
            if field.name == "📝 Имя Фамилия":
                full_name = field.value
            elif field.name == "🔢 Статик":
                static = field.value
            elif field.name == "📋 Порядок набора":
                reason = field.value
        
        if not full_name:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Не найдено поле с именем в заявке!", ephemeral=True)
            return

        try:
            await member.edit(nick=f"Курсант | {full_name}")
        except discord.Forbidden:
            pass

        HRSystem.add_personnel(member, interaction.user)
        updates = {
            "name": full_name,
            "static": static if static else "",
            "division": "Академия ФСИН"
        }
        HRSystem.update_personnel(member, **updates)

        try:
            roles_to_add = [
                discord.utils.get(interaction.guild.roles, name="========[🔗]Отдел[🔗]========"),
                discord.utils.get(interaction.guild.roles, name="Рядовой внутренней службы"),
                discord.utils.get(interaction.guild.roles, name="Академия ФСИН"),
                discord.utils.get(interaction.guild.roles, name="========[📘]Доступ[📘]========"),
                discord.utils.get(interaction.guild.roles, name="[©️] Сотрудник ФСИН"),
                discord.utils.get(interaction.guild.roles, name="========[👨🏻‍✈️]Звание[👨🏻‍✈️]========")
            ]
            
            for role in roles_to_add:
                if role:
                    await member.add_roles(role)
        except Exception as e:
            print(f"Ошибка при выдаче ролей: {e}")

        new_embed = embed.copy()
        new_embed.color = discord.Color.green()
        new_embed.add_field(
            name="✅ Статус",
            value=f"Одобрено сотрудником отдела кадров {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(embed=new_embed, view=None)

        # ИСПРАВЛЕННЫЙ ВЫЗОВ - убраны лишние параметры
        await HRSystem.log_action(
            action="Принятие на службу",
            target=member,
            executor=interaction.user,
            reason=reason or "Не указана",
            new_rank="Рядовой внутренней службы"
        )

        try:
            await member.send("🎉 Ваша заявка на вступление была одобрена! Добро пожаловать в ряды ФСИН!")
        except discord.Forbidden:
            pass

        if not interaction.response.is_done():
            await interaction.response.send_message("✅ Заявка успешно одобрена!", ephemeral=True)

    except Exception as e:
        print(f"Ошибка в handle_recruitment_approve: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке заявки!",
                ephemeral=True
            )

async def handle_dismissal_approve(interaction: discord.Interaction):
    if not has_dismissal_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для одобрения рапортов!", ephemeral=True)
        return
    
    embed = interaction.message.embeds[0]
    user_id = int(embed.description.split()[1][2:-1])
    member = interaction.guild.get_member(user_id)
    
    if not member:
        await interaction.response.send_message("❌ Пользователь не найден на сервере!", ephemeral=True)
        return
    
    data = HRSystem.get_personnel(member)
    
    reason = None
    for field in embed.fields:
        if field.name == "Причина увольнения":
            reason = field.value
            break
    
    if data:
        full_name = data["name"]

        rank = data.get("rank", "Не указано")
        static = data.get("static", "Не указан")
        position = data.get("position", "Не указана")
        
        roles_to_remove = [role for role in member.roles if role.name != "@everyone"]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
        
        try:
            await member.edit(nick=f"Уволен | {full_name}")
        except discord.Forbidden:
            pass
        
        # ИСПРАВЛЕННЫЙ ВЫЗОВ
        await HRSystem.log_action(
            action="Увольнение",
            target=member,
            executor=interaction.user,
            reason=reason or "Не указана",
            old_rank=rank
        )
    else:
        try:
            await member.edit(nick=f"Уволен | {member.display_name}")
        except discord.Forbidden:
            pass
        
        # ИСПРАВЛЕННЫЙ ВЫЗОВ
        await HRSystem.log_action(
            action="Увольнение (не был в базе)",
            target=member,
            executor=interaction.user,
            reason=reason or "Не указана"
        )
    
    HRSystem.remove_personnel(member)

    new_embed = embed.copy()
    new_embed.color = discord.Color.green()
    new_embed.add_field(
        name="✅ Обработано", 
        value=f"Сотрудник: {interaction.user.mention}\nВремя: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", 
        inline=True
    )
    
    await interaction.message.edit(embed=new_embed, view=None)
    
    try:
        await member.send("ℹ️ Ваш рапорт на увольнение был одобрен. Спасибо за службу!")
    except discord.Forbidden:
        pass
    
    await interaction.response.send_message("✅ Рапорт на увольнение успешно одобрен!", ephemeral=True)


# Google Sheets интеграция
class GoogleSheetsManager:
    def __init__(self):
        self.credentials_file = GOOGLE_CREDS_FILE
        self.spreadsheet_id = None
        self.worksheet_name = "Кадровый аудит"
        self.client = None
        self.sheet = None
        
    def initialize(self):
        """Инициализация подключения к Google Sheets"""
        if not os.path.exists(self.credentials_file):
            print("⚠️ Файл учетных данных Google не найден. Интеграция с Google Sheets отключена.")
            return False
            
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, scope)
            self.client = gspread.authorize(creds)
            print("✅ Подключение к Google Sheets установлено")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Sheets: {e}")
            return False
    
    def setup_spreadsheet(self, spreadsheet_id=None, worksheet_name=None):
        """Настройка таблицы для работы"""
        if not self.client:
            return False
            
        try:
            if spreadsheet_id:
                self.spreadsheet_id = spreadsheet_id
            if worksheet_name:
                self.worksheet_name = worksheet_name
                
            if self.spreadsheet_id:
                spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                try:
                    self.sheet = spreadsheet.worksheet(self.worksheet_name)
                except gspread.WorksheetNotFound:
                    self.sheet = spreadsheet.add_worksheet(title=self.worksheet_name, rows="1000", cols="20")
                
                # Создаем заголовки, если лист пустой
                if not self.sheet.get_all_values():
                    headers = [
                        "Дата и время", "Действие", "Целевой сотрудник", "ID целевого сотрудника",
                        "Исполнитель", "ID исполнителя", "Подразделение", "Звание", "Должность",
                        "Статик", "Причина", "Старое звание", "Новое звание", "Старая должность",
                        "Новая должность", "Старое подразделение", "Новое подразделение"
                    ]
                    self.sheet.insert_row(headers, 1)
                
                print(f"✅ Таблица Google Sheets настроена: {self.worksheet_name}")
                return True
                
        except Exception as e:
            print(f"❌ Ошибка настройки таблицы: {e}")
            return False
    
    def log_to_sheet(self, log_data):
        """Запись данных в Google Sheet"""
        if not self.sheet:
            print("❌ Лист Google Sheets не инициализирован")
            return False

        try:
            row_data = [
                log_data.get("timestamp", ""),
                log_data.get("action", ""),
                log_data.get("target_name", ""),
                log_data.get("target_id", ""),  # Уже строка
                log_data.get("executor_name", ""),
                log_data.get("executor_id", ""),  # Уже строка
                log_data.get("division", ""),
                log_data.get("rank", ""),
                log_data.get("position", ""),
                log_data.get("static", ""),
                log_data.get("reason", ""),
                log_data.get("old_rank", ""),
                log_data.get("new_rank", ""),
                log_data.get("old_position", ""),
                log_data.get("new_position", ""),
                log_data.get("old_division", ""),
                log_data.get("new_division", "")
            ]

            print(f"📝 Запись строки в Google Sheets: {row_data}")

            self.sheet.append_row(row_data)
            print("✅ Данные записаны в Google Sheets")
            return True

        except Exception as e:
            print(f"❌ Ошибка записи в Google Sheets: {e}")
            print(f"❌ Данные которые пытались записать: {log_data}")
            return False

# Инициализация менеджера Google Sheets
google_sheets = GoogleSheetsManager()

# Функции для работы с данными
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"personnel": {}}, f)
        return {"personnel": {}}
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return {"personnel": {}}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"personnel": {}}, f)
        return {"personnel": {}}

def save_data(data):
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    if os.path.exists(DATA_FILE):
        os.replace(temp_file, DATA_FILE)
    else:
        os.rename(temp_file, DATA_FILE)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "channels": {
                "recruitment_requests": REQUESTS_CHANNEL,
                "dismissal_requests": DISMISSAL_CHANNEL,
                "logs": LOG_CHANNEL,
                "status": REQUEST_STATUS_CHANNEL
            },
            "roles": {
                "recruitment": None,
                "hr_management": None,
                "dismissal": None
            },
            "admins": [BOT_ADMIN_ID],
            "moderators": [],
            "google_sheets": {
                "spreadsheet_id": None,
                "worksheet_name": "Кадровый аудит",
                "enabled": False
            }
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=4)
        return default_settings
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return load_settings()  # Пересоздаем настройки если файл пустой
            
            settings = json.loads(content)
            
            # Миграция старых настроек
            if "google_sheets" not in settings:
                settings["google_sheets"] = {
                    "spreadsheet_id": None,
                    "worksheet_name": "Кадровый аудит",
                    "enabled": False
                }
            
            # Миграция старых каналов
            if "requests" in settings.get("channels", {}):
                if "recruitment_requests" not in settings["channels"]:
                    settings["channels"]["recruitment_requests"] = settings["channels"]["requests"]
                if "dismissal_requests" not in settings["channels"]:
                    settings["channels"]["dismissal_requests"] = settings["channels"]["requests"]
                # Удаляем старый ключ если нужно
                # del settings["channels"]["requests"]
            
            # Сохраняем обновленные настройки
            save_settings(settings)
            
            return settings
            
    except (json.JSONDecodeError, FileNotFoundError):
        return load_settings()  # Пересоздаем настройки при ошибке

def save_settings(settings):
    temp_file = SETTINGS_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)
    
    if os.path.exists(SETTINGS_FILE):
        os.replace(temp_file, SETTINGS_FILE)
    else:
        os.rename(temp_file, SETTINGS_FILE)

# Функции проверки прав
def is_bot_admin(member: discord.Member):
    settings = load_settings()
    return member.id == BOT_ADMIN_ID or member.id in settings.get("admins", [])

def is_bot_moderator(member: discord.Member):
    settings = load_settings()
    return member.id in settings.get("moderators", []) or is_bot_admin(member)

def has_recruitment_permissions(member: discord.Member):
    settings = load_settings()
    recruitment_role_id = settings["roles"].get("recruitment")
    
    if is_bot_admin(member) or is_bot_moderator(member):
        return True
    
    if recruitment_role_id:
        return any(role.id == recruitment_role_id for role in member.roles)
    
    # Fallback to old system
    return has_hr_permissions(member)

def has_hr_permissions(member: discord.Member):
    settings = load_settings()
    hr_role_id = settings["roles"].get("hr_management")
    
    if is_bot_admin(member) or is_bot_moderator(member):
        return True
    
    if hr_role_id:
        return any(role.id == hr_role_id for role in member.roles)
    
    if member.id == BOT_ADMIN_ID:
        return True
    
    # Исправлено: проверка полного названия звания
    for role in member.roles:
        if role.name in RANK_HIERARCHY:
            try:
                rank_index = RANK_HIERARCHY.index(role.name)
                min_rank_index = RANK_HIERARCHY.index(MIN_RANK_FOR_HR)
                return rank_index >= min_rank_index
            except ValueError:
                continue  # Пропускаем если звание не найдено в списке
    return False

def has_dismissal_permissions(member: discord.Member):
    settings = load_settings()
    dismissal_role_id = settings["roles"].get("dismissal")
    
    if is_bot_admin(member) or is_bot_moderator(member):
        return True
    
    if dismissal_role_id:
        return any(role.id == dismissal_role_id for role in member.roles)
    
    # Fallback to old system
    return has_hr_permissions(member)

# Класс HR системы
class HRSystem:
    @staticmethod
    async def log_action(
        action: str,
        target: discord.Member,
        executor: discord.Member,
        reason: str = None,
        old_rank: str = None,
        new_rank: str = None,
        old_position: str = None,
        new_position: str = None,
        old_division: str = None,  # Исправлено с division на old_division
        new_division: str = None   # Добавлен new_division
    ):
        settings = load_settings()
        log_channel_id = settings["channels"].get("logs", LOG_CHANNEL)
        log_channel = bot.get_channel(log_channel_id)

        if log_channel is None:
            print("Ошибка: канал логов не найден!")
            return

        reason = reason or "Не указана"
        old_rank = old_rank or "Не указано"
        new_rank = new_rank or "Не указано"
        old_position = old_position or "Не указана"
        new_position = new_position or "Не указана"
        old_division = old_division or "Не указано"  # Исправлено
        new_division = new_division or "Не указано"  # Добавлено

        executor_data = HRSystem.get_personnel(executor) or {}
        executor_name = executor_data.get("name", executor.display_name)
        executor_static = executor_data.get("static", "Не указан")

        target_data = HRSystem.get_personnel(target) or {}
        target_division = target_data.get("division", "Не указано")  # Исправлено
        target_rank = target_data.get("rank", "Не указано")
        target_position = target_data.get("position", "Не указана")
        target_static = target_data.get("static", "Не указан")

        embed = discord.Embed(
            title=f"📝 Кадровый аудит ФСИН",
            color=0x2E73F0,
            timestamp=datetime.datetime.now()
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1401272012185276599/1412833532266418236/uvd.png?ex=68b9bb43&is=68b869c3&hm=aac09a72f63e8158a848deeee3dc279d6db20ead145b21b952e892567bc01fcb&")

        embed.add_field(
            name="Кадровую отписал", 
            value=f"{executor_name} | {executor_static}",
            inline=False
        )
        embed.add_field(
            name="Имя Фамилия | 6 цифр статика", 
            value=f"{target_data.get('name', target.display_name)} | {target_data.get('static', 'Не указан')}", 
            inline=False
        )

        embed.add_field(name="Дата Действия", value=datetime.datetime.now().strftime("%d-%m-%Y"), inline=False)
        embed.add_field(name="Действие", value=action, inline=False)
        text_before_embed = f"{target.mention}"
        embed.add_field(name="Звание", value=f"{target_rank}", inline=False)
        embed.add_field(name="Подразделение", value=f"{target_division}", inline=False)  # Исправлено

        if reason:
            embed.add_field(name="Причина", value=reason, inline=False)

        try:
            await log_channel.send(content=text_before_embed, embed=embed)
        except Exception as e:
            print(f"Ошибка при отправке лога: {e}")

        # Запись в Google Sheets
        settings = load_settings()
        if settings["google_sheets"].get("enabled", False) and google_sheets.sheet:
            log_data = {
                "timestamp": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
                "action": action,
                "target_name": target_data.get('name', target.display_name),
                "target_id": str(target.id),
                "executor_name": executor_name,
                "division": target_division,  # Исправлено
                "rank": target_rank,
                "position": target_position,
                "static": target_static,
                "reason": reason
            }
            google_sheets.log_to_sheet(log_data)

    @staticmethod
    async def update_personnel_sheet(member: discord.Member, action: str, old_data: dict = None):
        """Обновить лист личного состава в Google Sheets"""
        settings = load_settings()
        if not settings["google_sheets"].get("enabled", False):
            return
        
        try:
            spreadsheet = google_sheets.client.open_by_key(
                settings["google_sheets"]["spreadsheet_id"]
            )
            
            # Ищем или создаем лист "Личный состав"
            try:
                personnel_sheet = spreadsheet.worksheet("Личный состав")
            except gspread.WorksheetNotFound:
                personnel_sheet = spreadsheet.add_worksheet(title="Личный состав", rows="1000", cols="10")
                headers = ["Discord ID", "Имя Фамилия", "Статик", "Звание", "Подразделение", "Должность", "Дата приема", "Статус"]
                personnel_sheet.insert_row(headers, 1)
            
            data = HRSystem.get_personnel(member) or {}
            
            if action == "hired":
                # Добавляем нового сотрудника
                row_data = [
                    str(member.id),
                    data.get("name", ""),
                    data.get("static", ""),
                    data.get("rank", ""),
                    data.get("division", ""),
                    data.get("position", ""),
                    data.get("join_date", ""),
                    "Активен"
                ]
                personnel_sheet.append_row(row_data)
                
            elif action == "fired":
                # Помечаем как уволенного
                cell = personnel_sheet.find(str(member.id))
                if cell:
                    personnel_sheet.update_cell(cell.row, 8, "Уволен")  # Статус
                    
            elif action == "updated":
                # Обновляем данные
                cell = personnel_sheet.find(str(member.id))
                if cell:
                    personnel_sheet.update_cell(cell.row, 2, data.get("name", ""))  # Имя
                    personnel_sheet.update_cell(cell.row, 3, data.get("static", ""))  # Статик
                    personnel_sheet.update_cell(cell.row, 4, data.get("rank", ""))  # Звание
                    personnel_sheet.update_cell(cell.row, 5, data.get("division", ""))  # Подразделение
                    personnel_sheet.update_cell(cell.row, 6, data.get("position", ""))  # Должность
            
        except Exception as e:
            print(f"Ошибка обновления личного состава: {e}")

    @staticmethod
    def add_personnel(member: discord.Member, recruiter: discord.Member, division: str = "Академия ФСИН"):
        data = load_data()

        name_parts = member.display_name.split()
        name = name_parts[0] if len(name_parts) > 0 else member.name
        surname = name_parts[1] if len(name_parts) > 1 else ""
        full_name = f"{name} {surname}".strip()

        data["personnel"][str(member.id)] = {
            "name": full_name,
            "division": division,
            "rank": "Рядовой внутренней службы",
            "position": "",
            "recruiter": recruiter.display_name,
            "join_date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "static": ""
        }

        save_data(data)

        # Обновляем Google Sheets
        bot.loop.create_task(HRSystem.update_personnel_sheet(member, "hired"))

        return True
    
    async def process_audit(self, audit_data):
        """Обработка аудита из Google Таблиц"""
        try:
            # Создаем embed такой же как у бота
            action_colors = {
                "Принят": 0x00FF00,    # Зеленый
                "Уволен": 0xFF0000,    # Красный
                "Повышен": 0xFFA500,   # Оранжевый
                "Понижен": 0xFFFF00,   # Желтый
                "Переведен": 0xFFFF00  # Желтый
            }

            color = action_colors.get(audit_data['action'], 0x2E73F0)

            embed = discord.Embed(
                title="📝 Кадровый аудит ФСИН",
                color=color,
                timestamp=datetime.datetime.now()
            )

            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1401272012185276599/1412833532266418236/uvd.png?ex=68b9bb43&is=68b869c3&hm=aac09a72f63e8158a848deeee3dc279d6db20ead145b21b952e892567bc01fcb&")

            # Добавляем поля
            target_mention = f"<@{audit_data['discord_id']}>" if audit_data['discord_id'] else audit_data['full_name']

            embed.add_field(
                name="Кадровую отписал", 
                value="Google Таблица",
                inline=False
            )

            embed.add_field(
                name="Имя Фамилия | 6 цифр статика", 
                value=f"{audit_data['full_name']} | {audit_data['static']}", 
                inline=False
            )

            embed.add_field(name="Дата Действия", value=datetime.datetime.now().strftime("%d-%m-%Y"), inline=False)
            embed.add_field(name="Действие", value=audit_data['action'], inline=False)

            if audit_data['discord_id']:
                embed.add_field(name="Сотрудник", value=target_mention, inline=False)

            embed.add_field(name="Звание", value=audit_data['rank'], inline=True)
            embed.add_field(name="Подразделение", value=audit_data['division'], inline=True)
            embed.add_field(name="Источник", value="Google Таблица", inline=True)

            # Отправляем в канал аудита
            settings = load_settings()
            audit_channel_id = settings["channels"].get("logs", LOG_CHANNEL)
            channel = self.bot.get_channel(audit_channel_id)

            if channel:
                await channel.send(embed=embed)

                # Записываем в лист кадрового аудита
                await self.update_audit_sheet(audit_data)

                # Обновляем личный состав если действие - принят или уволен
                if audit_data['action'] in ['Принят', 'Уволен']:
                    await self.update_personnel_sheet(audit_data)

            return True

        except Exception as e:
            print(f"Ошибка обработки аудита: {e}")
            return False

    @staticmethod
    def update_personnel(member: discord.Member, **kwargs):
        data = load_data()
        if str(member.id) in data["personnel"]:
            data["personnel"][str(member.id)].update(kwargs)
            return save_data(data)
        return False

    @staticmethod
    def get_personnel(member: discord.Member):
        """Получить данные сотрудника"""
        data = load_data()
        return data["personnel"].get(str(member.id))

    @staticmethod
    def remove_personnel(member: discord.Member):
        """Удалить сотрудника из базы данных"""
        data = load_data()
        if str(member.id) in data["personnel"]:
            del data["personnel"][str(member.id)]
            save_data(data)
            
            # Обновляем Google Sheets
            bot.loop.create_task(HRSystem.update_personnel_sheet(member, "fired"))
            
            return True
        return False

    @staticmethod
    def get_all_personnel(division: str = None):
        data = load_data()
        if division:
            return {k: v for k, v in data["personnel"].items() if v["division"] == division}
        return data["personnel"]

class ModeratorRegistrationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        register_button = Button(
            label="Регистрация", 
            style=discord.ButtonStyle.primary, 
            emoji="📝", 
            custom_id="moderator_register_button"
        )
        self.add_item(register_button)

class ModeratorRegistrationForm(Modal, title='Регистрация модератора'):
    name = TextInput(
        label='Имя Фамилия',
        placeholder='Иван Иванов',
        required=True,
        max_length=100
    )
    
    static = TextInput(
        label='Статик',
        placeholder='XXX-XXX',
        required=True,
        max_length=7
    )
    
    email = TextInput(
        label='Почта Google',
        placeholder='example@gmail.com',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Отложить ответ
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        # Проверяем, является ли пользователь сотрудником
        personnel_data = HRSystem.get_personnel(interaction.user)
        if not personnel_data:
            await interaction.followup.send(
                "❌ Вы не являетесь сотрудником ФСИН!",
                ephemeral=True
            )
            return
        
        # Записываем данные в Google Таблицу
        settings = load_settings()
        if settings["google_sheets"].get("enabled", False) and google_sheets.sheet:
            try:
                # Ищем лист "Модераторы" или создаем его
                try:
                    mod_sheet = google_sheets.client.open_by_key(
                        settings["google_sheets"]["spreadsheet_id"]
                    ).worksheet("Модераторы")
                except gspread.WorksheetNotFound:
                    mod_sheet = google_sheets.client.open_by_key(
                        settings["google_sheets"]["spreadsheet_id"]
                    ).add_worksheet(title="Модераторы", rows="1000", cols="10")
                    headers = ["Дата", "Discord ID", "Имя Фамилия", "Статик", "Почта", "Статус"]
                    mod_sheet.insert_row(headers, 1)
                
                # Добавляем запись
                row_data = [
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    str(interaction.user.id),
                    self.name.value,
                    self.static.value,
                    self.email.value,
                    "На рассмотрении"
                ]
                mod_sheet.append_row(row_data)
                
                # Отправляем уведомление админам
                admin_embed = discord.Embed(
                    title="📋 Новая заявка модератора",
                    color=discord.Color.orange()
                )
                admin_embed.add_field(name="Сотрудник", value=f"{interaction.user.mention}", inline=False)
                admin_embed.add_field(name="Имя Фамилия", value=self.name.value, inline=True)
                admin_embed.add_field(name="Статик", value=self.static.value, inline=True)
                admin_embed.add_field(name="Почта", value=self.email.value, inline=False)
                admin_embed.set_footer(text="Требуется предоставить доступ к таблице")
                
                # Ищем канал для уведомлений или используем логи
                log_channel_id = settings["channels"].get("logs")
                if log_channel_id:
                    channel = bot.get_channel(log_channel_id)
                    if channel:
                        await channel.send(embed=admin_embed)
                
                await interaction.followup.send(
                    "✅ Ваша заявка отправлена на рассмотрение! Доступ будет предоставлен в течение 24 часов.",
                    ephemeral=True
                )
                
            except Exception as e:
                print(f"Ошибка записи заявки модератора: {e}")
                await interaction.followup.send(
                    "❌ Произошла ошибка при отправке заявки!",
                    ephemeral=True
                )

class RecruitmentButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        recruitment_button = Button(
            label="Подать заявку на вступление", 
            style=discord.ButtonStyle.green, 
            emoji="🎖️", 
            custom_id="recruitment_main_button"
        )
        self.add_item(recruitment_button)
    
# Модальные окна
class EditPersonnelModal(Modal, title='Редактирование сотрудника'):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member
        data = HRSystem.get_personnel(member) or {}
        
        self.name = TextInput(
            label='Имя',
            default=data.get("name", "").split()[0] if data.get("name") else "",
            required=True
        )
        self.surname = TextInput(
            label='Фамилия',
            default=data.get("name", "").split()[1] if data.get("name") and len(data.get("name", "").split()) > 1 else "",
            required=True
        )
        self.static = TextInput(
            label='Статик',
            default=data.get("static", ""),
            required=False
        )
        self.position = TextInput(
            label='Должность',
            default=data.get("position", ""),
            required=False
        )
        
        self.add_item(self.name)
        self.add_item(self.surname)
        self.add_item(self.static)
        self.add_item(self.position)
    
    async def on_submit(self, interaction: discord.Interaction):
        old_data = HRSystem.get_personnel(self.member) or {}
        updates = {
            "name": f"{self.name.value} {self.surname.value}",
            "static": self.static.value,
            "position": self.position.value
        }
        
        if HRSystem.update_personnel(self.member, **updates):
            await interaction.response.send_message(
                f"✅ Данные {self.member.mention} успешно обновлены!",
                ephemeral=True
            )
            
            # ИСПРАВЛЕННЫЙ ВЫЗОВ
            await HRSystem.log_action(
                action="Редактирование данных",
                target=self.member,
                executor=interaction.user,
                old_position=old_data.get("position", ""),
                new_position=self.position.value
            )
        else:
            await interaction.response.send_message(
                "❌ Не удалось обновить данные сотрудника!",
                ephemeral=True
            )

class RecruitmentForm(Modal, title='Заявка на вступление'):
    name = TextInput(label='Имя', placeholder='Иван', required=True)
    surname = TextInput(label='Фамилия', placeholder='Иванов', required=True)
    age = TextInput(label='Статик(6цифр XXX-XXX)', placeholder='XXX-XXX', required=True)
    experience = TextInput(
        label='Порядок набора',
        placeholder='Собеседование',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        settings = load_settings()
        requests_channel_id = settings["channels"].get("recruitment_requests", REQUESTS_CHANNEL)
        channel = bot.get_channel(requests_channel_id)

        embed = discord.Embed(
            title="📋 Заявка на получение роли",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="👤 Заявитель", value=f"<@{interaction.user.id}>", inline=False)
        embed.add_field(name="📝 Имя Фамилия", value=self.name.value + " " + self.surname.value, inline=True)
        embed.add_field(name="🔢 Статик", value=self.age.value, inline=True)
        embed.add_field(name="🎖️ Звание", value="Рядовой внутренней службы", inline=True)
        embed.add_field(name="📋 Порядок набора", value=self.experience.value, inline=False)

        if channel:
            view = RecruitmentRequestView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                "✅ Ваша заявка успешно отправлена на рассмотрение!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ошибка: канал для заявок не найден!",
                ephemeral=True
            )

class DismissalButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        dismissal_button = Button(
            label="Подать рапорт на увольнение", 
            style=discord.ButtonStyle.red, 
            emoji="🚪", 
            custom_id="dismissal_main_button"
        )
        self.add_item(dismissal_button)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        data = HRSystem.get_personnel(interaction.user)
        if not data:
            await interaction.response.send_message(
                "❌ Вы не являетесь сотрудником ФСИН!", 
                ephemeral=True
            )
            return False
        return True

class DismissalForm(Modal, title='Рапорт на увольнение'):
    reason = TextInput(
        label='Причина увольнения',
        style=discord.TextStyle.paragraph,
        placeholder='Опишите причину вашего увольнения',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        settings = load_settings()
        dismissal_channel_id = settings["channels"].get("dismissal_requests", DISMISSAL_CHANNEL)
        channel = bot.get_channel(dismissal_channel_id)
        
        embed = discord.Embed(
            title="🚨 Рапорт на увольнение",
            description=f"## <@{interaction.user.id}> подал рапорт на увольнение!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        text_before_embed = f"<@{interaction.user.id}>"
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        with open('personnel_data.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        user_id = str(interaction.user.id)
        full_name = data["personnel"][user_id]["name"]
        staticc = data["personnel"][user_id]["static"]
        divisionn = data["personnel"][user_id]["division"]
        rankk = data["personnel"][user_id]["rank"]

        embed.add_field(name="Имя Фамилия", value=full_name, inline=True)
        embed.add_field(name="Статик", value=staticc, inline=True)
        embed.add_field(name="Подразделение", value=divisionn, inline=True)
        embed.add_field(name="Звание", value=rankk, inline=True)
        embed.add_field(name="Причина увольнения", value=self.reason.value, inline=False)
        embed.set_footer(text=f"Отправлено: {interaction.user.display_name}")

        if channel:
            view = DismissalRequestView(interaction.user.id)
            await channel.send(content=text_before_embed, embed=embed, view=view)
            await interaction.response.send_message(
                "✅ Ваш рапорт на увольнение успешно отправлен!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ошибка: канал для рапортов не найден!",
                ephemeral=True
            )

# View классы
class RecruitmentRequestView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        approve_button = Button(label="Одобрить", style=discord.ButtonStyle.green, emoji="✅", custom_id="recruitment_approve")
        reject_button = Button(label="Отклонить", style=discord.ButtonStyle.red, emoji="❌", custom_id="recruitment_reject")
        
        self.add_item(approve_button)
        self.add_item(reject_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return has_recruitment_permissions(interaction.user)

class DismissalRequestView(View):
    def __init__(self, author_id: int = 0):
        super().__init__(timeout=None)
        self.author_id = author_id
        
        approve_button = Button(
            label="Одобрить", 
            style=discord.ButtonStyle.green, 
            emoji="✅", 
            custom_id="dismissal_approve"
        )
        reject_button = Button(
            label="Отклонить", 
            style=discord.ButtonStyle.red, 
            emoji="❌", 
            custom_id="dismissal_reject"
        )
        
        self.add_item(approve_button)
        self.add_item(reject_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id == 0:
            return has_dismissal_permissions(interaction.user)
        return has_dismissal_permissions(interaction.user) or interaction.user.id == self.author_id

class ConfirmDeleteView(View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id
        
        confirm_button = Button(
            label="Да, удалить", 
            style=discord.ButtonStyle.red, 
            emoji="⚠️", 
            custom_id="confirm_delete"
        )
        cancel_button = Button(
            label="Отмена", 
            style=discord.ButtonStyle.gray, 
            custom_id="cancel_delete"
        )
        
        self.add_item(confirm_button)
        self.add_item(cancel_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id or has_dismissal_permissions(interaction.user)

# Настройки View
class SettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        channel_button = Button(label="Настройка каналов", style=discord.ButtonStyle.primary, emoji="📝", custom_id="settings_channels")
        roles_button = Button(label="Настройка ролей", style=discord.ButtonStyle.primary, emoji="👑", custom_id="settings_roles")
        admins_button = Button(label="Управление админами", style=discord.ButtonStyle.success, emoji="⚙️", custom_id="settings_admins")
        moderators_button = Button(label="Управление модераторами", style=discord.ButtonStyle.success, emoji="🛠️", custom_id="settings_moderators")
        google_button = Button(label="Настройка Google Sheets", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="settings_google")
        reload_button = Button(label="Перезагрузить бота", style=discord.ButtonStyle.danger, emoji="🔄", custom_id="settings_reload")
        
        self.add_item(channel_button)
        self.add_item(roles_button)
        self.add_item(admins_button)
        self.add_item(moderators_button)
        self.add_item(google_button)
        self.add_item(reload_button)

class ChannelSettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        recruitment_button = Button(label="Канал заявок", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="channel_recruitment")
        dismissal_button = Button(label="Канал рапортов", style=discord.ButtonStyle.secondary, emoji="🚪", custom_id="channel_dismissal")
        logs_button = Button(label="Канал логов", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="channel_logs")
        status_button = Button(label="Канал статусов", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="channel_status")
        back_button = Button(label="Назад", style=discord.ButtonStyle.gray, emoji="◀️", custom_id="settings_back")
        
        self.add_item(recruitment_button)
        self.add_item(dismissal_button)
        self.add_item(logs_button)
        self.add_item(status_button)
        self.add_item(back_button)

class RoleSettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        recruitment_button = Button(label="Роль заявок", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="role_recruitment")
        hr_button = Button(label="Роль кадров", style=discord.ButtonStyle.secondary, emoji="👔", custom_id="role_hr")
        dismissal_button = Button(label="Роль увольнений", style=discord.ButtonStyle.secondary, emoji="🚪", custom_id="role_dismissal")
        back_button = Button(label="Назад", style=discord.ButtonStyle.gray, emoji="◀️", custom_id="settings_back")
        
        self.add_item(recruitment_button)
        self.add_item(hr_button)
        self.add_item(dismissal_button)
        self.add_item(back_button)

class AdminManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        add_admin_button = Button(label="Добавить админа", style=discord.ButtonStyle.success, emoji="➕", custom_id="admin_add")
        remove_admin_button = Button(label="Удалить админа", style=discord.ButtonStyle.danger, emoji="➖", custom_id="admin_remove")
        list_admins_button = Button(label="Список админов", style=discord.ButtonStyle.primary, emoji="📋", custom_id="admin_list")
        back_button = Button(label="Назад", style=discord.ButtonStyle.gray, emoji="◀️", custom_id="settings_back")
        
        self.add_item(add_admin_button)
        self.add_item(remove_admin_button)
        self.add_item(list_admins_button)
        self.add_item(back_button)

class ModeratorManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        add_mod_button = Button(label="Добавить модератора", style=discord.ButtonStyle.success, emoji="➕", custom_id="mod_add")
        remove_mod_button = Button(label="Удалить модератора", style=discord.ButtonStyle.danger, emoji="➖", custom_id="mod_remove")
        list_mods_button = Button(label="Список модераторов", style=discord.ButtonStyle.primary, emoji="📋", custom_id="mod_list")
        back_button = Button(label="Назад", style=discord.ButtonStyle.gray, emoji="◀️", custom_id="settings_back")
        
        self.add_item(add_mod_button)
        self.add_item(remove_mod_button)
        self.add_item(list_mods_button)
        self.add_item(back_button)

class GoogleSettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        enable_button = Button(label="Включить/Выключить", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="google_toggle")
        setup_button = Button(label="Настроить таблицу", style=discord.ButtonStyle.secondary, emoji="📝", custom_id="google_setup")
        test_button = Button(label="Тест подключения", style=discord.ButtonStyle.success, emoji="✅", custom_id="google_test")
        back_button = Button(label="Назад", style=discord.ButtonStyle.gray, emoji="◀️", custom_id="settings_back")
        
        self.add_item(enable_button)
        self.add_item(setup_button)
        self.add_item(test_button)
        self.add_item(back_button)

# Обработчики взаимодействий
async def handle_recruitment_approve(interaction: discord.Interaction):
    try:
        if not has_recruitment_permissions(interaction.user):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ У вас нет прав для одобрения заявок!", ephemeral=True)
            return

        # Отложить ответ сразу
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)

        embed = interaction.message.embeds[0]
        user_id = int(embed.fields[0].value[2:-1])
        member = interaction.guild.get_member(user_id)
        
        if not member:
            await interaction.followup.send("❌ Пользователь не найден на сервере!", ephemeral=True)
            return

        full_name = None
        static = None
        reason = None
        
        for field in embed.fields:
            if field.name == "📝 Имя Фамилия":
                full_name = field.value
            elif field.name == "🔢 Статик":
                static = field.value
            elif field.name == "📋 Порядок набора":
                reason = field.value
        
        if not full_name:
            await interaction.followup.send("❌ Не найдено поле с именем в заявке!", ephemeral=True)
            return

        try:
            await member.edit(nick=f"Курсант | {full_name}")
        except discord.Forbidden:
            pass

        HRSystem.add_personnel(member, interaction.user)
        updates = {
            "name": full_name,
            "static": static if static else "",
            "division": "Академия ФСИН"
        }
        HRSystem.update_personnel(member, **updates)

        try:
            roles_to_add = [
                discord.utils.get(interaction.guild.roles, name="========[🔗]Отдел[🔗]========"),
                discord.utils.get(interaction.guild.roles, name="Рядовой внутренней службы"),
                discord.utils.get(interaction.guild.roles, name="Академия ФСИН"),
                discord.utils.get(interaction.guild.roles, name="========[📘]Доступ[📘]========"),
                discord.utils.get(interaction.guild.roles, name="[©️] Сотрудник ФСИН"),
                discord.utils.get(interaction.guild.roles, name="========[👨🏻‍✈️]Звание[👨🏻‍✈️]========")
            ]
            
            for role in roles_to_add:
                if role:
                    await member.add_roles(role)
        except Exception as e:
            print(f"Ошибка при выдаче ролей: {e}")

        new_embed = embed.copy()
        new_embed.color = discord.Color.green()
        new_embed.add_field(
            name="✅ Статус",
            value=f"Одобрено Отделом Кадров {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(embed=new_embed, view=None)

        await HRSystem.log_action(
            action="Принятие на службу",
            target=member,
            executor=interaction.user,
            reason=reason or "Не указана",
            new_rank="Рядовой внутренней службы"
        )

        try:
            await member.send("🎉 Ваша заявка на вступление была одобрена! Добро пожаловать в ряды ФСИН!")
        except discord.Forbidden:
            pass

        # Используем followup вместо response
        await interaction.followup.send("✅ Заявка успешно одобрена!", ephemeral=True)

    except Exception as e:
        print(f"Ошибка в handle_recruitment_approve: {e}")
        try:
            # Пытаемся использовать followup, если response уже использован
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке заявки!",
                ephemeral=True
            )
        except:
            # Если всё провалилось, просто логируем ошибку
            print("Не удалось отправить сообщение об ошибке: взаимодействие завершено")

async def handle_recruitment_reject(interaction: discord.Interaction):
    if not has_recruitment_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для отклонения заявок!", ephemeral=True)
        return
    
    embed = interaction.message.embeds[0]
    user_id = int(embed.fields[0].value[2:-1])
    member = interaction.guild.get_member(user_id)
    
    embed.color = discord.Color.red()
    embed.add_field(name="Статус", value=f"❌ Отклонена инструктором ОРЛС {interaction.user.mention}", inline=True)
    
    await interaction.message.edit(embed=embed, view=None)
    
    settings = load_settings()
    status_channel_id = settings["channels"].get("status", REQUEST_STATUS_CHANNEL)
    status_channel = bot.get_channel(status_channel_id)
    
    if status_channel:
        await status_channel.send(embed=embed)
    
    if member:
        try:
            await member.send("😔 Ваша заявка на вступление была отклонена. Вы можете подать новую заявку позже.")
        except discord.Forbidden:
            pass
    
    await interaction.response.send_message("✅ Заявка успешно отклонена!", ephemeral=True)

async def handle_dismissal_approve(interaction: discord.Interaction):
    try:
        if not has_dismissal_permissions(interaction.user):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ У вас нет прав для одобрения рапортов!", ephemeral=True)
            return
        
        # Отложить ответ сразу
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)

        embed = interaction.message.embeds[0]
        user_id = int(embed.description.split()[1][2:-1])
        member = interaction.guild.get_member(user_id)
        
        if not member:
            await interaction.followup.send("❌ Пользователь не найден на сервере!", ephemeral=True)
            return
        
        data = HRSystem.get_personnel(member)
        
        reason = None
        for field in embed.fields:
            if field.name == "Причина увольнения":
                reason = field.value
                break
        
        if data:
            full_name = data["name"]
            division = data.get("division", "Не указано")
            rank = data.get("rank", "Не указано")
            static = data.get("static", "Не указан")
            position = data.get("position", "Не указана")
            
            roles_to_remove = [role for role in member.roles if role.name != "@everyone"]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            
            try:
                await member.edit(nick=f"Уволен | {full_name}")
            except discord.Forbidden:
                pass
            
            await HRSystem.log_action(
                action="Увольнение",
                target=member,
                executor=interaction.user,
                reason=reason or "Не указана",
                old_rank=rank,
                old_position=position
            )
        else:
            try:
                await member.edit(nick=f"Уволен | {member.display_name}")
            except discord.Forbidden:
                pass
            
            await HRSystem.log_action(
                action="Увольнение (не был в базе)",
                target=member,
                executor=interaction.user,
                reason=reason or "Не указана"
            )
        
        HRSystem.remove_personnel(member)

        new_embed = embed.copy()
        new_embed.color = discord.Color.green()
        new_embed.add_field(
            name="✅ Обработано", 
            value=f"Сотрудник: {interaction.user.mention}\nВремя: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", 
            inline=True
        )
        
        await interaction.message.edit(embed=new_embed, view=None)
        
        try:
            await member.send("ℹ️ Ваш рапорт на увольнение был одобрен. Спасибо за службу!")
        except discord.Forbidden:
            pass
        
        # Используем followup вместо response, так как мы уже использовали defer
        await interaction.followup.send("✅ Рапорт на увольнение успешно одобрен!", ephemeral=True)

    except Exception as e:
        print(f"Ошибка в handle_dismissal_approve: {e}")
        try:
            # Пытаемся использовать followup, если response уже использован
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке рапорта!",
                ephemeral=True
            )
        except:
            # Если всё провалилось, просто логируем ошибку
            print("Не удалось отправить сообщение об ошибке: взаимодействие завершено")

async def handle_dismissal_reject(interaction: discord.Interaction):
    if not has_dismissal_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для отклонения рапортов!", ephemeral=True)
        return
    
    embed = interaction.message.embeds[0]
    user_id = int(embed.description.split()[1][2:-1])
    member = interaction.guild.get_member(user_id)
    
    embed.color = discord.Color.red()
    embed.add_field(name="❌Обработано", value=f"Сотрудник: {interaction.user.mention}\nВремя: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", inline=True)
    
    await interaction.message.edit(embed=embed, view=None)
    
    if member:
        try:
            await member.send("ℹ️ Ваш рапорт на увольнение был отклонен. Обратитесь к командованию для уточнения деталей.")
        except discord.Forbidden:
            pass
    
    await interaction.response.send_message("✅ Рапорт на увольнение успешно отклонен!", ephemeral=True)

async def handle_dismissal_delete(interaction: discord.Interaction):
    try:
        embed = interaction.message.embeds[0]
        description = embed.description
        match = re.search(r'<@(\d+)>', description)
        
        if not match:
            await interaction.response.send_message(
                "❌ Не удалось определить автора рапорта!",
                ephemeral=True
            )
            return
            
        author_id = int(match.group(1))
        
        if interaction.user.id != author_id and not has_dismissal_permissions(interaction.user):
            await interaction.response.send_message(
                "❌ Вы можете удалять только свои рапорты!",
                ephemeral=True
            )
            return
        
        confirm_embed = discord.Embed(
            title="⚠️ Подтвердите удаление",
            description=f"Вы действительно хотите удалить этот рапорт?",
            color=discord.Color.orange()
        )
        
        view = ConfirmDeleteView(author_id)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
    except Exception as e:
        print(f"Ошибка при обработке удаления: {e}")
        await interaction.response.send_message(
            "❌ Произошла ошибка при обработке запроса!",
            ephemeral=True
        )

async def handle_confirm_delete(interaction: discord.Interaction, user_id: int):
    try:
        original_message = None
        async for message in interaction.channel.history(limit=100):
            if message.embeds and message.embeds[0].description:
                description = message.embeds[0].description
                user_mention = re.search(r'<@(\d+)>', description)
                if user_mention and int(user_mention.group(1)) == user_id:
                    original_message = message
                    break
        
        if original_message:
            await original_message.delete()
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"✅ Рапорт на увольнение пользователя <@{user_id}> был удален.",
                    ephemeral=True
                )
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Не удалось найти исходный рапорт для удаления!",
                    ephemeral=True
                )
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass

    except Exception as e:
        print(f"Ошибка при удалении рапорта: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Произошла ошибка при удалении рапорта!",
                ephemeral=True
            )


@bot.tree.command(name="проверить_гугл", description="Проверить подключение к Google Sheets")
async def check_google(interaction: discord.Interaction):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    if not os.path.exists(GOOGLE_CREDS_FILE):
        await interaction.response.send_message("❌ Файл google_credentials.json не найден!", ephemeral=True)
        return
    
    if google_sheets.initialize():
        settings = load_settings()
        spreadsheet_id = settings["google_sheets"].get("spreadsheet_id")
        
        if spreadsheet_id:
            try:
                success = google_sheets.setup_spreadsheet(spreadsheet_id)
                if success:
                    await interaction.response.send_message("✅ Подключение к Google Sheets успешно!", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Ошибка доступа к таблице! Проверьте ID и права доступа.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ID таблицы не настроен!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Ошибка подключения к Google API!", ephemeral=True)


# Команды бота
@bot.tree.command(name="настройки", description="Панель управления настройками бота")
async def settings_command(interaction: discord.Interaction):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚙️ Панель управления ботом",
        description="Выберите раздел для настройки:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📝 Настройка каналов",
        value="Настройка каналов для заявок, логов и статусов",
        inline=False
    )
    
    embed.add_field(
        name="👑 Настройка ролей",
        value="Настройка ролей для доступа к различным функциям",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Управление админами",
        value="Добавление и удаление администраторов бота",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Управление модераторами",
        value="Добавление и удаление модераторов бота",
        inline=False
    )
    
    embed.add_field(
        name="📊 Настройка Google Sheets",
        value="Интеграция с Google Таблицами для кадрового аудита",
        inline=False
    )
    
    embed.add_field(
        name="🔄 Перезагрузка",
        value="Горячая перезагрузка бота",
        inline=False
    )
    
    view = SettingsView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="вызвать_действие", description="Вызвать определенное действие (только для админов)")
@app_commands.describe(действие="Выберите действие для вызова")
@app_commands.choices(действие=[
    app_commands.Choice(name="Получение роли", value="role"),
    app_commands.Choice(name="Рапорт на увольнение", value="dismissal"),
    app_commands.Choice(name="Запрос склада", value="warehouse"),
    app_commands.Choice(name="Регистрация модератора", value="moderator_registration")  # Новое действие
])
async def call_action(interaction: discord.Interaction, действие: app_commands.Choice[str]):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    await interaction.response.send_message("✅ Действие успешно вызвано!", ephemeral=True)
    
    if действие.value == "role":
        recruitment_embed = discord.Embed(
            title="🎖️ Получение ролей на сервере",
            description="Добро пожаловать! Для получения соответствующих ролей на сервере выберите подходящий вариант ниже.\n"
            "### 📋 Важная информация:\n"
            "> • Одна заявка - подавайте только одну заявку за раз\n"
            "> • Достоверные данные - указывайте только правдивую информацию\n"
            "> • Доказательства - приложите ссылки на подтверждающие документы (если требуется)\n"
            "> • Терпение - дождитесь рассмотрения (у нас есть 24 часов)\n"
            " \n"
            "## ⏰ Время рассмотрения: обычно до 24 часов\n",
            color=0x69ED69
        )
        recruitment_embed.add_field(
            name="Собеседование",
            value="> • Участвуете в собеседовании\n",
            inline=True
        )
        recruitment_embed.set_footer(text="Нажмите на соответствующую кнопку ниже для подача заявки")
        
        recruitment_view = RecruitmentButtonView()
        await interaction.channel.send(embed=recruitment_embed, view=recruitment_view)
    
    elif действие.value == "dismissal":
        dismissal_embed = discord.Embed(
            title="Рапорты на увольнение",
            description="Нажмите на кнопку ниже, чтобы отправить рапорт на увольнение.",
            color=0x0000ff
        )
        dismissal_embed.add_field(
            name="Инструкция",
            value="1. Нажмите на кнопку и заполните открывшуюся форму\n2. Нажмите 'Отправить'\n3. Ваш рапорт будет рассматриваться в течении __24 часов__.",
            inline=False
        )
        
        dismissal_view = DismissalButtonView()
        await interaction.channel.send(embed=dismissal_embed, view=dismissal_view)
    
    elif действие.value == "warehouse":
        embed = await create_warehouse_embed()
        view = WarehouseMainView()
        await interaction.channel.send(embed=embed, view=view)

    elif действие.value == "moderator_registration":
        embed = discord.Embed(
            title="📋 Регистрация модератора кадрового аудита",
            description="Для регистрации в качестве модератора кадрового аудита нажмите кнопку ниже и заполните форму.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Требования",
            value="• Действующий сотрудник ФСИН\n• Наличие доступа к Google аккаунту\n• Ответственность и внимательность",
            inline=False
        )
        embed.set_footer(text="Доступ к таблице будет предоставлен в течение 24 часов")
        
        view = ModeratorRegistrationView()
        await interaction.channel.send(embed=embed, view=view)
        
# Остальные команды остаются без изменений (чc, кадровый, личное_дело, состав, редактировать_сотрудника, setup, перезагрузить)
@bot.tree.command(name="чc", description="Добавить пользователя в черный список")
@app_commands.describe(
    имя_фамилия="Имя и фамилия нарушителя",
    статик="Статик нарушителя (формат XXX-XXX)",
    причина="Причина добавления в черный список",
    дата_начала="Дата начала (ДД.ММ.ГГГГ)",
    дата_окончания="Дата окончания (ДД.ММ.ГГГГ)",
    доказательства="Ссылка на сообщение с доказательствами"
)
async def blacklist(
    interaction: discord.Interaction,
    имя_фамилия: str,
    статик: str,
    причина: str,
    дата_начала: str,
    дата_окончания: str,
    доказательства: str
):
    if not has_hr_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    if not re.match(r'^\d{3}-\d{3}$', статик):
        await interaction.response.send_message(
            "❌ Неверный формат статика! Используйте формат XXX-XXX",
            ephemeral=True
        )
        return
    
    date_pattern = r'^\d{2}\.\d{2}\.\d{4}$'
    if not re.match(date_pattern, дата_начала) or not re.match(date_pattern, дата_окончания):
        await interaction.response.send_message(
            "❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ",
            ephemeral=True
        )
        return
    
    executor_data = HRSystem.get_personnel(interaction.user) or {}
    executor_name = executor_data.get("name", interaction.user.display_name)
    executor_static = executor_data.get("static", "Не указан")
    
    embed = discord.Embed(
        title="📋 Новое дело",
        color=discord.Color.dark_red(),
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1407347004400472176/1419651572622823514/Gerb_FSIN.png?ex=68d2890e&is=68d1378e&hm=0bc74b74ae48c0f732d5a4af3610c3de78d1afddf7da41fb25f8f604f982bbb5&")
    
    embed.add_field(
        name="1. Кто выдаёт",
        value=f"{executor_name} | {executor_static}",
        inline=False
    )
    embed.add_field(
        name="2. Кому",
        value=f"{имя_фамилия} | {статик}",
        inline=False
    )
    embed.add_field(
        name="3. Причина",
        value=причина,
        inline=False
    )
    embed.add_field(
        name="4. Дата начала",
        value=дата_начала,
        inline=True
    )
    embed.add_field(
        name="5. Дата окончания",
        value=дата_окончания,
        inline=True
    )
    embed.add_field(
        name="6. Доказательства",
        value=f"{доказательства}",
        inline=False
    )
    
    embed.set_footer(text=f"{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    role_mentions = "<@&1245655012760092705> <@&1335657685940572253> <@&1246113710255374336>"
    
    try:
        await interaction.response.send_message(content=role_mentions, embed=embed)
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        await interaction.response.send_message(
            "❌ Произошла ошибка при создании дела!",
            ephemeral=True
        )

@bot.tree.command(name="кадровый", description="Управление кадровыми изменениями")
@app_commands.describe(
    действие="Выберите действие",
    сотрудник="Участник сервера",
    имя_фамилия="Имя и фамилия бойца (только для принятия)",
    статик="Статик бойца (6 цифр, формат XXX-XXX, только для принятия)",
    причина="Причина изменени�� (для принятия/увольнения)",
    звание="Выберите звание (для повышения/понижения)",
    подразделение="Выберите подразделение (для перевода)",
    должность="Выберите должность (для назначения)"
)
@app_commands.choices(действие=[
    app_commands.Choice(name="Принят", value="hired"),
    app_commands.Choice(name="Повышен", value="promoted"),
    app_commands.Choice(name="Понижен", value="demoted"),
    app_commands.Choice(name="Уволен", value="fired"),
    app_commands.Choice(name="Переведен", value="transferred"),
    app_commands.Choice(name="Назначить должность", value="position")
])
@app_commands.choices(звание=[
    app_commands.Choice(name=rank, value=rank) for rank in RANK_HIERARCHY
])
@app_commands.choices(подразделение=[
    app_commands.Choice(name=div, value=div) for div in DIVISIONS
])
@app_commands.choices(должность=[
    app_commands.Choice(name=pos, value=pos) for pos in POSITIONS
])
async def hr_command(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    сотрудник: discord.Member,
    имя_фамилия: Optional[str] = None,
    статик: Optional[str] = None,
    причина: Optional[str] = None,
    звание: Optional[app_commands.Choice[str]] = None,
    подразделение: Optional[app_commands.Choice[str]] = None,
    должность: Optional[app_commands.Choice[str]] = None
):
    if not has_hr_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    action = действие.value
    
    if action == "hired":
        if not имя_фамилия:
            await interaction.response.send_message(
                "❌ Для принятия сотрудника необходимо указать его имя и фамилию!",
                ephemeral=True
            )
            return
        if not статик:
            await interaction.response.send_message(
                "❌ Для принятия бойца необходимо указать его статик (6 цифр, формат XXX-XXX)!",
                ephemeral=True
            )
            return
        if not re.match(r'^\d{3}-\d{3}$', статик):
            await interaction.response.send_message(
                "❌ Неверный формат статика! Используйте 6 цифр в формате XXX-XXX",
                ephemeral=True
            )
            return

    if action == "position":
        if not должность:
            await interaction.response.send_message("❌ Укажите должность!", ephemeral=True)
            return
        
        if not звание:
            await interaction.response.send_message("❌ Укажите звание для назначения на должность!", ephemeral=True)
            return
            
        position = должность.value
        new_rank = звание.value
        
        HRSystem.update_personnel(сотрудник, position=position, rank=new_rank)
        
        # Исправлено: правильное удаление ролей
        for role in сотрудник.roles:
            if role.name in RANK_HIERARCHY:
                await сотрудник.remove_roles(role)
        
        new_role = discord.utils.get(interaction.guild.roles, name=new_rank)
        if new_role:
            await сотрудник.add_roles(new_role)
        
        data = HRSystem.get_personnel(сотрудник)
        full_name = data["name"] if data else сотрудник.display_name
        division = data["division"] if data else "Академия ФСИН"
        
        try:
            await сотрудник.edit(nick=f"{division} | {full_name}")
        except discord.Forbidden:
            pass
        
        await HRSystem.log_action(
            action="Назначение на должность",
            target=сотрудник,
            executor=interaction.user,
            reason=причина or "Не указана"
        )
        
        await interaction.response.send_message(
            f"✅ {сотрудник.mention} назначен на должность: {position} с званием {new_rank}!",
            ephemeral=True
        )
        return
    
    elif action == "transferred":
        if not подразделение:
            await interaction.response.send_message("❌ Укажите подразделение!", ephemeral=True)
            return
            
        division = подразделение.value
        HRSystem.update_personnel(сотрудник, division=division)
        
        data = HRSystem.get_personnel(сотрудник)
        full_name = data["name"] if data else сотрудник.display_name

        # Исправлено: правильное удаление ролей подразделений
        for role in сотрудник.roles:
            if role.name in DIVISIONS:
                await сотрудник.remove_roles(role)
        
        new_div_role = discord.utils.get(interaction.guild.roles, name=division)
        if new_div_role:
            await сотрудник.add_roles(new_div_role)
        
        try:
            await сотрудник.edit(nick=f"{division} | {full_name}")
        except discord.Forbidden:
            pass
        
        await HRSystem.log_action(
            action="Перевод в другое подразделение",
            target=сотрудник,
            executor=interaction.user,
            old_division=old_division,  # Если есть старое подразделение
            new_division=division,      # Новое подразделение
            reason=причина or "Не указана"
        )
        
        await interaction.response.send_message(
            f"✅ {сотрудник.mention} переведен в {division}!",
            ephemeral=True
        )
        return
    
    elif action in ["promoted", "demoted"]:
        if not звание:
            await interaction.response.send_message("❌ Укажите звание!", ephemeral=True)
            return
            
        new_rank = звание.value
        
        personnel_data = HRSystem.get_personnel(сотрудник)
        if not personnel_data:
            await interaction.response.send_message("❌ Сотрудник не найден в базе данных!", ephemeral=True)
            return
            
        current_rank = personnel_data.get("rank", "Рядовой")
        
        try:
            current_index = RANK_HIERARCHY.index(current_rank)
            new_index = RANK_HIERARCHY.index(new_rank)
        except ValueError:
            await interaction.response.send_message("❌ Ошибка в иерархии званий!", ephemeral=True)
            return
        
        if action == "promoted":
            if new_index <= current_index:
                await interaction.response.send_message(
                    f"❌ Новое звание должно быть выше текущего ({current_rank})!",
                    ephemeral=True
                )
                return
        elif action == "demoted":
            if new_index >= current_index:
                await interaction.response.send_message(
                    f"❌ Новое звание должно быть ниже текущего ({current_rank})!",
                    ephemeral=True
                )
                return
        
        # Исправлено: правильное удаление ролей
        for role in сотрудник.roles:
            if role.name in RANK_HIERARCHY:
                await сотрудник.remove_roles(role)
        
        new_role = discord.utils.get(interaction.guild.roles, name=new_rank)
        if new_role:
            await сотрудник.add_roles(new_role)
        
        HRSystem.update_personnel(сотрудник, rank=new_rank)
        
        data = HRSystem.get_personnel(сотрудник)
        full_name = data["name"] if data else сотрудник.display_name
        division = data["division"] if data else "Академия ФСИН"
        
        try:
            await сотрудник.edit(nick=f"{division} | {full_name}")
        except discord.Forbidden:
            pass
        
        await HRSystem.log_action(
            action=f"{'Повышение' if action == 'promoted' else 'Понижение'} в звании",
            target=сотрудник,
            executor=interaction.user,
            old_rank=current_rank,
            new_rank=new_rank,
            reason=причина or "Не указана"
        )
        
        await interaction.response.send_message(
            f"✅ {сотрудник.mention} {'повышен' if action == 'promoted' else 'понижен'} до {new_rank}!",
            ephemeral=True
        )
        return
    
    await process_hr_action(interaction, action, сотрудник, имя_фамилия, причина, статик)

async def process_hr_action(
    interaction: discord.Interaction, 
    action: str, 
    member: discord.Member,
    full_name: str = None,
    reason: str = None,
    static: str = None
):
    executor = interaction.user
    
    try:
        if action == "hired":
            if not reason:
                await interaction.response.send_message("❌ Укажите причину принятия!", ephemeral=True)
                return
            
            if not full_name:
                await interaction.response.send_message("❌ Укажите имя и фамилию сотрудника!", ephemeral=True)
                return
            
            full_name = ' '.join(full_name.split())
            
            try:
                roles_to_add = [
                    discord.utils.get(interaction.guild.roles, name="========[🔗]Отдел[🔗]========"),
                    discord.utils.get(interaction.guild.roles, name="Рядовой внутренней службы"),
                    discord.utils.get(interaction.guild.roles, name="Академия ФСИН"),
                    discord.utils.get(interaction.guild.roles, name="========[📘]Доступ[📘]========"),
                    discord.utils.get(interaction.guild.roles, name="[©️] Сотрудник ФСИН"),
                    discord.utils.get(interaction.guild.roles, name="========[👨🏻‍✈️]Звание[👨🏻‍✈️]========")
                ]
                
                for role in roles_to_add:
                    if role:
                        await member.add_roles(role)
            except Exception as e:
                print(f"Ошибка при выдаче ролей: {e}")
            
            try:
                await member.edit(nick=f"Курсант | {full_name}")
            except discord.Forbidden:
                pass
            
            HRSystem.add_personnel(member, interaction.user)
            updates = {
                "name": full_name,
                "static": static if static else "XXX-XXX",
                "division": "Академия ФСИН"
            }
            HRSystem.update_personnel(member, **updates)
            
            # ИСПРАВЛЕННЫЙ ВЫЗОВ
            await HRSystem.log_action(
                action="Принятие на службу",
                target=member,
                executor=executor,
                reason=reason,
                new_rank="Рядовой внутренней службы"
            )
            
            await interaction.response.send_message(
                f"✅ {member.mention} принят по контракту как {full_name}!",
                ephemeral=True
            )
            
        elif action == "fired":
            if not reason:
                await interaction.response.send_message("❌ Укажите причину увольнения!", ephemeral=True)
                return
            
            roles_to_remove = [role for role in member.roles if role.name != "@everyone"]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            
            data = HRSystem.get_personnel(member)
            current_name = data["name"] if data else member.display_name
            
            try:
                await member.edit(nick=f"Уволен | {current_name}")
            except discord.Forbidden:
                pass
            
            
            await HRSystem.log_action(
                action="Увольнение",
                target=member,
                executor=executor,
                old_division=data.get("division", "Не указано") if data else "Не указано",  # Исправлено
                reason=reason
            )

            HRSystem.remove_personnel(member)
            
            await interaction.response.send_message(
                f"✅ {member.mention} уволен!",
                ephemeral=True
            )
    
    except Exception as e:
        print(f"Ошибка: {e}")
        await interaction.response.send_message(
            "❌ Произошла ошибка при выполнении команды!",
            ephemeral=True
        )

@bot.tree.command(name="личное_дело", description="Просмотреть личное дело сотрудника")
@app_commands.describe(сотрудник="Участник сервера")
async def personnel_file(interaction: discord.Interaction, сотрудник: discord.Member):
    if not has_hr_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    data = HRSystem.get_personnel(сотрудник)
    if not data:
        await interaction.response.send_message("❌ Сотрудник не найден в базе!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"📂 Личное дело: {data['name']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Подразделение", value=data["division"], inline=True)
    embed.add_field(name="Звание", value=data["rank"], inline=True)
    embed.add_field(name="Должность", value=data["position"] or "Не указана", inline=True)
    embed.add_field(name="Статик", value=data["static"] or "Не указан", inline=True)
    embed.add_field(name="Принят", value=data["join_date"], inline=True)
    embed.add_field(name="Принявший", value=data["recruiter"], inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="состав", description="Просмотр состава подразделения")
@app_commands.describe(подразделение="Выберите подразделение")
@app_commands.choices(подразделение=[
    app_commands.Choice(name="Все", value="all"),
    *[app_commands.Choice(name=d, value=d) for d in DIVISIONS]
])
async def personnel_list(interaction: discord.Interaction, подразделение: app_commands.Choice[str]):
    if not has_hr_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    division = подразделение.value if подразделение.value != "all" else None
    personnel = HRSystem.get_all_personnel(division)
    
    if not personnel:
        await interaction.response.send_message("❌ В базе нет сотрудников!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"📋 Состав подразделения: {подразделение.name if division else 'Все'}",
        color=discord.Color.green()
    )
    
    for user_id, data in personnel.items():
        member = interaction.guild.get_member(int(user_id))
        mention = member.mention if member else "❌ Участник не на сервере"
        embed.add_field(
            name=f"{data['name']} ({data['division']})",
            value=f"{mention} | {data['rank']} | {data['position'] or 'Без должности'}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="редактировать_сотрудника", description="Редактировать данные сотрудника")
@app_commands.describe(сотрудник="Участник сервера")
async def edit_personnel(interaction: discord.Interaction, сотрудник: discord.Member):
    if not has_hr_permissions(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    await interaction.response.send_modal(EditPersonnelModal(сотрудник))

@bot.tree.command(name="setup", description="Настройка системы заявок")
async def setup(interaction: discord.Interaction):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    dismissal_embed = discord.Embed(
        title="Рапорты на увольнение",
        description="Нажмите на кнопку ниже, чтобы отправить рапорт на увольнение.",
        color=discord.Color.blue()
    )
    dismissal_embed.add_field(
        name="Инструкция",
        value="1. Нажмите на кнопку и заполните открывшуюся форму\n2. Нажмите 'Отправить'\n3. Ваш рапорт будет рассматриваться в течении __24 часов__.",
        inline=False
    )
    
    async def dismissal_callback(interaction: discord.Interaction):
        await interaction.response.send_modal(DismissalForm())
    
    dismissal_button.callback = dismissal_callback
    dismissal_view = View()
    dismissal_view.add_item(dismissal_button)
    
    recruitment_embed = discord.Embed(
        title="🎖️ Получение ролей на сервере",
        description="Добро пожаловать! Для получения соответствующих ролей на сервере выберите подходящий вариант ниже.\n"
        "**📋 Важная информация:**\n"
        "> • Одна заявка - подавайте только одну заявку за раз\n"
        "> • Достоверные данные - указывайте только правдивую информацию\n"
        "> • Доказательства - приложите ссылки на подтверждающие документы (если требуется)\n"
        "> • Терпение - дождитесь рассмотрения (у нас есть 24 часа)\n"
        " \n"
        "## ⏰ Время рассмотрения: обычно до 24 часов\n",
        color=discord.Color.green()
    )
    recruitment_embed.add_field(
        name="🪖 Призыв / Экскурсия",
        value="> • Проходите собеседование\n",
        inline=True
    )
    recruitment_embed.set_footer(text="Нажмите на соответствующую кнопку ниже для подачи заявки")
    recruitment_button = Button(label="Собеседование", style=discord.ButtonStyle.green, emoji="📜")
    
    async def recruitment_callback(interaction: discord.Interaction):
        await interaction.response.send_modal(RecruitmentForm())
    
    recruitment_button.callback = recruitment_callback
    recruitment_view = View()
    recruitment_view.add_item(recruitment_button)
    
    channel = interaction.channel
    await channel.send(embed=dismissal_embed, view=dismissal_view)
    await channel.send(embed=recruitment_embed, view=recruitment_view)
    
    await interaction.response.send_message("✅ Система заявок настроена!", ephemeral=True)

@bot.tree.command(name="перезагрузить", description="Горячая перезагрузка бота (только для админов)")
async def reload_bot(interaction: discord.Interaction):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    await interaction.response.send_message("🔄 Перезагружаю бота...", ephemeral=True)
    
    # Перезагрузка модулей
    modules_to_reload = []
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('discord'):
            modules_to_reload.append(module_name)
    
    for module_name in modules_to_reload:
        try:
            importlib.reload(sys.modules[module_name])
        except:
            pass
    
    # Перезагрузка команд
    try:
        await bot.tree.sync()
        await interaction.followup.send("✅ Команды успешно синхронизированы!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка синхронизации команд: {e}", ephemeral=True)

# Обработчики взаимодействий для настроек
@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get('custom_id', '')
            
            # Обработка кнопок склада
            if custom_id.startswith("wh_"):
                # ... существующий код обработки склада ...
                pass
            
            elif custom_id == "dismissal_main_button":
                data = HRSystem.get_personnel(interaction.user)
                if not data:
                    await interaction.response.send_message(
                        "❌ Вы не являетесь сотрудником ФСИН!", 
                        ephemeral=True
                    )
                    return

                await interaction.response.send_modal(DismissalForm())
                return
                
            elif custom_id == "recruitment_main_button":
                await interaction.response.send_modal(RecruitmentForm())
                return
                
            # Обработка основных кнопок
            elif custom_id == "recruitment_approve":
                await handle_recruitment_approve(interaction)
                return
            
            elif custom_id == "recruitment_reject":
                await handle_recruitment_reject(interaction)
                return
            
            elif custom_id == "dismissal_approve":
                await handle_dismissal_approve(interaction)
                return
            
            elif custom_id == "dismissal_reject":
                await handle_dismissal_reject(interaction)
                return
            
            elif custom_id == "dismissal_delete":
                await handle_dismissal_delete(interaction)
                return
            
            elif custom_id == "confirm_delete":
                try:
                    if not interaction.message.embeds:
                        return
                    
                    embed = interaction.message.embeds[0]
                    if not embed.description:
                        return
                    
                    description = embed.description
                    user_mention = re.search(r'<@(\d+)>', description)
                    
                    if user_mention:
                        user_id = int(user_mention.group(1))
                        await handle_confirm_delete(interaction, user_id)
                    
                except Exception as e:
                    print(f"Ошибка обработки confirm_delete: {e}")
                return
            
            elif custom_id == "cancel_delete":
                try:
                    await interaction.message.delete()
                except:
                    pass
                return
            
            elif custom_id == "moderator_register_button":
                # Проверяем, является ли пользователь сотрудником
                personnel_data = HRSystem.get_personnel(interaction.user)
                if not personnel_data:
                    await interaction.response.send_message(
                        "❌ Вы не являетесь сотрудником ФСИН!",
                        ephemeral=True
                    )
                    return
                
                await interaction.response.send_modal(ModeratorRegistrationForm())
            
            # Обработка кнопок настроек
            elif custom_id == "settings_channels":
                if not is_bot_admin(interaction.user):
                    return
                
                embed = discord.Embed(
                    title="📝 Настройка каналов",
                    description="Выберите канал для настройки:",
                    color=0x2E73F0
                )
                
                settings = load_settings()
                channels = settings["channels"]
                
                embed.add_field(
                    name="📋 Канал заявок",
                    value=f"<#{channels['recruitment_requests']}>" if channels['recruitment_requests'] else "Не настроен",
                    inline=True
                )
                embed.add_field(
                    name="🚪 Канал рапортов",
                    value=f"<#{channels['dismissal_requests']}>" if channels['dismissal_requests'] else "Не настроен",
                    inline=True
                )
                embed.add_field(
                    name="📊 Канал логов",
                    value=f"<#{channels['logs']}>" if channels['logs'] else "Не настроен",
                    inline=True
                )
                embed.add_field(
                    name="🔄 Канал статусов",
                    value=f"<#{channels['status']}>" if channels['status'] else "Не настроен",
                    inline=True
                )
                
                view = ChannelSettingsView()
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
            
            elif custom_id == "settings_google":
                if not is_bot_admin(interaction.user):
                    return
                
                settings = load_settings()
                google_settings = settings["google_sheets"]
                
                embed = discord.Embed(
                    title="📊 Настройка Google Sheets",
                    description="Управление интеграцией с Google Таблицами:",
                    color=0x2E73F0
                )
                
                status = "✅ Включено" if google_settings.get("enabled", False) else "❌ Выключено"
                spreadsheet_id = google_settings.get("spreadsheet_id", "Не настроено")
                worksheet_name = google_settings.get("worksheet_name", "Кадровый аудит")
                
                embed.add_field(name="Статус", value=status, inline=True)
                embed.add_field(name="ID таблицы", value=spreadsheet_id, inline=True)
                embed.add_field(name="Имя листа", value=worksheet_name, inline=True)
                
                view = GoogleSettingsView()
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
            
            # Обработка настройки Google Sheets
            elif custom_id.startswith("google_"):
                if not is_bot_admin(interaction.user):
                    return
                
                action = custom_id.split("_")[1]
                settings = load_settings()
                
                if action == "toggle":
                    settings["google_sheets"]["enabled"] = not settings["google_sheets"].get("enabled", False)
                    save_settings(settings)
                    
                    status = "включена" if settings["google_sheets"]["enabled"] else "выключена"
                    await interaction.response.send_message(
                        f"✅ Интеграция с Google Sheets {status}!",
                        ephemeral=True
                    )
                    
                elif action == "setup":
                    await interaction.response.send_message(
                        "📝 Введите ID Google Таблицы (из URL):",
                        ephemeral=True
                    )
                    
                    def check(m):
                        return m.author == interaction.user and m.channel == interaction.channel
                    
                    try:
                        msg = await bot.wait_for('message', check=check, timeout=60.0)
                        spreadsheet_id = msg.content.strip()
                        
                        settings["google_sheets"]["spreadsheet_id"] = spreadsheet_id
                        save_settings(settings)
                        
                        # Настраиваем таблицу
                        if google_sheets.initialize():
                            success = google_sheets.setup_spreadsheet(spreadsheet_id)
                            if success:
                                await interaction.followup.send(
                                    "✅ Google Таблица успешно настроена!",
                                    ephemeral=True
                                )
                            else:
                                await interaction.followup.send(
                                    "❌ Ошибка настройки таблицы! Проверьте ID и доступы.",
                                    ephemeral=True
                                )
                        else:
                            await interaction.followup.send(
                                "❌ Ошибка подключения к Google Sheets! Проверьте файл учетных данных.",
                                ephemeral=True
                            )
                            
                    except TimeoutError:
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                
                elif action == "test":
                    if google_sheets.initialize() and google_sheets.sheet:
                        test_data = {
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "Тестовая запись",
                            "target_name": "Test User",
                            "target_id": "123456789",
                            "executor_name": interaction.user.display_name,
                            "executor_id": interaction.user.id,
                            "division": "Тест",
                            "rank": "Тестовое звание",
                            "position": "Тестовая должность",
                            "static": "XXX-XXX",
                            "reason": "Тест интеграции"
                        }
                        
                        success = google_sheets.log_to_sheet(test_data)
                        if success:
                            await interaction.response.send_message(
                                "✅ Тестовая запись успешно добавлена в Google Sheets!",
                                ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                "❌ Ошибка записи в Google Sheets!",
                                ephemeral=True
                            )
                    else:
                        await interaction.response.send_message(
                            "❌ Google Sheets не настроена или не подключена!",
                            ephemeral=True
                        )
            
            # Обработка настройки каналов (добавлены отдельные каналы для заявок и рапортов)
            elif custom_id.startswith("channel_"):
                if not is_bot_admin(interaction.user):
                    return
                
                channel_type = custom_id.split("_")[1]
                channel_names = {
                    "recruitment": "канал заявок",
                    "dismissal": "канал рапортов",
                    "logs": "канал логов",
                    "status": "канал статусов"
                }
                
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"📝 Укажите ID канала для {channel_names[channel_type]} или упомяните канал:",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"📝 Укажите ID канала для {channel_names[channel_type]} или упомяните канал:",
                        ephemeral=True
                    )
                
                def check(m):
                    return m.author == interaction.user and m.channel == interaction.channel
                
                try:
                    msg = await bot.wait_for('message', check=check, timeout=60.0)
                    
                    channel_id = None
                    if msg.channel_mentions:
                        channel_id = msg.channel_mentions[0].id
                    else:
                        try:
                            channel_id = int(msg.content.strip().replace('<#', '').replace('>', ''))
                        except ValueError:
                            if interaction.response.is_done():
                                await interaction.followup.send("❌ Неверный формат ID канала!", ephemeral=True)
                            else:
                                await interaction.response.send_message("❌ Неверный формат ID канала!", ephemeral=True)
                            return
                    
                    settings = load_settings()
                    settings["channels"][channel_type + "_requests" if channel_type in ["recruitment", "dismissal"] else channel_type] = channel_id
                    save_settings(settings)
                    
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            f"✅ {channel_names[channel_type].capitalize()} успешно установлен на <#{channel_id}>!",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            f"✅ {channel_names[channel_type].capitalize()} успешно установлен на <#{channel_id}>!",
                            ephemeral=True
                        )
                    
                except TimeoutError:
                    if interaction.response.is_done():
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                    else:
                        await interaction.response.send_message("❌ Время ожидания истекло!", ephemeral=True)
                return
            
            # Обработка управления админами
            elif custom_id.startswith("admin_"):
                if not is_bot_admin(interaction.user):
                    await interaction.response.send_message("❌ У вас нет прав для этой настройки!", ephemeral=True)
                    return
                
                action = custom_id.split("_")[1]
                settings = load_settings()
                
                if action == "add":
                    await interaction.response.send_message(
                        "👤 Укажите ID пользователя для добавления в администраторы или упомяните пользователя:",
                        ephemeral=True
                    )
                    
                    def check(m):
                        return m.author == interaction.user and m.channel == interaction.channel
                    
                    try:
                        msg = await bot.wait_for('message', check=check, timeout=60.0)
                        
                        user_id = None
                        # Попытка извлечь ID из упоминания
                        if msg.mentions:
                            user_id = msg.mentions[0].id
                        else:
                            # Попытка извлечь числовой ID
                            try:
                                user_id = int(msg.content.strip().replace('<@', '').replace('>', ''))
                            except ValueError:
                                await interaction.followup.send("❌ Неверный формат ID пользователя!", ephemeral=True)
                                return
                        
                        if user_id in settings["admins"]:
                            await interaction.followup.send("❌ Этот пользователь уже является администратором!", ephemeral=True)
                            return
                        
                        settings["admins"].append(user_id)
                        save_settings(settings)
                        
                        await interaction.followup.send(
                            f"✅ Пользователь <@{user_id}> успешно добавлен в администраторы!",
                            ephemeral=True
                        )
                        
                    except TimeoutError:
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                
                elif action == "remove":
                    if not settings["admins"]:
                        await interaction.response.send_message("❌ Нет администраторов для удаления!", ephemeral=True)
                        return
                    
                    admin_list = "\n".join([f"{i+1}. <@{admin_id}>" for i, admin_id in enumerate(settings["admins"])])
                    
                    embed = discord.Embed(
                        title="🗑️ Удаление администратора",
                        description="Выберите номер администратора для удаления:",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Текущие администраторы:", value=admin_list, inline=False)
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    
                    def check(m):
                        return m.author == interaction.user and m.channel == interaction.channel
                    
                    try:
                        msg = await bot.wait_for('message', check=check, timeout=60.0)
                        
                        try:
                            index = int(msg.content.strip()) - 1
                            if index < 0 or index >= len(settings["admins"]):
                                await interaction.followup.send("❌ Неверный номер администратора!", ephemeral=True)
                                return
                            
                            removed_admin = settings["admins"].pop(index)
                            save_settings(settings)
                            
                            await interaction.followup.send(
                                f"✅ Администратор <@{removed_admin}> успешно удален!",
                                ephemeral=True
                            )
                            
                        except ValueError:
                            await interaction.followup.send("❌ Введите номер администратора!", ephemeral=True)
                            
                    except TimeoutError:
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                
                elif action == "list":
                    admins = settings["admins"]
                    admin_list = "\n".join([f"<@{admin_id}>" for admin_id in admins]) if admins else "Нет администраторов"
                    
                    embed = discord.Embed(
                        title="📋 Список администраторов",
                        description=admin_list,
                        color=discord.Color.blue()
                    )
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Обработка управления модераторами
            elif custom_id.startswith("mod_"):
                if not is_bot_admin(interaction.user):
                    await interaction.response.send_message("❌ У вас нет прав для этой настройки!", ephemeral=True)
                    return
                
                action = custom_id.split("_")[1]
                settings = load_settings()
                
                if action == "add":
                    await interaction.response.send_message(
                        "👤 Укажите ID пользователя для добавления в модераторы или упомяните пользователя:",
                        ephemeral=True
                    )
                    
                    def check(m):
                        return m.author == interaction.user and m.channel == interaction.channel
                    
                    try:
                        msg = await bot.wait_for('message', check=check, timeout=60.0)
                        
                        user_id = None
                        # Попытка извлечь ID из упоминания
                        if msg.mentions:
                            user_id = msg.mentions[0].id
                        else:
                            # Попытка извлечь числовой ID
                            try:
                                user_id = int(msg.content.strip().replace('<@', '').replace('>', ''))
                            except ValueError:
                                await interaction.followup.send("❌ Неверный формат ID пользователя!", ephemeral=True)
                                return
                        
                        if user_id in settings["moderators"]:
                            await interaction.followup.send("❌ Этот пользователь уже является модератором!", ephemeral=True)
                            return
                        
                        settings["moderators"].append(user_id)
                        save_settings(settings)
                        
                        await interaction.followup.send(
                            f"✅ Пользователь <@{user_id}> успешно добавлен в модераторы!",
                            ephemeral=True
                        )
                        
                    except TimeoutError:
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                
                elif action == "remove":
                    if not settings["moderators"]:
                        await interaction.response.send_message("❌ Нет модераторов для удаления!", ephemeral=True)
                        return
                    
                    mod_list = "\n".join([f"{i+1}. <@{mod_id}>" for i, mod_id in enumerate(settings["moderators"])])
                    
                    embed = discord.Embed(
                        title="🗑️ Удаление модератора",
                        description="Выберите номер модератора для удаления:",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Текущие модераторы:", value=mod_list, inline=False)
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    
                    def check(m):
                        return m.author == interaction.user and m.channel == interaction.channel
                    
                    try:
                        msg = await bot.wait_for('message', check=check, timeout=60.0)
                        
                        try:
                            index = int(msg.content.strip()) - 1
                            if index < 0 or index >= len(settings["moderators"]):
                                await interaction.followup.send("❌ Неверный номер модератора!", ephemeral=True)
                                return
                            
                            removed_mod = settings["moderators"].pop(index)
                            save_settings(settings)
                            
                            await interaction.followup.send(
                                f"✅ Модератор <@{removed_mod}> успешно удален!",
                                ephemeral=True
                            )
                            
                        except ValueError:
                            await interaction.followup.send("❌ Введите номер модератора!", ephemeral=True)
                            
                    except TimeoutError:
                        await interaction.followup.send("❌ Время ожидания истекло!", ephemeral=True)
                
                elif action == "list":
                    moderators = settings["moderators"]
                    mod_list = "\n".join([f"<@{mod_id}>" for mod_id in moderators]) if moderators else "Нет модераторов"
                    
                    embed = discord.Embed(
                        title="📋 Список модераторов",
                        description=mod_list,
                        color=discord.Color.blue()
                    )
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        print(f"Общая ошибка в on_interaction: {e}")
        print(traceback.format_exc())

        
async def grant_moderator_access(email: str, user_id: int):
    """Предоставить доступ модератору к Google таблице"""
    try:
        settings = load_settings()
        if not settings["google_sheets"].get("enabled", False):
            return False
        
        # Открываем таблицу
        spreadsheet = google_sheets.client.open_by_key(
            settings["google_sheets"]["spreadsheet_id"]
        )
        
        # Предоставляем доступ
        spreadsheet.share(email, perm_type='user', role='writer')
        
        # Обновляем статус в листе модераторов
        try:
            mod_sheet = spreadsheet.worksheet("Модераторы")
            cells = mod_sheet.findall(str(user_id))
            for cell in cells:
                mod_sheet.update_cell(cell.row, 6, "Доступ предоставлен")  # Статус
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"Ошибка предоставления доступа: {e}")
        return False

@bot.tree.command(name="управление_модераторами", description="Управление доступом модераторов")
@app_commands.describe(действие="Выберите действие", пользователь="Пользователь Discord")
@app_commands.choices(действие=[
    app_commands.Choice(name="Предоставить доступ", value="grant"),
    app_commands.Choice(name="Отозвать доступ", value="revoke"),
    app_commands.Choice(name="Список модераторов", value="list")
])
async def manage_moderators(interaction: discord.Interaction, действие: app_commands.Choice[str], пользователь: discord.User = None):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ У вас нет прав для этой команды!", ephemeral=True)
        return
    
    if действие.value == "grant" and пользователь:
        # Поиск заявки пользователя
        settings = load_settings()
        try:
            mod_sheet = google_sheets.client.open_by_key(
                settings["google_sheets"]["spreadsheet_id"]
            ).worksheet("Модераторы")
            
            cell = mod_sheet.find(str(пользователь.id))
            if cell:
                email = mod_sheet.cell(cell.row, 5).value  # Столбец с почтой
                if await grant_moderator_access(email, пользователь.id):
                    await interaction.response.send_message(
                        f"✅ Доступ предоставлен пользователю {пользователь.mention}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Ошибка предоставления доступа!",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Заявка пользователя не найдена!",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            ) 
       
def migrate_old_settings():
    """Миграция старых настроек в новый формат"""
    if not os.path.exists(SETTINGS_FILE):
        return
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        changed = False
        
        # Добавляем google_sheets если нет
        if "google_sheets" not in settings:
            settings["google_sheets"] = {
                "spreadsheet_id": None,
                "worksheet_name": "Кадровый аудит",
                "enabled": False
            }
            changed = True
        
        # Миграция каналов
        if "channels" in settings:
            if "requests" in settings["channels"]:
                old_channel = settings["channels"]["requests"]
                if "recruitment_requests" not in settings["channels"]:
                    settings["channels"]["recruitment_requests"] = old_channel
                if "dismissal_requests" not in settings["channels"]:
                    settings["channels"]["dismissal_requests"] = old_channel
                # Можно удалить старый ключ если нужно
                # del settings["channels"]["requests"]
                # changed = True
        
        if changed:
            save_settings(settings)
            print("✅ Настройки успешно мигрированы в новый формат")
            
    except Exception as e:
        print(f"❌ Ошибка миграции настроек: {e}")



# Инициализация persistent views
@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} готов к службе!')
    await bot.change_presence(activity=discord.Game(name="ФСИН"))
    

    # Запускаем HTTP сервер
    # Запускаем HTTP сервер
    bot.web_server = BotWebServer(bot, host='0.0.0.0', port=5000)
    bot.web_server.start_server()  # Убрано await, так как это синхронный метод
    # Загружаем настройки
    settings = load_settings()
    
    # Инициализация Google Sheets
    if google_sheets.initialize():
        if settings.get("google_sheets", {}).get("enabled", False):
            spreadsheet_id = settings["google_sheets"].get("spreadsheet_id")
            worksheet_name = settings["google_sheets"].get("worksheet_name", "Кадровый аудит")
            if spreadsheet_id:
                google_sheets.setup_spreadsheet(spreadsheet_id, worksheet_name)
    
    # Инициализация persistent views
    bot.add_view(RecruitmentRequestView())
    bot.add_view(DismissalRequestView(0))
    bot.add_view(ConfirmDeleteView(0))
    bot.add_view(SettingsView())
    bot.add_view(ChannelSettingsView())
    bot.add_view(RoleSettingsView())
    bot.add_view(AdminManagementView())
    bot.add_view(ModeratorManagementView())
    bot.add_view(GoogleSettingsView())
    bot.add_view(DismissalButtonView())
    bot.add_view(RecruitmentButtonView())
    
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

bot.run('MTQxOTY3NjAyOTI0MDM0ODgxNg.G9Zq7p.znRtvLrgpfwUJmCl06nI8zCAtO3EcTEEzWatIU')