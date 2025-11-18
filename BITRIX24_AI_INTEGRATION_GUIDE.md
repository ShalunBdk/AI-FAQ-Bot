# Руководство для AI: Интеграция приложения в Bitrix24

> **Целевая аудитория:** AI-ассистенты, помогающие разработчикам интегрировать React/Node.js приложения с Bitrix24
>
> **Версия:** 1.0
> **Дата обновления:** 2025-01-11

---

## 📋 Содержание

1. [Введение](#введение)
2. [Архитектура интеграции](#архитектура-интеграции)
3. [Пошаговая инструкция](#пошаговая-инструкция)
4. [Backend реализация](#backend-реализация)
5. [Frontend реализация](#frontend-реализация)
6. [База данных](#база-данных)
7. [Системы прав доступа](#системы-прав-доступа)
8. [Тестирование и отладка](#тестирование-и-отладка)
9. [Production deployment](#production-deployment)
10. [Типичные проблемы и решения](#типичные-проблемы-и-решения)

---

## Введение

### Что такое интеграция с Bitrix24?

Bitrix24 - это корпоративный портал и CRM-система, которая позволяет встраивать сторонние приложения через OAuth 2.0 и REST API. Интеграция позволяет:

- ✅ Встроить приложение в интерфейс Bitrix24 (iframe)
- ✅ Получить данные о пользователях портала
- ✅ Использовать SSO (Single Sign-On) авторизацию
- ✅ Работать с REST API Bitrix24
- ✅ Поддерживать множественные установки (несколько порталов)

### Типы интеграции

1. **Локальное приложение** (Local Application) - встраивается в конкретный портал
2. **Маркетплейс приложение** - публикуется в Bitrix24.Market для всех пользователей
3. **Webhook интеграция** - односторонняя интеграция без UI

Это руководство фокусируется на **локальном приложении**.

---

## Архитектура интеграции

### Общая схема

```
┌─────────────────────────────────────────────────────────────┐
│                    Bitrix24 Portal                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Bitrix24 UI (iframe container)                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Your React Application                         │  │  │
│  │  │  + Bitrix24 JS SDK (BX24)                       │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ OAuth 2.0 / REST API
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              Your Backend (Express/Node.js)                 │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Bitrix24 Routes │  │ Token Storage│  │ Permissions   │  │
│  │ /bitrix24/*     │  │ (in-memory/  │  │ Management    │  │
│  │                 │  │  PostgreSQL) │  │               │  │
│  └─────────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                        │
│  - bitrix24_permissions (user roles)                        │
│  - your_app_data                                            │
└─────────────────────────────────────────────────────────────┘
```

### Ключевые компоненты

1. **Bitrix24 JS SDK (BX24)** - клиентская библиотека для взаимодействия с Bitrix24
2. **OAuth 2.0 токены** - access_token и refresh_token для REST API
3. **Webhook endpoints** - серверные обработчики для установки и открытия приложения
4. **Token storage** - хранилище токенов (in-memory, PostgreSQL, Redis)
5. **Permissions system** - управление правами доступа пользователей

---

## Пошаговая инструкция

### Шаг 1: Регистрация приложения в Bitrix24

#### 1.1 Создание локального приложения

1. Откройте портал Bitrix24
2. Перейдите: **Приложения** → **Разработчикам** → **Другое** → **Добавить приложение**
3. Выберите тип: **Локальное приложение**

#### 1.2 Настройка параметров приложения

**Основная информация:**
```
Название: Ваше приложение
Код: your_app_code (латиница, цифры, подчеркивание)
Описание: Краткое описание функционала
```

**URL обработчиков:**
```
Обработчик установки (Install handler):
https://your-domain.com/bitrix24/install

Обработчик первого открытия (Index handler):
https://your-domain.com/bitrix24/index

URL встраивания приложения (Application URL):
https://your-domain.com/bitrix24/app
```

**Права доступа (Scopes):**
- Минимум: `app` (базовый доступ)
- Дополнительно: `user`, `department`, `crm`, и т.д. (в зависимости от функционала)

#### 1.3 Получение учетных данных

После создания приложения сохраните:
- **CLIENT_ID** (Application ID) - например: `local.5c8bb1b0891cf2.87252039`
- **CLIENT_SECRET** (Application key) - например: `SakeVG5mbRdcQet45UUrt6q72AMTo7fkwXSO7Y5LYFYNCRsA6f`

### Шаг 2: Настройка окружения разработки

#### 2.1 Установка зависимостей

**Backend (Node.js/Express):**
```bash
npm install express cors helmet cookie-parser bcryptjs jsonwebtoken
npm install @types/express @types/cors @types/bcryptjs @types/jsonwebtoken --save-dev
```

**Frontend (React):**
```bash
npm install react react-router-dom
npm install @types/react @types/react-router-dom --save-dev
```

#### 2.2 Настройка .env файла

Создайте `.env` в корне проекта:

```env
# Server
NODE_ENV=development
PORT=3001

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/your_db

# JWT
JWT_SECRET=your_super_secret_jwt_key_here
REFRESH_SECRET=your_super_secret_refresh_key_here

# Bitrix24 Integration
BITRIX24_CLIENT_ID=local.xxxxxxxxxx.xxxxxxxx
BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
BITRIX24_REDIRECT_URI=https://your-ngrok-url.ngrok.io/bitrix24/callback

# CORS
CLIENT_ORIGIN=http://localhost:3000
```

#### 2.3 Настройка ngrok для локальной разработки

Bitrix24 требует HTTPS. Используйте ngrok:

```bash
# Установка (если еще не установлен)
# Windows: choco install ngrok
# macOS: brew install ngrok
# Linux: snap install ngrok

# Запуск
ngrok http 3001

# Вы получите URL вида:
# https://abc123def456.ngrok.io -> http://localhost:3001
```

**Обновите URL в настройках приложения Bitrix24:**
```
https://abc123def456.ngrok.io/bitrix24/install
https://abc123def456.ngrok.io/bitrix24/index
https://abc123def456.ngrok.io/bitrix24/app
```

---

## Backend реализация

### Структура файлов

```
server/
├── index.ts                  # Точка входа
├── server.ts                 # Основной Express сервер
├── database.ts               # Подключение к PostgreSQL
└── bitrix24/
    ├── config.ts             # Конфигурация Bitrix24
    ├── storage.ts            # Хранилище токенов
    ├── routes.ts             # Маршруты установки и открытия
    ├── permissions.ts        # API управления правами
    └── api.ts                # Интеграция с REST API Bitrix24
```

### 1. Конфигурация (config.ts)

```typescript
/**
 * server/bitrix24/config.ts
 * Конфигурация для интеграции с Битрикс24
 */

export const BITRIX24_CONFIG = {
  // Client ID приложения Битрикс24
  CLIENT_ID: process.env.BITRIX24_CLIENT_ID || '',

  // Client Secret приложения Битрикс24
  CLIENT_SECRET: process.env.BITRIX24_CLIENT_SECRET || '',

  // URL для OAuth callback
  REDIRECT_URI: process.env.BITRIX24_REDIRECT_URI || 'http://localhost:3001/bitrix24/callback',

  // OAuth endpoints Битрикс24
  OAUTH_URL: 'https://oauth.bitrix.info/oauth/token/',

  // Проверка, настроено ли приложение
  isConfigured(): boolean {
    return !!(this.CLIENT_ID && this.CLIENT_SECRET);
  }
};
```

### 2. Хранилище токенов (storage.ts)

```typescript
/**
 * server/bitrix24/storage.ts
 * Хранилище токенов Битрикс24
 */

export interface Bitrix24Tokens {
  domain: string;
  access_token: string;
  refresh_token: string;
  expires_at: number;
  application_token?: string;
  member_id?: string;
  client_endpoint?: string;
}

// In-memory хранилище (для разработки)
const tokensStore = new Map<string, Bitrix24Tokens>();

/**
 * Сохранить токены для портала
 */
export const saveTokens = (domain: string, tokens: Bitrix24Tokens): void => {
  tokensStore.set(domain, {
    ...tokens,
    domain
  });
};

/**
 * Получить токены для портала
 */
export const getTokens = (domain: string): Bitrix24Tokens | undefined => {
  return tokensStore.get(domain);
};

/**
 * Удалить токены для портала
 */
export const deleteTokens = (domain: string): boolean => {
  return tokensStore.delete(domain);
};

/**
 * Проверить, истекли ли токены
 */
export const isTokenExpired = (tokens: Bitrix24Tokens): boolean => {
  return Date.now() >= tokens.expires_at;
};

/**
 * Получить все сохраненные домены
 */
export const getAllDomains = (): string[] => {
  return Array.from(tokensStore.keys());
};

/**
 * Очистить все токены (для тестирования)
 */
export const clearAllTokens = (): void => {
  tokensStore.clear();
};
```

**⚠️ Важно для production:** Замените in-memory хранилище на PostgreSQL или Redis!

### 3. Маршруты установки (routes.ts)

```typescript
/**
 * server/bitrix24/routes.ts
 * API маршруты для интеграции с Битрикс24
 */

import express, { Request, Response } from 'express';
import { saveTokens, getTokens } from './storage';
import { getDb } from '../database';
import path from 'path';

const router = express.Router();

/**
 * Добавить первого администратора при установке приложения
 */
const addInitialAdmin = async (domain: string, accessToken: string) => {
  try {
    // Получаем текущего пользователя через REST API
    const userResponse = await fetch(`https://${domain}/rest/user.current?auth=${accessToken}`);
    const userData = await userResponse.json() as any;

    if (userData.error) {
      return;
    }

    const currentUser = userData.result;
    const userId = currentUser.ID;
    const userName = `${currentUser.LAST_NAME} ${currentUser.NAME}`;

    const db = await getDb();

    // Проверяем, есть ли уже администраторы для этого портала
    const existing = await db.query(
      'SELECT COUNT(*) FROM bitrix24_permissions WHERE domain = $1',
      [domain]
    );

    if (Number(existing.rows[0].count) === 0) {
      // Добавляем первого администратора (того кто установил приложение)
      await db.query(
        'INSERT INTO bitrix24_permissions (domain, user_id, user_name, role, createdat, createdby) VALUES ($1, $2, $3, $4, $5, $6)',
        [domain, userId, userName, 'admin', new Date().toISOString(), userId]
      );
    }
  } catch (error) {
    // Handle error silently
  }
};

/**
 * Универсальный обработчик установки приложения
 * Обрабатывает данные из query (GET) или body (POST)
 */
const handleInstall = async (req: Request, res: Response) => {
  try {
    // Битрикс24 может отправлять данные через GET (query) или POST (body)
    const params = { ...req.query, ...req.body };

    const { event, PLACEMENT } = params;

    // Обработка установки через событие ONAPPINSTALL
    if (event === 'ONAPPINSTALL' && params.auth) {
      const auth = params.auth as any;

      if (typeof auth === 'object' && auth.domain && auth.access_token) {
        const tokens = {
          domain: auth.domain,
          access_token: auth.access_token,
          refresh_token: auth.refresh_token || '',
          expires_at: Date.now() + (parseInt(auth.expires_in || '3600') * 1000),
          member_id: auth.member_id || '',
          client_endpoint: `https://${auth.domain}/rest/`
        };

        saveTokens(auth.domain, tokens);

        // Добавляем установщика как первого администратора
        await addInitialAdmin(auth.domain, auth.access_token);

        return res.send(`
          <!DOCTYPE html>
          <html>
            <head>
              <meta charset="UTF-8">
              <title>Установка приложения</title>
              <script src="//api.bitrix24.com/api/v1/"></script>
            </head>
            <body>
              <script>
                BX24.init(function() {
                  BX24.installFinish();
                });
              </script>
              <h2>Приложение успешно установлено!</h2>
              <p>Теперь вы можете использовать приложение из меню Битрикс24.</p>
            </body>
          </html>
        `);
      }
    }

    // Обработка установки через PLACEMENT
    if (PLACEMENT === 'DEFAULT') {
      const domain = params.DOMAIN as string;
      const authId = params.AUTH_ID as string;
      const refreshId = params.REFRESH_ID as string;
      const expires = params.AUTH_EXPIRES as string;
      const memberId = params.member_id as string;

      if (domain && authId) {
        const tokens = {
          domain,
          access_token: authId,
          refresh_token: refreshId || '',
          expires_at: Date.now() + (parseInt(expires || '3600') * 1000),
          member_id: memberId || '',
          client_endpoint: `https://${domain}/rest/`
        };

        saveTokens(domain, tokens);

        // Добавляем установщика как первого администратора
        await addInitialAdmin(domain, authId);

        return res.send(`
          <!DOCTYPE html>
          <html>
            <head>
              <meta charset="UTF-8">
              <title>Установка приложения</title>
              <script src="//api.bitrix24.com/api/v1/"></script>
            </head>
            <body>
              <script>
                BX24.init(function() {
                  BX24.installFinish();
                });
              </script>
              <h2>Приложение успешно установлено!</h2>
            </body>
          </html>
        `);
      }
    }

    // Если параметры не подошли
    res.status(400).send(`
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <title>Ошибка установки</title>
        </head>
        <body>
          <h2>Ошибка установки приложения</h2>
          <p>Не удалось получить данные авторизации от Битрикс24.</p>
        </body>
      </html>
    `);

  } catch (error: any) {
    res.status(500).send(`
      <!DOCTYPE html>
      <html>
        <head><meta charset="UTF-8"><title>Ошибка</title></head>
        <body>
          <h2>Ошибка при установке приложения</h2>
          <p>${error.message}</p>
        </body>
      </html>
    `);
  }
};

/**
 * Обработчик установки приложения (GET и POST)
 */
router.get('/install', handleInstall);
router.post('/install', handleInstall);

/**
 * Универсальный обработчик первого открытия приложения
 */
const handleIndex = async (req: Request, res: Response) => {
  try {
    const params = { ...req.query, ...req.body };

    const domain = params.DOMAIN as string;
    const authId = params.AUTH_ID as string;
    const refreshId = params.REFRESH_ID as string;
    const expires = params.AUTH_EXPIRES as string;
    const memberId = params.member_id as string;

    // Сохранить токены если они есть
    if (domain && authId) {
      const tokens = {
        domain,
        access_token: authId,
        refresh_token: refreshId || '',
        expires_at: Date.now() + (parseInt(expires || '3600') * 1000),
        member_id: memberId || '',
        client_endpoint: `https://${domain}/rest/`
      };

      saveTokens(domain, tokens);

      // Добавляем первого администратора если его еще нет
      await addInitialAdmin(domain, authId);
    }

    // Перенаправить на встраиваемое приложение
    const redirectParams = new URLSearchParams({
      domain: domain || '',
      auth: authId || '',
      member_id: memberId || ''
    });

    res.redirect(`/bitrix24/app?${redirectParams.toString()}`);

  } catch (error: any) {
    res.status(500).send('Ошибка при открытии приложения');
  }
};

/**
 * Обработчик первого открытия приложения (GET и POST)
 */
router.get('/index', handleIndex);
router.post('/index', handleIndex);

/**
 * Страница встраиваемого приложения
 * Отдает React приложение
 */
router.get('/app', (req: Request, res: Response) => {
  try {
    const buildPath = path.join(__dirname, '../../build/index.html');
    res.sendFile(buildPath);
  } catch (error: any) {
    res.status(500).send(`
      <!DOCTYPE html>
      <html>
        <head><meta charset="UTF-8"><title>Ошибка</title></head>
        <body>
          <h2>Приложение не собрано</h2>
          <p>Запустите: npm run build</p>
        </body>
      </html>
    `);
  }
});

export default router;
```

### 4. Подключение маршрутов в server.ts

```typescript
/**
 * server/server.ts (фрагмент)
 */

import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import bitrix24Routes from './bitrix24/routes';
import bitrix24PermissionsRoutes from './bitrix24/permissions';

const app = express();

// Настройка Helmet для работы с Bitrix24 iframe
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      ...helmet.contentSecurityPolicy.getDefaultDirectives(),
      "script-src": ["'self'", "'unsafe-inline'", "api.bitrix24.com", "*.bitrix24.ru", "*.bitrix24.com"],
      "connect-src": ["'self'", "*.bitrix24.ru", "*.bitrix24.com", "*.bitrix24.ua", "*.bitrix24.eu"],
      "frame-ancestors": ["'self'", "*.bitrix24.ru", "*.bitrix24.com", "*.bitrix24.ua", "*.bitrix24.eu"],
    },
  },
  frameguard: false // Отключаем X-Frame-Options
}));

// CORS для Bitrix24
app.use(cors({
  origin: (origin, callback) => {
    // Разрешаем все домены Bitrix24
    if (!origin || origin.includes('bitrix24')) {
      return callback(null, true);
    }

    // Разрешаем локальную разработку
    if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
      return callback(null, true);
    }

    callback(new Error('Not allowed by CORS'));
  },
  credentials: true
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Подключаем маршруты Bitrix24
app.use('/bitrix24', bitrix24Routes);
app.use('/api/bitrix24/permissions', bitrix24PermissionsRoutes);

// Статические файлы для production
if (process.env.NODE_ENV === 'production') {
  app.use(express.static('build'));
}

app.listen(3001, () => {
  console.log('Server running on port 3001');
});
```

---

## Frontend реализация

### Структура файлов

```
src/
├── App.tsx                           # Главный роутинг
├── Bitrix24App.tsx                   # Компонент для работы в Bitrix24
├── contexts/
│   ├── Bitrix24Context.tsx           # Контекст пользователя Bitrix24
│   └── ToastContext.tsx              # Уведомления
└── components/
    ├── Bitrix24AdminWrapper.tsx      # Обертка админки для Bitrix24
    └── Bitrix24PermissionsManager.tsx # Управление правами
```

### 1. TypeScript типы для Bitrix24 SDK

```typescript
/**
 * src/types.ts (добавьте эти типы)
 */

declare global {
  interface Window {
    BX24?: {
      init: (callback: () => void) => void;
      getAuth: () => {
        access_token: string;
        domain: string;
        expires: number;
        expires_in: number;
        member_id: string;
        refresh_token: string;
        scope: string;
        status: string;
        user_id: number;
      };
      callMethod: (method: string, params: any, callback: (result: any) => void) => void;
      fitWindow: () => void;
      resizeWindow: (width: number, height: number) => void;
      closeApplication: () => void;
      installFinish: () => void;
    };
  }
}

export {};
```

### 2. Контекст Bitrix24 (Bitrix24Context.tsx)

```typescript
/**
 * src/contexts/Bitrix24Context.tsx
 * Контекст для хранения данных пользователя Bitrix24
 */

import React, { createContext, useContext, ReactNode } from 'react';

interface Bitrix24User {
  id: string;
  name: string;
  lastName: string;
  fullName: string;
}

interface Bitrix24ContextType {
  user: Bitrix24User | null;
  isInBitrix24: boolean;
}

const Bitrix24Context = createContext<Bitrix24ContextType>({
  user: null,
  isInBitrix24: false
});

export const useBitrix24 = () => useContext(Bitrix24Context);

interface Bitrix24ProviderProps {
  children: ReactNode;
  user: Bitrix24User | null;
}

export const Bitrix24Provider: React.FC<Bitrix24ProviderProps> = ({ children, user }) => {
  return (
    <Bitrix24Context.Provider value={{ user, isInBitrix24: !!user }}>
      {children}
    </Bitrix24Context.Provider>
  );
};
```

### 3. Главный компонент Bitrix24 (Bitrix24App.tsx)

```typescript
/**
 * src/Bitrix24App.tsx
 * Компонент для работы приложения внутри Битрикс24
 */

import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Bitrix24Provider } from './contexts/Bitrix24Context';

function Bitrix24App() {
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string>('');
  const [userRole, setUserRole] = useState<string | null>(null);
  const [bitrixUser, setBitrixUser] = useState<any>(null);

  // Проверка прав пользователя через API
  const checkUserPermissions = async (domain: string) => {
    try {
      // Получаем текущего пользователя через API Bitrix24
      const currentUser: any = await new Promise((resolve, reject) => {
        window.BX24.callMethod('user.current', {}, (result: any) => {
          if (result.error()) {
            reject(result.error());
          } else {
            resolve(result.data());
          }
        });
      });

      const userId = currentUser.ID;
      const userName = `${currentUser.LAST_NAME} ${currentUser.NAME}`;

      // Сохраняем данные пользователя
      setBitrixUser({
        id: currentUser.ID,
        name: currentUser.NAME,
        lastName: currentUser.LAST_NAME,
        fullName: userName
      });

      // Проверяем права пользователя
      const response = await fetch(
        `/api/bitrix24/permissions/check?domain=${encodeURIComponent(domain)}&user_id=${encodeURIComponent(userId)}`
      );
      const data = await response.json();

      if (data.hasPermission && (data.role === 'admin' || data.role === 'observer')) {
        setUserRole(data.role);

        // Получаем JWT токен для работы с backend API
        const authResponse = await fetch('/api/bitrix24/permissions/auth', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            domain: domain,
            user_id: userId,
            user_name: userName
          })
        });

        if (authResponse.ok) {
          const authData = await authResponse.json();
          localStorage.setItem('accessToken', authData.accessToken);
          localStorage.setItem('user', JSON.stringify(authData.user));
        }
      } else {
        // Обычный пользователь без прав администратора
        setUserRole(null);
        localStorage.removeItem('accessToken');
        localStorage.removeItem('user');
      }

      setIsInitialized(true);

      // Подстраиваем размер iframe под содержимое
      window.BX24.fitWindow();

    } catch (error) {
      setUserRole(null);
      setIsInitialized(true);
    }
  };

  useEffect(() => {
    // Загрузка Bitrix24 JS SDK
    const loadBitrix24SDK = () => {
      if (window.BX24) {
        initBitrix24();
        return;
      }

      const script = document.createElement('script');
      script.src = '//api.bitrix24.com/api/v1/';
      script.async = true;

      script.onload = () => {
        initBitrix24();
      };

      script.onerror = () => {
        setError('Не удалось загрузить Bitrix24 SDK');
      };

      document.head.appendChild(script);
    };

    // Инициализация Bitrix24
    const initBitrix24 = () => {
      if (!window.BX24) {
        setError('Bitrix24 SDK не доступен');
        return;
      }

      try {
        window.BX24.init(() => {
          const auth = window.BX24.getAuth();
          checkUserPermissions(auth.domain);
        });
      } catch (err: any) {
        setError('Ошибка инициализации Bitrix24: ' + err.message);
      }
    };

    loadBitrix24SDK();
  }, []);

  // Автоматическая подстройка размера при изменении содержимого
  useEffect(() => {
    if (isInitialized && window.BX24) {
      let timeoutId: NodeJS.Timeout;
      const debouncedFitWindow = () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          if (window.BX24) {
            window.BX24.fitWindow();
          }
        }, 300);
      };

      const resizeObserver = new ResizeObserver(debouncedFitWindow);
      const mainContainer = document.querySelector('#root > div');
      if (mainContainer) {
        resizeObserver.observe(mainContainer as Element);
      }

      return () => {
        clearTimeout(timeoutId);
        resizeObserver.disconnect();
      };
    }
  }, [isInitialized]);

  // Показываем ошибку
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Ошибка</h2>
          <p className="text-gray-700">{error}</p>
        </div>
      </div>
    );
  }

  // Показываем загрузку
  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-700 text-center">Загрузка приложения...</p>
        </div>
      </div>
    );
  }

  // Если пользователь с правами - показываем админку
  if (userRole === 'admin' || userRole === 'observer') {
    return (
      <div>
        <h1>Admin Dashboard</h1>
        <p>Role: {userRole}</p>
        {/* Ваш админ-интерфейс */}
      </div>
    );
  }

  // Для обычного пользователя
  return (
    <Bitrix24Provider user={bitrixUser}>
      <Routes>
        <Route path="app" element={<div>Your App Content</div>} />
        <Route path="*" element={<Navigate to="app" replace />} />
      </Routes>
    </Bitrix24Provider>
  );
}

