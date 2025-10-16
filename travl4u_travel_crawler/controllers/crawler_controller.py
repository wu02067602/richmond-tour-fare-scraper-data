from config.config_manager import ConfigManager
from utils.log_manager import LogManager
from processors.data_processor import DataProcessor
from storage.storage_manager import StorageManager
from controllers.task_manager import TaskManager
from controllers.api_client import ApiClient
from parsers.html_parser import HtmlParser, FlightInfo
import uuid
import datetime
import time
import threading
import os
from typing import List, Dict, Optional, Any, Tuple
import requests
import json


class CrawlerController:
    """
    山富旅遊機票資料爬蟲系統 - 爬蟲控制器
    
    作為系統的主要入口點，協調整個爬蟲流程，管理任務執行
    """
    
    def __init__(self):
        """
        初始化爬蟲控制器
        """
        self.config_manager = ConfigManager()
        config_path = os.path.join(os.getcwd(), "travl4u_travel_crawler/config/config.yaml")
        self.config_manager.load_config(config_path)
        self.log_manager = LogManager(self.config_manager)
        self.api_client = ApiClient(
            config_manager=self.config_manager, 
            log_manager=self.log_manager
        )
        self.html_parser = HtmlParser(
            log_manager=self.log_manager,
            config_manager=self.config_manager
        )
        self.task_manager = TaskManager(
            max_concurrent_tasks=self.config_manager.config["task"]["max_concurrent_tasks"]
        )
        # 設置任務管理器的回調函數
        self.task_manager.set_crawler_callback(self._execute_crawling_task)
        self.log_manager.log_info("山富旅遊爬蟲控制器初始化完成")
    
    def _execute_crawling_task(self, task_id):
        """
        執行單個爬蟲任務的內部方法，用作任務管理器的回調函數
        
        使用山富旅遊的 RESTful API 獲取機票資料，解析後存儲到指定位置
        
        Args:
            task_id: 任務ID
            
        Returns:
            任務執行結果
        """
        # 初始化API客戶端為 None，便於在 finally 區塊中檢查是否需要關閉
        api_client = None

        try:
            # 通過直接執行start_crawling的內部邏輯來避免重複釋放任務槽
            task = self.task_manager.get_task_status(task_id)
            if task is None:
                return {"status": "error", "message": f"找不到任務 {task_id}"}
            
            # 更新任務的開始時間
            task.start_time = datetime.datetime.now()
            created_time = task.parameters.get("created_time")
            created_time_str = created_time.strftime("%Y-%m-%d %H:%M:%S.%f") if created_time else "未知"
            
            # 記錄任務基本信息
            dep_city = task.parameters.get("DepCity1", "未知")
            arr_city = task.parameters.get("ArrCity1", "未知")
            
            self.log_manager.log_info(f"開始執行爬蟲任務 {task_id}，創建於 {created_time_str}，實際開始於 {task.start_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
            self.log_manager.log_info(f"任務 {task_id} 詳情: ({dep_city} → {arr_city})")

            # 檢查是否是重試任務，如果是則記錄日誌
            if hasattr(task, 'retry_info') and getattr(task, 'retry_count', 0) > 0:
                original_start = getattr(task, 'original_start_time', task.start_time)
                elapsed = (datetime.datetime.now() - original_start).total_seconds()
                self.log_manager.log_debug(
                    f"這是任務 {task_id} 的第 {getattr(task, 'retry_count', 0)} 次重試，距離原始開始時間已過 {elapsed:.2f} 秒"
                )

            # 如果是第一次執行任務，保存原始開始時間
            if not hasattr(task, 'original_start_time'):
                task.original_start_time = task.start_time
            
            # 更新任務狀態為運行中
            task.status = "running"
            self.log_manager.log_task_status(task_id, "running")
            
            flight_data = self._process_system_flights(task)
            
            self.log_manager.log_info(f"開始處理山富旅遊系統的航班資料: {task_id}")
            self.log_manager.log_info(f"共生成 {len(flight_data)} 個有效的去回程組合")
            

     
            # 處理數據
            storage_manager = StorageManager(
                config_manager=self.config_manager,
                log_manager=self.log_manager
            )
            data_processor = DataProcessor(
                log_manager=self.log_manager,
                storage_manager=storage_manager
            )
            data_processor.process_data(raw_data=flight_data)
            json_result = data_processor.convert_to_json()
            table_result = data_processor.convert_to_table()
            data_processor.save_to_storage(filename=f"richmond_travel_data_{task_id}")

            
            # 更新任務狀態為已完成，並使用 log_task_status 記錄
            task.status = "completed"
            task.end_time = datetime.datetime.now()
            self.log_manager.log_task_status(task_id, "completed")
            
            # 計算總執行時間，使用 original_start_time
            original_start = task.original_start_time
            if original_start is None:
                self.log_manager.log_info(f"任務 {task_id} 無原始開始時間記錄，使用當前開始時間")
                original_start = task.start_time
            
            total_execution_time = (task.end_time - original_start).total_seconds()
            
            task.result = {
                "flight_data": flight_data,
                "json": json_result,
                "table": table_result,
                "total_execution_time": f"{total_execution_time:.2f} 秒"
            }
            
            # 記錄總執行時間
            if hasattr(task, 'retry_info') and getattr(task, 'retry_count', 0) > 0:
                self.log_manager.log_debug(
                    f"爬蟲任務 {task_id} 完成，經過 {getattr(task, 'retry_count', 0)} 次重試，總耗時 {total_execution_time:.2f} 秒"
                )
            else:
                self.log_manager.log_debug(
                    f"爬蟲任務 {task_id} 完成，耗時 {total_execution_time:.2f} 秒，實際執行開始時間: {task.start_time.strftime('%Y-%m-%d %H:%M:%S.%f')}"
                )
                
            return {"status": "success", "task_id": task_id, "result": task.result}
            
        except Exception as e:
            error_message = f"爬蟲任務 {task_id} 執行出錯: {str(e)}"
            self.log_manager.log_error(error_message, e)
            
            # 更新任務狀態為失敗，並使用 log_task_status 記錄
            if task:
                task.status = "failed"
                task.end_time = datetime.datetime.now()
                task.error = str(e)
                self.log_manager.log_task_status(task_id, "failed")
                
                # 計算總執行時間
                if hasattr(task, 'original_start_time'):
                    total_execution_time = (task.end_time - task.original_start_time).total_seconds()
                    self.log_manager.log_info(
                        f"爬蟲任務 {task_id} 失敗，總耗時 {total_execution_time:.2f} 秒"
                    )
                
            return self.handle_error(e, task_id)
        finally:
            # 確保API客戶端資源被正確釋放
            if api_client is not None:
                try:
                    self.log_manager.log_debug(f"關閉任務 {task_id} 的API客戶端資源")
                    api_client.close_session()
                except Exception as close_error:
                    self.log_manager.log_error(f"關閉API客戶端時出錯: {str(close_error)}", close_error)
    
    def _process_system_flights(self, task):
        """
        處理單一系統的完整航班查詢流程（去程 + 回程組合）。
        此方法協調抓取去程和回程航班，並使用 HtmlParser 進行 HTML 解析。
        會針對設定檔中定義的多個艙等進行查詢。

        Args:
            task: 任務資料物件，預期包含 task.parameters (dict) 儲存任務參數。

        Returns:
            該系統的所有航班組合列表。
        """
        system_name = "travl4u"
        
        # 記錄任務詳細信息，便於從任務ID追蹤具體內容
        dep_city = task.parameters.get("DepCity1", "未知")
        arr_city = task.parameters.get("ArrCity1", "未知") 
        dep_date = task.parameters.get("DepDate1", "未知")
        return_date = task.parameters.get("DepDate2", "未知")
        
        self.log_manager.log_info(f"開始處理 {system_name} 系統的航班查詢 (HTML 解析)")
        self.log_manager.log_info(f"任務 {task.task_id} - 航線: {dep_city} → {arr_city}, 出發: {dep_date}, 回程: {return_date}")

        # --- 除錯檢查點 2：查看 Controller 實際收到的任務參數 ---
        try:
            self.log_manager.log_debug(f"--- DEBUG: 任務 {task.task_id} 進入 Controller 的參數 ---")
            # 使用 str() 來避免 JSON 序列化 datetime 物件時出錯，確保能看到內容
            self.log_manager.log_debug(str(task.parameters))
            self.log_manager.log_debug("--- DEBUG: 參數列表結束 ---")
        except Exception as dump_error:
            self.log_manager.log_error(f"--- DEBUG: 無法紀錄任務參數: {dump_error} ---")
        

        all_flight_combinations_for_task = []

        
        try:
            cabin_classes_to_search = self.config_manager.config['flight_tasks'][0]['url_params']['cabin_classes']
        except (KeyError, IndexError, TypeError) as e:
            self.log_manager.log_error(f"從設定檔讀取艙等列表失敗: {e}，使用預設值 ['2']", e)
            cabin_classes_to_search = ["2"]

        if not isinstance(cabin_classes_to_search, list):
            cabin_classes_to_search = [str(cabin_classes_to_search)]

        for i, current_cabin_class in enumerate(cabin_classes_to_search):
            if i > 0:
                # 在處理不同艙等之間添加延遲，避免過於頻繁地請求
                time.sleep(self.config_manager.config.get("crawler", {}).get("delay_between_requests", 2))
            
            self.log_manager.log_info(f"開始查詢艙等: {current_cabin_class}")

            current_task_params = task.parameters.copy()
            current_task_params["class_classes"] = current_cabin_class

            try:
                # 1. 抓取並解析所有去程航班
                parsed_outbound_flights = self._fetch_outbound_flights(current_task_params)
                
                if not parsed_outbound_flights:
                    self.log_manager.log_info(f"艙等 {current_cabin_class} 沒有找到去程航班，跳至下一個艙等。")
                    continue

                # 2. 為每個去程航班，抓取並組合回程航班
                current_cabin_combinations = self._process_inbound_for_outbound_flights(
                    parsed_outbound_flights, 
                    current_task_params
                )
                
                self.log_manager.log_info(f"{system_name} 系統艙等 {current_cabin_class} 共生成 {len(current_cabin_combinations)} 個有效去回程組合")
                all_flight_combinations_for_task.extend(current_cabin_combinations)

            except requests.exceptions.RequestException as req_err:
                self.log_manager.log_error(f"{system_name} 系統艙等 {current_cabin_class} 請求錯誤: {str(req_err)}", req_err)
            except Exception as e:
                self.log_manager.log_error(f"{system_name} 系統處理艙等 {current_cabin_class} 時發生未預期錯誤: {str(e)}", e)
                # 根據需要決定是否要因為單一艙等錯誤而中斷整個任務

        self.log_manager.log_info(f"{system_name} 系統所有艙等查詢完成，總共生成 {len(all_flight_combinations_for_task)} 個航班組合")
        return all_flight_combinations_for_task

    def _fetch_outbound_flights(self, task_params: Dict[str, Any]) -> List[FlightInfo]:
        """
        抓取並解析指定艙等的去程航班，支援分頁處理
        """
        system_name = "travl4u"
        current_cabin_class = task_params.get("class_classes", "N/A")
        self.log_manager.log_info(f"開始為艙等 {current_cabin_class} 抓取去程航班資料")

        all_outbound_flights = []  # 收集所有分頁的航班
        current_page = 1
        
        while True:
            self.log_manager.log_debug(f"處理去程航班第 {current_page} 頁")
            
            # 1. 構建去程查詢 URL 和參數
            outbound_url, outbound_api_params = self._build_url(
                task_params,
                target_page=str(current_page)
            )
            self.log_manager.log_debug(f"去程請求 URL: {outbound_url}, 參數: {outbound_api_params}")

            # 2. 發送去程請求
            outbound_response_html = self.api_client.send_rest_request(
                url=outbound_url, 
                params=outbound_api_params
            )
            if not outbound_response_html:
                self.log_manager.log_warning(f"{system_name} 系統艙等 {current_cabin_class} 去程查詢第 {current_page} 頁沒有收到回應 HTML")
                break

            # 3. 解析JSON回應並提取flights_html和分頁資訊
            try:
                json_data = json.loads(outbound_response_html)
                flights_html = json_data.get("flights_html", "")
                page_count = json_data.get("page_count", 1)
                search_key = json_data.get("searchkey", "")

                # 保存 search_key 到 task_params
                if search_key:
                    task_params["search_key"] = search_key
                    self.log_manager.log_debug(f"保存 search_key: {search_key}")
                
                if not flights_html:
                    self.log_manager.log_warning(f"{system_name} 系統艙等 {current_cabin_class} 去程查詢第 {current_page} 頁沒有找到flights_html欄位")
                    break
                    
                self.log_manager.log_debug(f"去程第 {current_page} 頁，總共 {page_count} 頁")
            except Exception as e:
                self.log_manager.log_error(f"{system_name} 系統艙等 {current_cabin_class} 去程查詢第 {current_page} 頁JSON解析失敗: {str(e)}", e)
                break

            # 4. 使用 HtmlParser 解析航班HTML
            if self.html_parser.parse_html_response(flights_html):
                # 使用去程專用方法提取航班
                outbound_flights = self.html_parser.extract_outbound_flights()
                
                # 設置艙等信息
                for flight in outbound_flights:
                    flight.cabin_class = current_cabin_class
                
                # 將本頁航班加入總列表
                all_outbound_flights.extend(outbound_flights)
                self.log_manager.log_debug(f"去程第 {current_page} 頁解析到 {len(outbound_flights)} 個航班")
                
                # 檢查是否還有更多頁面
                if current_page >= page_count:
                    self.log_manager.log_debug(f"已處理完所有去程頁面（共 {page_count} 頁）")
                    break
                    
                # 準備處理下一頁
                current_page += 1
                
                # 分頁間延遲，避免請求過於頻繁
                if current_page <= page_count:
                    time.sleep(self.config_manager.config.get("crawler", {}).get("delay_between_requests", 2))
                    
            else:
                self.log_manager.log_warning(f"{system_name} 系統艙等 {current_cabin_class} 去程查詢第 {current_page} 頁HTML解析失敗")
                break
            
        self.log_manager.log_info(f"{system_name} 系統艙等 {current_cabin_class} 所有去程頁面處理完成，共解析到 {len(all_outbound_flights)} 個去程航班")
        return all_outbound_flights

    def _process_inbound_for_outbound_flights(self, outbound_flights: List[FlightInfo], task_params: Dict[str, Any]) -> List[FlightInfo]:
        """
        為每個已解析的去程航班抓取並組合回程航班
        """
        system_name = "travl4u"
        search_key = task_params.get("search_key", "")
       
        all_combinations_for_cabin = []
        
        self.log_manager.log_info(f"開始處理 {len(outbound_flights)} 個去程航班")

        for idx, outbound_flight_data in enumerate(outbound_flights):
            time.sleep(self.config_manager.config.get("crawler", {}).get("delay_between_requests", 2))

            # 獲取這個去程航班的 session_id
            flight_session_id = outbound_flight_data.selection_id
            self.log_manager.log_debug(f"處理去程航班 {idx+1}/{len(outbound_flights)}, session_id: {flight_session_id}")
            
            if not flight_session_id:
                self.log_manager.log_warning(f"去程航班 {idx+1} 缺少 session_id，跳過此航班")
                continue

            # 為這個去程航班抓取所有回程頁面
            current_page = 1
            inbound_flights_for_this_outbound = []
            
            while True:
                self.log_manager.log_debug(f"處理去程航班 {idx+1} 的回程第 {current_page} 頁")
                
                # 構建回程查詢 URL（包含分頁參數）
                inbound_url, inbound_api_params = self._build_url(
                    task_params=task_params,
                    search_key=search_key,
                    target_page=str(current_page),
                    session_id=flight_session_id
                )
                self.log_manager.log_debug(f"回程請求 URL: {inbound_url}, 參數: {inbound_api_params}")

                # 發送回程請求
                inbound_response_html = self.api_client.send_rest_request(
                    inbound_url,
                    inbound_api_params
                )
                

                if not inbound_response_html:
                    self.log_manager.log_warning(f"{system_name} 去程航班 {idx+1} 第 {current_page} 頁回程查詢沒有收到回應 HTML")
                    break
                
                # 解析JSON回應並提取flights_html和page_count
                try:
                    json_data = json.loads(inbound_response_html)
                    flights_html = json_data.get("flights_html", "")
                    page_count = json_data.get("page_count", 1)
                    
                    if not flights_html:
                        self.log_manager.log_warning(f"{system_name} 回程第 {current_page} 頁查詢沒有找到flights_html欄位")
                        break
                except Exception as e:
                    self.log_manager.log_error(f"{system_name} 回程第 {current_page} 頁查詢JSON解析失敗: {str(e)}", e)
                    break
            
                # 使用 HtmlParser 解析回程 HTML
                if self.html_parser.parse_html_response(flights_html):
                    # 使用回程專用方法提取航班
                    page_inbound_flights = self.html_parser.extract_inbound_flights()
                    inbound_flights_for_this_outbound.extend(page_inbound_flights)
                    
                    self.log_manager.log_info(f"去程航班 {idx+1} 第 {current_page} 頁找到 {len(page_inbound_flights)} 個回程航班")
                else:
                    self.log_manager.log_warning(f"{system_name} 去程航班 {idx+1} 第 {current_page} 頁回程航班HTML解析失敗")
                
                # 檢查是否還有更多頁面
                if current_page >= page_count:
                    self.log_manager.log_debug(f"去程航班 {idx+1} 已處理完所有回程頁面（共 {page_count} 頁）")
                    break
                    
                # 準備處理下一頁
                current_page += 1
            
            # 組合這個去程航班的所有回程航班
            for inbound_flight in inbound_flights_for_this_outbound:
                if inbound_flight.inbound_segments:
                    # 創建完整航程的副本
                    from dataclasses import asdict
                    from models.flight_segment import FlightSegment
                    from datetime import datetime
                    complete_flight = FlightInfo(**asdict(outbound_flight_data))
                    
                    # 【修正】確保 outbound_segments 是 FlightSegment 物件列表
                    # 檀查第一個元素是否為字典，如果是，則整個列表都需要轉換
                    if complete_flight.outbound_segments and isinstance(complete_flight.outbound_segments[0], dict):
                        complete_flight.outbound_segments = [FlightSegment(**seg) for seg in complete_flight.outbound_segments]

                    # 分配回程航段
                    complete_flight.inbound_segments = inbound_flight.inbound_segments
                    
                    # **重要：使用回程的價格信息，因為去程響應中不含總價
                    complete_flight.price = inbound_flight.price
                    complete_flight.tax = inbound_flight.tax
                    # 記錄日誌，無論價格是否為零，以方便追蹤
                    self.log_manager.log_debug(f"組合航班並設定價格：總價={complete_flight.price}, 稅金={complete_flight.tax}")
                    
                    # 設置正確的回程日期
                    return_date_str = task_params.get('DepDate2') 
                    if return_date_str and isinstance(return_date_str, str):
                        # 【修正】確保 return_date 是 datetime.date 物件
                        try:
                            complete_flight.return_date = datetime.strptime(return_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            self.log_manager.log_error(f"無法解析回程日期字串: {return_date_str}")
                            complete_flight.return_date = None # 或其他預設值
                    elif return_date_str:
                         # 如果已經是 date 物件，直接賦值
                        complete_flight.return_date = return_date_str
                    
                    all_combinations_for_cabin.append(complete_flight)
                else:
                    self.log_manager.log_warning(f"回程航班缺少航段信息，已跳過")
            
            if inbound_flights_for_this_outbound:
                valid_combinations = len([f for f in inbound_flights_for_this_outbound if f.inbound_segments])
                self.log_manager.log_info(f"去程航班 {idx+1} 成功組合了 {valid_combinations} 個完整行程")
            else:
                self.log_manager.log_warning(f"去程航班 {idx+1} 沒有找到任何回程航班")
                
        self.log_manager.log_info(f"完成處理，總共生成 {len(all_combinations_for_cabin)} 個去回程組合")
        return all_combinations_for_cabin
    
    def _build_url(self, task_params: Dict[str, Any], search_key: str = "", target_page: str = "", session_id: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        根據任務數據構建山富旅遊 RESTful API 查詢參數
        """
        
        # 正確的取值方式
        dep_city = task_params.get("DepCity1")
        arr_city = task_params.get("ArrCity1") 
        dep_date = task_params.get("DepDate1")
        return_date = task_params.get("DepDate2")
        cabin_class = task_params.get("class_classes", "2")
        ret_dep_time_range = f"{return_date}T00:55:00.000Z,{return_date}T21:40:00.000Z" if return_date else ""

        if search_key:
            # 回程：第1頁使用原始端點，第2頁以後使用filtered端點
            if target_page == "1" or not target_page:
                # 第1頁使用原始端點
                url = "https://www.travel4u.com.tw/flight/ajax/search/flights/return/"
                params = {
                    "origin_location_code": dep_city,
                    "destination_location_code": arr_city,
                    "search_key": search_key,
                    "session_id": session_id,
                    "target_page": target_page
                }
            else:
                # 第2頁以後使用filtered端點，支援真正的分頁
                url = "https://www.travel4u.com.tw/flight/ajax/search/flights/return/filtered"
                params = {
                    "search_key": search_key,
                    "session_id": session_id,
                    "target_page": target_page,
                    "order_by": "0_1",
                    "ret_dep_time_range": ret_dep_time_range
                }
        else:
            # 去程：使用完整參數
            url = "https://www.travel4u.com.tw/flight/ajax/search/flights/"
            
            params = {
                "origin_location_code": dep_city,
                "destination_location_code": arr_city,
                "trip": "2",
                "dep_location_codes": dep_city,
                "arr_location_codes": arr_city,
                "dep_location_types": "1",  
                "arr_location_types": "1",  
                "dep_dates": dep_date,
                "return_date": return_date,
                "adult": "1",
                "child": "0",
                "cabin_class": cabin_class,
                "is_direct_flight_only": "False",
                "exclude_budget_airline": "False",
                "search_key": search_key,
                "target_page": target_page,
                "order_by": "0_1",
                "source": ""
            }
            
        return url, params
    
    def select_outbound_flight(self, search_key: str, flight_selection_id: str, task_params: Dict[str, Any]) -> Optional[str]:
        """
        選擇特定的去程航班，獲得該去程對應的回程查詢 search_key
        
        參數：
            search_key (str): 原始搜尋鍵值
            flight_selection_id (str): 要選擇的去程航班ID
            task_params (Dict[str, Any]): 任務參數
            
        返回：
            Optional[str]: 成功時返回新的 search_key，失敗時返回 None
        """
        if not search_key or not flight_selection_id:
            self.log_manager.log_error("選擇去程航班需要 search_key 和 flight_selection_id")
            return None
        
        # 構建選擇去程航班的 URL 和參數
        select_url = "https://www.travel4u.com.tw/flight/search/flights/select/"
        
        select_params = {
            "search_key": search_key,
            "flight_id": flight_selection_id,
            "origin_location_code": task_params.get("DepCity1"),
            "destination_location_code": task_params.get("ArrCity1"),
            "session_id": "18"
        }
        
        self.log_manager.log_debug(f"選擇去程航班: {flight_selection_id}, 原始 search_key: {search_key}")
        
        try:
            response_text = self.api_client.send_rest_request(
                url=select_url,
                params=select_params
            )
            
            if not response_text:
                self.log_manager.log_warning(f"選擇去程航班沒有收到回應")
                return None
            
            # 解析回應，提取新的 search_key
            try:
                json_data = json.loads(response_text)
                new_search_key = json_data.get("searchkey", "")
                
                if new_search_key:
                    self.log_manager.log_debug(f"成功選擇去程航班，獲得新的 search_key: {new_search_key}")
                    return new_search_key
                else:
                    self.log_manager.log_warning(f"選擇去程航班回應中沒有找到新的 search_key")
                    return None
                    
            except json.JSONDecodeError as e:
                self.log_manager.log_error(f"選擇去程航班回應JSON解析失敗: {str(e)}", e)
                return None
                
        except Exception as e:
            self.log_manager.log_error(f"選擇去程航班時發生錯誤: {str(e)}", e)
            return None 

    def start_crawling(self, task_id: str = None) -> Dict:
        """
        開始單個爬蟲任務
        
        Args:
            task_id: 任務ID
            
        Returns:
            任務執行結果
        """
        if task_id is None:
            # 如果沒有提供任務ID，獲取隊列中的第一個任務
            task = self.task_manager.get_next_task()
            if task is None:
                return {"status": "error", "message": "沒有可執行的任務"}
            task_id = task.task_id
        
        try:
            result = self._execute_crawling_task(task_id)
            return result
        finally:
            # 釋放任務槽位
            self.task_manager.release_task_slot()
    
    def batch_crawling(self, task_list: List[Dict]) -> Dict:
        """
        批次執行多個爬蟲任務
        
        Args:
            task_list: 任務參數列表
            
        Returns:
            批次任務執行結果
        """
        task_ids = []
        
        # 將所有任務添加到隊列
        batch_id = f"batch_{str(uuid.uuid4())[:8]}"
        self.log_manager.log_info(f"開始批次任務 {batch_id} 的任務初始化")
        
        for task_params in task_list:
            task_id = str(uuid.uuid4())
            created_time = datetime.datetime.now()
            
            task_params["task_id"] = task_id
            task_params["status"] = "initialized"
            task_params["created_time"] = created_time  # 記錄任務創建時間
            task_params["start_time"] = None  # 開始時間暫設為 None，等到任務執行時再更新
            
            self.task_manager.add_task(task_params)
            task_ids.append(task_id)
            
            # 每10個任務記錄一次進度，避免日誌過多
            if len(task_ids) % 10 == 0 or len(task_ids) == len(task_list):
                self.log_manager.log_debug(f"批次任務 {batch_id} 已初始化 {len(task_ids)}/{len(task_list)} 個任務")
        
        # 啟動批處理任務
        self.log_manager.log_info(f"批次任務 {batch_id} 初始化完成，共 {len(task_ids)} 個任務，開始處理")
        
        # 交給任務管理器處理批量任務
        self.task_manager.process_batch_tasks()
        
        # 等待任務完成或超時
        max_wait_time = self.config_manager.config["task"]["task_timeout"] * 60
        start_time = time.time()
        completed_tasks = []
        last_progress_report = start_time
        progress_interval = 5  # 每5秒報告一次進度
        
        while len(completed_tasks) < len(task_ids) and (time.time() - start_time) < max_wait_time:
            current_time = time.time()
            # 檢查新完成的任務
            for task_id in task_ids:
                if task_id not in completed_tasks:
                    task = self.task_manager.get_task_status(task_id)
                    if task and task.status in ["completed", "failed"]:
                        completed_tasks.append(task_id)
                        # 立即報告任務完成情況
                        self.log_manager.log_info(
                            f"任務 {task_id} 已{task.status}，進度: {len(completed_tasks)}/{len(task_ids)}"
                        )
            
            # 定期報告進度
            if current_time - last_progress_report >= progress_interval:
                last_progress_report = current_time
                self.log_manager.log_info(
                    f"批次任務 {batch_id} 進度: {len(completed_tasks)}/{len(task_ids)} 已完成"
                )
                
                # 檢查並報告運行中任務
                running_count = 0
                for task_id in task_ids:
                    if task_id not in completed_tasks:
                        task = self.task_manager.get_task_status(task_id)
                        if task and task.status == "running":
                            running_count += 1
                
                if running_count > 0:
                    self.log_manager.log_info(f"當前有 {running_count} 個任務正在運行")
            
            # 所有任務已完成，提前結束等待
            if len(completed_tasks) == len(task_ids):
                self.log_manager.log_info(f"批次任務 {batch_id} 所有任務已完成")
                break
                
            # 避免頻繁檢查，節省CPU資源
            time.sleep(0.5)
        
        elapsed_time = time.time() - start_time
        
        # 收集結果
        results = {
            "batch_id": batch_id,
            "total_tasks": len(task_ids),
            "completed_tasks": len(completed_tasks),
            "elapsed_time": f"{elapsed_time:.2f} 秒",
            "tasks": {}
        }
        
        for task_id in task_ids:
            task = self.task_manager.get_task_status(task_id)
            if task:
                results["tasks"][task_id] = {
                    "status": task.status,
                }
                
                # 添加創建時間
                if hasattr(task, "created_time") and task.created_time is not None:
                    results["tasks"][task_id]["created_time"] = task.created_time
                
                # 添加開始時間
                if hasattr(task, "start_time") and task.start_time is not None:
                    results["tasks"][task_id]["start_time"] = task.start_time
                
                # 安全地獲取 end_time (如果存在)
                if hasattr(task, "end_time") and task.end_time is not None:
                    results["tasks"][task_id]["end_time"] = task.end_time
                else:
                    # 如果任務已完成但沒有 end_time，添加當前時間作為 end_time
                    if task.status in ["completed", "failed"]:
                        results["tasks"][task_id]["end_time"] = datetime.datetime.now()
                
                if task.status == "completed" and hasattr(task, "result"):
                    results["tasks"][task_id]["result"] = "available"
                elif task.status == "failed" and hasattr(task, "error"):
                    results["tasks"][task_id]["error"] = task.error
        
        # 檢查是否有超時未完成的任務
        if len(completed_tasks) < len(task_ids):
            self.log_manager.log_error(
                f"批次任務 {batch_id} 已超時，有 {len(task_ids) - len(completed_tasks)} 個任務未完成"
            )
            results["timeout"] = True
        
        self.log_manager.log_info(f"批次任務 {batch_id} 執行完成，耗時 {elapsed_time:.2f} 秒")
        return results
    
    def handle_error(self, exception: Exception, task_id: Optional[str] = None) -> Dict:
        """
        處理錯誤情況，並執行重試邏輯
        
        Args:
            exception: 異常對象
            task_id: 任務ID（可選）
            
        Returns:
            錯誤處理結果
        """
        error_message = str(exception)
        error_type = type(exception).__name__
        
        self.log_manager.log_error(f"錯誤: {error_message}", exception)
        
        # 檢查是否需要重試
        retry_config = self.config_manager.config["retry"]
        should_retry = error_type in retry_config["retry_on_errors"]
        
        if task_id and should_retry:
            # 獲取任務
            task = self.task_manager.get_task_status(task_id)
            if task:
                retry_count = task.get("retry_count", 0)
                max_attempts = retry_config["max_attempts"]
                
                if retry_count <= max_attempts:
                    # 計算重試延遲時間
                    backoff_factor = retry_config["backoff_factor"]
                    retry_interval = retry_config["interval"] * (backoff_factor ** retry_count)
                    
                    # 更新重試計數
                    task.retry_count = retry_count + 1
                    # 更新任務狀態為重試中，並使用 log_task_status 記錄
                    task.status = "retrying"
                    self.log_manager.log_task_status(task_id, "retrying")
                    task.last_error = error_message
                    
                    self.log_manager.log_info(f"任務 {task_id} 將在 {retry_interval} 秒後重試 (嘗試 {retry_count + 1}/{max_attempts})")
                    
                    # 使用定時器在指定延遲後執行重試
                    timer = threading.Timer(
                        retry_interval, 
                        self._schedule_retry_task, 
                        args=[task_id]
                    )
                    timer.daemon = True  # 設置為守護線程，避免主程序退出時線程仍在運行
                    timer.start()
                    
                    # 直接返回重試信息
                    return {
                        "status": "retrying",
                        "task_id": task_id,
                        "retry_count": retry_count + 1,
                        "max_attempts": max_attempts,
                        "retry_interval": retry_interval,
                        "error": error_message
                    }
        
        # 無需重試或無法重試
        return {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "task_id": task_id
        }
    
    def _schedule_retry_task(self, task_id: str) -> None:
        """
        將重試任務加入任務管理器的隊列，並確保不超過最大並行限制
        
        Args:
            task_id: 需要重試的任務ID
        """
        # 獲取任務信息
        task = self.task_manager.get_task_status(task_id)
        if not task:
            self.log_manager.log_error(f"無法重試任務 {task_id}：找不到任務信息")
            return
            
        # 確保任務仍處於等待重試狀態
        if task.status != "retrying":
            self.log_manager.log_info(f"任務 {task_id} 狀態已變更為 {task.status}，取消重試")
            return
            
        self.log_manager.log_info(f"開始重試任務 {task_id} (第 {task.get('retry_count', 0)} 次嘗試)")
        
        # 保存原始開始時間（首次執行時間）
        original_start_time = task.get("original_start_time")
        
        # 如果沒有原始開始時間（極少數情況），使用任務最早的有效開始時間
        if original_start_time is None:
            original_start_time = task.get("start_time")
            if original_start_time is None:
                # 如果還是沒有有效的時間，使用創建時間
                original_start_time = task.get("created_time") or datetime.datetime.now()
            self.log_manager.log_info(f"任務 {task_id} 沒有原始開始時間記錄，使用最早的可用時間")
        
        # 將任務重置為初始狀態以便重新執行
        # 但保留重試計數、原始開始時間和其他重要信息
        retry_info = {
            "retry_count": task.get("retry_count", 0),
            "last_error": task.get("last_error"),
            "original_start_time": original_start_time,
            "retry_history": task.get("retry_info", {}).get("retry_history", []) + [
                {
                    "retry_number": task.get("retry_count", 0),
                    "error": task.get("last_error"),
                    "retry_time": datetime.datetime.now().isoformat()
                }
            ]
        }
        
        # 保存原始任務參數但更新狀態
        task.status = "initialized"
        self.log_manager.log_task_status(task_id, "initialized")
        task.retry_info = retry_info
        task.original_start_time = original_start_time
        task.start_time = None
        
        # 重新加入隊列
        self.task_manager.add_task(task)
        self.log_manager.log_info(f"任務 {task_id} 已重新加入隊列末尾，等待執行")
        
        # 如果批處理尚未啟動，則嘗試啟動
        if hasattr(self.task_manager, "process_batch_tasks"):
            # 檢查工作線程是否已經啟動
            worker_threads_running = hasattr(self.task_manager, "worker_threads") and len(self.task_manager.worker_threads) > 0
            if not worker_threads_running:
                self.log_manager.log_info("啟動批次任務處理")
                self.task_manager.process_batch_tasks()

