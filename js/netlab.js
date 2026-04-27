/**
 * Кастомный скрипт для оценки лабораторных работ в PNetLab
 * Версия 0.5 - поддержка локальной и серверной проверки, авторизация с привязкой к пользователю PNet
 */

(function() {
    'use strict';

    // Конфигурация
    const CONFIG = {
        LOCAL_SERVER_URL: 'http://' + window.location.hostname + ':5000',
        CENTRAL_API_URL: 'http://netlab.kkat.edu.kz/api', // Замените на реальный URL вашего Laravel API
        TOKEN_STORAGE_KEY: 'pnet_eval_token',
        PNET_USER_KEY: 'pnet_eval_pnet_user'
    };

    $(document).ready(function() {
        setTimeout(addEvaluationButton, 500);
    });

    function addEvaluationButton() {
        var $navbar = $('.navbar-nav, .nav.navbar-nav, .top-menu, .navbar-right').first();

        if ($navbar.length === 0) {
            $('body').append('<div id="customEvalFloatBtn" style="position:fixed; bottom:40px; right:10px; z-index:9999;"><button class="btn btn-success btn-lg" id="evalBtn"><i class="fa fa-check-square-o"></i> Оценка</button></div>');
            $('#evalBtn').on('click', onEvaluateClick);
            return;
        }

        var $listItem = $('<li>', { 'class': 'dropdown' });
        var $link = $('<a>', {
            'href': '#',
            'id': 'evalBtn',
            'html': '<i class="fa fa-check-square-o"></i> Оценка'
        });

        $link.on('click', onEvaluateClick);
        $listItem.append($link);
        $navbar.append($listItem);

        console.log('[Eval] Кнопка "Оценка" успешно добавлена в интерфейс.');
    }

    function onEvaluateClick(e) {
        e.preventDefault();
        var payload = collectTopologyData();
        showEvalModal(payload);
    }

    function collectTopologyData() {
        var pnetInfo = {
            username: (typeof USERNAME !== 'undefined') ? USERNAME : 'unknown',
            server_host: window.location.hostname,
        };

        var labId = (typeof topology !== 'undefined' && topology.labinfo && topology.labinfo.id) ? topology.labinfo.id : 'unknown_lab';

        var nodes = {};
        if (typeof topology !== 'undefined' && topology.nodes) {
            for (var nodeId in topology.nodes) {
                if (topology.nodes.hasOwnProperty(nodeId)) {
                    var node = topology.nodes[nodeId];
                    var nodeName = node.name || 'Unnamed_' + nodeId;
                    if (nodes.hasOwnProperty(nodeName)) {
                        nodeName = nodeName + '_' + nodeId;
                    }
                    nodes[nodeName] = {
                        id: parseInt(nodeId),
                        name: nodeName,
                        type: node.template_type || node.type || 'unknown',
                        template: node.template || 'unknown',
                        console: node.console,
                        port: node.port,
                        console_2nd: node.console_2nd,
                        port_2nd: node.port_2nd,
                    };
                }
            }
        }

        return {
            pnet_info: pnetInfo,
            lab_id: labId,
            nodes: nodes
        };
    }

    function isAuthorizedForCurrentUser() {
        var token = localStorage.getItem(CONFIG.TOKEN_STORAGE_KEY);
        var savedPnetUser = localStorage.getItem(CONFIG.PNET_USER_KEY);
        var currentPnetUser = (typeof USERNAME !== 'undefined') ? USERNAME : null;

        if (!token || !savedPnetUser || savedPnetUser !== currentPnetUser) {
            localStorage.removeItem(CONFIG.TOKEN_STORAGE_KEY);
            localStorage.removeItem(CONFIG.PNET_USER_KEY);
            return false;
        }
        return true;
    }

    function showEvalModal(data) {
        var isAuthorized = isAuthorizedForCurrentUser();
        var pnetInfo = data.pnet_info;

        var modalHtml = `
            <div class="modal fade" id="evalMainModal" tabindex="-1" role="dialog">
                <div class="modal-dialog" style="width:700px;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <button type="button" class="close" data-dismiss="modal">&times;</button>
                            <h4 class="modal-title">Оценка лабораторной работы</h4>
                        </div>
                        <div class="modal-body" style="font-size:14px;">
                            <div class="panel panel-default">
                                <div class="panel-heading">Информация о сессии</div>
                                <div class="panel-body">
                                    <p><strong>Пользователь PNet:</strong> ${escapeHtml(pnetInfo.username)}</p>
                                    <p><strong>IP / Хост PNet:</strong> ${escapeHtml(pnetInfo.server_host)}</p>
                                    <p><strong>ID лаборатории:</strong> ${escapeHtml(data.lab_id)}</p>
                                </div>
                            </div>
                            
                            <div id="authBlock">
                                ${isAuthorized ? `
                                    <div class="alert alert-success">
                                        <i class="fa fa-check-circle"></i> Вы авторизованы на центральном сервере
                                    </div>
                                ` : `
                                    <div class="panel panel-default">
                                        <div class="panel-heading">Авторизация на сервере</div>
                                        <div class="panel-body">
                                            <div class="form-group">
                                                <label>Логин:</label>
                                                <input type="text" class="form-control" id="authUsername" placeholder="Логин">
                                            </div>
                                            <div class="form-group">
                                                <label>Пароль:</label>
                                                <input type="password" class="form-control" id="authPassword" placeholder="Пароль">
                                            </div>
                                            <button class="btn btn-primary" id="loginBtn">Войти</button>
                                            <span id="loginError" class="text-danger" style="margin-left:10px;"></span>
                                        </div>
                                    </div>
                                `}
                            </div>
                            
                            <div class="row" style="margin-top:20px;">
                                <div class="col-xs-6">
                                    <button class="btn btn-success btn-block" id="localCheckBtn">
                                        <i class="fa fa-laptop"></i> Проверить локально
                                    </button>
                                </div>
                                <div class="col-xs-6">
                                    <button class="btn btn-primary btn-block" id="serverCheckBtn" ${isAuthorized ? '' : 'disabled'}>
                                        <i class="fa fa-cloud-upload"></i> Отправить на сервер
                                    </button>
                                </div>
                            </div>
                            <div class="text-muted" style="margin-top:10px;">
                                Локальная проверка выполняется на этом компьютере и показывает детальные результаты.<br>
                                Отправка на сервер сохранит результат в вашем профиле.
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-default" data-dismiss="modal">Закрыть</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        $('#evalMainModal').remove();
        $('body').append(modalHtml);
        $('#evalMainModal').modal('show');

        $('#loginBtn').on('click', function() {
            var username = $('#authUsername').val().trim();
            var password = $('#authPassword').val();
            if (!username || !password) {
                $('#loginError').text('Введите логин и пароль');
                return;
            }
            $('#loginError').text('');
            fetch(CONFIG.CENTRAL_API_URL + '/auth/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, password: password })
            })
                .then(r => r.json())
                .then(resp => {
                    if (resp.token) {
                        localStorage.setItem(CONFIG.TOKEN_STORAGE_KEY, resp.token);
                        localStorage.setItem(CONFIG.PNET_USER_KEY, pnetInfo.username);
                        $('#authBlock').html('<div class="alert alert-success"><i class="fa fa-check-circle"></i> Авторизация успешна</div>');
                        $('#serverCheckBtn').prop('disabled', false);
                    } else {
                        $('#loginError').text(resp.message || 'Ошибка авторизации');
                    }
                })
                .catch(err => {
                    $('#loginError').text('Ошибка соединения с сервером');
                });
        });

        $('#localCheckBtn').on('click', function() {
            $('#evalMainModal').modal('hide');
            startLocalEvaluation(data);
        });

        $('#serverCheckBtn').on('click', function() {
            $('#evalMainModal').modal('hide');
            startServerEvaluation(data);
        });

        $('#evalMainModal').on('hidden.bs.modal', function() {
            $(this).remove();
        });
    }

    function startLocalEvaluation(payload) {
        var modalHtml = `
            <div class="modal fade" id="evalProgressModal" tabindex="-1" role="dialog">
                <div class="modal-dialog modal-lg" style="width:90%; max-width:1200px;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <button type="button" class="close" data-dismiss="modal">&times;</button>
                            <h4 class="modal-title">Локальная проверка</h4>
                        </div>
                        <div class="modal-body">
                            <h4>Проверка лабораторной работы</h4>
                            <div class="progress">
                                <div id="evalProgressBar" class="progress-bar progress-bar-striped active" style="width:0%">0%</div>
                            </div>
                            <p id="evalStatusText">Запуск проверки...</p>
                            <div style="max-height:400px; overflow-y:auto;">
                                <table class="table table-condensed table-hover" style="font-size:14px;">
                                    <thead><tr><th>Критерий</th><th>Результат</th><th>Баллы</th></tr></thead>
                                    <tbody id="evalResultsBody"></tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-default" data-dismiss="modal">Закрыть</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        $('body').append(modalHtml);
        $('#evalProgressModal').modal('show');

        var serverUrl = CONFIG.LOCAL_SERVER_URL;
        fetch(serverUrl + '/start_check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(r => r.json())
            .then(startData => {
                var taskId = startData.task_id;
                var pollInterval = setInterval(function() {
                    fetch(serverUrl + '/status/' + taskId)
                        .then(r => r.json())
                        .then(taskData => {
                            $('#evalProgressBar').css('width', taskData.progress + '%').text(taskData.progress + '%');
                            $('#evalStatusText').text(taskData.current_criterion || 'Выполняется...');
                            if (taskData.results) {
                                renderResultsTable(taskData.results);
                            }
                            if (taskData.status === 'completed') {
                                clearInterval(pollInterval);
                                $('#evalStatusText').text('Проверка завершена');
                                $('#evalProgressBar').removeClass('active').addClass('progress-bar-success');
                                var finalScore = taskData.score + ' / ' + taskData.total_points;
                                $('#evalStatusText').after('<p><strong>Итоговый счёт: ' + finalScore + '</strong></p>');
                            } else if (taskData.status === 'failed') {
                                clearInterval(pollInterval);
                                $('#evalStatusText').text('Ошибка: ' + taskData.error);
                                $('#evalProgressBar').removeClass('active').addClass('progress-bar-danger');
                            }
                        })
                        .catch(err => { console.error(err); });
                }, 1000);
            })
            .catch(err => {
                $('#evalProgressModal .modal-body').html('<div class="alert alert-danger">Ошибка запуска: ' + err.message + '</div>');
            });

        $('#evalProgressModal').on('hidden.bs.modal', function() { $(this).remove(); });
    }

    function startServerEvaluation(payload) {
        var token = localStorage.getItem(CONFIG.TOKEN_STORAGE_KEY);
        var modalHtml = `
            <div class="modal fade" id="evalServerModal" tabindex="-1" role="dialog">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <button type="button" class="close" data-dismiss="modal">&times;</button>
                            <h4 class="modal-title">Отправка на сервер</h4>
                        </div>
                        <div class="modal-body">
                            <div class="progress">
                                <div id="serverProgressBar" class="progress-bar progress-bar-striped active" style="width:0%">0%</div>
                            </div>
                            <p id="serverStatusText">Отправка данных...</p>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-default" data-dismiss="modal">Закрыть</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        $('body').append(modalHtml);
        $('#evalServerModal').modal('show');

        fetch(CONFIG.CENTRAL_API_URL + '/evaluation/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        })
            .then(r => r.json())
            .then(data => {
                if (data.session_uuid) {
                    var sessionUuid = data.session_uuid;
                    var pollInterval = setInterval(function() {
                        fetch(CONFIG.CENTRAL_API_URL + '/evaluation/status/' + sessionUuid, {
                            headers: { 'Authorization': 'Bearer ' + token }
                        })
                            .then(r => r.json())
                            .then(status => {
                                $('#serverProgressBar').css('width', status.progress + '%').text(status.progress + '%');
                                $('#serverStatusText').text(status.current_criterion || 'Выполняется...');
                                if (status.status === 'completed') {
                                    clearInterval(pollInterval);
                                    $('#serverProgressBar').removeClass('active').addClass('progress-bar-success');
                                    $('#serverStatusText').text('Проверка завершена. Результат сохранён в вашем профиле.');
                                } else if (status.status === 'failed') {
                                    clearInterval(pollInterval);
                                    $('#serverProgressBar').removeClass('active').addClass('progress-bar-danger');
                                    $('#serverStatusText').text('Ошибка: ' + status.error);
                                }
                            })
                            .catch(err => { console.error(err); });
                    }, 1500);
                } else {
                    $('#serverStatusText').text('Ошибка: ' + (data.message || 'Неизвестная ошибка'));
                }
            })
            .catch(err => {
                $('#serverStatusText').text('Ошибка соединения с сервером');
            });

        $('#evalServerModal').on('hidden.bs.modal', function() { $(this).remove(); });
    }

    function renderResultsTable(results) {
        var $tbody = $('#evalResultsBody');
        $tbody.empty();
        results.forEach(function(r) {
            var statusIcon = r.status === 'passed' ? '✅' : (r.status === 'failed' ? '❌' : '⚠️');
            var expected = '';
            if (r.checks) {
                expected = r.checks.map(c => `${c.type} "${c.pattern}"`).join(' И ');
            } else if (r.expected) {
                expected = r.expected;
            } else if (r.message) {
                expected = r.message;
            }
            var row = `<tr><td>${statusIcon} ${escapeHtml(r.description)}</td><td>${escapeHtml(expected)}</td><td>${r.points_earned}/${r.points_max}</td></tr>`;
            if (r.output_snippet) {
                var cmd = r.command ? `<strong>Команда:</strong> ${escapeHtml(r.command)}<br>` : '';
                row += `<tr><td colspan="3"><details><summary>Показать вывод</summary><div style="margin-top:5px;">${cmd}<pre style="font-size:11px; max-height:200px; overflow:auto; white-space:pre-wrap;">${escapeHtml(r.output_snippet)}</pre></div></details></td></tr>`;
            }
            $tbody.append(row);
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        var map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
})();