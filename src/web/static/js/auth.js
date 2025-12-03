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
 * Обновить access token используя refresh token
 * @returns {Promise<boolean>} true если токен успешно обновлен
 */
async function refreshAccessToken() {
    try {
        const response = await fetch('/api/bitrix24/permissions/refresh', {
            method: 'POST',
            credentials: 'include', // Отправляет httpOnly cookie с refresh token
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();

            // Сохраняем новый access token
            localStorage.setItem('accessToken', data.accessToken);
            localStorage.setItem('user', JSON.stringify(data.user));

            console.log('✅ Токен успешно обновлен');
            return true;
        } else {
            console.warn('❌ Не удалось обновить токен:', response.status);
            return false;
        }
    } catch (error) {
        console.error('❌ Ошибка при обновлении токена:', error);
        return false;
    }
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

        // Если получили 401 - токен истек, пытаемся обновить и повторить запрос
        if (response.status === 401) {
            console.warn('⚠️ Токен истек, пытаемся обновить...');

            // Пытаемся обновить токен
            const refreshed = await refreshAccessToken();

            if (refreshed) {
                // Токен обновлен, повторяем запрос с новым токеном
                const newToken = getAuthToken();
                options.headers = options.headers || {};
                options.headers['Authorization'] = `Bearer ${newToken}`;

                console.log('🔄 Повторяем запрос с новым токеном');
                return await fetch(url, options);
            } else {
                // Не удалось обновить токен
                console.error('❌ Не удалось обновить токен, требуется повторная авторизация');
                // В контексте Bitrix24 просто выводим ошибку
                // Пользователь может перезагрузить страницу
            }
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
        console.log('✅ JWT токен загружен успешно');

        // Устанавливаем автоматическое обновление токена каждые 3.5 часа
        // (токен живет 4 часа, обновляем с запасом)
        const REFRESH_INTERVAL = 3.5 * 60 * 60 * 1000; // 3.5 часа в миллисекундах

        setInterval(async () => {
            console.log('⏰ Плановое обновление токена...');
            const success = await refreshAccessToken();

            if (success) {
                console.log('✅ Токен автоматически обновлен');
            } else {
                console.error('❌ Не удалось автоматически обновить токен');
            }
        }, REFRESH_INTERVAL);

        console.log(`🔄 Автоматическое обновление токена настроено (каждые 3.5 часа)`);
    }
});
