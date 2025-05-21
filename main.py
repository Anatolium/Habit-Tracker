import telebot
from progress_chart import *
from telebot import types
from config import BOT_TOKEN
from actions import *
from db import *
from report import report
import time
from datetime import datetime
import json

init_db()

init_habit("Чтение", "Читать книгу 30 минут в день")
init_habit("Спорт", "Заниматься спортом 3 раза в неделю")
init_habit("Медитация", "Практиковать медитацию 10 минут ежедневно")
init_habit("Вода", "Пить 2 литра воды в день")
init_habit("Ранний подъем", "Вставать в 7 утра ежедневно")

print("bot is being started", datetime.now())

bot = telebot.TeleBot(BOT_TOKEN)

start_message = 'Привет! Я научу тебя успешно нарабатывать полезные привычки. \n' \
                'Небольшие ежедневные победы приведут тебя к взятию трудных вершин!\n' \
                'Добавляй свою первую привычку, чтоб не забросить её через неделю, как всегда.'
help_message = 'Здесь будет список доступных команд и описание их функций.'
# Словарь кнопок
buttons_dict = {
    'menu': 'На главную',
    'status': 'Статус',
    'report': 'Отчеты',
    'edit_menu': 'Редактировать',
    'edit_habit': 'Изменить привычку',
    'new_habit': 'Добавить',
    'del_habit': 'Удалить',
    'mark_habit': 'Отметить V',
    'habits': 'Привычки',
    'chart': 'График'
}


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            bot.stop_polling()
            time.sleep(5)  # Дайте немного времени перед перезапуском
            # bot.polling(none_stop=True)
            # TODO вызвать стартовое меню handle_start()

    return wrapper


# Функция для создания inline клавиатуры
@error_handler
def create_inline_keyboard(button_keys):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=buttons_dict[key], callback_data=key) for key in button_keys if
               key in buttons_dict]
    keyboard.add(*buttons)
    return keyboard


def send_custom_message_to_all_active_users():
    active_users = get_all_active_users()
    menu_keyboard = create_inline_keyboard(['status', 'edit_habit', 'mark_habit'])

    for user_id_tuple in active_users:
        user_id = user_id_tuple[0]  # предполагается, что user_id это первый элемент кортежа
        try:
            habits_info = habit_status(user_id)
            if not habits_info:
                message_text = "У вас нет активных привычек. Начните добавлять привычки!"
            else:
                message_text = "Ваши текущие привычки:\n" + "\n".join([
                    f"{habit} - {info['description']} {info['frequency']}x в {info['frequency']} {pluralize_count(info['count'])}"
                    for habit, info in habits_info.items()
                ])

            bot.send_message(user_id, message_text, reply_markup=menu_keyboard)
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


# Обработчик для возврата в главное меню
@bot.callback_query_handler(func=lambda call: call.data == 'menu')
@error_handler
def handle_menu(call):
    keyboard = create_inline_keyboard(['status', 'edit_habit', 'mark_habit'])
    bot.send_message(call.message.chat.id, 'На главную', reply_markup=keyboard)


# Обработчик для вывода статуса текущих привычек
@bot.callback_query_handler(func=lambda call: call.data == 'status')
@error_handler
def handle_status(call):
    habits_info = habit_status(call.from_user.id)
    keyboard = create_inline_keyboard(['edit_menu', 'mark_habit', 'report', 'chart', 'menu'])

    if not habits_info:
        keyboard = create_inline_keyboard(['new_habit', 'menu'])
        bot.send_message(call.message.chat.id, 'Активных привычек нет, заведём?',
                         reply_markup=keyboard)
        return

    # Создание одной строки с описанием всех привычек
    respond_message = "\n".join([
        f"{habit} - {info['description']} {info['frequency']} {info['count']} {pluralize_count(info['count'])}"
        for habit, info in habits_info.items()
    ])
    bot.send_message(call.message.chat.id, f'Привычки, которые вы отслеживаете:\n\n{respond_message}',
                     reply_markup=keyboard)


