import sqlite3
from contextlib import closing
from datetime import datetime
from config import DB_NAME

PERIOD = ("month", "week")
FREQUENCY = ("ежедневно", "еженедельно", "ежемесячно")


# Метод создания нового юзера.  У нового юзера из ТГ достается его telegram id,
# и записывается в таблицу users как users.id
# (где users - название таблицы, id - название столбца)
# также, функция datetime.now().strftime('%Y-%m-%d') записывает дату создания записи
# о пользователе в таблицу users в столбец creation_date
# по умолчанию статус active = 1 (столбец users.active)
def init_user(user_id):  # где user_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO user (id, creation_date) VALUES (?, ?)",
                (user_id, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()


# Добавление привычки в таблицу, вводим вручную 5 предопределенных привычек
# надо продумать, как грамматически описывать новые привычки в зависимости от способа вывода в ТГ
# например name = "Пить воду", description = "Необходимо пить воду для поддержания водного баланса в организме"
# тогда в ТГ выводим "Вы выбрали привычку: {habit.name}. Она важна, потому что {habit.description}"
def init_habit(name, description):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO habit ( name, description) VALUES (?, ?)",
                (name, description))
    conn.commit()
    conn.close()


# Метод присваивания привычки юзеру.В таблицу user_habit записывается user_id юзера -
# id юзера из ТГ user_id = message.chat.id,
# habit_id - habit.id привычки из таблицы habit,
# Значения frequency_name (ежедневно, еженедельно, ежемесячно) и
# frequency_count (количество повторений привычки за период)
# должны быть заданы юзером в ТГ

def assign_habit(user_id, habit_id, frequency_name, frequency_count):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Проверяем существует ли уже такая запись и её статус
    cur.execute("""
        SELECT active FROM user_habit 
        WHERE user_id = ? AND habit_id = ?
        """, (user_id, habit_id))
    result = cur.fetchone()

    if result is None:
        # Добавляем новую запись, если она не существует
        cur.execute("""
            INSERT INTO user_habit (user_id, habit_id, frequency_name, frequency_count) 
            VALUES (?, ?, ?, ?)
            """, (user_id, habit_id, frequency_name, frequency_count))
    elif result[0] == 0:
        # Обновляем существующую неактивную запись
        cur.execute("""
            UPDATE user_habit 
            SET active = 1, frequency_name = ?, frequency_count = ?
            WHERE user_id = ? AND habit_id = ?
            """, (frequency_name, frequency_count, user_id, habit_id))

    # Получаем имя привычки для сообщения пользователю
    cur.execute("SELECT name FROM habit WHERE id = ?", (habit_id,))
    habit_name = cur.fetchone()[0]

    # Определение правильного склонения слова "раз"
    if frequency_count == 1:
        count_word = "раз"
    elif 2 <= frequency_count % 10 <= 4 and (frequency_count % 100 < 10 or frequency_count % 100 > 20):
        count_word = "раза"
    else:
        count_word = "раз"

    # Формирование текста в зависимости от периодичности
    frequency_text = {
        "ежедневно": "в день",
        "еженедельно": "в неделю",
        "ежемесячно": "в месяц"
    }.get(frequency_name, "в неопределённый период")

    message_text = f"Вы добавили себе привычку '{habit_name}', которую хотите выполнять {frequency_count} {count_word} {frequency_text}."

    conn.commit()
    conn.close()
    return message_text


def list_habits():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM habit")
    habits = cur.fetchall()
    print(f"Fetched habits: {habits}")
    message_text = ""
    for habit in habits:
        message_text += f"{habit[0]}. {habit[1]}: {habit[2]}\n"
    conn.close()
    print(f"Returning message: {message_text}")
    return message_text


# Запрос для получения названия и описания всех активных привычек пользователя
# Входной параметр id юзера из ТГ: user_id = message.chat.id
# сначала метод достает все активные привычки пользователя
# (столбцы habit.name и habit.description) из таблицы user_habit,
# и записывает данные в список habits,
# затем проверяется, если список пуст, то выводим сообщение об этом:
# "У Вас нет подключенных привычек"
# если список не пуст, то циклом выводим сообщением ТГ привычки, каждая с новой строки