export default Bitrix24App;
```

### 4. Роутинг в App.tsx

```typescript
/**
 * src/App.tsx
 * Главный роутинг приложения
 */

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Bitrix24App from './Bitrix24App';
import HomePage from './HomePage'; // Standalone режим

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Маршруты для Bitrix24 */}
        <Route path="/bitrix24/*" element={<Bitrix24App />} />

        {/* Standalone режим */}
        <Route path="/" element={<HomePage />} />
        <Route path="/admin" element={<div>Admin Panel (Standalone)</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

---

## База данных

### Создание таблицы прав доступа

```sql
/**
 * Таблица для управления правами пользователей Bitrix24
 */

CREATE TABLE IF NOT EXISTS bitrix24_permissions (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,           -- Домен портала (например, mycompany.bitrix24.ru)
    user_id VARCHAR(50) NOT NULL,           -- ID пользователя в Bitrix24
    user_name VARCHAR(255),                 -- ФИО пользователя
    role VARCHAR(50) NOT NULL,              -- Роль: 'admin' или 'observer'
    createdat TIMESTAMP DEFAULT NOW(),      -- Дата добавления прав
    createdby VARCHAR(50),                  -- ID пользователя, который выдал права

    CONSTRAINT unique_domain_user UNIQUE (domain, user_id)
);

-- Индекс для быстрого поиска по домену и user_id
CREATE INDEX idx_bitrix24_permissions_domain_user
ON bitrix24_permissions(domain, user_id);

-- Индекс для поиска по домену
CREATE INDEX idx_bitrix24_permissions_domain
ON bitrix24_permissions(domain);
```

### (Опционально) Таблица для хранения токенов в PostgreSQL

```sql
/**
 * Таблица для хранения OAuth токенов Bitrix24
 * Рекомендуется для production вместо in-memory хранилища
 */

CREATE TABLE IF NOT EXISTS bitrix24_tokens (
    domain VARCHAR(255) PRIMARY KEY,        -- Домен портала
    access_token TEXT NOT NULL,             -- OAuth access token
    refresh_token TEXT NOT NULL,            -- OAuth refresh token
    expires_at BIGINT NOT NULL,             -- Время истечения токена (Unix timestamp)
    member_id VARCHAR(255),                 -- ID установки приложения
    client_endpoint TEXT,                   -- REST API endpoint
    updated_at TIMESTAMP DEFAULT NOW()      -- Время последнего обновления
);

-- Индекс для очистки истекших токенов
CREATE INDEX idx_bitrix24_tokens_expires
ON bitrix24_tokens(expires_at);
```

### Миграция storage.ts на PostgreSQL

```typescript
/**
 * server/bitrix24/storage.ts (PostgreSQL версия)
 */

import { getDb } from '../database';

export interface Bitrix24Tokens {
  domain: string;
  access_token: string;
  refresh_token: string;
  expires_at: number;
  application_token?: string;
  member_id?: string;
  client_endpoint?: string;
}

/**
 * Сохранить токены для портала
 */
export const saveTokens = async (domain: string, tokens: Bitrix24Tokens): Promise<void> => {
  const db = await getDb();

  await db.query(`
    INSERT INTO bitrix24_tokens (domain, access_token, refresh_token, expires_at, member_id, client_endpoint, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, NOW())
    ON CONFLICT (domain)
    DO UPDATE SET
      access_token = EXCLUDED.access_token,
      refresh_token = EXCLUDED.refresh_token,
      expires_at = EXCLUDED.expires_at,
      member_id = EXCLUDED.member_id,
      client_endpoint = EXCLUDED.client_endpoint,
      updated_at = NOW()
  `, [domain, tokens.access_token, tokens.refresh_token, tokens.expires_at, tokens.member_id, tokens.client_endpoint]);
};

/**
 * Получить токены для портала
 */
export const getTokens = async (domain: string): Promise<Bitrix24Tokens | undefined> => {
  const db = await getDb();

  const result = await db.query(
    'SELECT * FROM bitrix24_tokens WHERE domain = $1',
    [domain]
  );

  if (result.rows.length === 0) {
    return undefined;
  }

  return result.rows[0] as Bitrix24Tokens;
};

/**
 * Проверить, истекли ли токены
 */
export const isTokenExpired = (tokens: Bitrix24Tokens): boolean => {
  return Date.now() >= tokens.expires_at;
};
```

---

## Системы прав доступа

### API для управления правами (permissions.ts)

```typescript
/**
 * server/bitrix24/permissions.ts
 * API для управления правами пользователей Битрикс24
 */

import express, { Request, Response } from 'express';
import { getDb } from '../database';
import jwt from 'jsonwebtoken';

const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET || 'supersecretkey';
const REFRESH_SECRET = process.env.REFRESH_SECRET || 'refreshsecretkey';
const ACCESS_TOKEN_EXPIRES = '15m';
const REFRESH_TOKEN_EXPIRES = '7d';

/**
 * Проверка прав пользователя
 * GET /api/bitrix24/permissions/check?domain=xxx&user_id=yyy
 */
router.get('/check', async (req: Request, res: Response) => {
  try {
    const { domain, user_id } = req.query;

    if (!domain || !user_id) {
      return res.status(400).json({ error: 'Domain and user_id are required' });
    }

    const db = await getDb();
    const result = await db.query(
      'SELECT role FROM bitrix24_permissions WHERE domain = $1 AND user_id = $2',
      [domain, user_id]
    );

    if (result.rows.length === 0) {
      return res.json({ hasPermission: false, role: null });
    }

    res.json({
      hasPermission: true,
      role: result.rows[0].role
    });

  } catch (error: any) {
    res.status(500).json({ error: 'Failed to check permissions' });
  }
});

/**
 * Получить список пользователей с правами для портала
 * GET /api/bitrix24/permissions/list?domain=xxx
 */
router.get('/list', async (req: Request, res: Response) => {
  try {
    const { domain } = req.query;

    if (!domain) {
      return res.status(400).json({ error: 'Domain is required' });
    }

    const db = await getDb();
    const result = await db.query(
      'SELECT id, user_id, user_name, role, createdat, createdby FROM bitrix24_permissions WHERE domain = $1 ORDER BY createdat DESC',
      [domain]
    );

    res.json({ users: result.rows });

  } catch (error: any) {
    res.status(500).json({ error: 'Failed to get permissions list' });
  }
});

/**
 * Добавить права пользователю
 * POST /api/bitrix24/permissions/add
 * Body: { domain, user_id, user_name, role, created_by }
 */
router.post('/add', async (req: Request, res: Response) => {
  try {
    const { domain, user_id, user_name, role, created_by } = req.body;

    if (!domain || !user_id || !role) {
      return res.status(400).json({ error: 'Domain, user_id, and role are required' });
    }

    // Validate role
    if (!['admin', 'observer'].includes(role)) {
      return res.status(400).json({ error: 'Role must be admin or observer' });
    }

    const db = await getDb();

    // Check if user already has permissions
    const existing = await db.query(
      'SELECT id FROM bitrix24_permissions WHERE domain = $1 AND user_id = $2',
      [domain, user_id]
    );

    if (existing.rows.length > 0) {
      // Update existing permission
      await db.query(
        'UPDATE bitrix24_permissions SET role = $1, user_name = $2 WHERE domain = $3 AND user_id = $4',
        [role, user_name, domain, user_id]
      );

      return res.json({ message: 'Permission updated successfully' });
    }

    // Insert new permission
    await db.query(
      'INSERT INTO bitrix24_permissions (domain, user_id, user_name, role, createdat, createdby) VALUES ($1, $2, $3, $4, $5, $6)',
      [domain, user_id, user_name, role, new Date().toISOString(), created_by]
    );

    res.json({ message: 'Permission added successfully' });

  } catch (error: any) {
    res.status(500).json({ error: 'Failed to add permission' });
  }
});

/**
 * Удалить права пользователя
 * DELETE /api/bitrix24/permissions/remove
 * Body: { domain, user_id }
 */
router.delete('/remove', async (req: Request, res: Response) => {
  try {
    const { domain, user_id } = req.body;

    if (!domain || !user_id) {
      return res.status(400).json({ error: 'Domain and user_id are required' });
    }

    const db = await getDb();
    await db.query(
      'DELETE FROM bitrix24_permissions WHERE domain = $1 AND user_id = $2',
      [domain, user_id]
    );

    res.json({ message: 'Permission removed successfully' });

  } catch (error: any) {
    res.status(500).json({ error: 'Failed to remove permission' });
  }
});

/**
 * Получить JWT токены для Bitrix24 пользователя
 * POST /api/bitrix24/permissions/auth
 * Body: { domain, user_id, user_name }
 */
router.post('/auth', async (req: Request, res: Response) => {
  try {
    const { domain, user_id, user_name } = req.body;

    if (!domain || !user_id) {
      return res.status(400).json({ error: 'Domain and user_id are required' });
    }

    const db = await getDb();
    const result = await db.query(
      'SELECT role FROM bitrix24_permissions WHERE domain = $1 AND user_id = $2',
      [domain, user_id]
    );

    if (result.rows.length === 0) {
      return res.status(403).json({ error: 'User does not have permissions' });
    }

    const role = result.rows[0].role;

    // Генерируем JWT токены
    const accessToken = jwt.sign(
      { id: user_id, username: user_name, role },
      JWT_SECRET,
      { expiresIn: ACCESS_TOKEN_EXPIRES }
    );

    const refreshToken = jwt.sign(
      { id: user_id, username: user_name, role },
      REFRESH_SECRET,
      { expiresIn: REFRESH_TOKEN_EXPIRES }
    );

    // Устанавливаем refresh токен в httpOnly cookie
    res.cookie('refreshToken', refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000 // 7 дней
    });

    res.json({
      accessToken,
      user: {
        id: user_id,
        username: user_name,
        role
      }
    });

  } catch (error: any) {
    res.status(500).json({ error: 'Failed to authenticate' });
  }
});

export default router;
```

### Логика разграничения доступа

**Роли:**
1. **admin** - полный доступ (управление сессиями, пользователями, экспорт данных, управление правами)
2. **observer** - только просмотр (результаты дегустаций, статистика)
3. **обычный пользователь** - участие в дегустациях (без доступа к админке)

**Реализация на Frontend:**
```typescript
// Пример проверки прав
if (userRole === 'admin') {
  // Показать кнопки управления
} else if (userRole === 'observer') {
  // Показать только просмотр
} else {
  // Показать форму дегустации
}
```

---

## Тестирование и отладка

### 1. Проверка токенов (dev режим)

```bash
# Посмотреть все сохраненные токены
curl http://localhost:3001/bitrix24/api/debug/tokens

# Проверить статус токена для портала
curl "http://localhost:3001/bitrix24/api/status?domain=mycompany.bitrix24.ru"
```

### 2. Тестирование установки

**Шаги:**
1. Откройте приложение в Bitrix24: **Приложения** → **Мои приложения**
2. Нажмите **Установить**
3. Проверьте browser console на наличие ошибок
4. Проверьте backend логи: `console.log('[Bitrix24] Install request:', params)`

### 3. Проверка работы SDK

В browser console:
```javascript
// Проверить, загружен ли SDK
console.log(window.BX24);

// Получить данные авторизации
BX24.getAuth();

// Получить текущего пользователя
BX24.callMethod('user.current', {}, (result) => {
  console.log(result.data());
});
```

### 4. Типичные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `BX24 is not defined` | SDK не загрузился | Проверьте `<script src="//api.bitrix24.com/api/v1/">` |
| `CORS error` | Неправильная настройка CORS | Добавьте домены Bitrix24 в allowed origins |
| `Cannot GET /bitrix24/app` | Build не создан | Выполните `npm run build` |
| `Refused to display in a frame` | X-Frame-Options блокирует iframe | Настройте Helmet: `frameguard: false` |
| `Tokens expired` | Токены истекли | Реализуйте refresh token механизм |
| `User not found` | Нет прав в БД | Добавьте пользователя через permissions API |

---

## Production Deployment

### 1. Подготовка к деплою

**Checklist:**
- [ ] Собрать frontend: `npm run build`
- [ ] Настроить переменные окружения (.env)
- [ ] Мигрировать token storage на PostgreSQL/Redis
- [ ] Настроить HTTPS (обязательно!)
- [ ] Обновить URL в настройках Bitrix24 приложения
- [ ] Настроить CORS для production доменов
- [ ] Удалить debug endpoints (`/api/debug/tokens`)

### 2. Переменные окружения для production

```env
NODE_ENV=production
PORT=3001

DATABASE_URL=postgresql://user:password@db-host:5432/production_db

JWT_SECRET=your_super_secure_jwt_secret_key_here_min_32_chars
REFRESH_SECRET=your_super_secure_refresh_secret_key_here_min_32_chars

BITRIX24_CLIENT_ID=local.xxxxxxxxxx.xxxxxxxx
BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
BITRIX24_REDIRECT_URI=https://your-domain.com/bitrix24/callback

CLIENT_ORIGIN=https://your-domain.com
```

### 3. Настройка HTTPS

**Используйте Let's Encrypt:**
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

**Или настройте nginx как reverse proxy:**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # Для Bitrix24 iframe
        add_header X-Frame-Options "ALLOW-FROM https://*.bitrix24.ru";
    }
}
```

### 4. Docker deployment (опционально)

```dockerfile
# Dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 3001

