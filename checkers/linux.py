# checkers/linux.py
import paramiko
import time
import socket
from .base import BaseChecker

class LinuxChecker(BaseChecker):
    def __init__(self, node_info, credentials=None, timeout=30):
        super().__init__(node_info, timeout)
        self.host = node_info.get('host', '127.0.0.1')
        # Используем порт вторичной консоли (SSH)
        self.port = int(node_info.get('port_2nd', 22))
        self.credentials = credentials or {}
        self.username = self.credentials.get('username', 'root')
        self.password = self.credentials.get('password', '')
        self.ssh_key_file = self.credentials.get('ssh_key')  # путь к приватному ключу

    def connect_and_execute(self, command):
        print(f"[LinuxChecker] Подключение по SSH к {self.host}:{self.port} (устройство: {self.node.get('name')})")
        print(f"[LinuxChecker] Используем логин: {self.username}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Пробуем подключиться
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': self.timeout,
                'look_for_keys': False,
                'allow_agent': False
            }
            if self.ssh_key_file:
                # Аутентификация по ключу
                key = paramiko.RSAKey.from_private_key_file(self.ssh_key_file)
                connect_kwargs['pkey'] = key
            else:
                # Аутентификация по паролю
                connect_kwargs['password'] = self.password

            client.connect(**connect_kwargs)
            print("[LinuxChecker] SSH-соединение установлено")

            # Выполняем команду
            print(f"[LinuxChecker] Выполнение команды: {command}")
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)

            # Читаем вывод
            output = stdout.read().decode('utf-8', errors='ignore')
            error_output = stderr.read().decode('utf-8', errors='ignore')

            # Ждём завершения команды
            exit_status = stdout.channel.recv_exit_status()
            print(f"[LinuxChecker] Код завершения: {exit_status}")

            if error_output:
                print(f"[LinuxChecker] STDERR: {error_output[:200]}")

            # Возвращаем объединённый вывод (можно и раздельно, но для проверки обычно нужен stdout)
            full_output = output
            if error_output:
                full_output += "\n[STDERR]\n" + error_output

            print(f"[LinuxChecker] Вывод (первые 500 символов):\n{full_output[:500]}")
            return full_output.strip()

        except paramiko.AuthenticationException:
            raise Exception(f"Ошибка аутентификации SSH для {self.username}@{self.host}:{self.port}")
        except paramiko.SSHException as e:
            raise Exception(f"Ошибка SSH: {e}")
        except socket.timeout:
            raise Exception(f"Таймаут подключения к {self.host}:{self.port}")
        except Exception as e:
            raise e
        finally:
            client.close()
            print("[LinuxChecker] Соединение закрыто")