# Обработчик для меню редактирования
@bot.callback_query_handler(func=lambda call: call.data == 'edit_menu')
@error_handler
def handle_edit_menu(call):
    keyboard = create_inline_keyboard(['edit_habit', 'new_habit', 'del_habit', 'menu'])
    bot.send_message(call.message.chat.id, 'Выберите действие', reply_markup=keyboard)


# Обработчик для вывода отчета
@bot.callback_query_handler(func=lambda call: call.data == 'report')
@error_handler
def handle_report(call):
    user_habits = habit_status(call.from_user.id)
    if not user_habits:
        bot.send_message(call.message.chat.id, 'У вас нет активных привычек для создания отчета.',
                         reply_markup=create_inline_keyboard(['menu']))
        return

    keyboard = types.InlineKeyboardMarkup()
    for habit_name, info in user_habits.items():
        # Проверяем, что habit_name является строкой и получаем habit_id
        if isinstance(habit_name, str):
            habit_id = get_habit_id(habit_name)
            if habit_id:
                keyboard.add(types.InlineKeyboardButton(text=habit_name, callback_data=f'report_select_{habit_id}'))
            else:
                print(f"Ошибка: ID привычки не найден для {habit_name}")
        else:
            print(f"Ошибка: название привычки не является строкой для {habit_name}")
    bot.send_message(call.message.chat.id, 'Выберите привычку для создания отчета:', reply_markup=keyboard)


# Обработчик для выбора привычки и запроса периода
@bot.callback_query_handler(func=lambda call: call.data.startswith('report_select_'))
@error_handler
def select_habit_for_report(call):
    habit_id = call.data.split('_')[2]
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='Неделя', callback_data=f'report_week_{habit_id}'))
    keyboard.add(types.InlineKeyboardButton(text='Месяц', callback_data=f'report_month_{habit_id}'))
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='menu'))
    bot.send_message(call.message.chat.id, 'Выберите период для отчета:', reply_markup=keyboard)


# Обработчик для генерации отчета
@bot.callback_query_handler(
    func=lambda call: call.data.startswith('report_week_') or call.data.startswith('report_month_'))
@error_handler
def generate_report(call):
    habit_id = int(call.data.split('_')[2])
    period = 'week' if 'week' in call.data else 'month'
    user_id = call.from_user.id
    report_result = report(user_id, habit_id, period)

    # Обработка ответа от функции report
    if isinstance(report_result, str):
        bot.send_message(call.message.chat.id, report_result)
    else:
        report_message = f"Привычка: {report_result['Habit Name']}\n" \
                         f"Период: с {report_result['Period Start']} по {report_result['Period End']}\n" \
                         f"Количество выполнений: {report_result['Completion Count']}"
        bot.send_message(call.message.chat.id, report_message, reply_markup=create_inline_keyboard(['menu']))


# Редактирование активной привычки
# Обработчик для вызова колбэка по изменению привычки
@bot.callback_query_handler(func=lambda call: call.data == 'edit_habit')
@error_handler
def handle_edit_habit(call):
    user_id = call.from_user.id  # Получаем ID пользователя, который инициировал вызов
    habits_info = habit_status(user_id)  # Получаем информацию о привычках пользователя
    if not habits_info:
        # Если у пользователя нет активных привычек, отправляем сообщение
        bot.send_message(call.message.chat.id, "У вас нет активных привычек для редактирования.",
                         reply_markup=create_inline_keyboard(['menu']))
        return

    keyboard = types.InlineKeyboardMarkup()  # Создаем клавиатуру для выбора привычки
    for habit, info in habits_info.items():
        # Для каждой привычки добавляем кнопку на клавиатуру
        keyboard.add(types.InlineKeyboardButton(text=f"{habit}", callback_data=f'edit_select_{habit}'))
    # Отправляем сообщение с клавиатурой для выбора привычки
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='menu'))
    bot.send_message(call.message.chat.id, "Выберите привычку для редактирования:", reply_markup=keyboard)