def habit_status(user_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT habit.name, habit.description, user_habit.frequency_name, user_habit.frequency_count
            FROM habit 
            INNER JOIN user_habit ON user_habit.habit_id = habit.id
            WHERE user_habit.user_id = ? AND user_habit.active = 1
        ''', (user_id,))

        habits = cur.fetchall()

        if not habits:  # если список активных привычек пуст
            return None

        output_dictionary = {}  # Инициализация пустого словаря для вывода
        for habit in habits:
            output_dictionary[habit[0]] = {
                'description': habit[1],
                'frequency': habit[2],
                'count': habit[3]
            }
        return output_dictionary
    finally:
        conn.close()


# Метод редактирования привычки - возможность изменения периодичночти frequency_name
# и количества повторений привычки за период frequency_count.
# Входные параметры id юзера из ТГ: user_id = message.chat.id,
# habit_id = id привычки из таблицы habit
# frequency_name (ежедневно, еженедельно, ежемесячно) вводит пользователь в ТГ
# frequency_count (количество повторений привычки за период) вводит пользователь в ТГ

def edit_habit(user_id, habit_id, frequency_name: FREQUENCY, frequency_count):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_habit SET frequency_name = ?, frequency_count = ?, active = 1 WHERE user_id = ? AND habit_id = ?",
        (frequency_name, frequency_count, user_id, habit_id))
    cur.execute("SELECT name FROM habit WHERE id = ?", (habit_id,))
    habit_name = cur.fetchone()[0]
    message_text = f"Вы изменили параметры привычки {habit_name} на {frequency_name}, {frequency_count} раз за период"
    conn.commit()
    conn.close()
    return message_text


# Метод удаления привычки - меняет столбец user_habit.active на 0
# и количества повторений привычки за период frequency_count.
# Входные параметры id юзера из ТГ: user_id = message.chat.id,
# habit_id = id привычки из таблицы habit

def delete_habit(user_id, habit_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("  UPDATE user_habit SET active = 0 "
                "WHERE user_id = ? AND habit_id = ?",
                (user_id, habit_id))
    cur.execute("SELECT name FROM habit WHERE id = ?", (habit_id,))
    habit_name = cur.fetchone()[0]
    output_message = f"Вы удалили привычку {habit_name}"
    conn.commit()
    conn.close()
    return output_message


# cur.execute('''
# UPDATE user_habit
# SET frequency_count = 10
# WHERE user_id = 1 AND habit_id = 2
# ''')


# Функция для отметки привычки

# ????????????????????????? Вопрос для FE - по умолчанию mark_count увеличивается на 1, то есть человек,
# который уже попил воду 2 раза из 3 нужных должен два раза зайти и отметить
# выполненной привычку. Это неудобно, если он вспомнил об отметке позже.
# Для этого мы можем задать количество отмечаний count,
# чтобы отметить сразу несколько выполнений, но тогда нужен соответствующий функционал в FE???????????????????????????

# Принцип работы функции: из таблицы user_habit_history достаем user_habit_history.id
# (просто порядковый номер записи о выполнении привычки) и
# переменную count - то, сколько раз привычка уже была отмечена
# и записываем эти данные в переменную result.
# если нет записи в таблице user_habit_history, мы ее создаем, по умолчанию параметр count = 1
# (но его можно изменить, если просто прописать ему значение).
# Если запись есть, то мы увеличиваем count на frequency_count на величину count (по умолчанию count = 1)
# Также, входные параметры id юзера из ТГ: user_id = message.chat.id,
# # habit_id = id привычки из таблицы habit.

# Замечание: если привычка была отмечена достаточно раз, то при повторном вызове функции
# будет выведено сообщение об этом: "Вы уже выполняли эту привычку достаточно раз",
# но если она выполнена недостаточно раз: 2 раза из 3,
# то теоретически пользователь может добавить еще 2 выполнения.
# Сейчас он получает об этом сообщение и не может добавить еще 2 выполнения.
# Стоит ли ограничивать перевыполнение нормы?


def mark_habit(user_id, habit_id, mark_date=datetime.now().date().strftime('%Y-%m-%d'), count=1):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
        # Проверяем наличие записи для данной привычки, пользователя и даты
        cur.execute('''
            SELECT id, mark_count FROM user_habit_history
            WHERE user_id = ? AND habit_id = ? AND mark_date = ?
        ''', (user_id, habit_id, mark_date))
        result = cur.fetchone()

        if result:
            # Если запись найдена, увеличиваем mark_count
            user_habit_history_id, current_count = result
            new_count = current_count + count
            cur.execute('''
                UPDATE user_habit_history
                SET mark_count = ?
                WHERE id = ?
            ''', (new_count, user_habit_history_id))
        else:
            # Если записи нет, добавляем новую
            cur.execute('''
                INSERT INTO user_habit_history (user_id, habit_id, mark_date, mark_count)
                VALUES (?, ?, ?, ?)
            ''', (user_id, habit_id, mark_date, count))

        conn.commit()
        return "OK"
    except Exception as e:
        return f"Произошла ошибка: {e}"
    finally:
        conn.close()


def db_connection():
    """Устанавливает соединение с базой данных."""
    return sqlite3.connect(DB_NAME)


def save_user_session(user_id, state, data):
    """ Сохранение данных сессии для пользователя """
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (user_id, state, last_interaction, data) 
            VALUES (?, ?, datetime('now'), ?)
            ''', (user_id, state, data))
        conn.commit()


def update_user_session(user_id, new_state, new_data):
    """ Обновление данных сессии для пользователя """
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sessions 
            SET state = ?, data = ?, last_interaction = datetime('now') 
            WHERE user_id = ?
            ''', (new_state, new_data, user_id))
        conn.commit()


def get_user_session(user_id):
    """ Получение данных сессии пользователя """
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data FROM sessions 
            WHERE user_id = ? 
            ORDER BY last_interaction DESC 
            LIMIT 1
            ''', (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None


def clear_user_session(user_id):
    """ Очистка данных сессии пользователя """
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM sessions 
            WHERE user_id = ?
            ''', (user_id,))
        conn.commit()


# Вспомогательная функция для определения склонения слова "раз"
def pluralize_count(n):
    if n % 10 == 1 and n % 100 != 11:
        return 'раз'
    elif n % 10 in [2, 3, 4] and n % 100 not in [12, 13, 14]:
        return 'раза'
    else:
        return 'раз'


# Вспомогательная функция для получения id привычки по её имени
def get_habit_id(habit_name):
    with closing(db_connection()) as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM habit WHERE name = ?', (habit_name,))
        result = cur.fetchone()  # Получаем первую запись из результатов запроса
        return result[0] if result else None


# Вспомогательная функция для получения имени привычки по её id
def get_habit_name(habit_id):
    with closing(db_connection()) as conn:
        cur = conn.cursor()
        cur.execute('SELECT name FROM habit WHERE id = ?', (habit_id,))
        result = cur.fetchone()  # Получаем первую запись из результатов запроса
        return result[0] if result else None


def get_all_active_users():
    with closing(db_connection()) as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM user WHERE active = 1")
        active_users = cur.fetchall()
        return active_users
