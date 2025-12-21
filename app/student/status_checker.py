import aiohttp
import re
import time
from typing import Dict, Optional, Tuple, List
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from app.logger import logger

# ID таблиц Google Sheets
SHEETS_CONFIG = {
    'material_help': {
        'id': '117QNcwjcsQ1ScFlTbOm6oOcPlXiMefR8rNgb15dA8Ms',
        'sheet_name': 'осень 2025',
        'range': 'A:F',
        'header_rows': 4
    },
    'travel_compensation': {
        'id': '18NYYQNvdJINpUXvoPH1_MHqldH4GfgdWEPrGqMkPtUU',
        'sheet_name': 'осень 2025',
        'range': 'A:E',
        'header_rows': 8
    },
    'housing_compensation': {
        'id': '1gmM_hJocQ1tfz5Pzu8SNhvt-s1u739sJgVKjFCXVETs',
        'sheet_name': 'осень 2025',
        'range': 'A:D',
        'header_rows': 4
    }
}

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"

CACHE_TTL = 3600
DEFAULT_CACHE_TTL = 1800


class CacheManager:
    """Менеджер кэша для Google Sheets данных"""
    
    def __init__(self, ttl: int = CACHE_TTL):
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Dict, float]] = {}
    
    def get(self, key: str) -> Optional[Dict]:
        """Получить значение из кэша если оно актуально"""
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Dict) -> None:
        """Сохранить значение в кэш с текущим временем"""
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        self._cache.clear()
    
    def invalidate(self, key: str) -> None:
        """Удалить конкретный ключ из кэша"""
        if key in self._cache:
            del self._cache[key]


