import logging
import os
import time
import sys

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """
    проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная
    окружения — продолжать работу бота нет смысла.
    """
    if all ([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def send_message(bot, message):
    """
    Отправляет сообщение в Telegram чат.
    Чат задан переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра: экземпляр класса Bot и
    строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Бот отправил сообщение "{message}"')
    except telegram.error.TelegramError as error:
        logger.error(f'Бот не отправил сообщение "{message}": {error}')


def get_api_answer(timestamp):
    """
    делает запрос к единственному эндпоинту API-сервиса. 
    В качестве параметра в функцию передается временная метка. 
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        raise ReferenceError('Статус ответа API не OK')
    return response.json()


def check_response(response):
    """
    проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    """
    if type(response) is not dict:
        raise TypeError('Ответ API отличен от словаря')
    try:
        list_works = response['homeworks']
    except KeyError:
        logger.error('Ошибка словаря по ключу homeworks')
        raise KeyError('Ошибка словаря по ключу homeworks')
    try:
        homework = list_works[0]
    except IndexError:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """
    извлекает из информации о конкретной домашней работе 
    статус этой работы. В качестве параметра функция 
    получает только один элемент из списка домашних работ. 
    В случае успеха, функция возвращает подготовленную 
    для отправки в Telegram строку, содержащую один из 
    вердиктов словаря HOMEWORK_VERDICTS.
    """
    if 'homework_name' not in homework:
        raise KeyError('Ключ homevork_name отсустсвует в homework')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус {homework_status} неизвестен')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения.'
            'Программа принудительно остановлена.'
        )
        raise SystemExit
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                message = 'На данный момент обновлений нет'
            else:
                message = parse_status(homework[0])
            timestamp = response.get('current_date')

            message = parse_status(check_response(response))
            if message != STATUS:
                send_message(bot, message)
                STATUS = message
            time.sleep(RETRY_PERIOD)
        except ReferenceError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
        except KeyError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
        except TypeError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
        finally:
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
