from bs4 import BeautifulSoup
import traceback
import re
from typing import Dict, List, Optional
from models.flight_info import FlightInfo
from models.flight_segment import FlightSegment
from utils.log_manager import LogManager
from config.config_manager import ConfigManager
from datetime import datetime


class HtmlParser:
    """
    山富旅遊HTML解析器類別 (使用 BeautifulSoup)
    
    負責解析從山富旅遊網站獲取的 HTML 數據，提取航班資訊。
    根據類別圖設計，提供結構化的航班數據解析功能。
    """

    def __init__(self, log_manager: LogManager, config_manager: ConfigManager):
        """
        初始化 HTML 解析器
        
        參數：
            log_manager: 日誌管理器實例
            config_manager: 配置管理器實例
        """
        self.log_manager = log_manager
        self.config_manager = config_manager
        self.html_content = ""
        self.soup = None
        
        self.log_manager.log_info("山富旅遊HTML解析器初始化完成")

    def parse_html_response(self, html_content: str) -> bool:
        """
        解析HTML頁面內容，初始化BeautifulSoup解析器
        
        參數：
            html_content (str): 從山富旅遊網站獲取的HTML內容
            
        返回：
            bool: 解析是否成功
        """
        if not html_content:
            self.log_manager.log_warning("提供的HTML內容為空，無法解析")
            return False
        
        # 完全清理所有舊狀態，防止數據污染
        self.html_content = ""
        self.soup = None
        
        # 設置新的HTML內容和解析器
        self.html_content = html_content
        self.soup = self._init_beautifulsoup(html_content)
        
        self.log_manager.log_debug("HTML內容解析成功，BeautifulSoup初始化完成，舊狀態已清理")
        return True


    def extract_outbound_flights(self) -> List[FlightInfo]:
        """
        從HTML中提取去程航班選項
        """
        flights: List[FlightInfo] = []
        
        if not self.soup:
            self.log_manager.log_warning("BeautifulSoup未初始化，無法提取航班")
            return flights

        # 根據HTML結構，每個航班的主要容器是 <div class="shadow">
        flight_item_elements = self.soup.find_all('div', class_=lambda value: value and 'shadow' in str(value))
        
        self.log_manager.log_info(f"找到 {len(flight_item_elements)} 個去程航班容器")

        for idx, item_element in enumerate(flight_item_elements):
            try:
                flight_info = FlightInfo()

                # 提取session_id
                session_id = self._extract_session_id_from_html(item_element)
                if session_id:
                    flight_info.selection_id = session_id  # 使用selection_id字段存儲session_id
                else:
                    self.log_manager.log_warning(f"航班 #{idx} 未找到 session_id")

                # 提取去程日期信息
                date_data = self._extract_flight_dates(item_element)
                flight_info.departure_date = date_data.get('departure_date')

                # 提取航段信息
                segments = self._extract_segments_from_html(item_element)
                if not segments:
                    self.log_manager.log_warning(f"航班 #{idx} 未找到航段信息，跳過")
                    continue
                
                # 設置去程航段
                flight_info.outbound_segments = segments
                flights.append(flight_info)
                
            except Exception as e:
                self.log_manager.log_error(f"解析去程航班項目 {idx} 時出錯: {str(e)}", e)
                self.log_manager.log_error(f"錯誤詳情：\n{traceback.format_exc()}")

        self.log_manager.log_info(f"成功提取 {len(flights)} 個去程航班")
        return flights

    def extract_inbound_flights(self) -> List[FlightInfo]:
        """
        從HTML中提取回程航班選項
        """
        flights: List[FlightInfo] = []
        
        if not self.soup:
            self.log_manager.log_warning("BeautifulSoup未初始化，無法提取航班")
            return flights
        # 根據HTML結構，每個航班的主要容器是 <div class="shadow">
        flight_item_elements = self.soup.find_all('div', class_=lambda value: value and 'shadow' in str(value))
        
        self.log_manager.log_info(f"找到 {len(flight_item_elements)} 個航班容器 (第一個為去程參考，其餘為回程選項)")

        # 跳過第一個元素，因為它是去程航班的參考信息
        for idx, item_element in enumerate(flight_item_elements[1:]):
            try:
                flight_info = FlightInfo()

                # 提取價格信息
                price_data = self._extract_fare_info_from_html(item_element)
                flight_info.price = price_data.get('total_price', 0.0)
                flight_info.tax = price_data.get('total_tax', 0.0)

                # 提取日期信息
                date_data = self._extract_flight_dates(item_element)
                flight_info.return_date = date_data.get('departure_date')
                
                # 提取航段信息
                segments = self._extract_segments_from_html(item_element)

                # 基本有效性檢查
                if not segments:
                    self.log_manager.log_warning(f"回程航班 #{idx+1} 缺少航段信息，已跳過")
                    continue
                
                # 設置回程航段
                flight_info.inbound_segments = segments
                flights.append(flight_info)
                
            except Exception as e:
                self.log_manager.log_error(f"解析回程航班項目 {idx+1} 時出錯: {str(e)}", e)
                self.log_manager.log_error(f"錯誤詳情：\n{traceback.format_exc()}")

        self.log_manager.log_info(f"成功提取 {len(flights)} 個回程航班")
        return flights

    def _init_beautifulsoup(self, html_content: str) -> BeautifulSoup:
        """
        初始化BeautifulSoup解析器
        
        參數：
            html_content (str): HTML內容
            
        返回：
            BeautifulSoup: 解析器實例
        """
        return BeautifulSoup(html_content, "html.parser")

    def _format_flight_number(self, flight_number_raw: str) -> str:
        """
        格式化航班號，統一格式
        
        參數：
            flight_number_raw (str): 原始航班號
            
        返回：
            str: 格式化後的航班號
        """
        # 去除連字符
        flight_number = flight_number_raw.replace('-', '')
        
        # 確保正確分離航空公司代碼和數字
        # 航空公司代碼：1-3個字符（字母或數字），後面跟著數字部分
        match = re.match(r'^([A-Z0-9]{1,2}?)(\d{1,4})$', flight_number.upper())
        if match:
            airline_code = match.group(1)
            number_part = match.group(2)
            
            # 統一補0規定：確保數字部分至少3位數
            if len(number_part) == 1:
                number_part = '00' + number_part  # 1位數前面補2個0: 7 → 007
            elif len(number_part) == 2:
                number_part = '0' + number_part   # 2位數前面補1個0: 47 → 047
            # 3位數以上保持原樣: 123 → 123, 8888 → 8888
                
            return airline_code + number_part
        else:
            self.log_manager.log_warning(f"航班號碼 '{flight_number}' 格式不符合預期")
            raise ValueError(f"航班號碼 '{flight_number}' 格式不符合預期")

    def _extract_fare_info_from_html(self, item_element) -> Dict[str, float]:
        """
        從HTML中提取票價和稅金
        """
        try:
            price_table = item_element.find_all('table', class_='tkt-price-table')
            if price_table is None:
                self.log_manager.log_warning("在航班項目中找不到價格表 (tkt-price-table)。")
            else:
                rows = price_table[0].find_all('tr')

                if len(rows) < 3:
                    self.log_manager.log_warning(f"價格表中的行數不足 ({len(rows)})")
                    return {'total_price': 0.0, 'total_tax': 0.0}
                else:
                    # 從成人行（第二行）獲取稅金
                    total_tax = float(rows[1].find_all('td')[2].get_text(strip=True).replace(',', ''))
                    
                    # 從最後一行獲取合計金額
                    total_price = float(rows[1].find_all('td')[1].get_text(strip=True).replace(',', ''))
                
                return {'total_price': total_price, 'total_tax': total_tax}

        except AttributeError as e:
            self.log_manager.log_error(f"解析票價信息時發生未預期錯誤: {str(e)}", e)
            self.log_manager.log_debug(f"出錯的HTML片段: {item_element.prettify()}")
            return {'total_price': 0.0, 'total_tax': 0.0}
                

    def _extract_flight_dates(self, item_element) -> Dict[str, Optional[datetime.date]]:
        dates = {'departure_date': None, 'return_date': None}
        try:
            date_elements = item_element.find_all('div', class_='neutral-color')
            
            for date_element in date_elements:
                date_text = date_element.get_text(strip=True)
                
                # 使用正則表達式提取日期
                match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                if match:
                    date_str = match.group(1)
                    if '出發' in date_text:
                        dates['departure_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()
                    elif '回程' in date_text:
                        dates['return_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()

        except Exception as e:
            self.log_manager.log_error(f"提取日期信息時發生錯誤: {str(e)}", e)
            raise Exception(f"提取日期信息時發生錯誤: {str(e)}")
            
        return dates

    def _extract_segments_from_html(self, item_element) -> List[FlightSegment]:
        """
        從單個航班的HTML元素中提取所有航段資料
        只從詳情區域提取航段信息，避免主要顯示區域的重複
        """
        segments: List[FlightSegment] = []
        
        try:
            # 只從詳情區域提取航段信息，避免主要顯示區域的重複
            detail_info = item_element.find('div', class_='flight-detail-info')
            
            if not detail_info:
                self.log_manager.log_warning("未找到詳情區域 flight-detail-info")
                return []
            
            # 在詳情區域中查找所有 class 包含 'w-100' 的 div 元素
            w100_elements = detail_info.find_all('div', class_=lambda x: x and 'w-100' in str(x))
            
            for idx, elem in enumerate(w100_elements):
                try:
                    segment = self._parse_single_flight_segment(elem)
                    if segment:
                        segments.append(segment)
                except ValueError as e:
                    self.log_manager.log_warning(f"解析詳情區域 w-100[{idx}]時發生資料格式錯誤，已跳過: {e}")
                except Exception as e:
                    self.log_manager.log_error(f"解析詳情區域 w-100[{idx}]時發生未預期錯誤: {e}", e)

            # 如果沒有提取到任何航段，記錄所有w-100元素的內容供除錯
            if not segments and w100_elements:
                self.log_manager.log_warning("未提取到任何航段，記錄詳情區域所有w-100元素內容供除錯:")
                for idx, elem in enumerate(w100_elements):
                    elem_text = elem.get_text(strip=True)
                    self.log_manager.log_warning(f"  詳情區域 w-100[{idx}]: {elem_text}")
        
        except Exception as e:
            self.log_manager.log_error(f"提取航段信息時發生錯誤: {str(e)}", e)
            raise Exception(f"提取航段信息時發生錯誤: {str(e)}")
            
        return segments

    def _parse_single_flight_segment(self, elem) -> Optional[FlightSegment]:
        """
        從單一HTML元素中解析並提取一個航班航段的資料。
        這個函數處理了複雜的文本解析和正規化，以確保提取到正確的航班號和艙等資訊。

        解析步驟：
        1. 獲取元素的純文本內容。
        2. 進行第一層篩選：檢查文本是否包含關鍵分隔符 "/"，這是判斷是否為有效航班資訊的初步條件。
        3. 進行第二層篩選：使用更寬鬆的正則表達式檢查文本是否包含航班號模式（字母+數字）和中文「艙」字，確保是航班和艙等資訊。
        4. 正規化文本：將多個空白字符（包括換行符）合併為單個空格，並移除前後空白，以便後續解析。
        5. 分割文本：使用 "/" 分割文本為多個部分，預期至少有兩個部分（航班號原始部分和艙等資訊）。
           - 註解：`len(parts) < 2` 表示分割後的結果不符合預期，例如缺少艙等資訊，此時視為無效數據。
           - 註解：空格為2的原因是因為前面是航班編號後面是艙等，如果沒有兩個資料的話就有問題
        6. 提取原始航班號和艙等資訊。
        7. 再次從原始航班號部分中提取純航班號碼。這裡採用更寬鬆的正則表達式 `([0-9A-Z]{1,3}-?\d{1,4})`，
           因為它已經包含了之前較為嚴格的 `([A-Z0-9]{1,3}-?\d{1,4})` 匹配範圍，從而簡化了代碼邏輯。
        8. 格式化航班號碼，統一為標準格式（例如：去除連字符，補零確保數字部分至少三位）。
        9. 提取並清理艙等資訊：移除括號等特殊字符，並確保包含「艙」字的部分被正確識別。
        10. 驗證所有提取到的信息是否有效。如果任何關鍵信息缺失，則視為無效航段。
        11. 建立 `FlightSegment` 物件並返回。

        注意事項：
        - 如果在解析過程中發生任何預期外的錯誤（例如數據格式不符合預期），將拋出 `ValueError` 或其他 `Exception`，
          以便呼叫者能夠捕獲並處理這些錯誤，而不是默默跳過，避免遺漏應處理的航段。

        參數：
            elem: BeautifulSoup元素，代表單一航班的航段資訊容器。

        返回：
            Optional[FlightSegment]: 解析成功的 `FlightSegment` 物件，如果解析失敗則返回 `None`。
                                   此函數在失敗時會拋出錯誤，因此呼叫者需處理例外。
        """
        text = elem.get_text(strip=True)

        # 第一層篩選：必須包含"/"
        if '/' not in text:
            return None

        # 第二層篩選：必須符合航班號格式（更寬鬆的條件）和艙等
        # 處理換行和特殊字符
        text_normalized = re.sub(r'\s+', ' ', text)  # 將多個空白字符（包括換行）合併為單個空格
        if not (re.search(r'[0-9A-Z]{1,3}-?\d{1,4}', text_normalized) and '艙' in text_normalized):
            return None

        # 解析航班資訊，先正規化文字（處理換行等）
        text_normalized = re.sub(r'\s+', ' ', text).strip()
        parts = text_normalized.split('/')
        if len(parts) < 2:
            raise ValueError(f"航班航段資訊格式不完整，缺少必要部分: '{text}'")

        flight_number_raw = parts[0].strip()
        cabin_info = parts[1].strip()

        # 從航班號部分提取純航班號（可能包含航空公司名稱、廉航標記等）
        # 使用正則表達式提取航班號：字母+數字的組合 (採用更寬鬆的匹配)
        flight_match = re.search(r'([0-9A-Z]{1,3}-?\d{1,4})', flight_number_raw)
        if not flight_match:
            raise ValueError(f"無法從 '{flight_number_raw}' 中提取有效航班號碼")
        flight_number_raw = flight_match.group(1)

        # 格式化航班號
        flight_number = self._format_flight_number(flight_number_raw)

        # 提取艙等信息 - 改進處理邏輯
        cabin_class = cabin_info.strip()
        # 移除括號和其他特殊字符
        cabin_class = re.sub(r'[()（）]', '', cabin_class)
        # 如果包含中文"艙"字，提取艙等部分
        if '艙' in cabin_class:
            cabin_match = re.search(r'(.*艙[A-Z0-9]*)', cabin_class)
            if cabin_match:
                cabin_class = cabin_match.group(1)
        else:
            raise ValueError(f"艙等資訊 '{cabin_info}' 未包含關鍵字 '艙'")

        # 驗證提取的信息
        if not flight_number or not cabin_class:
            raise ValueError(f"提取到的航班號或艙等資訊無效: 航班號 '{flight_number}', 艙等 '{cabin_class}'")

        return FlightSegment(
            flight_number=flight_number,
            cabin_class=cabin_class
        )

    def _extract_session_id_from_html(self, item_element) -> Optional[str]:
        """
        從去程航班HTML元素中提取session_id
        查找 onclick="searchReturnFlights('xxx')" 中的 session_id
        
        參數：
            item_element: BeautifulSoup元素，包含去程航班信息
            
        返回：
            Optional[str]: 提取到的session_id，如果找不到則返回None
        """
        try:
            # 查找包含 onclick 屬性的 <a> 標籤
            select_buttons = item_element.find_all('a', onclick=True)
            
            for button in select_buttons:
                onclick_attr = button.get('onclick', '')
                
                # 使用正則表達式匹配 searchReturnFlights('xxx')
                match = re.search(r"searchReturnFlights\(['\"](\d+)['\"]\)", onclick_attr)
                if match:
                    session_id = match.group(1)
                    return session_id
            
            # 如果沒有找到 onclick，嘗試搜索所有包含 searchReturnFlights 的文本
            all_text = item_element.get_text()
            match = re.search(r"searchReturnFlights\(['\"](\d+)['\"]\)", all_text)
            if match:
                session_id = match.group(1)
                return session_id
            else:
                raise ValueError("未找到 session_id")
            
        except Exception as e:
            self.log_manager.log_error(f"提取 session_id 時發生錯誤: {str(e)}", e)
            raise Exception(f"提取 session_id 時發生錯誤: {str(e)}")
