import sqlite3
from datetime import datetime, timedelta
from config import DB_NAME


def report(user_id, habit_id, period):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        today = datetime.now()

        # Определение начальной даты для периода
        if period == 'week':
            start_of_week = today - timedelta(days=today.weekday())  # Начало текущей недели (понедельник)
            start_date = start_of_week.strftime('%Y-%m-%d')
        elif period == 'month':
            start_of_month = today.replace(day=1)  # Начало текущего месяца
            start_date = start_of_month.strftime('%Y-%m-%d')

        # Завершающая дата — текущий день
        end_date = today.strftime('%Y-%m-%d')

        # Выборка данных из базы
        query = '''
                SELECT h.name, COUNT(*) as completion_count
                FROM user_habit_history uhh
                JOIN user_habit uh ON uh.habit_id = uhh.habit_id AND uh.user_id = uhh.user_id and uh.active = 1
                JOIN habit h ON h.id = uh.habit_id
                WHERE uhh.mark_date BETWEEN ? AND ? AND uh.user_id = ? AND uh.habit_id = ?
                GROUP BY uh.habit_id
            '''
        cur.execute(query, (start_date, end_date, user_id, habit_id))
        result = cur.fetchone()
    except sqlite3.DatabaseError as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        if conn:
            conn.close()

    # Формируем и возвращаем отчет
    if not result:
        return f"No records found for habit ID {habit_id} from {start_date} to {end_date}"
    else:
        habit_name, completion_count = result
        return {
            "Habit Name": habit_name,
            "Period Start": start_date,
            "Period End": end_date,
            "Completion Count": completion_count
        }
