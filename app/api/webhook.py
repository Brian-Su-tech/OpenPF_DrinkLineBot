from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, PostbackAction
)
import os
import sys
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.drink_service import DrinkService
from app.services.gemini_service import GeminiService

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# LINE Bot 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 初始化服務
drink_service = DrinkService()
gemini_service = GeminiService()

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
    
    # 處理選單按鈕
    if text == "查詢飲料熱量":
        response = "🔎請輸入飲料資訊。\n格式：[店家]的[飲料名稱]\n例如：五十嵐的珍珠奶茶"
    elif text == "飲料熱量比較":
        response = "🔥請輸入兩店家的飲料資訊\n格式：比較店家A的飲料A和店家B的飲料B\n例如：比較五十嵐的珍珠奶茶和清心福全的紅茶拿鐵"
    elif text == "AI 飲料推薦":
        response = "💬請告訴我你想要什麼樣的飲料，例如：\n- 想要低熱量的飲料\n- 想要茶類的飲料\n- 想要有珍珠的飲料"
    elif text == "點餐資料儲存":
        response = "請輸入你要儲存的飲料資訊，格式：\n[店家]的[飲料名稱]"
    elif text == "歷史紀錄查詢":
        response = "請選擇要查詢的時間範圍：\n- 今天\n- 本週\n- 本月"
    elif text == "官網菜單連結":
        response = "以下是各店家的官方菜單連結：\n- 五十嵐：https://www.50lan.com.tw/menu\n- 清心福全：https://www.chingshin.tw/product.php\n- 可不可：https://www.kebuke.com/menu/"
    # 處理熱量比較功能
    elif "比較" in text:
        response = handle_drink_comparison(text)
    # 處理 AI 推薦功能
    elif text.startswith("想要") or text.startswith("我想"):
        response = gemini_service.get_drink_recommendations(text)
    # 處理熱量查詢功能
    else:
        response = handle_drink_search(text)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080) 