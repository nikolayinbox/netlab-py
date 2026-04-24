import paramiko
import time
import socket
from .base import BaseChecker

class WindowsChecker(BaseChecker):
    def __init__(self, node_info, credentials=None, timeout=30):
        super().__init__(node_info, timeout)
        self.host = node_info.get('host', '127.0.0.1')
        self.port = int(node_info.get('port_2nd', 22))
        self.credentials = credentials or {}
        self.username = self.credentials.get('username', 'Administrator')
        self.password = self.credentials.get('password', '')
        self.ssh_key_file = self.credentials.get('ssh_key')
        # Кодировка для Windows (обычно cp866 в русской версии, cp1251 или utf-8)
        self.encoding = self.credentials.get('encoding', 'cp866')

    def connect_and_execute(self, command):
        print(f"[WindowsChecker] Подключение по SSH к {self.host}:{self.port} (устройство: {self.node.get('name')})")
        print(f"[WindowsChecker] Используем логин: {self.username}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': self.timeout,
                'look_for_keys': False,
                'allow_agent': False
            }
            if self.ssh_key_file:
                key = paramiko.RSAKey.from_private_key_file(self.ssh_key_file)
                connect_kwargs['pkey'] = key
            else:
                connect_kwargs['password'] = self.password

            client.connect(**connect_kwargs)
            print("[WindowsChecker] SSH-соединение установлено")

            # Создаем сессию и запускаем PowerShell с нужной кодировкой
            # Чтобы вывод был в UTF-8, можно выполнить chcp 65001 перед командой
            full_command = f'chcp 65001 > nul & powershell -Command "& {{ {command} }}"'
            print(f"[WindowsChecker] Выполнение команды: {full_command}")

            stdin, stdout, stderr = client.exec_command(full_command, timeout=self.timeout)

            # Читаем вывод с указанием кодировки
            output = stdout.read().decode(self.encoding, errors='replace')
            error_output = stderr.read().decode(self.encoding, errors='replace')

            exit_status = stdout.channel.recv_exit_status()
            print(f"[WindowsChecker] Код завершения: {exit_status}")

            if error_output:
                print(f"[WindowsChecker] STDERR: {error_output[:200]}")

            full_output = output
            if error_output:
                full_output += "\n[STDERR]\n" + error_output

            print(f"[WindowsChecker] Вывод (первые 500 символов):\n{full_output[:500]}")
            return full_output.strip()

        except Exception as e:
            raise e
        finally:
            client.close()
            print("[WindowsChecker] Соединение закрыто")