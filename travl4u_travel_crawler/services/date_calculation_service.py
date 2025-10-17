#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日期計算服務模組

提供日期計算功能，透過呼叫外部 API 計算日期。
"""

from typing import Dict
import requests


class DateCalculationService:
    """
    日期計算服務
    
    負責透過呼叫外部 API 計算日期，根據月份偏移量和出發/回程日期計算實際日期。
    
    屬性:
        endpoint_url (str): API 端點 URL
        timeout (int): 請求超時時間（秒）
    """
    
    def __init__(self, endpoint_url: str, timeout: int = 10):
        """
        初始化日期計算服務
        
        Args:
            endpoint_url (str): API 端點 URL
            timeout (int): 請求超時時間（秒），預設為 10 秒
            
        Examples:
            >>> service = DateCalculationService("http://localhost:8000/calculate_dates")
            >>> service.endpoint_url
            'http://localhost:8000/calculate_dates'
            
        Raises:
            ValueError: 當 endpoint_url 為空時
        """
        if not endpoint_url:
            raise ValueError("endpoint_url 不可為空")
        
        self.endpoint_url = endpoint_url
        self.timeout = timeout
    
    def calculate_dates(self, month_offset: int, dep_day: int, return_day: int) -> Dict:
        """
        計算日期
        
        根據月份偏移量和出發/回程日期計算實際日期。
        
        Args:
            month_offset (int): 月份偏移量（幾個月後），必須為正整數
            dep_day (int): 出發日期（該月的第幾天），必須為 1-31 之間的整數
            return_day (int): 回程日期（該月的第幾天），必須為 1-31 之間的整數
            
        Returns:
            Dict: 包含計算結果的字典，格式如下：
                {
                    "departure_date": "2025-12-05",
                    "return_date": "2025-12-10",
                    "target_year": 2025,
                    "target_month": 12
                }
                
        Examples:
            >>> service = DateCalculationService("http://localhost:8000/calculate_dates")
            >>> result = service.calculate_dates(2, 5, 10)
            >>> result
            {
                "departure_date": "2025-12-05",
                "return_date": "2025-12-10",
                "target_year": 2025,
                "target_month": 12
            }
            
        Raises:
            ValueError: 當 API 回應錯誤訊息時
            ValueError: 當參數驗證失敗時
            requests.Timeout: 當 API 請求超時時
            requests.ConnectionError: 當無法連接到 API 伺服器時
            requests.HTTPError: 當 API 回應 HTTP 錯誤狀態碼時
        """
        # 驗證參數
        self._validate_parameters(month_offset, dep_day, return_day)
        
        # 準備請求資料
        request_data = {
            "month_offset": month_offset,
            "dep_day": dep_day,
            "return_day": return_day
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
            raise requests.Timeout(f"呼叫日期計算 API 超時：{self.endpoint_url}") from e
        except requests.ConnectionError as e:
            raise requests.ConnectionError(f"無法連接到日期計算 API：{self.endpoint_url}") from e
        except requests.HTTPError as e:
            raise requests.HTTPError(f"日期計算 API 回應錯誤：{e}") from e
    
    def _validate_parameters(self, month_offset: int, dep_day: int, return_day: int) -> None:
        """
        驗證參數
        
        檢查參數是否符合要求。
        
        Args:
            month_offset (int): 月份偏移量
            dep_day (int): 出發日期
            return_day (int): 回程日期
            
        Raises:
            ValueError: 當參數驗證失敗時
        """
        if month_offset < 0:
            raise ValueError(f"month_offset 必須為正整數，目前值為 {month_offset}")
        
        if not 1 <= dep_day <= 31:
            raise ValueError(f"dep_day 必須為 1-31 之間的整數，目前值為 {dep_day}")
        
        if not 1 <= return_day <= 31:
            raise ValueError(f"return_day 必須為 1-31 之間的整數，目前值為 {return_day}")
