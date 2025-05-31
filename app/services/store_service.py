import googlemaps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import pandas as pd
from typing import List, Dict, Tuple, Optional
import requests
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

class StoreService:
    def __init__(self):
        # 初始化 Google Maps API
        self.google_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.google_api_key:
            raise ValueError("未設定 GOOGLE_MAPS_API_KEY 環境變數")
        
        # 測試 API 金鑰是否有效
        test_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        test_params = {
            "location": "25.0330,121.5654",  # 台北 101
            "radius": 1000,
            "keyword": "飲料店",
            "key": self.google_api_key
        }
        response = requests.get(test_url, params=test_params)
        if response.json().get("status") == "REQUEST_DENIED":
            raise ValueError("Google Places API 金鑰無效或未啟用 Places API 服務")
        
        self.gmaps = googlemaps.Client(key=self.google_api_key)
        
        # 初始化 Google Sheets API
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE'), scope)
        self.gc = gspread.authorize(creds)
        
        # 載入飲料資料
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(current_dir, 'data', 'drink_data.csv')
        self.drinks_df = pd.read_csv(csv_path)
        
        # 品牌名稱對應關係
        self.brand_mapping = {
            '五十嵐': ['50嵐'],
            '清心福全': ['清心福全'],
            '麻古茶坊': ['麻古茶坊', '麻古', '麻古茶坊 MACU TEA']
        }
    
    def search_nearby_stores(self, brand: str, location: Tuple[float, float], radius: int = 2000) -> List[Dict]:
        """
        搜尋附近的店家
        :param brand: 店家品牌
        :param location: 位置座標 (緯度, 經度)
        :param radius: 搜尋半徑（公尺），預設為 2000 公尺（2公里）
        :return: 店家列表（依照距離排序，只回傳 1 公里內的店家）
        """
        try:
            # 品牌名稱對應關係
            brand_keywords = {
                '五十嵐': ['50嵐'],
                '清心福全': ['清心福全'],
                '麻古茶坊': ['麻古茶坊']
            }
            
            # 取得搜尋關鍵字列表
            search_keywords = brand_keywords.get(brand, [brand])
            print(f"搜尋品牌：{brand}")
            print(f"使用關鍵字：{search_keywords}")
            
            # 收集所有店家資訊
            all_stores = []
            
            # 使用每個關鍵字進行搜尋
            for keyword in search_keywords:
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    "location": f"{location[0]},{location[1]}",
                    "radius": radius,
                    "keyword": keyword,
                    "language": "zh-TW",  # 設定為繁體中文
                    "key": self.google_api_key
                }
                
                print(f"搜尋關鍵字：{keyword}")
                response = requests.get(url, params=params)
                data = response.json()
                
                print(f"API 回應狀態：{data.get('status')}")
                if data.get("status") == "OK":
                    print(f"找到 {len(data['results'])} 個結果")
                    for place in data["results"]:
                        # 檢查店名是否包含關鍵字
                        store_name = place["name"]
                        if not any(kw in store_name for kw in search_keywords):
                            print(f"跳過不符合的店家：{store_name}")
                            continue
                        
                        # 計算距離
                        distance = self._calculate_distance(
                            location[0], location[1],
                            place["geometry"]["location"]["lat"],
                            place["geometry"]["location"]["lng"]
                        )
                        
                        print(f"店家：{store_name}, 距離：{distance} 公尺")
                        
                        # 只加入 1 公里內的店家
                        if distance <= 1000:
                            store_info = {
                                "name": store_name,
                                "address": place.get("vicinity", "無地址資訊"),
                                "rating": place.get("rating", "無評分"),
                                "distance": int(distance)
                            }
                            
                            # 避免重複的店家
                            if not any(s["name"] == store_info["name"] for s in all_stores):
                                all_stores.append(store_info)
                                print(f"加入店家：{store_info['name']}")
                else:
                    print(f"搜尋失敗：{data.get('status')}")
            
            # 依照距離排序
            all_stores.sort(key=lambda x: x['distance'])
            print(f"最終找到 {len(all_stores)} 個符合條件的店家")
            
            # 只回傳前三筆結果
            return all_stores[:3]
        
        except Exception as e:
            print(f"搜尋店家時發生錯誤：{str(e)}")
            return []
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用 Google Maps Distance Matrix API 計算步行距離（公尺）
        """
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": f"{lat1},{lon1}",
                "destinations": f"{lat2},{lon2}",
                "mode": "walking",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data["status"] == "OK" and data["rows"]:
                # 取得步行距離（公尺）
                distance = data["rows"][0]["elements"][0]["distance"]["value"]
                return distance
            else:
                # 如果 API 呼叫失敗，回傳直線距離
                return self._calculate_straight_line_distance(lat1, lon1, lat2, lon2)
                
        except Exception as e:
            print(f"計算步行距離時發生錯誤：{str(e)}")
            # 發生錯誤時回傳直線距離
            return self._calculate_straight_line_distance(lat1, lon1, lat2, lon2)
    
    def get_drink_calories(self, brand: str, drink_name: str) -> Optional[int]:
        """
        取得飲料熱量
        :param brand: 店家品牌
        :param drink_name: 飲料名稱
        :return: 熱量（卡路里）
        """
        try:
            # 讀取飲料資料
            with open('data/drink_data.csv', 'r', encoding='utf-8') as f:
                import csv
                reader = csv.DictReader(f)
                for row in reader:
                    if row['brand'] == brand and row['drink_name'] == drink_name:
                        return int(row['calories'])
            return None
        except Exception as e:
            print(f"取得飲料熱量時發生錯誤：{str(e)}")
            return None
    
    def save_order(self, user_id: str, brand: str, location: str, drink_name: str) -> bool:
        """
        儲存訂單
        :param user_id: 使用者ID
        :param brand: 店家品牌
        :param location: 店家位置
        :param drink_name: 飲料名稱
        :return: 是否成功
        """
        try:
            print(f"開始儲存訂單：user_id={user_id}, brand={brand}, location={location}, drink_name={drink_name}")
            
            # 取得飲料熱量
            calories = self.get_drink_calories(brand, drink_name)
            if calories is None:
                print(f"找不到飲料熱量：brand={brand}, drink_name={drink_name}")
                return False
            
            print(f"找到飲料熱量：{calories}")
            
            # 檢查 Google Sheets ID
            sheets_id = os.getenv('GOOGLE_SHEETS_ID')
            if not sheets_id:
                print("未設定 GOOGLE_SHEETS_ID 環境變數")
                return False
            print(f"使用 Google Sheets ID：{sheets_id}")
            
            # 取得 Google Sheets 工作表
            try:
                sheet = self.gc.open_by_key(sheets_id).sheet1
                print("成功開啟 Google Sheets")
            except Exception as e:
                print(f"開啟 Google Sheets 失敗：{str(e)}")
                print("請確認：")
                print("1. GOOGLE_SHEETS_ID 是否正確")
                print("2. 服務帳號是否有權限存取該試算表")
                print("3. 試算表是否已建立")
                return False
            
            # 新增訂單
            try:
                order_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sheet.append_row([user_id, brand, location, drink_name, calories, order_time])
                print("成功新增訂單")
                return True
            except Exception as e:
                print(f"新增訂單失敗：{str(e)}")
                return False
        
        except Exception as e:
            print(f"儲存訂單時發生錯誤：{str(e)}")
            return False
    
    def get_order_history(self, user_id: str, start_date: str, end_date: str) -> List[Dict]:
        """
        取得訂單歷史紀錄
        :param user_id: 使用者ID
        :param start_date: 開始日期（YYYY-MM-DD）
        :param end_date: 結束日期（YYYY-MM-DD）
        :return: 訂單列表
        """
        try:
            # 取得 Google Sheets 工作表
            sheet = self.gc.open_by_key(os.getenv('GOOGLE_SHEETS_ID')).sheet1
            
            # 取得所有訂單
            orders = sheet.get_all_records()
            
            # 過濾訂單
            filtered_orders = []
            for order in orders:
                if order['user_id'] != user_id:
                    continue
                
                order_date = order['date_time'].split()[0]  # 取得日期部分
                if start_date <= order_date <= end_date:
                    filtered_orders.append({
                        "user_id": order['user_id'],
                        "brand": order['brand'],
                        "location": order['location'],
                        "drink_name": order['drink_name'],
                        "calories": int(order['calories']),
                        "created_at": order['date_time']  # 使用 date_time 欄位
                    })
            
            # 依照時間排序（新到舊）
            filtered_orders.sort(key=lambda x: x['created_at'], reverse=True)
            
            return filtered_orders
        
        except Exception as e:
            print(f"取得訂單歷史紀錄時發生錯誤：{str(e)}")
            return [] 