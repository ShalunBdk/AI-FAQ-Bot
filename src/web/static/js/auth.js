/**
 * Модуль авторизации для админ-панели
 * Управляет JWT токенами и добавляет их во все API запросы
 */

/**
 * Получить JWT токен из localStorage или URL
 * @returns {string|null} JWT токен
 */
function getAuthToken() {
    // 1. Сначала проверяем URL параметр ?token=...
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');

    if (tokenFromUrl) {
        // Сохраняем токен в localStorage
        localStorage.setItem('accessToken', tokenFromUrl);

        // Очищаем URL от токена (для безопасности)
        const cleanUrl = window.location.pathname + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);

        return tokenFromUrl;
    }

    // 2. Иначе берем из localStorage
    return localStorage.getItem('accessToken');
}

/**
 * Получить данные пользователя из localStorage
 * @returns {Object|null} Объект с данными пользователя
 */
function getCurrentUser() {
    const userJson = localStorage.getItem('user');
    return userJson ? JSON.parse(userJson) : null;
}

/**
 * Выполнить fetch запрос с автоматическим добавлением Authorization заголовка
 * @param {string} url - URL для запроса
 * @param {Object} options - Опции для fetch (method, body, headers и т.д.)
 * @returns {Promise<Response>} Promise с ответом
 */
async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();

    // Добавляем Authorization заголовок если есть токен
    if (token) {
        options.headers = options.headers || {};
        options.headers['Authorization'] = `Bearer ${token}`;
    }

    // Добавляем Content-Type для JSON если его нет
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.headers = options.headers || {};
        if (!options.headers['Content-Type']) {
            options.headers['Content-Type'] = 'application/json';
        }
        // Конвертируем body в JSON строку если это объект
        if (!(typeof options.body === 'string')) {
            options.body = JSON.stringify(options.body);
        }
    }

    try {
        const response = await fetch(url, options);

        // Если получили 401 - токен истек или невалидный
        if (response.status === 401) {
            console.warn('Токен истек или невалиден');
            // Можно добавить автоматический редирект на страницу входа
            // window.location.href = '/bitrix24/auth';
        }

        return response;
    } catch (error) {
        console.error('Ошибка при выполнении запроса:', error);
        throw error;
    }
}

/**
 * Проверить наличие валидного токена
 * @returns {boolean} true если токен есть
 */
function isAuthenticated() {
    return !!getAuthToken();
}

/**
 * Выйти из системы (очистить токен)
 */
function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    // Перенаправляем на главную Bitrix24
    if (window.BX24) {
        window.BX24.closeApplication();
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Извлекаем токен из URL при первой загрузке
    const token = getAuthToken();

    if (!token) {
        console.warn('JWT токен не найден. Некоторые функции могут быть недоступны.');
    } else {
        console.log('JWT токен загружен успешно');
    }
});
