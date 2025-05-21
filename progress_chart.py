from calendar import monthrange
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import sqlite3
from datetime import datetime, timedelta
import numpy as np
import os
from config import DB_NAME


def fetch_progress_data(user_id, period):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    today = datetime.now().date()

    if period == 'week':
        start_date = today - timedelta(days=today.weekday())  # Понедельник текущей недели
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = today.replace(day=1)  # Первый день текущего месяца
        end_date = today
        days_in_month = monthrange(today.year, today.month)[1]  # количество дней в месяце
        last_day_of_month = start_date.replace(day=days_in_month)  # Последний день текущего месяца

    cur.execute('''
        SELECT habit.id, habit.name, user_habit.frequency_name, user_habit.frequency_count, 
               IFNULL(SUM(user_habit_history.mark_count), 0) as total_done
        FROM habit 
        JOIN user_habit  ON habit.id = user_habit.habit_id
        LEFT JOIN user_habit_history ON habit.id = user_habit_history.habit_id AND user_habit_history.mark_date BETWEEN ? AND ?
        WHERE user_habit.active = 1 AND user_habit.user_id = ?
        GROUP BY habit.id
    ''', (start_date, end_date, user_id))

    habits = cur.fetchall()
    conn.close()

    # Проверяем, есть ли подключенные привычки
    if not habits:  # Если список привычек пуст
        return None

    results = {}
    for habit in habits:
        habit_id, name, freq_name, freq_count, total_done = habit
        if freq_name == 'ежедневно' and period == 'week':
            target = (end_date - start_date).days * freq_count
        elif freq_name == 'ежедневно' and period == 'month':
            target = ((last_day_of_month - start_date).days + 1) * freq_count
        elif freq_name == 'еженедельно' and period == 'week':
            target = freq_count
        elif freq_name == 'еженедельно' and period == 'month':
            target = 4 * freq_count  # Предполагаем 4 полные недели в месяце
        elif freq_name == 'ежемесячно':
            target = freq_count

        percentage_done = min((total_done / target) * 100, 100) if target != 0 else 0
        results[name] = {'percentage_done': percentage_done, 'total_done': total_done, 'target': target}

    return results, start_date, end_date


def plot_progress_chart(user_id, period):
    if fetch_progress_data(user_id, period) is None:
        return None
    data, start_date, end_date = fetch_progress_data(user_id, period)
    names = list(data.keys())
    percentages = [data[name]['percentage_done'] for name in names]

    fig, ax = plt.subplots(figsize=(10, max(5, len(names) * 0.8)))  # Увеличиваем высоту фигуры

    bar_height = 0.1  # Фиксированная ширина столбцов
    y_positions = np.arange(0.15, 0.15 + len(names) * 0.2, 0.2)[:len(names)]

    goals = ax.barh(y_positions, [100] * len(names), color='silver', label='Цель', height=bar_height)
    progress_bars = ax.barh(y_positions, percentages, color='darksalmon', label='Выполнено', height=bar_height)

    ax.set_yticks([y for y in y_positions])  # Центрируем названия привычек

    ax.invert_yaxis()  # Начинаем снизу
    ax.set_xlabel('Процент выполнения', color="dimgray", fontweight='bold')
    ax.set_title(
        f'Прогресс выполнения привычек за {"неделю" if period == "week" else "месяц"} с {start_date} по {end_date}',
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
    # Определяем относительный путь к папке для сохранения изображений
    save_path = os.path.join(os.path.dirname(__file__), 'saved_charts')

    # Если папка не существует, то создаем ее
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # Получаем полный путь к файлу
    full_file_path = os.path.join(save_path, f'progress_chart_{period}, {user_id}.png')
    fig.savefig(full_file_path)  # Сохраняем график

    plt.close(fig)  # Закрываем фигуру после сохранения, чтобы освободить память

    # plt.show() #Показываем график в консоли, если нужно проверить

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