# Обработчик для выбора привычки к редактированию
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_select_'))
@error_handler
def select_habit_for_editing(call):
    habit_name = call.data.split('_')[2]
    habit_id = get_habit_id(habit_name)  # Получаем ID привычки по её названию
    if habit_id is None:
        bot.send_message(call.message.chat.id, "Привычка не найдена. Пожалуйста, проверьте данные.",
                         reply_markup=create_inline_keyboard(['menu']))
        return
    state = 'selecting_habit_for_edit'
    data = json.dumps({'habit_id': habit_id})
    save_user_session(call.from_user.id, state, data)
    keyboard = types.InlineKeyboardMarkup()
    periods = ["ежедневно", "еженедельно", "ежемесячно"]
    for period in periods:
        keyboard.add(types.InlineKeyboardButton(text=period, callback_data=f'edit_period_{period}_{habit_id}'))
    keyboard.add(types.InlineKeyboardButton(text='Отмена', callback_data='menu'))
    bot.send_message(call.message.chat.id, "Выберите новую периодичность привычки:", reply_markup=keyboard)


# Обработчик для выбора новой периодичности привычки
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_period_'))
@error_handler
def select_new_period(call):
    parts = call.data.split('_')  # Разбиваем данные вызова на части
    period = parts[2]  # Получаем выбранную периодичность
    habit_id = parts[3]  # Получаем ID привычки
    state = 'selecting_new_period'  # Устанавливаем новое состояние сессии пользователя
    new_data = json.dumps(
        {'frequency_name': period, 'habit_id': habit_id})  # Сериализуем новые данные о привычке в JSON
    update_user_session(call.from_user.id, state, new_data)  # Обновляем состояние сессии пользователя
    msg = "Введите новое количество выполнений для привычки (от 1 до 30):"  # Сообщение пользователю
    # Отправляем сообщение с запросом на ввод количества выполнений
    bot.send_message(call.message.chat.id, msg, reply_markup=types.ForceReply(selective=True))


# Обработчик для ввода нового количества выполнений
@bot.message_handler(func=lambda message: message.reply_to_message and message.reply_to_message.text.startswith(
    "Введите новое количество выполнений"))
@error_handler
def handle_repetition_count_input(message):
    raw_session_data = get_user_session(message.chat.id)
    if raw_session_data:
        try:
            session_data = json.loads(raw_session_data)
            repetition_count = int(message.text)
            if 1 <= repetition_count <= 30:
                # Вызываем функцию редактирования с полученными данными
                user_id = message.chat.id
                habit_id = session_data['habit_id']
                frequency_name = session_data['frequency_name']
                response = edit_habit(user_id, habit_id, frequency_name, repetition_count)
                bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(['menu']))
                clear_user_session(message.chat.id)
            else:
                bot.send_message(message.chat.id, "Введите число от 1 до 30.")
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректное число.")
    else:
        bot.send_message(message.chat.id, "Сессия не найдена или истекло время ожидания. Пожалуйста, начните заново.",
                         reply_markup=create_inline_keyboard(['menu']))


# Добавление новой привычки
# Обработчик для начала процесса добавления новой привычки
@bot.callback_query_handler(func=lambda call: call.data == 'new_habit')
@error_handler
def handle_new_habit(call):
    # Получаем список привычек для пользователя
    habits_list_str = list_habits()  # Функция возвращает строку с описаниями привычек
    # Предположим, что формат строки: "ID. Название: Описание"
    habits = [line.split('. ', 1) for line in habits_list_str.strip().split('\n') if line]
    keyboard = types.InlineKeyboardMarkup()
    for habit_info in habits:
        if len(habit_info) == 2:
            habit_id_with_dot, habit_desc = habit_info
            habit_id = habit_id_with_dot.split('.')[0]  # Удаление точки после ID
            habit_name = habit_desc.split(': ')[0]  # Извлекаем название привычки
            button_text = habit_name  # Используем название для подписи кнопки
            keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f'add_select_{habit_id.strip()}'))
        else:
            continue  # Пропустить записи, которые не соответствуют ожидаемому формату
    bot.send_message(call.message.chat.id, "Выберите привычку для добавления:", reply_markup=keyboard)


