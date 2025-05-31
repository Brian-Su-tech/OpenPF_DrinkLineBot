import pandas as pd
import os

class DrinkService:
    def __init__(self):
        # 使用相對於專案根目錄的路徑
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(current_dir, 'data', 'drink_data.csv')
        self.drinks_df = pd.read_csv(csv_path)
    
    def search_drink(self, brand, drink_name):
        """
        查詢飲料熱量
        """
        # 搜尋飲料（使用完全匹配）
        drinks = self.drinks_df[
            (self.drinks_df['brand'] == brand) &
            (self.drinks_df['drink_name'] == drink_name)
        ]
        
        if drinks.empty:
            # 如果找不到完全匹配，提供可能的選項
            similar_drinks = self.drinks_df[
                (self.drinks_df['brand'] == brand) |
                (self.drinks_df['drink_name'] == drink_name)
            ]
            
            if similar_drinks.empty:
                return "找不到這個飲料，請確認店家名稱和飲料名稱是否正確"
            
            # 生成相似飲料列表
            result = f"找不到完全符合的飲料，以下是相似的飲料：\n\n"
            for _, drink in similar_drinks.iterrows():
                result += f"{drink['brand']} {drink['drink_name']}：{drink['calories']} 大卡\n"
            return result
        
        # 如果找到飲料
        drink_info = drinks.iloc[0]
        return f"""{drink_info['brand']} {drink_info['drink_name']}：
- 熱量：{drink_info['calories']} 大卡"""
    
    def compare_drinks(self, drink1_brand, drink1_name, drink2_brand, drink2_name):
        """
        比較兩款飲料的熱量
        """
        # 搜尋飲料（使用完全匹配）
        drink1 = self.drinks_df[
            (self.drinks_df['brand'] == drink1_brand) &
            (self.drinks_df['drink_name'] == drink1_name)
        ]
        drink2 = self.drinks_df[
            (self.drinks_df['brand'] == drink2_brand) &
            (self.drinks_df['drink_name'] == drink2_name)
        ]
        
        if drink1.empty or drink2.empty:
            # 如果找不到完全匹配，提供可能的選項
            similar_drinks1 = self.drinks_df[
                (self.drinks_df['brand'] == drink1_brand) |
                (self.drinks_df['drink_name'] == drink1_name)
            ]
            similar_drinks2 = self.drinks_df[
                (self.drinks_df['brand'] == drink2_brand) |
                (self.drinks_df['drink_name'] == drink2_name)
            ]
            
            error_msg = "找不到指定的飲料，請確認店家名稱和飲料名稱是否正確\n\n"
            
            if not similar_drinks1.empty:
                error_msg += f"在 {drink1_brand} 找到的相似飲料：\n"
                for _, drink in similar_drinks1.iterrows():
                    error_msg += f"- {drink['drink_name']}\n"
            
            if not similar_drinks2.empty:
                error_msg += f"\n在 {drink2_brand} 找到的相似飲料：\n"
                for _, drink in similar_drinks2.iterrows():
                    error_msg += f"- {drink['drink_name']}\n"
            
            return error_msg
        
        # 取得飲料資訊
        drink1_info = drink1.iloc[0]
        drink2_info = drink2.iloc[0]
        
        # 計算熱量差異
        calorie_diff = abs(drink1_info['calories'] - drink2_info['calories'])
        
        # 生成比較結果
        result = f"""{drink1_info['brand']} {drink1_info['drink_name']}：
- 熱量：{drink1_info['calories']} 大卡

{drink2_info['brand']} {drink2_info['drink_name']}：
- 熱量：{drink2_info['calories']} 大卡

熱量差異：{calorie_diff} 大卡"""
        return result 