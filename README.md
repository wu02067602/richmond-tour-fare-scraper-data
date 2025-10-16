# 山富旅遊網機票資料爬蟲系統

這個專案是一個自動化爬蟲系統，專門用於抓取山富旅遊網站的機票資料，透過分析 GraphQL API 取得機票價格及相關資訊，並將資料存儲至 Google Cloud Storage 和 BigQuery 中以便後續分析。

## 目錄

- [功能特點](#功能特點)
- [專案結構](#專案結構)
- [安裝方法](#安裝方法)
- [使用方法](#使用方法)
- [環境需求](#環境需求)
- [容器化部署](#容器化部署)

## 功能特點

- **動態爬蟲功能**：透過 API 抓取山富旅遊網站的機票資料，支援指定多種查詢參數
- **非同步任務處理**：支援多任務並行執行，提高爬蟲效率
- **批次處理**：支援批次提交多組查詢參數，同時監控多條航線價格變化
- **資料儲存與管理**：將抓取的資料結構化後存儲至 Google BigQuery 和 Cloud Storage
- **可靠性設計**：具備錯誤重試機制，確保資料抓取的完整性

## 專案結構

```
travl4u_travel_crawler/
│
├── main.py                      # 主程式入口點
├── .env                         # 環境變量
├── requirements.txt             # 專案依賴
├── README.md                    # 專案說明文件
│
├── config/                      # 配置文件目錄
│   ├── __init__.py
│   ├── config.yaml              # 主要配置文件
│   └── config_manager.py        # 配置管理器類
│
├── controllers/                 # 控制器目錄
│   ├── __init__.py
│   ├── crawler_controller.py    # 爬蟲控制器
│   ├── api_client.py            # API客戶端
│   └── task_manager.py          # 任務管理器
│
├── models/                      # 數據模型目錄
│   ├── __init__.py
│   ├── flight_info.py           # 航班信息類
│   ├── flight_segment.py        # 航班段類
│   └── crawl_task.py            # 爬蟲任務類
│
├── parsers/                     # 解析器目錄
│   ├── __init__.py
│   └── html_parser.py           # HTML解析器
│
├── processors/                  # 處理器目錄
│   ├── __init__.py
│   ├── data_processor.py                           # 數據處理器
│   ├── flight_tasks_fixed_month_processors.py      # 固定月份日期任務處理
│   └── flight_tasks_holidays_processors.py         # 節日爬蟲任務處理
│
├── storage/                     # 存儲管理目錄
│   ├── __init__.py
│   └── storage_manager.py       # 存儲管理器
│
└── utils/                       # 工具類目錄
    ├── __init__.py
    ├── log_manager.py           # 日誌管理器
    └── debug_tools.py           # 除錯工具
```

## 安裝方法

1. 克隆此專案到本地：
   ```bash
   git clone https://github.com/colatour/travl4u-tour-fare-scraper-data.git
   ```

2. 進入專案目錄並創建虛擬環境：
   ```bash
   cd travl4u-tour-fare-scraper-data
   python -m venv .venv
   ```

3. 啟動虛擬環境：

   - 對於Windows：
     ```bash
     .venv\Scripts\activate
     ```

   - 對於macOS和Linux：
     ```bash
     source .venv/bin/activate
     ```

4. 安裝所需的Python套件：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

### 使用預設配置

不提供參數時，系統將從配置文件讀取預定義任務：

```bash
python travl4u_travel_crawler/main.py
```

## 環境需求

- Python 3.10+
- Google Cloud 服務（BigQuery、Cloud Storage）訪問權限
- 必要的Python套件（詳見requirements.txt）

## 容器化部署

本專案支援使用Docker容器部署：

1. 建立Docker映像檔：
   ```bash
   docker build -t travl4u-tour-fare-scraper-data .
   ```

2. 運行容器：
   ```bash
   docker run -d travl4u-tour-fare-scraper-data
   ```

此爬蟲系統設計為可在Google Cloud Run環境下自動運行，並可透過Cloud Build進行CI/CD部署。
