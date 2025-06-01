from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    LocationMessage, LocationSendMessage, PostbackEvent,
    ImagemapSendMessage, BaseSize, URIImagemapAction, ImagemapArea,
    ImageSendMessage
)
import os
import sys
from dotenv import load_dotenv
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')  # 設定使用非互動式後端
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
import seaborn as sns
import numpy as np

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.drink_service import DrinkService
from app.services.gemini_service import GeminiService
from app.services.store_service import StoreService

# 載入環境變數
load_dotenv()

app = Flask(__name__, static_folder='../../static')

# LINE Bot 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 初始化服務
drink_service = DrinkService()
gemini_service = GeminiService()
store_service = StoreService()

# 使用者狀態管理
user_states = defaultdict(dict)

def handle_drink_comparison(text):
    """
    處理飲料比較的邏輯
    """
    try:
        # 移除「比較」並分割成兩部分
        parts = text.replace("比較", "").split("和")
        if len(parts) != 2:
            raise ValueError("格式錯誤")
        
        # 解析第一部分（店家A的飲料A）
        part1 = parts[0].strip()
        if "的" not in part1:
            raise ValueError("格式錯誤")
        brand1, drink1 = part1.split("的")
        
        # 解析第二部分（店家B的飲料B）
        part2 = parts[1].strip()
        if "的" not in part2:
            raise ValueError("格式錯誤")
        brand2, drink2 = part2.split("的")
        
        # 使用 DrinkService 進行比較
        return drink_service.compare_drinks(
            brand1.strip(), drink1.strip(),
            brand2.strip(), drink2.strip()
        )
    except ValueError:
        return "請使用正確的格式：比較[店家A]的[飲料A]和[店家B]的[飲料B]\n例如：比較五十嵐的珍珠奶茶和清心的烏龍綠茶"

def handle_drink_search(text):
    """
    處理飲料查詢的邏輯
    """
    try:
        if "的" not in text:
            raise ValueError("格式錯誤")
        
        brand, drink_name = text.split("的")
        return drink_service.search_drink(brand.strip(), drink_name.strip())
    except ValueError:
        return "請使用正確的格式：[店家]的[飲料名稱]\n例如：五十嵐的珍珠奶茶"

def handle_store_selection(user_id: str, brand: str):
    """
    處理店家選擇的邏輯
    """
    # 更新使用者狀態
    user_states[user_id]['brand'] = brand
    user_states[user_id]['state'] = 'waiting_for_location'
    
    return "📍請傳送您的位置資訊～\n我會幫您搜尋附近的飲料店！"

def handle_location(user_id: str, latitude: float, longitude: float):
    """
    處理位置資訊的邏輯
    """
    try:
        # 取得使用者選擇的店家
        brand = user_states[user_id].get('brand')
        if not brand:
            return "請先幫我選擇飲料店～🧋（五十嵐、清心福全、麻古茶坊）"
        
        # 搜尋附近的店家
        stores = store_service.search_nearby_stores(brand, (latitude, longitude))
        if not stores:
            return "找不到附近的店家噢～請重新選擇位置。"
        
        # 更新使用者狀態
        user_states[user_id]['stores'] = stores
        user_states[user_id]['state'] = 'waiting_for_store_selection'
        
        # 生成店家列表訊息
        message = "以下是我找到的店家👉🏻\n請選擇一間😊\n\n"
        for i, store in enumerate(stores, 1):
            message += f"{i}. {store['name']}\n"
            message += f"   評分：{store['rating']}\n"
            message += f"   距離：{store['distance']} 公尺\n\n"
        message += "請輸入店家的編號（1-3）"
        
        return message
    except Exception as e:
        return f"處理位置資訊時發生錯誤：{str(e)}"