class ApplicationStatusChecker:
    """Проверка статусов заявлений студентов в Google Sheets с кэшированием"""

    def __init__(self, credentials_path: str, cache_ttl: int = CACHE_TTL):
        self.credentials_path = credentials_path
        self._token = None
        self._token_expiry = 0
        self.cache = CacheManager(ttl=cache_ttl)

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        """Получить актуальный access token для Google API с кэшированием"""
        current_time = time.time()
        
        if self._token and current_time < self._token_expiry and not force_refresh:
            return self._token
        
        try:
            logger.info(f"Получаю новый токен из {self.credentials_path}")
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[DRIVE_SCOPE, SHEETS_SCOPE]
            )
            creds.refresh(Request())
            self._token = creds.token
            self._token_expiry = current_time + 3500
            logger.info(f"Токен получен успешно")
            return self._token
        except Exception as exc:
            logger.error(f"Ошибка получения access token: {exc}")
            raise

    async def get_all_statuses(
        self, 
        student_number: str, 
        last_name: str, 
        first_name: str,
        use_cache: bool = True
    ) -> Dict[str, Dict]:
        """Получить статусы по всем трём выплатам"""
        cache_key = f"{student_number}:{last_name}:{first_name}"
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.info(f"Вернул статусы из кэша для {student_number}")
                return cached
        
        results = {}
        
        try:
            token = await self._get_access_token()
            
            results['material_help'] = await self._check_material_help(
                token, student_number, last_name, first_name
            )
            
            results['travel_compensation'] = await self._check_travel_compensation(
                token, student_number, last_name, first_name
            )
            
            results['housing_compensation'] = await self._check_housing_compensation(
                token, last_name, first_name
            )
            
            if use_cache:
                self.cache.set(cache_key, results)
            
        except Exception as exc:
            logger.error(f"Ошибка при проверке статусов: {exc}")
            results = {
                'material_help': {'found': False, 'status': 'error', 'text': 'Ошибка загрузки'},
                'travel_compensation': {'found': False, 'status': 'error', 'text': 'Ошибка загрузки'},
                'housing_compensation': {'found': False, 'status': 'error', 'text': 'Ошибка загрузки'}
            }
        
        return results

    async def _get_sheet_data(
        self, 
        token: str, 
        sheet_id: str, 
        sheet_name: str, 
        range_str: str
    ) -> Tuple[List[List], Optional[Dict]]:
        """Получить данные из Google Sheets"""
        try:
            url = f"{SHEETS_API_URL}/{sheet_id}/values/{sheet_name}!{range_str}"
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        values = data.get('values', [])
                        return values, None
                    else:
                        text = await response.text()
                        logger.error(f"Ошибка API Google Sheets: {response.status}")
                        logger.error(f"Ответ: {text[:300]}")
                        return [], None
        except Exception as exc:
            logger.error(f"Ошибка получения данных из Sheets: {exc}")
            return [], None

    async def _check_material_help(
        self, 
        token: str, 
        student_number: str, 
        last_name: str, 
        first_name: str
    ) -> Dict:
        """Проверка статуса материальной помощи - СТРОГО ПО НОМЕРУ БИЛЕТА"""
        config = SHEETS_CONFIG['material_help']
        rows, _ = await self._get_sheet_data(token, config['id'], config['sheet_name'], config['range'])
        
        if not rows:
            return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}
        
        data_rows = rows[config['header_rows']:] if len(rows) > config['header_rows'] else []
        
        # СТРОГО ищем только по номеру студенческого билета (колонка 3, индекс 2)
        normalized_student_number = self._normalize_student_number(student_number)
        for idx, row in enumerate(data_rows):
            if len(row) >= 3:
                row_student_num = self._normalize_student_number(row[2] if len(row) > 2 else '')
                if row_student_num == normalized_student_number and row_student_num:  # Не пустая строка
                    return self._parse_material_help_row(row)
        
        # Не нашли по билету → заявление не подано
        return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}


    async def _check_travel_compensation(
        self, 
        token: str, 
        student_number: str, 
        last_name: str, 
        first_name: str
    ) -> Dict:
        """Проверка статуса компенсации проезда"""
        config = SHEETS_CONFIG['travel_compensation']
        rows, _ = await self._get_sheet_data(token, config['id'], config['sheet_name'], config['range'])
        
        if not rows:
            return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}
        
        data_rows = rows[config['header_rows']:] if len(rows) > config['header_rows'] else []
        
        for idx, row in enumerate(data_rows):
            if len(row) >= 2:
                row_student_num = self._normalize_student_number(row[1] if len(row) > 1 else '')
                if row_student_num == self._normalize_student_number(student_number):
                    return self._parse_travel_compensation_row(row)
        
        for idx, row in enumerate(data_rows):
            if len(row) >= 1:
                fio = row[0].strip()
                if last_name.lower() in fio.lower():
                    return self._parse_travel_compensation_row(row)
        
        return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}

    async def _check_housing_compensation(
        self, 
        token: str, 
        last_name: str, 
        first_name: str
    ) -> Dict:
        """Проверка статуса компенсации общежития"""
        config = SHEETS_CONFIG['housing_compensation']
        rows, _ = await self._get_sheet_data(token, config['id'], config['sheet_name'], config['range'])
        
        if not rows:
            return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}
        
        data_rows = rows[config['header_rows']:] if len(rows) > config['header_rows'] else []
        
        full_name_pattern = f"{last_name} {first_name[0]}."
        
        for idx, row in enumerate(data_rows):
            if len(row) >= 2:
                fio = row[1].strip()
                if full_name_pattern.lower() in fio.lower() or fio.lower() in full_name_pattern.lower():
                    return self._parse_housing_compensation_row(row)
        
        return {'found': False, 'status': 'not_submitted', 'text': 'Заявление не подано'}

    def _parse_material_help_row(self, row: List) -> Dict:
        """Парсинг строки материальной помощи
        Выводим значения колонок D и E (индексы 3 и 4)
        """
        if len(row) < 5:
            return {'found': True, 'status': 'unknown', 'text': 'Данные неполные'}
        
        # Берём содержимое из колонки D (индекс 3) и E (индекс 4)
        column_d = row[3].strip() if len(row) > 3 else ''
        column_e = row[4].strip() if len(row) > 4 else ''
        
        # Выводим оба значения
        text = ''
        if column_d:
            text += column_d
        if column_e:
            if text:
                text += f'\n{column_e}'
            else:
                text += column_e
        
        if not text:
            return {'found': True, 'status': 'pending', 'text': '⏳ На рассмотрении'}
        
        # Определяем иконку по содержимому
        combined_lower = (column_d + ' ' + column_e).lower()
        if any(word in combined_lower for word in ['одобрено', 'выплачено', 'выплачена', 'согласовано']):
            return {'found': True, 'status': 'approved', 'text': f'✅ {text}'}
        elif any(word in combined_lower for word in ['отклонено', 'не может', 'невозможно']):
            return {'found': True, 'status': 'rejected', 'text': f'❌ {text}'}
        
        return {'found': True, 'status': 'pending', 'text': f'ℹ️ {text}'}

    def _parse_travel_compensation_row(self, row: List) -> Dict:
        """Парсинг строки компенсации проезда
        Структура: [ФИО, № билета, № группы, статус, комментарий]
        """
        if len(row) < 4:
            return {'found': True, 'status': 'unknown', 'text': 'Данные неполные'}
        
        # Колонка 3 (индекс 3): что с заявлением (статус)
        status_code = row[3].strip() if len(row) > 3 else ''
        # Колонка 4 (индекс 4): Комментарии
        comment = row[4].strip() if len(row) > 4 else ''
        
        # Определяем статус
        status_lower = status_code.lower()
        
        # Числовой код (1 = одобрено, 2 = нужны документы)
        if status_code == '1':
            text = '✅ Одобрено'
            if comment and comment != '.':
                text += f'\n💬 {comment}'
            return {'found': True, 'status': 'approved', 'text': text}
        
        elif status_code == '2':
            text = '⏳ Нужны документы'
            if comment and comment != '.':
                text += f'\n💬 {comment}'
            return {'found': True, 'status': 'pending', 'text': text}
        
        # Текстовые варианты отклонения
        elif any(word in status_lower for word in ['отклонено', 'не может', 'нет подтверждения', 'невозможно', 'недействительно']):
            text = f'❌ {status_code}'
            if comment and comment != '.':
                text += f'\n💬 {comment}'
            return {'found': True, 'status': 'rejected', 'text': text}
        
        # Текстовые варианты одобрения
        elif any(word in status_lower for word in ['одобрено', 'выплачено', 'согласовано']):
            text = f'✅ {status_code}'
            if comment and comment != '.':
                text += f'\n💬 {comment}'
            return {'found': True, 'status': 'approved', 'text': text}
        
        # Если не смогли определить - выводим как есть
        text = f'ℹ️ {status_code}'
        if comment and comment != '.':
            text += f'\n💬 {comment}'
        return {'found': True, 'status': 'pending', 'text': text}

    def _parse_housing_compensation_row(self, row: List) -> Dict:
        """Парсинг строки компенсации общежития - берём статус прямо из таблицы"""
        if len(row) < 2:
            return {'found': True, 'status': 'unknown', 'text': 'Данные неполные'}
        
        # Берём содержимое из 4-й колонки (индекс 3) - комментарий/статус
        status_text = row[3].strip() if len(row) > 3 else ''
        
        if not status_text:
            return {'found': True, 'status': 'approved', 'text': '✅ Принято'}
        
        # Определяем иконку по содержимому
        status_lower = status_text.lower()
        if any(word in status_lower for word in ['допущена', 'принято', 'одобрено', 'согласовано']):
            return {'found': True, 'status': 'approved', 'text': f'✅ {status_text}'}
        elif any(word in status_lower for word in ['отклонено', 'не может', 'невозможно']):
            return {'found': True, 'status': 'rejected', 'text': f'❌ {status_text}'}
        
        return {'found': True, 'status': 'pending', 'text': f'ℹ️ {status_text}'}

    @staticmethod
    def _normalize_student_number(num: str) -> str:
        """Нормализация номера студенческого для сравнения"""
        return re.sub(r'\s+', '', num.upper().strip())


# Singleton экземпляр
_checker = None


async def get_status_checker(credentials_path: str = "source/creds.json") -> ApplicationStatusChecker:
    """Получить или создать экземпляр проверки статусов"""
    global _checker
    if _checker is None:
        _checker = ApplicationStatusChecker(credentials_path)
    return _checker


async def check_student_applications(
    student_number: str,
    last_name: str,
    first_name: str,
    credentials_path: str = "source/creds.json",
    use_cache: bool = True
) -> Dict[str, Dict]:
    """
    Удобная функция для проверки всех статусов студента
    """
    checker = await get_status_checker(credentials_path)
    return await checker.get_all_statuses(
        student_number, last_name, first_name, use_cache=use_cache
    )


async def clear_all_status_cache() -> None:
    """Очистить весь кэш статусов"""
    global _checker
    if _checker is not None:
        _checker.cache.clear()
        logger.info("✅ Весь кэш статусов очищен")
