#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import uuid
import threading
import os
import yaml
import traceback

app = Flask(__name__)
CORS(app)

tasks = {}
CRITERIA_DIR = os.path.join(os.path.dirname(__file__), 'criteries')

def load_criteria(lab_id):
    file_path = os.path.join(CRITERIA_DIR, f"{lab_id}.yml")
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

sys.path.append(os.path.dirname(__file__))
from checkers.base import BaseChecker

def get_checker(node_info, credentials):
    template = node_info.get('template', '').lower()
    device_name = node_info.get('name', '')
    dev_creds = credentials.get('devices', {}).get(device_name, {})
    default_creds = credentials.get('default', {})
    merged_creds = {**default_creds, **dev_creds}

    if template in ['vios', 'viosl2', 'iol', 'dynamips']:
        from checkers.cisco import CiscoChecker
        return CiscoChecker(node_info, credentials=merged_creds)
    elif template == 'linux':
        from checkers.linux import LinuxChecker
        return LinuxChecker(node_info, credentials=merged_creds)
    elif template == 'winserver':
        from checkers.windows import WindowsChecker
        return WindowsChecker(node_info, credentials=merged_creds)
    else:
        raise ValueError(f"Неизвестный тип устройства: {template}")

def run_check_task(task_id, data):
    try:
        tasks[task_id]['status'] = 'running'
        tasks[task_id]['progress'] = 0
        tasks[task_id]['current_criterion'] = 'Инициализация...'
        tasks[task_id]['results'] = []
        tasks[task_id]['score'] = 0

        lab_id = data['lab_id']
        nodes = data['nodes']

        criteria_data = load_criteria(lab_id)
        if not criteria_data:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = f'Не найден файл критериев для lab_id {lab_id}'
            return

        credentials = criteria_data.get('credentials', {})
        sections = criteria_data.get('sections', [])
        total_points = criteria_data.get('total_points', 100)

        flat_criteria = []
        for section in sections:
            for item in section.get('items', []):
                item_copy = item.copy()
                item_copy['section_name'] = section.get('name', '')
                item_copy['section_description'] = section.get('description', '')
                flat_criteria.append(item_copy)

        total_criteria = len(flat_criteria)
        score = 0

        for idx, crit in enumerate(flat_criteria):
            progress = int((idx / total_criteria) * 100)
            tasks[task_id]['progress'] = progress
            tasks[task_id]['current_criterion'] = crit.get('description', f'Критерий {idx+1}')

            device_name = crit['device']
            if device_name not in nodes:
                result = {
                    'section': crit['section_name'],
                    'description': crit['description'],
                    'command': crit.get('command', ''),
                    'status': 'error',
                    'message': f'Устройство {device_name} не найдено в топологии',
                    'points_earned': 0,
                    'points_max': crit['points']
                }
                tasks[task_id]['results'].append(result)
                continue

            node_info = nodes[device_name]

            try:
                checker = get_checker(node_info, credentials)
                print(f"[DEBUG] Проверка критерия для {device_name}: {crit['description']}")
                output = checker.connect_and_execute(crit['command'])
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                # Определяем checks: либо массив checks, либо одиночный match_type/pattern
                checks = crit.get('checks')
                if checks is None:
                    match_type = crit.get('match_type')
                    pattern = crit.get('pattern')
                    if match_type and pattern is not None:
                        checks = [{'type': match_type, 'pattern': pattern}]
                    else:
                        checks = []

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
                    else:
                        print(f"[WARN] Неизвестный тип проверки: {ch_type}")

                points_earned = crit['points'] if passed else 0
                score += points_earned

                result = {
                    'section': crit['section_name'],
                    'description': crit['description'],
                    'command': crit['command'],
                    'status': 'passed' if passed else 'failed',
                    'checks': checks,
                    'output_snippet': output[:5000] + ('...' if len(output) > 5000 else ''),
                    'points_earned': points_earned,
                    'points_max': crit['points']
                }
                print(f"[DEBUG] Результат: {result['status']}, баллы: {points_earned}/{crit['points']}")

            except Exception as e:
                print(f"[ERROR] Ошибка при проверке {device_name}: {e}")
                traceback.print_exc()
                result = {
                    'section': crit['section_name'],
                    'description': crit['description'],
                    'command': crit.get('command', ''),
                    'status': 'error',
                    'message': str(e),
                    'points_earned': 0,
                    'points_max': crit['points']
                }

            tasks[task_id]['results'].append(result)
            tasks[task_id]['score'] = score
            tasks[task_id]['total_points'] = total_points

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['result'] = {
            'score': score,
            'total_points': total_points,
            'results': tasks[task_id]['results']
        }
        print(f"[DEBUG] Проверка завершена. Итоговый счёт: {score}/{total_points}")

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        traceback.print_exc()

@app.route('/start_check', methods=['POST'])
def start_check():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data'}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'pending',
        'progress': 0,
        'current_criterion': '',
        'results': [],
        'score': 0,
        'total_points': 0
    }
    thread = threading.Thread(target=run_check_task, args=(task_id, data))
    thread.daemon = True
    thread.start()
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({
        'status': task.get('status'),
        'progress': task.get('progress'),
        'current_criterion': task.get('current_criterion'),
        'results': task.get('results', []),
        'score': task.get('score', 0),
        'total_points': task.get('total_points', 0),
        'result': task.get('result'),
        'error': task.get('error')
    })

@app.route('/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Нет данных JSON"}), 400
        print("=" * 70)
        print("Получен запрос на проверку:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("=" * 70)
        sys.stdout.flush()
        return jsonify({"status": "received", "message": "Данные приняты"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Запуск сервера оценки PNetLab...")
    print(f"Папка критериев: {CRITERIA_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)