import sqlite3
import os
from config import DB_NAME
import logging

from datetime import datetime, timedelta


def fetch_progress_data(user_id, period):
    conn = sqlite3.connect(DB_NAME)
    try:
        cur = conn.cursor()
        # Определяем начальную и конечную даты для периода
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7 if period == 'week' else 30)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        cur.execute('''
            SELECT habit.name, COALESCE(SUM(user_habit_history.mark_count), 0), user_habit.frequency_count
            FROM habit
            JOIN user_habit ON habit.id = user_habit.habit_id
            LEFT JOIN user_habit_history ON user_habit.habit_id = user_habit_history.habit_id
            WHERE user_habit.user_id = ? AND user_habit.active = 1
            AND (user_habit_history.mark_date >= ? OR user_habit_history.mark_date IS NULL)
            GROUP BY habit.id
        ''', (user_id, start_date_str))

        results = cur.fetchall()
        progress_data = []

        if not results:
            logging.info(f"No progress data found for user {user_id}, period {period}")
            return None, start_date, end_date

        for habit_name, total_done, frequency_count in results:
            target = frequency_count if frequency_count is not None else 0
            percentage_done = min((total_done / target) * 100, 100) if target != 0 else 0
            progress_data.append({
                'habit_name': habit_name,
                'percentage_done': percentage_done,
                'total_done': total_done,
                'target': target
            })

        logging.info(f"Fetched progress data for user {user_id}: {progress_data}")
        return progress_data, start_date, end_date

    except sqlite3.Error as e:
        logging.error(f"Database error in fetch_progress_data for user {user_id}: {e}", exc_info=True)
        return None, start_date, end_date
    finally:
        conn.close()


def plot_progress_chart(user_id, period):
    import matplotlib
    matplotlib.use('Agg')  # Устанавливаем неинтерактивный бэкенд
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np
    import os
    import logging
    data, start_date, end_date = fetch_progress_data(user_id, period)

    if data is None:
        logging.info(f"No data to plot for user {user_id}, period {period}")
        return None

    # Извлекаем данные из списка словарей
    names = [item['habit_name'] for item in data]
    percentages = [item['percentage_done'] for item in data]

    if not names:
        logging.info(f"No valid data to plot for user {user_id}, period {period}")
        return None

    fig, ax = plt.subplots(figsize=(10, max(5, len(names) * 0.8)))  # Увеличиваем высоту фигуры

    bar_height = 0.1  # Фиксированная ширина столбцов
    y_positions = np.arange(0.15, 0.15 + len(names) * 0.2, 0.2)[:len(names)]

    goals = ax.barh(y_positions, [100] * len(names), color='silver', label='Цель', height=bar_height)
    progress_bars = ax.barh(y_positions, percentages, color='darksalmon', label='Выполнено', height=bar_height)

    ax.set_yticks([y for y in y_positions])  # Центрируем названия привычек

    ax.invert_yaxis()  # Начинаем снизу
    ax.set_xlabel('Процент выполнения', color="dimgray", fontweight='bold')
    ax.set_title(
        f'Прогресс выполнения привычек за {"неделю" if period == "week" else "месяц"} с {start_date.strftime("%Y-%m-%d")} по {end_date.strftime("%Y-%m-%d")}',
        pad=20, color="dimgray", fontweight='bold', fontsize=14)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(20))
    legend = ax.legend(loc='upper right')  # Перемещаем легенду в правый верхний угол
    for text in legend.get_texts():
        text.set_color('dimgray')  # Изменяем цвет текста легенды
        text.set_fontweight('bold')

    # Добавляем вертикальные линии и меняем цвет осей
    major_ticks = np.arange(0, 101, 20)
    for mtick in major_ticks:
        ax.axvline(x=mtick, color='silver', linestyle='--', linewidth=0.5)  # Линии на основных тиках

    # Изменение цветов осей и тиков
    ax.spines['bottom'].set_color('silver')
    ax.spines['top'].set_color('silver')
    ax.spines['right'].set_color('silver')
    ax.spines['left'].set_color('silver')
    ax.tick_params(axis='both', colors='silver')  # Меняем цвет тиков

    ax.set_yticklabels(names, color="dimgray", fontweight='bold')  # Устанавливаем названия привычек

    # Расширяем ось X для дополнительного пространства
    ax.set_xlim(0, 100)
    # На оси У сверху последней привычки добавляется пространство в 0.5 единиц
    ax.set_ylim(0, y_positions[-1] + 0.5)

    # Добавляем текст внутри красного столбца прогресса
    for bar, percentage in zip(progress_bars, percentages):
        if f'{percentage:.1f}%' == '0.0%':
            x_position = max(bar.get_width(),
                             1)  # Используем минимальную ширину 1 для отображения текста внутри серого столбца
            ax.text(x_position, bar.get_y() + bar.get_height() / 2, f'{percentage:.1f}%', ha='left', va='center',
                    color='dimgrey',
                    fontweight='bold')
        else:
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f'{percentage:.1f}%', ha='right', va='center',
                    color='dimgrey', fontweight='bold')

    # Добавляем текст процентов внутри серых столбцов цели (всегда 100 процентов)
    for bar, goal, percentage in zip(goals, [100] * len(names), percentages):
        # Условие для добавления текста только если фактическое выполнение не 100%, иначе текст уже есть на красной полосе
        if f'{percentage:.1f}%' != '100.0%':
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f'{goal}%', ha='right', va='center',
                    color='dimgrey', fontweight='bold')
        # Редактируем края графика
        plt.subplots_adjust(top=0.85, bottom=0.15)  # Увеличиваем верхнюю и нижнюю границы графика

    # Сохраняем график
    save_path = os.path.join(os.path.dirname(__file__), 'saved_charts')

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    full_file_path = os.path.join(save_path, f'progress_chart_{period}_{user_id}.png')
    fig.savefig(full_file_path)  # Сохраняем график

    plt.close(fig)  # Закрываем фигуру после сохранения

    logging.info(f"Generated chart for user {user_id}, period {period}: {full_file_path}")
    return full_file_path


def get_file_path(chat_id, period):
    file_path = plot_progress_chart(user_id=chat_id, period=period)
    if not file_path:
        return
    else:
        return file_path


def delete_file(file_path):
    try:
        os.remove(file_path)
    except OSError:
        pass
