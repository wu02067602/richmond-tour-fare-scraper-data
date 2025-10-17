#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
節日日期計算服務模組

提供節日日期計算功能，透過呼叫外部 API 計算節日相關日期。
"""

from typing import Dict, List
import requests


class HolidayCalculationService:
    """
    節日日期計算服務
    
    負責透過呼叫外部 API 計算節日相關日期，根據月份偏移量獲取該月的節假日資料。
    
    屬性:
        endpoint_url (str): API 端點 URL
        timeout (int): 請求超時時間（秒）
    """
    
    def __init__(self, endpoint_url: str, timeout: int = 10):
        """
        初始化節日日期計算服務
        
        Args:
            endpoint_url (str): API 端點 URL
            timeout (int): 請求超時時間（秒），預設為 10 秒
            
        Examples:
            >>> service = HolidayCalculationService("http://localhost:8000/calculate_holiday_dates")
            >>> service.endpoint_url
            'http://localhost:8000/calculate_holiday_dates'
            
        Raises:
            ValueError: 當 endpoint_url 為空時
        """
        if not endpoint_url:
            raise ValueError("endpoint_url 不可為空")
        
        self.endpoint_url = endpoint_url
        self.timeout = timeout
    
    def calculate_holiday_dates(self, month_offset: int) -> Dict:
        """
        計算節日日期
        
        根據月份偏移量計算該月的節假日資料，包含節日名稱、日期和爬取日期範圍。
        
        Args:
            month_offset (int): 月份偏移量（幾個月後），必須為正整數
            
        Returns:
            Dict: 包含計算結果的字典，格式如下：
                {
                    "target_year": 2025,
                    "target_month": 12,
                    "holidays": [
                        {
                            "holiday_name": "行憲紀念日",
                            "holiday_date": "2025-12-25",
                            "departure_date": "2025-12-21",
                            "return_date": "2025-12-25",
                            "weekday": "四"
                        }
                    ]
                }
                
        Examples:
            >>> service = HolidayCalculationService("http://localhost:8000/calculate_holiday_dates")
            >>> result = service.calculate_holiday_dates(2)
            >>> result["target_month"]
            12
            >>> len(result["holidays"]) > 0
            True
            
        Raises:
            ValueError: 當 API 回應錯誤訊息時
            ValueError: 當參數驗證失敗時
            requests.Timeout: 當 API 請求超時時
            requests.ConnectionError: 當無法連接到 API 伺服器時
            requests.HTTPError: 當 API 回應 HTTP 錯誤狀態碼時
        """
        # 驗證參數
        self._validate_parameters(month_offset)
        
        # 準備請求資料
        request_data = {
            "month_offset": month_offset
        }
        
        try:
            # 發送 POST 請求到 API
            response = requests.post(
                self.endpoint_url,
                json=request_data,
                timeout=self.timeout
            )
            
            # 檢查 HTTP 狀態碼
            response.raise_for_status()
            
            # 解析回應
            response_data = response.json()
            
            # 檢查 API 是否回應成功
            if response_data.get("success"):
                return response_data["data"]
            else:
                error_message = response_data.get("error", "未知錯誤")
                raise ValueError(f"API 回應錯誤：{error_message}")
                
        except requests.Timeout as e:
            raise requests.Timeout(f"呼叫節日日期計算 API 超時：{self.endpoint_url}") from e
        except requests.ConnectionError as e:
            raise requests.ConnectionError(f"無法連接到節日日期計算 API：{self.endpoint_url}") from e
        except requests.HTTPError as e:
            raise requests.HTTPError(f"節日日期計算 API 回應錯誤：{e}") from e
    
    def _validate_parameters(self, month_offset: int) -> None:
        """
        驗證參數
        
        檢查參數是否符合要求。
        
        Args:
            month_offset (int): 月份偏移量
            
        Raises:
            ValueError: 當參數驗證失敗時
        """
        if month_offset <= 0:
            raise ValueError(f"month_offset 必須為正整數，目前值為 {month_offset}")
