from abc import ABC, abstractmethod

class BaseChecker(ABC):
    def __init__(self, node_info, timeout=30):
        self.node = node_info
        self.timeout = timeout

    @abstractmethod
    def connect_and_execute(self, command):
        pass

    @staticmethod
    def factory(node_info, credentials=None):
        template = node_info.get('template', '').lower()
        device_name = node_info.get('name', '')

        # Извлекаем учётные данные для конкретного устройства
        dev_creds = {}
        if credentials:
            dev_creds = credentials.get('devices', {}).get(device_name, {})
            default_creds = credentials.get('default', {})
            merged_creds = {**default_creds, **dev_creds}
        else:
            merged_creds = {}

        if template in ['vios', 'viosl2', 'iol', 'dynamips']:
            from .cisco import CiscoChecker
            return CiscoChecker(node_info, credentials=merged_creds)
        elif template == 'linux':
            from .linux import LinuxChecker
            return LinuxChecker(node_info, credentials=merged_creds)
        elif template == 'winserver':
            from .windows import WindowsChecker
            return WindowsChecker(node_info, credentials=merged_creds)
        else:
            raise ValueError(f"Неизвестный тип устройства: {template}")