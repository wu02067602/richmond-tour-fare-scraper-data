"""
API客戶端模組

此模組提供了一個專門用於與易遊網 requests API 進行互動的客戶端類別。
該類別負責處理所有的 API 請求、響應處理和錯誤處理邏輯。

主要功能：
- 初始化和管理 HTTP 會話
- 發送 requests 查詢請求
- 處理 API 響應和錯誤
- 提供日誌記錄功能

依賴項：
- requests: 用於發送 HTTP 請求
- typing: 用於類型提示
"""

import requests
import time
from typing import Dict, Any, Optional
from config.config_manager import ConfigManager
from utils.log_manager import LogManager

class ApiClient:
    """
    API客戶端類別
    
    負責與山富旅遊網的 requests API 進行互動，處理所有的 API 請求、
    響應和錯誤處理邏輯。
    
    屬性：
        session (requests.Session): HTTP 會話實例
        config_manager (ConfigManager): 配置管理器實例
        log_manager (LogManager): 日誌管理器實例
        headers (Dict[str, str]): API 請求標頭
    """
    
    def __init__(self, config_manager: ConfigManager, log_manager: LogManager):
        """
        初始化 API 客戶端
        
        參數：
            config_manager (ConfigManager): 配置管理器實例
            log_manager (LogManager): 日誌管理器實例
        """
        self.session = None
        self.config_manager = config_manager
        self.log_manager = log_manager
        self.headers = {}
        self.api_config = config_manager.get_api_config()
        self.retry_config = config_manager.get_retry_config()
        self.initialize_session()
    
    def initialize_session(self) -> None:
        """
        初始化 HTTP 會話
        
        設置請求標頭、超時和其他會話相關配置。
        包括設置必要的認證信息和 API 特定的標頭。
        """
        self.session = requests.Session()
        
        # 從配置中獲取標頭
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }
        
        # 如果配置中有定義標頭，使用配置中的標頭
        if 'headers' in self.api_config and isinstance(self.api_config['headers'], dict):
            self.headers.update(self.api_config['headers'])
        
        # 確保必要的標頭存在
        if 'User-Agent' not in self.headers and 'user_agent' in self.api_config:
            self.headers['User-Agent'] = self.api_config['user_agent']
            
        if 'Origin' not in self.headers and 'origin' in self.api_config:
            self.headers['Origin'] = self.api_config['origin']
            
        if 'Referer' not in self.headers and 'referer' in self.api_config:
            self.headers['Referer'] = self.api_config['referer']
        
        # 加入認證信息（如果有）
        auth_token = self.api_config.get('auth_token')
        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'
        
        # 設置請求超時
        self.timeout = self.api_config.get('timeout', 30)
    
    def send_rest_request(self, url: str, params: Optional[Dict[str, Any]] = None, method: str = 'GET') -> Optional[str]:
        """
        發送 HTTP 請求到指定的 URL。
        
        參數：
            url (str): 要發送請求的完整 URL。
            params (Optional[Dict[str, Any]]): GET 請求的查詢參數字典。
            method (str): HTTP 方法 (目前主要支援 'GET')。
            
        返回：
            Optional[str]: 成功時返回 HTML 內容，失敗時返回 None。
        """
        if not self.session:
            self.initialize_session()
        
        if not url:
            self.log_manager.log_error("請求 URL 未提供。")
            raise ValueError("請求 URL 未提供")

        max_retries = self.retry_config.get('max_attempts', 3)
        retry_delay = self.retry_config.get('interval', 1)
        backoff_factor = self.retry_config.get('backoff_factor', 2.0)
        
        for attempt in range(max_retries):
            try:
                # 對於 GET 請求，requests 會自動將 params 字典附加到 url
                response = self.session.get(
                    url=url,
                    headers=self.headers,
                    params=params,
                    timeout=self.timeout
                )
                
                # 處理響應
                return self.handle_response(response)
                
            except requests.RequestException as e:
                wait_time = retry_delay * (backoff_factor ** attempt)
                
                self.log_manager.log_error(
                    f"請求失敗（嘗試 {attempt+1}/{max_retries}）: {str(e)}，將在 {wait_time:.2f} 秒後重試", 
                    e
                )
                
                if attempt == max_retries - 1:
                    # 在最後一次失敗時記錄請求詳細信息
                    params_info = f"，URL參數: {params}" if params else ""
                    self.log_manager.log_error(f"達到最大重試次數，任務失敗。錯誤: {e}{params_info}")
                    return None
                
                time.sleep(wait_time)
        return None

    def handle_response(self, response: requests.Response) -> Optional[str]:
        """
        處理 HTTP 響應，主要用於爬蟲。
        
        參數：
            response (requests.Response): HTTP 響應對象
            
        返回：
            Optional[str]: 成功時返回響應的文本內容 (HTML)，失敗則返回 None。
        """
        if response.status_code == 200:
            return response.text
        else:
            error_msg = f"HTTP 請求收到非 200 狀態碼: {response.status_code}"
            self.log_manager.log_error(error_msg)
            raise requests.RequestException(f"Server error: {response.status_code}")
    
    def handle_errors(self, exception: Exception) -> None:
        """
        處理請求過程中的錯誤
        
        參數：
            exception (Exception): 捕獲的異常
            
        異常：
            requests.RequestException: 當需要重試請求時拋出
        """
        error_msg = f"API 請求處理過程中發生錯誤: {str(exception)}"
        self.log_manager.log_error(error_msg, exception)
        
        # 根據錯誤類型進行不同處理
        if isinstance(exception, requests.Timeout):
            self.log_manager.log_error("API 請求超時", exception)
        elif isinstance(exception, requests.ConnectionError):
            self.log_manager.log_error("API 連接錯誤", exception)
        elif isinstance(exception, requests.HTTPError):
            self.log_manager.log_error(f"HTTP 錯誤，狀態碼: {exception.response.status_code}", exception)
        else:
            self.log_manager.log_error(f"未分類錯誤: {str(exception)}", exception)
    
    def close_session(self) -> None:
        """
        關閉 HTTP 會話
        
        釋放所有資源並確保會話被正確關閉。
        """
        if self.session:
            self.session.close()
            self.session = None
            self.log_manager.log_info("API 客戶端會話已關閉") 