def handle_store_number(user_id: str, store_number: str):
    """
    處理使用者選擇的店家編號
    """
    try:
        # 取得店家列表
        stores = user_states[user_id].get('stores', [])
        if not stores:
            return "請先選擇位置"
        
        # 檢查編號是否有效
        try:
            index = int(store_number) - 1
            if not 0 <= index < len(stores):
                raise ValueError
        except ValueError:
            return "請輸入有效的店家編號（1-3）"
        
        # 更新使用者狀態
        selected_store = stores[index]
        user_states[user_id]['selected_store'] = selected_store
        user_states[user_id]['state'] = 'waiting_for_drink'
        
        return f"收到🫡\n您選擇了：{selected_store['name']}\n最後請輸入您要點的飲料名稱"
    except Exception as e:
        return f"處理店家選擇時發生錯誤：{str(e)}"

def handle_drink_selection(user_id: str, drink_name: str):
    """
    處理飲料選擇的邏輯
    """
    try:
        # 取得使用者選擇的店家
        brand = user_states[user_id].get('brand')
        selected_store = user_states[user_id].get('selected_store')
        if not brand or not selected_store:
            return "請重新開始點餐流程"
        
        # 先檢查飲料是否存在
        calories = store_service.get_drink_calories(brand, drink_name)
        if calories is None:
            # 取得該品牌的所有飲料
            with open('data/drink_data.csv', 'r', encoding='utf-8') as f:
                import csv
                reader = csv.DictReader(f)
                brand_drinks = [row['drink_name'] for row in reader if row['brand'] == brand]
            
            return f"找不到飲料：{drink_name}\n\n{brand}的飲料有：\n" + "\n".join(brand_drinks)
        
        # 儲存訂單
        success = store_service.save_order(
            user_id=user_id,
            brand=brand,
            location=selected_store['name'],
            drink_name=drink_name
        )
        
        if success:
            # 清除使用者狀態
            user_states[user_id].clear()
            return "訂單已成功儲存🎉"
        else:
            return "儲存訂單時發生錯誤，請稍後再試。"
    except Exception as e:
        return f"處理飲料選擇時發生錯誤：{str(e)}"

