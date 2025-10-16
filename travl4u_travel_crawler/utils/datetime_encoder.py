import json
import datetime

class DateTimeEncoder(json.JSONEncoder):
    """
    自定義 JSON 編碼器，用於將 datetime.date 和 datetime.datetime 物件
    序列化為 ISO 8601 格式的字符串。
    """
    def default(self, o: any) -> any:
        """
        覆蓋 json.JSONEncoder.default 方法。

        如果物件是 datetime.date 或 datetime.datetime 的實例，
        則返回其 ISO 8601 格式的字符串表示。
        否則，調用父類的 default 方法。

        參數：
            o (any): 要序列化的物件。

        返回：
            any: 序列化後的物件。
        """
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return super().default(o) 