from config.config_manager import ConfigManager
from services.holiday_calculation_service import HolidayCalculationService
from typing import Dict, List


class FlightTasksHolidaysProcessors:
    """
    節日爬蟲任務處理器
    
    負責處理節日爬蟲任務，透過節日計算服務取得計算後的節假日資料。
    
    屬性:
        config_manager (ConfigManager): 配置管理器實例
        holiday_calculation_service (HolidayCalculationService): 節日計算服務實例
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化節日爬蟲任務處理器
        
        Args:
            config_manager (ConfigManager): 配置管理器實例
            
        Examples:
            >>> processor = FlightTasksHolidaysProcessors(config_manager)
            >>> isinstance(processor.holiday_calculation_service, HolidayCalculationService)
            True
            
        Raises:
            ValueError: 當配置尚未加載時
        """
        self.config_manager = config_manager
        
        # 從配置中獲取 API 設定並初始化節日計算服務
        api_config = self.config_manager.get_holiday_calculation_api_config()
        endpoint_url = api_config.get("endpoint_url")
        timeout = api_config.get("timeout", 10)
        
        self.holiday_calculation_service = HolidayCalculationService(endpoint_url, timeout)

    def process_flight_tasks(self) -> List[Dict]:
        """
        處理節日爬蟲任務列表
        
        透過呼叫節日計算服務取得計算後的節假日資料，並將其套用到任務參數中。

        Returns:
            List[Dict]: 處理後的爬蟲任務列表
            
        Examples:
            >>> processor = FlightTasksHolidaysProcessors(config_manager)
            >>> tasks = processor.process_flight_tasks()
            >>> tasks[0]
            {
                'name': '台北到新加坡 行憲紀念日 2025-12-21出發 2025-12-25回程',
                'url_params': {
                    'DepCity1': 'TPE',
                    'ArrCity1': 'SIN',
                    'DepCountry1': 'TW',
                    'ArrCountry1': 'SG',
                    'DepDate1': '2025-12-21',
                    'DepDate2': '2025-12-25',
                    'Rtow': 1
                }
            }
            
        Raises:
            ValueError: 當配置尚未加載或 API 回應錯誤時
            requests.Timeout: 當 API 請求超時時
            requests.ConnectionError: 當無法連接到 API 伺服器時
            requests.HTTPError: 當 API 回應 HTTP 錯誤狀態碼時
        """
        # 獲取基礎任務列表
        holidays_task_list = self._get_holidays_task_list()
        
        # 處理後的任務列表
        processed_flight_tasks = []
        
        # 遍歷每個基礎任務
        for base_task in holidays_task_list:
            # 從任務中提取月份偏移量
            month_offset = base_task["url_params"]["Month"]
            
            # 呼叫節日計算服務獲取節假日資料
            holiday_result = self.holiday_calculation_service.calculate_holiday_dates(month_offset)
            
            # 遍歷該月份的每個節假日
            for holiday in holiday_result.get("holidays", []):
                # 複製基礎任務並更新參數
                processed_task = base_task.copy()
                processed_task["url_params"] = base_task["url_params"].copy()
                
                # 更新任務參數
                processed_task["url_params"]["DepDate1"] = holiday["departure_date"]
                processed_task["url_params"]["DepDate2"] = holiday["return_date"]
                
                # 移除原始的 Month 參數，因為已經轉換為具體日期
                if "Month" in processed_task["url_params"]:
                    del processed_task["url_params"]["Month"]
                
                # 生成任務名稱
                dep_city = base_task["url_params"].get("DepCity1", "")
                arr_city = base_task["url_params"].get("ArrCity1", "")
                holiday_name = holiday["holiday_name"]
                
                processed_task["name"] = f"{dep_city}到{arr_city} {holiday_name} {holiday['departure_date']}出發 {holiday['return_date']}回程"
                
                processed_flight_tasks.append(processed_task)
                    
        return processed_flight_tasks
    
    def _get_holidays_task_list(self) -> List[Dict]:
        """
        獲取節日爬蟲任務列表
        
        從配置管理器中獲取節日爬蟲任務的基礎配置列表。

        Returns:
            List[Dict]: 節日爬蟲任務列表
            
        Examples:
            >>> processor = FlightTasksHolidaysProcessors(config_manager)
            >>> tasks = processor._get_holidays_task_list()
            >>> isinstance(tasks, list)
            True
            
        Raises:
            ValueError: 當配置尚未加載時
        """
        return self.config_manager.get_flight_tasks_holidays()
 