def generate_statistics_plots(user_id: str, start_date: str, end_date: str):
    """
    生成統計圖表
    """
    try:
        # 讀取訂單資料
        orders = store_service.get_order_history(user_id, start_date, end_date)
        if not orders:
            return None
        
        # 轉換為 DataFrame
        df = pd.DataFrame(orders)
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        # 品牌名稱對應
        brand_mapping = {
            '五十嵐': 'FIFTYLAN',
            '清心福全': 'QING XIN FU QUAN',
            '麻古茶坊': 'MACU TEA'
        }
        
        # 轉換品牌名稱為英文
        df['brand'] = df['brand'].map(brand_mapping)
        
        # 創建圖表
        plt.style.use('default')  # 使用預設樣式
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 1. 品牌圓餅圖
        brand_counts = df['brand'].value_counts()
        colors = ['#FF9999', '#66B2FF', '#99FF99']  # 設定顏色
        ax1.pie(brand_counts.values, labels=brand_counts.index, autopct='%1.1f%%', colors=colors)
        ax1.set_title('Drink Brand Distribution', pad=20, fontsize=12)
        
        # 2. 每日飲料數量長條圖
        # 將日期轉換為 YYYY/MM/DD 格式
        df['date'] = df['created_at'].dt.strftime('%Y/%m/%d')
        daily_counts = df.groupby('date').size()
        
        ax2.bar(daily_counts.index, daily_counts.values, color='#66B2FF')
        ax2.set_title('Daily Drink Count', pad=20, fontsize=12)
        ax2.set_xlabel('Date', fontsize=10)
        ax2.set_ylabel('Count', fontsize=10)
        plt.xticks(rotation=45)
        
        # 調整布局
        plt.tight_layout()
        
        # 儲存圖表
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')
        os.makedirs(static_dir, exist_ok=True)
        plot_path = os.path.join(static_dir, 'statistics.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return plot_path
    except Exception as e:
        print(f"生成統計圖表時發生錯誤：{str(e)}")
        return None

def handle_history_query(user_id: str, text: str):
    """
    處理歷史紀錄查詢的邏輯
    """
    try:
        state = user_states[user_id].get('history_state')
        
        if state == 'waiting_for_start_date':
            # 檢查日期格式是否正確
            try:
                start_date = datetime.strptime(text, '%Y/%m/%d').strftime('%Y-%m-%d')
                user_states[user_id]['start_date'] = start_date
                user_states[user_id]['history_state'] = 'waiting_for_end_date'
                return "請輸入結束日期（格式：YYYY/MM/DD）"
            except ValueError:
                return "日期格式錯誤，請使用 YYYY/MM/DD 格式（例如：2024/04/30）"
        
        elif state == 'waiting_for_end_date':
            try:
                end_date = datetime.strptime(text, '%Y/%m/%d').strftime('%Y-%m-%d')
                start_date = user_states[user_id].get('start_date')
                
                # 查詢歷史紀錄
                orders = store_service.get_order_history(user_id, start_date, end_date)
                
                if not orders:
                    user_states[user_id].clear()
                    return f"在 {start_date} 到 {end_date} 期間沒有找到您的訂單紀錄"
                
                # 生成訂單列表訊息
                message = f"📅 {start_date} 到 {end_date} 的訂單紀錄：\n\n"
                
                for i, order in enumerate(orders, 1):
                    message += f"{i}. {order['brand']} - {order['drink_name']}\n"
                    message += f"   地點：{order['location']}\n"
                    message += f"   熱量：{order['calories']} 卡路里\n"
                    message += f"   時間：{order['created_at']}\n\n"
                
                # 更新狀態為等待使用者決定是否查看統計資料
                user_states[user_id]['history_state'] = 'waiting_for_statistics_decision'
                user_states[user_id]['start_date'] = start_date
                user_states[user_id]['end_date'] = end_date
                
                return message + "\n想要查看統計資料嗎😁我能幫你畫出圖表喔～\n\n👉🏻請回答「要」或「不要」"
            except ValueError:
                return "日期格式錯誤，請使用 YYYY/MM/DD 格式（例如：2024/04/30）"
        
        elif state == 'waiting_for_statistics_decision':
            if text == "要":
                # 生成統計圖表
                plot_path = generate_statistics_plots(
                    user_id,
                    user_states[user_id]['start_date'],
                    user_states[user_id]['end_date']
                )
                
                if plot_path:
                    # 清除使用者狀態
                    user_states[user_id].clear()
                    
                    # 回傳圖表
                    return ImageSendMessage(
                        original_content_url=f"https://{request.host}/static/statistics.png",
                        preview_image_url=f"https://{request.host}/static/statistics.png"
                    )
                else:
                    user_states[user_id].clear()
                    return "生成統計圖表時發生錯誤，請稍後再試。"
            
            elif text == "不要":
                user_states[user_id].clear()
                return "謝謝您的使用！如果之後需要查看統計資料，隨時都可以查詢歷史紀錄。"
            
            else:
                return "請回答「要」或「不要」"
        
        else:
            # 初始化查詢狀態
            user_states[user_id]['history_state'] = 'waiting_for_start_date'
            return "請輸入開始日期（格式：YYYY/MM/DD）"
    
    except Exception as e:
        user_states[user_id].clear()
        return f"查詢歷史紀錄時發生錯誤：{str(e)}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id
    
    # 檢查使用者狀態
    state = user_states[user_id].get('state')
    history_state = user_states[user_id].get('history_state')
    
    if history_state:
        # 處理歷史紀錄查詢
        response = handle_history_query(user_id, text)
        if isinstance(response, ImageSendMessage):
            line_bot_api.reply_message(
                event.reply_token,
                response
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response)
            )
    elif state == 'waiting_for_store_selection':
        # 處理店家編號選擇
        response = handle_store_number(user_id, text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
    elif state == 'waiting_for_drink':
        # 處理飲料選擇
        response = handle_drink_selection(user_id, text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
    else:
        # 處理一般訊息
        if text == "查詢飲料熱量":
            response = "🔎請輸入飲料資訊。\n格式：[店家]的[飲料名稱]\n例如：五十嵐的珍珠奶茶"
        elif text == "飲料熱量比較":
            response = "🔥請輸入兩店家的飲料資訊\n格式：比較店家A的飲料A和店家B的飲料B\n例如：比較五十嵐的珍珠奶茶和清心福全的紅茶拿鐵"
        elif text == "AI 飲料推薦":
            response = "💬請告訴我你想要什麼樣的飲料，例如：\n- 想要低熱量的飲料\n- 想要茶類的飲料\n- 想要有珍珠的飲料"
        elif text == "點餐資料儲存":
            response = "請先幫我選擇飲料店～🧋\n（五十嵐、清心福全、麻古茶坊）"
        elif text == "歷史紀錄查詢":
            response = "請輸入開始日期（格式：YYYY/MM/DD）"
            user_states[user_id]['history_state'] = 'waiting_for_start_date'
        elif text == "官網菜單連結":
            response = ImagemapSendMessage(
                base_url='https://res.cloudinary.com/df8pqukj6/image/upload/v1748697999/link_zjrzoj.jpg#',  # 圖片網址
                alt_text='點選前往官網',
                base_size=BaseSize(height=520, width=1040),
                actions=[
                    URIImagemapAction(
                        link_uri='http://50lan.com/web/products.asp',  # 五十嵐官網
                        area=ImagemapArea(x=0, y=0, width=346, height=520)
                    ),
                    URIImagemapAction(
                        link_uri='https://www.chingshin.tw/product.php',  # 清心福全官網
                        area=ImagemapArea(x=346, y=0, width=346, height=520)
                    ),
                    URIImagemapAction(
                        link_uri='https://www.macutea.com.tw',  # 麻古茶坊官網
                        area=ImagemapArea(x=692, y=0, width=348, height=520)
                    )
                ]
            )
        elif "比較" in text:
            response = handle_drink_comparison(text)
        elif text.startswith("想要") or text.startswith("我想"):
            response = gemini_service.get_drink_recommendations(text)
        elif "的" in text and not text.startswith("比較"):  # 檢查是否為飲料查詢格式
            response = handle_drink_search(text)
        else:
            # 假設是店家選擇
            response = handle_store_selection(user_id, text)
        
        # 回傳訊息
        if isinstance(response, (ImagemapSendMessage, ImageSendMessage)):
            line_bot_api.reply_message(
                event.reply_token,
                response
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response)
            )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    user_id = event.source.user_id
    latitude = event.message.latitude
    longitude = event.message.longitude
    
    try:
        # 取得使用者選擇的店家
        brand = user_states[user_id].get('brand')
        if not brand:
            response = "請先幫我選擇飲料店～🧋\n（五十嵐、清心福全、麻古茶坊）"
        else:
            # 搜尋附近的店家
            stores = store_service.search_nearby_stores(brand, (latitude, longitude))
            if not stores:
                response = "找不到附近的店家，請重新選擇位置"
            else:
                # 更新使用者狀態
                user_states[user_id]['stores'] = stores
                user_states[user_id]['state'] = 'waiting_for_store_selection'
                
                # 生成店家列表訊息
                response = "以下是我找到的店家👉🏻\n請選擇一間😊\n\n"
                for i, store in enumerate(stores, 1):
                    response += f"{i}. {store['name']}\n"
                    response += f"   評分：{store['rating']}\n"
                    response += f"   距離：{store['distance']} 公尺\n\n"
                response += "請輸入有效的店家編號（1-3）"
    except Exception as e:
        response = f"處理位置資訊時發生錯誤：{str(e)}"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    if data == 'action=location':
        # 回傳位置按鈕
        line_bot_api.reply_message(
            event.reply_token,
            LocationSendMessage(
                title='選擇位置',
                address='請選擇您的位置'
            )
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080) 