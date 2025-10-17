from config.config_manager import ConfigManager
from services.date_calculation_service import DateCalculationService
from typing import Dict, List


class FlightTasksFixedMonthProcessors:
    """
    固定月份日期爬蟲任務處理器
    
    負責處理固定月份日期爬蟲任務，透過日期計算服務取得計算後的日期。
    
    屬性:
        config_manager (ConfigManager): 配置管理器實例
        date_calculation_service (DateCalculationService): 日期計算服務實例
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化固定月份日期爬蟲任務處理器
        
        Args:
            config_manager (ConfigManager): 配置管理器實例
            
        Examples:
            >>> processor = FlightTasksFixedMonthProcessors(config_manager)
            >>> isinstance(processor.date_calculation_service, DateCalculationService)
            True
            
        Raises:
            ValueError: 當配置尚未加載時
        """
        self.config_manager = config_manager
        
        # 從配置中獲取 API 設定並初始化日期計算服務
        api_config = self.config_manager.get_date_calculation_api_config()
        endpoint_url = api_config.get("endpoint_url")
        timeout = api_config.get("timeout", 10)
        
        self.date_calculation_service = DateCalculationService(endpoint_url, timeout)

    def process_flight_tasks(self) -> List[Dict]:
        """
        處理固定月份日期爬蟲任務列表
        
        透過呼叫日期計算 API 取得計算後的日期，並將其套用到任務參數中。

        Returns:
            List[Dict]: 處理後的爬蟲任務列表
            
        Examples:
            >>> processor = FlightTasksFixedMonthProcessors(config_manager)
            >>> tasks = processor.process_flight_tasks()
            >>> tasks[0]
            {
                'name': '範例：台北到新加坡 2025-05-19出發 2025-05-20回程',
                'url_params': {
                    'DepCity1': 'TPE',
                    'ArrCity1': 'SIN',
                    'DepCountry1': 'TW',
                    'ArrCountry1': 'SG',
                    'DepDate1': '2025-05-19',
                    'DepDate2': '2025-05-20',
                    'Rtow': 1
                }
            }
            
        Raises:
            ValueError: 當配置尚未加載或 API 回應錯誤時
            requests.Timeout: 當 API 請求超時時
            requests.ConnectionError: 當無法連接到 API 伺服器時
            requests.HTTPError: 當 API 回應 HTTP 錯誤狀態碼時
        """
        fixed_month_task_list = self._get_fixed_month_task_list()

        # 儲存處理後的爬蟲任務列表
        processed_flight_tasks = []

        # 將固定月份日期爬蟲任務列表中的任務進行處理
        for task in fixed_month_task_list:
            # 從任務中提取參數
            month_offset = task["url_params"]["Month"]
            dep_day = int(task["url_params"]["DepDate1"])
            return_day = int(task["url_params"]["DepDate2"])
            
            # 呼叫日期計算服務計算日期
            date_result = self.date_calculation_service.calculate_dates(month_offset, dep_day, return_day)
            
            # 複製任務並更新參數
            processed_task = task.copy()
            processed_task["url_params"] = task["url_params"].copy()
            
            # 更新任務參數
            processed_task["url_params"]["DepDate1"] = date_result["departure_date"]
            processed_task["url_params"]["DepDate2"] = date_result["return_date"]
            
            # 移除原始的 Month 參數，因為已經轉換為具體日期
            if "Month" in processed_task["url_params"]:
                del processed_task["url_params"]["Month"]
            
            # 更新任務名稱
            dep_city = task["url_params"].get("DepCity1", "")
            arr_city = task["url_params"].get("ArrCity1", "")
            target_year = date_result["target_year"]
            target_month = date_result["target_month"]
            
            processed_task["name"] = f"範例：{dep_city}到{arr_city} {date_result['departure_date']}出發 {date_result['return_date']}回程"
            
            processed_flight_tasks.append(processed_task)
            
        return processed_flight_tasks
    
    def _get_fixed_month_task_list(self) -> List[Dict]:
        """
        獲取固定月份日期爬蟲任務列表

        返回:
            List[Dict]: 固定月份日期爬蟲任務列表
        """
        return self.config_manager.get_flight_tasks_fixed_month()