CMD ["node", "server/index.js"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "3001:3001"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:password@db:5432/appdb
      - JWT_SECRET=${JWT_SECRET}
      - REFRESH_SECRET=${REFRESH_SECRET}
      - BITRIX24_CLIENT_ID=${BITRIX24_CLIENT_ID}
      - BITRIX24_CLIENT_SECRET=${BITRIX24_CLIENT_SECRET}
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 5. Обновление настроек в Bitrix24

Замените ngrok URL на production домен:
```
Обработчик установки: https://your-domain.com/bitrix24/install
Обработчик первого открытия: https://your-domain.com/bitrix24/index
URL встраивания: https://your-domain.com/bitrix24/app
```

---

## Типичные проблемы и решения

### Проблема 1: Iframe не отображается

**Симптомы:**
- Белый экран в Bitrix24
- Ошибка в console: "Refused to display in a frame"

**Решение:**
```typescript
// server.ts
app.use(helmet({
  frameguard: false, // Отключить X-Frame-Options
  contentSecurityPolicy: {
    directives: {
      "frame-ancestors": ["'self'", "*.bitrix24.ru", "*.bitrix24.com"],
    },
  },
}));
```

### Проблема 2: CORS ошибки

**Симптомы:**
- "Access to fetch blocked by CORS policy"
- Network errors в DevTools

**Решение:**
```typescript
app.use(cors({
  origin: (origin, callback) => {
    // Разрешаем все домены Bitrix24
    if (!origin || origin.includes('bitrix24')) {
      return callback(null, true);
    }
    callback(new Error('Not allowed by CORS'));
  },
  credentials: true
}));
```

### Проблема 3: Токены теряются при перезапуске

**Симптомы:**
- После перезапуска сервера нужно переустанавливать приложение
- "Приложение не установлено"

**Решение:**
Мигрируйте на PostgreSQL storage (см. раздел "База данных")

### Проблема 4: BX24.fitWindow() не работает

**Симптомы:**
- Появляются scrollbars в iframe
- Контент обрезается

**Решение:**
```typescript
// Используйте ResizeObserver для автоматической подстройки
useEffect(() => {
  const resizeObserver = new ResizeObserver(() => {
    if (window.BX24) {
      window.BX24.fitWindow();
    }
  });

  const container = document.querySelector('#root > div');
  if (container) {
    resizeObserver.observe(container);
  }

  return () => resizeObserver.disconnect();
}, []);
```

### Проблема 5: Не получается получить данные пользователя

**Симптомы:**
- `user.current` возвращает ошибку
- Нет прав на вызов метода

**Решение:**
Добавьте scope `user` в настройках приложения Bitrix24

---

## Дополнительные возможности

### 1. Получение списка пользователей

```typescript
// server/bitrix24/api.ts
router.get('/users', async (req: Request, res: Response) => {
  const { domain } = req.query;
  const tokens = getTokens(domain as string);

  if (!tokens) {
    return res.status(401).json({ error: 'No tokens' });
  }

  const response = await fetch(
    `https://${domain}/rest/user.get?auth=${tokens.access_token}`
  );
  const data = await response.json();

  res.json({ users: data.result });
});
```

### 2. Уведомления в Bitrix24

```typescript
// Отправка уведомления пользователю
const sendNotification = async (domain: string, userId: string, message: string) => {
  const tokens = getTokens(domain);

  await fetch(`https://${domain}/rest/im.notify?auth=${tokens.access_token}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      to: userId,
      message: message,
      type: 'SYSTEM'
    })
  });
};
```

### 3. Интеграция с CRM

```typescript
// Создание лида в CRM
const createLead = async (domain: string, leadData: any) => {
  const tokens = getTokens(domain);

  await fetch(`https://${domain}/rest/crm.lead.add?auth=${tokens.access_token}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields: leadData })
  });
};
```

---

## Полезные ссылки

**Официальная документация:**
- [Bitrix24 REST API](https://dev.1c-bitrix.ru/rest_help/)
- [Bitrix24 JS SDK](https://dev.1c-bitrix.ru/rest_help/js_library/index.php)
- [OAuth 2.0 в Bitrix24](https://dev.1c-bitrix.ru/rest_help/general/auth.php)
- [Примеры приложений](https://dev.1c-bitrix.ru/rest_help/application_embedding/)

**Инструменты:**
- [ngrok](https://ngrok.com/) - Туннель для локальной разработки
- [Postman](https://www.postman.com/) - Тестирование REST API
- [VS Code REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)

---

## Чеклист для AI-ассистента

При помощи разработчику в интеграции с Bitrix24, убедитесь что:

- [ ] Создан `.env` файл с CLIENT_ID и CLIENT_SECRET
- [ ] Настроен ngrok для локальной разработки
- [ ] Созданы все необходимые файлы backend (config.ts, storage.ts, routes.ts, permissions.ts)
- [ ] Подключены маршруты в server.ts
- [ ] Настроены Helmet и CORS для работы с iframe
- [ ] Создана таблица bitrix24_permissions в PostgreSQL
- [ ] Реализован Bitrix24App.tsx с загрузкой SDK
- [ ] Добавлены TypeScript типы для window.BX24
- [ ] Настроена система прав (admin/observer/user)
- [ ] Реализован auto-resize iframe через BX24.fitWindow()
- [ ] Протестирована установка приложения
- [ ] Протестировано открытие приложения
- [ ] Проверена работа permissions API
- [ ] Подготовлен production build

---

## Заключение

Эта инструкция покрывает основные аспекты интеграции React/Node.js приложения с Bitrix24.

**Ключевые моменты:**
1. **HTTPS обязателен** для интеграции с Bitrix24
2. **Токены должны храниться безопасно** (PostgreSQL/Redis в production)
3. **Используйте BX24.fitWindow()** для автоматической подстройки размера iframe
4. **Настройте CORS и Helmet** для работы с iframe
5. **Реализуйте систему прав** для разграничения доступа
6. **Тестируйте локально через ngrok** перед деплоем

При возникновении проблем обращайтесь к официальной документации Bitrix24 и проверяйте browser console + backend логи.

**Версия документации:** 1.0
**Последнее обновление:** 2025-01-11
**Поддерживаемые версии Bitrix24:** Cloud и On-Premise
