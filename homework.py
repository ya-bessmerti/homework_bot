import logging
import os
import time
import sys

import requests
import telegram




from dotenv import load_dotenv
from http import HTTPStatus

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

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
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
    except Exception as error:
        logger.error(f'Бот не отправил сообщение: {error}')


def get_api_answer(timestamp):
    """
    делает запрос к единственному эндпоинту API-сервиса. 
    В качестве параметра в функцию передается временная метка. 
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    time_index = timestamp or int(time.time())
    payload = {'from_date': time_index}
    response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    if response.status_code != HTTPStatus.OK:
        raise ReferenceError('Статус ответа API не OK')
    return response.json()


def check_response(response):
    """
    проверяет ответ API на соответствие документации.
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
            timestamp = response('current_date')
        except ReferenceError as error:
            message = parse_status(check_response(response))
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
