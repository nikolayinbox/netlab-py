import telnetlib
import time
import re
from .base import BaseChecker

class CiscoChecker(BaseChecker):
    def __init__(self, node_info, credentials=None, timeout=30):
        super().__init__(node_info, timeout)
        self.host = node_info.get('host', '127.0.0.1')
        self.port = int(node_info['port'])
        self.credentials = credentials or {}
        self.enable_password = self.credentials.get('enable_password', 'cisco')

    def _wake_up(self, tn):
        """Пробуждает консоль, отправляя Enter и очищая буфер."""
        print("[CiscoChecker] Пробуждение консоли...")
        tn.write(b'\r\n')
        time.sleep(1)
        # Читаем всё, что накопилось
        garbage = tn.read_very_eager().decode('ascii', errors='ignore')
        if garbage:
            print(f"[CiscoChecker] Пробуждение: прочитано {len(garbage)} символов мусора")
        # Убеждаемся, что видим приглашение
        if not (garbage.strip().endswith('>') or garbage.strip().endswith('#')):
            # Отправляем ещё Enter и ждём
            tn.write(b'\r\n')
            time.sleep(1)
            extra = tn.read_very_eager().decode('ascii', errors='ignore')
            if extra:
                print(f"[CiscoChecker] Дополнительный вывод: {extra[:200]}")

    def _clean_output(self, raw_output, command):
        """
        Удаляет из вывода:
        - строки до появления команды (включая само эхо команды)
        - приглашение в конце
        """
        lines = raw_output.splitlines()
        if not lines:
            return ""

        # Найти индекс строки, содержащей команду (эхо)
        cmd_idx = -1
        for i, line in enumerate(lines):
            if command in line:
                cmd_idx = i
                break

        if cmd_idx != -1:
            # Оставляем всё после строки с командой
            lines = lines[cmd_idx + 1:]
        else:
            # Если команда не найдена, возможно, она была в первой строке?
            # Пробуем удалить первую строку, если она похожа на приглашение с командой
            if lines and re.search(r'[#>]\s*' + re.escape(command), lines[0]):
                lines = lines[1:]

        # Удаляем финальное приглашение (последняя строка, заканчивающаяся на # или >)
        if lines and re.search(r'[#>]\s*$', lines[-1].strip()):
            lines = lines[:-1]

        # Удаляем возможные пустые строки в начале
        while lines and not lines[0].strip():
            lines.pop(0)

        return '\n'.join(lines).strip()

    def connect_and_execute(self, command):
        print(f"[CiscoChecker] Подключение к {self.host}:{self.port} (устройство: {self.node.get('name')})")
        tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)

        try:
            # Пробуждаем консоль и очищаем мусор
            self._wake_up(tn)

            # Проверяем, где мы находимся (user или enable)
            tn.write(b'\r\n')
            time.sleep(0.5)
            prompt_check = tn.read_very_eager().decode('ascii', errors='ignore')
            print(f"[CiscoChecker] Состояние консоли: {prompt_check[-50:]}")

            # Если видим '>', переходим в enable
            if '>' in prompt_check:
                tn.write(b'enable\r\n')
                time.sleep(1)
                enable_output = tn.read_very_eager().decode('ascii', errors='ignore')
                print(f"[CiscoChecker] Ответ на enable: {enable_output[:200]}")
                if 'Password:' in enable_output:
                    tn.write(self.enable_password.encode('ascii') + b'\r\n')
                    time.sleep(1)
                    post_pass = tn.read_very_eager().decode('ascii', errors='ignore')
                    print(f"[CiscoChecker] После ввода enable пароля: {post_pass[:200]}")

            # Отключаем пагинацию
            tn.write(b'terminal length 0\r\n')
            time.sleep(0.5)
            tn.read_very_eager()  # съедаем вывод команды terminal length

            # Выполняем целевую команду
            print(f"[CiscoChecker] Выполнение команды: {command}")
            tn.write(command.encode('ascii') + b'\r\n')
            time.sleep(2)

            # Собираем весь вывод до следующего приглашения
            cmd_output = b""
            while True:
                chunk = tn.read_very_eager()
                if chunk:
                    cmd_output += chunk
                # Проверяем, что вывод закончился приглашением
                if cmd_output and re.search(rb'[#>]\s*$', cmd_output.strip()):
                    break
                if len(cmd_output) > 100000:
                    break
                time.sleep(0.5)

            raw_output = cmd_output.decode('utf-8', errors='ignore')
            print(f"[CiscoChecker] Сырой вывод (первые 500 символов):\n{raw_output[:500]}")

            # Очищаем вывод
            clean = self._clean_output(raw_output, command)
            print(f"[CiscoChecker] Очищенный вывод (первые 500 символов):\n{clean[:500]}")

            return clean

        except Exception as e:
            raise e
        finally:
            tn.close()