# Обработчик для выбора привычки и перехода к выбору периодичности
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_select_'))
@error_handler
def select_habit_for_addition(call):
    habit_id = call.data.split('_')[2]
    state = 'selecting_habit'  # Устанавливаем состояние сессии
    data = json.dumps({'habit_id': habit_id})  # Конвертируем данные в строку JSON
    save_user_session(call.from_user.id, state, data)
    keyboard = types.InlineKeyboardMarkup()
    periods = ["ежедневно", "еженедельно", "ежемесячно"]
    for period in periods:
        keyboard.add(types.InlineKeyboardButton(text=period, callback_data=f'add_period_{period}_{habit_id}'))
    keyboard.add(types.InlineKeyboardButton(text='Отмена', callback_data='menu'))
    bot.send_message(call.message.chat.id, "Выберите периодичность привычки:", reply_markup=keyboard)


# Обработчик для выбора периодичности и перехода к вводу количества выполнений
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_period_'))
@error_handler
def select_period(call):
    parts = call.data.split('_')
    if len(parts) < 4:
        bot.send_message(call.message.chat.id, "Произошла ошибка в данных. Пожалуйста, попробуйте ещё раз.")
        return
    period = parts[2]
    habit_id = '_'.join(parts[3:])  # Объединение оставшихся частей для сохранения целостности habit_id
    state = 'selecting_period'  # или другое актуальное состояние
    new_data = json.dumps({'frequency_name': period, 'habit_id': habit_id})
    # Обновляем сессию пользователя
    update_user_session(call.from_user.id, state, new_data)
    # Запрашиваем количество выполнений
    msg = "Введите количество выполнений для привычки (от 1 до 30):"
    bot.send_message(call.message.chat.id, msg, reply_markup=types.ForceReply(selective=True))


# Обработчик для текстового ввода количества выполнений
@bot.message_handler(func=lambda message: message.reply_to_message and message.reply_to_message.text.startswith(
    "Введите количество выполнений"))
@error_handler
def handle_repetition_count_input(message):
    raw_session_data = get_user_session(message.chat.id)
    if raw_session_data:
        try:
            session_data = json.loads(raw_session_data)  # Десериализация строки JSON в словарь
            repetition_count = int(message.text)
            if 1 <= repetition_count <= 30:
                response = assign_habit(message.chat.id, session_data['habit_id'], session_data['frequency_name'],
                                        repetition_count)
                bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(['menu']))
                clear_user_session(message.chat.id)
            else:
                bot.send_message(message.chat.id, "Введите число от 1 до 30.")
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректное число.")
    else:
        bot.send_message(message.chat.id, "Сессия не найдена или истекло время ожидания. Пожалуйста, начните заново.")


# Удаление привычки
# Обработчик для выбора удаления привычки
@bot.callback_query_handler(func=lambda call: call.data == 'del_habit')
@error_handler
def handle_del_habit(call):
    user_habits = habit_status(call.from_user.id)
    if not user_habits:
        bot.send_message(call.message.chat.id, 'У вас нет активных привычек.',
                         reply_markup=create_inline_keyboard(['menu']))
        return

    keyboard = types.InlineKeyboardMarkup()
    # Обновленная обработка вывода информации о привычке
    for habit_name, habit_info in user_habits.items():
        button_text = f"{habit_name}"
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data='del_' + habit_name))
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='menu'))
    bot.send_message(call.message.chat.id, 'Выберите привычку для удаления:', reply_markup=keyboard)


# Обработчик для удаления выбранной привычки
@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
@error_handler
def delete_selected_habit(call):
    habit_name = call.data.split('_')[1]
    habit_id = get_habit_id(habit_name)
    if habit_id:
        # Передаем user_id и habit_id в функцию удаления, получаем ответное сообщение
        response_message = delete_habit(call.from_user.id, habit_id)
        bot.send_message(call.message.chat.id, response_message, reply_markup=create_inline_keyboard(['menu']))
    else:
        # Сообщение об ошибке, если ID привычки не найден
        bot.send_message(call.message.chat.id, f"Ошибка: не удалось найти привычку '{habit_name}'.",
                         reply_markup=create_inline_keyboard(['menu']))


