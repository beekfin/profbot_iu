-- Таблица ролей (студент, админ)
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    patronymic VARCHAR(255),
    group_name VARCHAR(50),
    student_number VARCHAR(50),
    bauman_login VARCHAR(100),
    phone VARCHAR(50),
    role_id INTEGER REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица новостей
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    image_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Категории рассылок (новости, мероприятия и т.д.)
CREATE TABLE IF NOT EXISTS mailing_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

-- Подписки пользователей на категории
CREATE TABLE IF NOT EXISTS mailing_subscriptions (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES mailing_categories(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, category_id)
);

-- Мероприятия
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Типы заявлений (документ, обращение, запись на мероприятие)
CREATE TABLE IF NOT EXISTS application_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

-- Статусы заявлений (на рассмотрении, одобрено, отклонено)
CREATE TABLE IF NOT EXISTS application_statuses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

-- Заявления (общая таблица для документов, обращений и записей)
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type_id INTEGER REFERENCES application_types(id),
    status_id INTEGER REFERENCES application_statuses(id),
    subject VARCHAR(255),
    description TEXT,
    file_id TEXT,           -- ID файла в Telegram (для фото/документов)
    admin_reply TEXT,       -- Ответ администратора
    related_event_id INTEGER REFERENCES events(id) ON DELETE SET NULL, -- Ссылка на мероприятие (если это запись)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Платежи профвзносов
CREATE TABLE IF NOT EXISTS fee_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(10, 2) DEFAULT 0,
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    method VARCHAR(50),
    receipt_file_id TEXT,   -- Фото чека
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
    comment TEXT
);

-- Инициализация базовых данных (Справочники)

-- Роли
INSERT INTO roles (code, name) VALUES ('student', 'Студент') ON CONFLICT (code) DO NOTHING;
INSERT INTO roles (code, name) VALUES ('admin', 'Администратор') ON CONFLICT (code) DO NOTHING;

-- Типы заявлений
INSERT INTO application_types (code, name) VALUES ('document', 'Документ') ON CONFLICT (code) DO NOTHING;
INSERT INTO application_types (code, name) VALUES ('appeal', 'Обращение') ON CONFLICT (code) DO NOTHING;
INSERT INTO application_types (code, name) VALUES ('event', 'Мероприятие') ON CONFLICT (code) DO NOTHING;

-- Статусы заявлений
INSERT INTO application_statuses (code, name) VALUES ('pending', 'На рассмотрении') ON CONFLICT (code) DO NOTHING;
INSERT INTO application_statuses (code, name) VALUES ('approved', 'Одобрено') ON CONFLICT (code) DO NOTHING;
INSERT INTO application_statuses (code, name) VALUES ('rejected', 'Отклонено') ON CONFLICT (code) DO NOTHING;
INSERT INTO application_statuses (code, name) VALUES ('answered', 'Отвечено') ON CONFLICT (code) DO NOTHING;

-- Категории рассылок
INSERT INTO mailing_categories (code, name) VALUES ('events', 'Мероприятия') ON CONFLICT (code) DO NOTHING;
INSERT INTO mailing_categories (code, name) VALUES ('payments', 'Выплаты') ON CONFLICT (code) DO NOTHING;
INSERT INTO mailing_categories (code, name) VALUES ('benefits', 'Льготы') ON CONFLICT (code) DO NOTHING;
INSERT INTO mailing_categories (code, name) VALUES ('contests', 'Конкурсы') ON CONFLICT (code) DO NOTHING;
INSERT INTO mailing_categories (code, name) VALUES ('mass', 'Массовые') ON CONFLICT (code) DO NOTHING;
