import sqlite3
from contextlib import closing
from datetime import datetime
from config import DB_NAME
import logging

PERIOD = ("month", "week")
FREQUENCY = ("Ежедневно", "Еженедельно", "Ежемесячно")


def init_user(user_id):  # где user_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO user (id, creation_date) VALUES (?, ?)",
                (user_id, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()


def init_habit(name, description):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO habit ( name, description) VALUES (?, ?)",
                (name, description))
    conn.commit()
    conn.close()


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

        if not habits:
            return None

        output_dictionary = {}
        for habit in habits:
            output_dictionary[habit[0]] = {
                'description': habit[1],
                'frequency': habit[2],
                'count': habit[3]
            }
        return output_dictionary
    finally:
        conn.close()


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


def mark_habit(user_id, habit_id, mark_date=datetime.now().date().strftime('%Y-%m-%d'), count=1):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
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
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (user_id, state, last_interaction, data) 
            VALUES (?, ?, datetime('now'), ?)
        ''', (user_id, state, data))
        conn.commit()
        logging.info(f"Saved session for user {user_id}: state={state}, data={data}")


def update_user_session(user_id, new_state, new_data):
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sessions 
            SET state = ?, data = ?, last_interaction = datetime('now') 
            WHERE user_id = ?
        ''', (new_state, new_data, user_id))
        conn.commit()
        logging.info(f"Updated session for user {user_id}: state={new_state}, data={new_data}")


def get_user_session(user_id):
    with closing(db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data FROM sessions 
            WHERE user_id = ? 
            ORDER BY last_interaction DESC 
            LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        logging.info(f"Fetched session for user {user_id}: {row[0] if row else None}")
        return row[0] if row else None


def assign_habit(user_id, habit_id, frequency_name, frequency_count):
    logging.info(f"Starting assign_habit for user {user_id}, habit_id={habit_id}")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT active FROM user_habit WHERE user_id = ? AND habit_id = ?", (user_id, habit_id))
    result = cur.fetchone()
    if result is None:
        cur.execute("""
            INSERT INTO user_habit (user_id, habit_id, frequency_name, frequency_count) 
            VALUES (?, ?, ?, ?)
        """, (user_id, habit_id, frequency_name, frequency_count))
    elif result[0] == 0:
        cur.execute("""
            UPDATE user_habit 
            SET active = 1, frequency_name = ?, frequency_count = ?
            WHERE user_id = ? AND habit_id = ?
        """, (frequency_name, frequency_count, user_id, habit_id))
    cur.execute("SELECT name FROM habit WHERE id = ?", (habit_id,))
    habit_name = cur.fetchone()[0]
    if frequency_count == 1:
        count_word = "раз"
    elif 2 <= frequency_count % 10 <= 4 and (frequency_count % 100 < 10 or frequency_count % 100 > 20):
        count_word = "раза"
    else:
        count_word = "раз"
    frequency_text = {
        "Ежедневно": "в день",
        "Еженедельно": "в неделю",
        "Ежемесячно": "в месяц"
    }.get(frequency_name, "в неопределённый период")
    message_text = f"Вы добавили себе привычку '{habit_name}', которую хотите выполнять {frequency_count} {count_word} {frequency_text}."
    conn.commit()
    conn.close()
    logging.info(
        f"Assigned habit for user {user_id}: habit_id={habit_id}, frequency={frequency_name}, count={frequency_count}")
    print(f"Completed assign_habit for user {user_id}, returning: {message_text}")
    return message_text


def clear_user_session(user_id):
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

