import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exception import InvalidJSONTransform, SendMessedge

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """проверяет доступность переменных окружения.
    Если отсутствует хотя бы одна переменная окружения —
    продолжать работу бота нет смысла.
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    Чат задан переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра: экземпляр класса Bot и
    строку с текстом сообщения.
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except telegram.error.TelegramError as error:
        logging.error(f'Бот не отправил сообщение"{message}": {error}')
        raise SendMessedge(
            f'Бот не отправил сообщение"{message}": {error}'
        )


def get_api_answer(timestamp):
    """делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра в функцию передается временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.exceptions.RequestException:
        message = f'Ошибка при запросе к API: {response.status_code}'
        logging.error(message)
        raise requests.exceptions.RequestException(message)
    if response.status_code != HTTPStatus.OK:
        raise ReferenceError('Статус ответа API не OK')
    logging.info('Ответ на запрос к API: 200 OK')
    try:
        return response.json()
    except Exception as error:
        message = f'Сбой при переводе в формат json: {error}'
        logging.error(message)
        raise InvalidJSONTransform(message)    


def check_response(response):
    """проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    """
    if not isinstance(response, dict):
        raise TypeError('В ответе API нет словаря')
    if 'homeworks' not in response:
        raise KeyError('Ключа "homeworks" в словаре нет')
    if not isinstance(response['homeworks'], list):
        raise TypeError('По ключу "homeworks" не получен список')
    return response['homeworks']


def parse_status(homework):
    """извлекает статус домашней работы.
    В качестве параметра функция получает только один
    элемент из списка домашних работ. В случае успеха,
    функция возвращает подготовленную для отправки в
    Telegram строку, содержащую один из вердиктов
    словаря HOMEWORK_VERDICTS.
    """
    if 'homework_name' not in homework:
        raise KeyError('Ключ homevork_name отсустсвует в homework')
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует в homework')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус {homework_status} неизвестен')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'Отсутствует обязательная переменная окружения.'
            'Программа принудительно остановлена.'
        )
        raise SystemExit

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            logging.debug('Начало итерации, запрос к API')
            response = get_api_answer(timestamp)
            homework = check_response(response)
            logging.info('Список домашних работ получен')
            if not homework:
                logging.info('Новых заданий нет')
                send_message(bot, 'На данный момент обновлений нет')
            else:
                send_message(bot, parse_status(homework[0]))
                timestamp = response['current_date']
        except Exception as error:
            logging.error(error)
            send_message(bot, parse_status(check_response(response)))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        filename='program.log'
    )
    main()
