from controllers.crawler_controller import CrawlerController
from processors.flight_tasks_fixed_month_processors import FlightTasksFixedMonthProcessors
from processors.flight_tasks_holidays_processors import FlightTasksHolidaysProcessors
from config.config_manager import ConfigManager
import os
import json

def main():
    """
    山富旅遊網機票爬蟲系統主入口

    Args:
        url: 直接指定要爬取的URL (目前主要用於觸發單一預設任務)
        task_file: 包含爬蟲任務列表的JSON文件路徑
    """
    crawler_controller = CrawlerController()
    final_result = {"status": "error", "message": "未執行任何任務"} # 初始化預設結果
    
    # 載入配置文件
    config_manager = ConfigManager()
    config_manager.load_config(os.path.join(os.getcwd(), "travl4u_travel_crawler/config/config.yaml"))

    # 處理固定月份日期爬蟲任務
    flight_tasks_fixed_month_processors = FlightTasksFixedMonthProcessors(config_manager)
    # 處理節日爬蟲任務
    flight_tasks_holidays_processors = FlightTasksHolidaysProcessors(config_manager)
    
    try:
        # 1. 從 Processors 獲取巢狀的任務列表
        tasks_from_fixed_month = flight_tasks_fixed_month_processors.process_flight_tasks()
        tasks_from_holidays = flight_tasks_holidays_processors.process_flight_tasks()
        
        all_nested_tasks = tasks_from_fixed_month + tasks_from_holidays

        # 2. 【關鍵修正】將巢狀的 "信封" 拆開，只取出裡面的 "信件" (url_params)
        flattened_tasks = []
        for nested_task in all_nested_tasks:
            # 只提取 url_params 字典，這才是我們需要的核心參數
            if 'url_params' in nested_task:
                flattened_tasks.append(nested_task['url_params'])
        
        if flattened_tasks:
            print(f"從處理器共生成 {len(flattened_tasks)} 個標準化爬蟲任務")
            # 3. 調用 batch_crawling 執行標準化後的任務
            final_result = crawler_controller.batch_crawling(flattened_tasks)
            print(f"批量任務執行狀態: 總計 {final_result.get('total_tasks', 0)} 個任務，已完成 {final_result.get('completed_tasks', 0)} 個")
        else:
            print("錯誤: 未能根據設定檔生成任何爬蟲任務。")
            final_result = {"status": "error", "message": "未能生成任何爬蟲任務"}
    except Exception as e:
        print(f"執行預定義任務時出錯: {str(e)}")
        final_result = {"status": "error", "message": f"執行預定義任務出錯: {str(e)}"}
        import traceback
        traceback.print_exc()

    return final_result

if __name__ == "__main__":
    # 執行主邏輯
    result = main()

    # 將最終結果輸出為JSON格式
    print("\n--- 最終執行結果 ---")
    # 使用 default=str 處理 datetime 對象
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
