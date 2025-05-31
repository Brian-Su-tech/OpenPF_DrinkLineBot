import google.generativeai as genai
import pandas as pd
import os
from typing import List, Dict

class GeminiService:
    def __init__(self):
        # 設定 Gemini API
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 載入飲料資料
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(current_dir, 'data', 'drink_data.csv')
        self.drinks_df = pd.read_csv(csv_path)
    
    def _prepare_context(self) -> str:
        """
        準備 RAG 的上下文資料
        """
        # 將飲料資料轉換為易讀的格式
        drinks_info = []
        for _, row in self.drinks_df.iterrows():
            drinks_info.append(
                f"店家：{row['brand']}，飲料：{row['drink_name']}，"
                f"類型：{row['type']}，熱量：{row['calories']}大卡"
            )
        
        return "\n".join(drinks_info)
    
    def get_drink_recommendations(self, user_input: str) -> str:
        """
        根據使用者輸入推薦飲料
        """
        # 準備系統提示和上下文
        context = self._prepare_context()
        system_prompt = f"""你是一個飲料推薦專家。你只能根據以下資料庫中的飲料進行推薦。
請根據使用者的需求，從資料庫中找出最適合的飲料，並說明推薦原因。
如果使用者提到熱量，請特別注意飲料的熱量資訊。

飲料資料庫：
{context}

請用繁體中文回答，並遵循以下格式：
1. 推薦的飲料（最多3個），不用說明它的type是什麼，直接說飲料名稱
2. 每個飲料的特點和推薦原因
3. 如果使用者提到熱量，請特別說明熱量資訊

注意：
- 只能推薦資料庫中存在的飲料
- 如果找不到完全符合的飲料，請推薦最接近的選項
- 回答要簡潔明瞭，不要過於冗長
"""

        # 組合完整的提示
        prompt = f"{system_prompt}\n\n使用者需求：{user_input}"
        
        try:
            # 呼叫 Gemini API
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"抱歉，在處理您的請求時發生錯誤：{str(e)}" 