# Обработчик для выбора отметки привычки
@bot.callback_query_handler(func=lambda call: call.data == 'mark_habit')
@error_handler
def handle_mark_habit(call):
    habits_dict = habit_status(call.from_user.id)  # Получаем словарь активных привычек
    if habits_dict is None:
        keyboard = create_inline_keyboard(['status', 'new_habit', 'menu'])
        bot.send_message(call.message.chat.id, 'У вас пока нет активных привычек.', reply_markup=keyboard)
        return

    keyboard = types.InlineKeyboardMarkup()
    for habit_name, habit_info in habits_dict.items():
        habit_id = get_habit_id(habit_name)  # Получаем ID привычки по её названию
        button_text = f"{habit_name}"
        callback_data = f'mark_{habit_id}_{habit_name.strip()}'
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='menu'))
    bot.send_message(call.message.chat.id, 'Выберите привычку для отметки:', reply_markup=keyboard)


# Обработчик для отметки выбранной привычки
@bot.callback_query_handler(func=lambda call: call.data.startswith('mark_'))
@error_handler
def mark_selected_habit(call):
    # Разделяем callback_data для получения habit_id
    parts = call.data.split('_')
    habit_id = parts[1]  # Убеждаемся, что habit_id корректно извлечён без дополнительных символов

    # Получаем имя привычки из базы данных
    habit_name = get_habit_name(habit_id)  # Эта функция должна возвращать имя привычки по её ID

    # Проверяем, что имя привычки было успешно получено
    if habit_name:
        # Вызываем функцию для отметки привычки
        response = mark_habit(call.from_user.id, habit_id)

        # Обработка ответа от функции mark_habit
        if response == "OK":
            success_message = f"Привычка '{habit_name}' успешно отмечена как выполненная!"
            bot.send_message(call.message.chat.id, success_message, reply_markup=create_inline_keyboard(['menu']))
        else:
            error_message = "Извините, не смог отметить - что-то пошло не так."
            bot.send_message(call.message.chat.id, error_message, reply_markup=create_inline_keyboard(['menu']))
    else:
        error_message = "Не удалось получить название привычки. Пожалуйста, попробуйте ещё раз."
        bot.send_message(call.message.chat.id, error_message, reply_markup=create_inline_keyboard(['menu']))

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'habits')
@error_handler
def handle_habits(call):
    respond_message = list_habits()
    keyboard = create_inline_keyboard(['new_habit', 'edit_habit', 'del_habit', 'menu'])
    if not respond_message.strip():
        bot.send_message(call.message.chat.id,
                         "Список привычек пуст. Свяжитесь с администратором для добавления привычек.",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id, respond_message, reply_markup=keyboard)


# Отправка графика по требованию
@bot.callback_query_handler(func=lambda call: call.data == 'chart')
@error_handler
def handle_chart(call):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='Неделя', callback_data='chart_week'))
    keyboard.add(types.InlineKeyboardButton(text='Месяц', callback_data='chart_month'))
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='menu'))
    bot.send_message(call.message.chat.id, 'Выберите период для отображения графика:', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data in ['chart_week', 'chart_month'])
@error_handler
def send_selected_chart(call):
    period = 'week' if 'week' in call.data else 'month'
    file_path = get_file_path(call.message.chat.id, period)
    if file_path is None:
        bot.send_message(call.message.chat.id, "Нет данных для отображения графика.")
    else:
        keyboard = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(text='Назад', callback_data='menu')
        keyboard.add(back_button)

        with open(file_path, 'rb') as photo:
            bot.send_photo(call.message.chat.id, photo, reply_markup=keyboard)
        delete_file(file_path)  # Удаление файла после отправки

    bot.answer_callback_query(call.id)


# Обработчик для команды /start
@bot.message_handler(commands=['start'])
@error_handler
def handle_start(message):
    try:
        init_user(message.chat.id)
    except Exception as e:
        print(e)
    finally:
        keyboard = create_inline_keyboard(['habits', 'status', 'new_habit'])
        bot.send_message(message.chat.id, start_message, reply_markup=keyboard)


# Обработчик для команды /help
@bot.message_handler(commands=['help'])
@error_handler
def handle_help(message):
    keyboard = create_inline_keyboard(['status', 'habits', 'mark_habit'])
    bot.send_message(message.chat.id, help_message, reply_markup=keyboard)


# Отправка сообщения пользователю
@error_handler
def user_notify(user_id, message):
    bot.send_message(user_id, message)


# bot.polling(none_stop=True)
if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)
