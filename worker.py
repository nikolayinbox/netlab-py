#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import redis
import requests
import yaml
import os
import sys
import traceback
from time import sleep

# Подключаем путь к чекерам
sys.path.append(os.path.dirname(__file__))
from checkers.base import BaseChecker

# Конфигурация
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_CHANNEL = 'laravel-database-evaluation:queue'
CRITERIA_DIR = '/var/www/nikolay/data/www/netlab.kkat.edu.kz/storage/app/criteria/criteria'  # общая папка с критериями
INTERNAL_API_TOKEN = 'oIj0oaLeLo9gC0jRUj4fj7GokSjvl3nhehvQ7ukhas9to1YxVwdXmG8SNrJGym93bovutprDn7mjbzSnZE5zn8dyvXjF6lsDLN5oHXAjYIci8xru0vsQijD6KvhY9aIi'

def load_criteria(lab_id):
    file_path = os.path.join(CRITERIA_DIR, f"{lab_id}.yml")
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def send_update(callback_url, session_uuid, status, progress=None, current_criterion=None, results=None, score=None):
    payload = {
        'session_uuid': session_uuid,
        'status': status,
    }
    if progress is not None:
        payload['progress'] = progress
    if current_criterion:
        payload['current_criterion'] = current_criterion
    if results:
        payload['results'] = results
    if score is not None:
        payload['score'] = score

    headers = {'Authorization': f'Bearer {INTERNAL_API_TOKEN}'}
    try:
        requests.post(callback_url, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки обновления: {e}")

def process_task(task_data):
    session_uuid = task_data['session_uuid']
    lab_id = task_data['lab_id']
    nodes = task_data['nodes']
    pnet_host = task_data['pnet_host']
    callback_url = task_data['callback_url']

    print(f"Запуск проверки сессии {session_uuid}")

    # Загружаем критерии
    criteria_data = load_criteria(lab_id)
    if not criteria_data:
        send_update(callback_url, session_uuid, 'failed', error_message='Критерии не найдены')
        return

    credentials = criteria_data.get('credentials', {})
    sections = criteria_data.get('sections', [])
    total_points = criteria_data.get('total_points', 100)

    flat_criteria = []
    for section in sections:
        for item in section.get('items', []):
            item_copy = item.copy()
            item_copy['section_name'] = section.get('name', '')
            flat_criteria.append(item_copy)

    results = []
    score = 0
    total_criteria = len(flat_criteria)

    for idx, crit in enumerate(flat_criteria):
        progress = int((idx / total_criteria) * 100)
        current_criterion = crit.get('description', '')
        send_update(callback_url, session_uuid, 'running', progress=progress, current_criterion=current_criterion)

        device_name = crit['device']
        if device_name not in nodes:
            result = {
                'section': crit['section_name'],
                'description': crit['description'],
                'command': crit.get('command', ''),
                'status': 'error',
                'expected': '',
                'output_snippet': '',
                'points_earned': 0,
                'points_max': crit['points'],
                'checks': crit.get('checks', [])
            }
            results.append(result)
            continue

        node_info = nodes[device_name]
        # Модифицируем порты на pnet_host (если воркер работает на другой машине)
        node_info['host'] = pnet_host['host']
        node_info['port'] = int(node_info['port'])
        node_info['port_2nd'] = int(node_info['port_2nd']) if node_info.get('port_2nd') else None

        try:
            # Используем фабрику чекеров (она должна быть адаптирована для работы с удалённым хостом)
            # Здесь предполагается, что чекеры уже поддерживают параметр host
            # Если нет, нужно модифицировать CiscoChecker и другие, чтобы принимали host
            checker = BaseChecker.factory(node_info, credentials)
            output = checker.connect_and_execute(crit['command'])
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='ignore')

            # Проверка
            checks = crit.get('checks', [])
            if not checks:
                match_type = crit.get('match_type')
                pattern = crit.get('pattern')
                if match_type and pattern:
                    checks = [{'type': match_type, 'pattern': pattern}]

            passed = True
            for check in checks:
                ch_type = check['type']
                ch_pattern = check['pattern']
                if ch_type == 'include':
                    if ch_pattern not in output:
                        passed = False
                        break
                elif ch_type == 'exclude':
                    if ch_pattern in output:
                        passed = False
                        break
                elif ch_type == 'regex':
                    import re
                    if not re.search(ch_pattern, output):
                        passed = False
                        break

            points_earned = crit['points'] if passed else 0
            score += points_earned

            result = {
                'section': crit['section_name'],
                'description': crit['description'],
                'device': device_name,  # <-- добавляем
                'command': crit['command'],
                'status': 'passed' if passed else 'failed',
                'expected': checks,
                'output_snippet': output[:5000],
                'points_earned': points_earned,
                'points_max': crit['points'],
                'checks': checks
            }
        except Exception as e:
            traceback.print_exc()
            result = {
                'section': crit['section_name'],
                'description': crit['description'],
                'device': device_name,
                'command': crit.get('command', ''),
                'status': 'error',
                'expected': str(e),
                'output_snippet': '',
                'points_earned': 0,
                'points_max': crit['points'],
                'checks': crit.get('checks', [])
            }

        results.append(result)

    # Финальное обновление
    send_update(callback_url, session_uuid, 'completed', progress=100, results=results, score=score)
    print(f"Проверка сессии {session_uuid} завершена. Счёт: {score}/{total_points}")

if __name__ == '__main__':
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)
    print(f"Ожидание заданий в канале {REDIS_CHANNEL}...")
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                task_data = json.loads(message['data'])
                process_task(task_data)
            except Exception as e:
                print(f"Ошибка обработки задания: {e}")
                traceback.print_exc()