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
import logging

init_db()

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Проверка содержимого таблицы habit
def check_habits():
    conn = sqlite3.connect('habit_tracker.db')  # Изменено
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM habit")
    habits = cur.fetchall()
    print("Habits in DB after init:", habits)
    conn.close()


check_habits()  # Вызов для отладки

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

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}", exc_info=True)
            try:
                if args and hasattr(args[0], 'message'):
                    bot.send_message(
                        args[0].message.chat.id,
                        "Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.",
                        reply_markup=create_inline_keyboard(['menu'])
                    )
            except Exception as send_error:
                logging.error(f"Failed to send error message: {send_error}", exc_info=True)
            return None

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
    if not active_users:
        logging.info("No active users found for sending custom messages")
        return

    menu_keyboard = create_inline_keyboard(['habits', 'status', 'add'])  # Стартовое меню
    for user_id_tuple in active_users:
        user_id = user_id_tuple[0]
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
            logging.info(f"Sent custom message to user {user_id}: {message_text[:50]}...")
        except Exception as e:
            logging.error(f"Failed to send message to user {user_id}: {e}", exc_info=True)


# Обработчик для возврата в главное меню
@bot.callback_query_handler(func=lambda call: call.data == 'menu')
@error_handler
def handle_menu(call):
    logging.info(f"User {call.from_user.id} returned to main menu")
    clear_user_session(call.from_user.id)
    keyboard = create_inline_keyboard(['habits', 'status', 'add'])
    bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=keyboard)


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
    periods = ["Ежедневно", "Еженедельно", "Ежемесячно"]
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


@bot.message_handler(func=lambda message: message.reply_to_message and message.reply_to_message.text.startswith(
    "Введите количество выполнений"))
@error_handler
def handle_repetition_count_input(message):
    raw_session_data = get_user_session(message.chat.id)
    logging.info(f"Received input for user {message.chat.id}: {message.text}")
    print(f"Handling repetition count input for user {message.chat.id}")
    if raw_session_data:
        try:
            session_data = json.loads(raw_session_data)
            logging.info(f"Session data: {session_data}")
            repetition_count = int(message.text)
            if 1 <= repetition_count <= 30:
                response = assign_habit(message.chat.id, session_data['habit_id'], session_data['frequency_name'],
                                        repetition_count)
                logging.info(f"Assign habit response: {response}")
                print(f"Sending response: {response}")
                clear_user_session(message.chat.id)
                keyboard = create_inline_keyboard(['menu'])
                bot.send_message(message.chat.id, response, reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, "Введите число от 1 до 30.",
                                 reply_markup=types.ForceReply(selective=True))
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите число (например, 1, 2, 3).",
                             reply_markup=types.ForceReply(selective=True))
        except Exception as e:
            logging.error(f"Error in handle_repetition_count_input: {e}", exc_info=True)
            bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.",
                             reply_markup=create_inline_keyboard(['menu']))
    else:
        bot.send_message(message.chat.id, "Сессия истекла. Начните заново, выбрав 'Добавить'.",
                         reply_markup=create_inline_keyboard(['menu']))


@bot.callback_query_handler(func=lambda call: call.data == 'new_habit')
@error_handler
def handle_new_habit(call):
    state = 'entering_habit_name'
    data = json.dumps({})
    save_user_session(call.from_user.id, state, data)
    bot.send_message(call.message.chat.id, "Введите название новой привычки:",
                     reply_markup=types.ForceReply(selective=True))


@bot.message_handler(func=lambda
        message: message.reply_to_message and message.reply_to_message.text == "Введите название новой привычки:")
@error_handler
def handle_habit_name_input(message):
    habit_name = message.text.strip()
    if habit_name.lower() == "отмена":
        clear_user_session(message.chat.id)
        bot.send_message(message.chat.id, "Добавление привычки отменено.",
                         reply_markup=create_inline_keyboard(['menu']))
        return
    if not habit_name:
        bot.send_message(message.chat.id, "Название не может быть пустым. Попробуйте снова или введите 'отмена':",
                         reply_markup=types.ForceReply(selective=True))
        return
    if len(habit_name) > 50:
        bot.send_message(message.chat.id,
                         "Название слишком длинное (максимум 50 символов). Попробуйте снова или введите 'отмена':",
                         reply_markup=types.ForceReply(selective=True))
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM habit WHERE name = ?", (habit_name,))
    if cur.fetchone():
        conn.close()
        bot.send_message(message.chat.id,
                         f"Привычка с названием '{habit_name}' уже существует. Введите другое название или введите 'отмена':",
                         reply_markup=types.ForceReply(selective=True))
        return
    conn.close()
    state = 'entering_habit_description'
    data = json.dumps({'habit_name': habit_name})
    update_user_session(message.chat.id, state, data)
    bot.send_message(message.chat.id, "Введите описание привычки (или 'отмена'):",
                     reply_markup=types.ForceReply(selective=True))


@bot.message_handler(
    func=lambda message: message.reply_to_message and "Введите описание привычки" in message.reply_to_message.text)
@error_handler
def handle_habit_description_input(message):
    logging.info(f"Entering handle_habit_description_input for user {message.chat.id}")
    print(f"Processing description input for user {message.chat.id}")
    habit_description = message.text.strip()
    logging.info(f"User {message.chat.id} entered description: {habit_description}")
    print(f"Description: {habit_description}")
    if habit_description.lower() == "отмена":
        logging.info(f"User {message.chat.id} cancelled habit creation")
        clear_user_session(message.chat.id)
        bot.send_message(message.chat.id, "Добавление привычки отменено.",
                         reply_markup=create_inline_keyboard(['menu']))
        return
    logging.info(f"Fetching session for user {message.chat.id}")
    raw_session_data = get_user_session(message.chat.id)
    logging.info(f"Session data: {raw_session_data}")
    print(f"Session data: {raw_session_data}")
    if raw_session_data:
        try:
            logging.info(f"Parsing session data")
            session_data = json.loads(raw_session_data)
            habit_name = session_data['habit_name']
            logging.info(f"Extracted habit name: {habit_name}")
            print(f"Habit name: {habit_name}")
            if len(habit_description) > 200:
                logging.info(f"Description too long for user {message.chat.id}")
                bot.send_message(message.chat.id,
                                 "Описание слишком длинное (максимум 200 символов). Попробуйте снова или введите 'отмена':",
                                 reply_markup=types.ForceReply(selective=True))
                return
            logging.info(f"Connecting to database")
            print("Connecting to database")
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            logging.info(f"Executing INSERT for habit: name={habit_name}, description={habit_description}")
            print(f"Executing INSERT: name={habit_name}, description={habit_description}")
            cur.execute("INSERT INTO habit (name, description) VALUES (?, ?)", (habit_name, habit_description))
            habit_id = cur.lastrowid
            logging.info(f"Inserted habit with id={habit_id}")
            print(f"Inserted habit with id={habit_id}")
            conn.commit()
            conn.close()
            logging.info(f"Updating session to selecting_habit for user {message.chat.id}")
            state = 'selecting_habit'
            data = json.dumps({'habit_id': habit_id})
            update_user_session(message.chat.id, state, data)
            keyboard = types.InlineKeyboardMarkup()
            periods = ["Ежедневно", "Еженедельно", "Ежемесячно"]
            for period in periods:
                keyboard.add(types.InlineKeyboardButton(text=period, callback_data=f'add_period_{period}_{habit_id}'))
            keyboard.add(types.InlineKeyboardButton(text='Отмена', callback_data='menu'))
            logging.info(f"Sending period selection message to user {message.chat.id}")
            print("Sending period selection message")
            bot.send_message(message.chat.id, "Выберите периодичность привычки:", reply_markup=keyboard)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for user {message.chat.id}: {e}", exc_info=True)
            bot.send_message(message.chat.id, "Ошибка в данных сессии. Начните заново, выбрав 'Добавить'.",
                             reply_markup=create_inline_keyboard(['menu']))
        except sqlite3.Error as e:
            logging.error(f"Database error for user {message.chat.id}: {e}", exc_info=True)
            bot.send_message(message.chat.id, "Ошибка при сохранении привычки. Попробуйте снова.",
                             reply_markup=create_inline_keyboard(['menu']))
        except Exception as e:
            logging.error(f"Unexpected error for user {message.chat.id}: {e}", exc_info=True)
            bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.",
                             reply_markup=create_inline_keyboard(['menu']))
    else:
        logging.warning(f"No session found for user {message.chat.id}")
        bot.send_message(message.chat.id, "Сессия истекла. Начните заново, выбрав 'Добавить'.",
                         reply_markup=create_inline_keyboard(['menu']))


# Обработчик для выбора периодичности и перехода к вводу количества выполнений
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_period_'))
@error_handler
def select_period(call):
    parts = call.data.split('_')
    if len(parts) < 4:
        bot.send_message(call.message.chat.id, "Произошла ошибка в данных. Пожалуйста, попробуйте ещё раз.")
        return
    period = parts[2]
    habit_id = parts[3]  # Изменено: берем только parts[3]
    state = 'selecting_period'
    new_data = json.dumps({'frequency_name': period, 'habit_id': habit_id})
    print(f"Updating session for user {call.from_user.id}: state={state}, data={new_data}")
    update_user_session(call.from_user.id, state, new_data)
    msg = "Введите количество выполнений для привычки (от 1 до 30):"
    bot.send_message(call.message.chat.id, msg, reply_markup=types.ForceReply(selective=True))


@bot.message_handler(func=lambda message: message.reply_to_message and message.reply_to_message.text.startswith(
    "Введите количество выполнений"))
@error_handler
def handle_repetition_count_input(message):
    raw_session_data = get_user_session(message.chat.id)
    logging.info(f"Received input for user {message.chat.id}: {message.text}")
    if raw_session_data:
        try:
            session_data = json.loads(raw_session_data)
            logging.info(f"Session data: {session_data}")
            repetition_count = int(message.text)
            if 1 <= repetition_count <= 30:
                response = assign_habit(message.chat.id, session_data['habit_id'], session_data['frequency_name'],
                                        repetition_count)
                logging.info(f"Assign habit response: {response}")
                clear_user_session(message.chat.id)  # Сбрасываем сессию
                keyboard = create_inline_keyboard(['menu'])  # Только кнопка "На главная"
                bot.send_message(message.chat.id, response, reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, "Введите число от 1 до 30.",
                                 reply_markup=types.ForceReply(selective=True))
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите число (например, 1, 2, 3).",
                             reply_markup=types.ForceReply(selective=True))
        except Exception as e:
            logging.error(f"Error in handle_repetition_count_input: {e}", exc_info=True)
            bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.",
                             reply_markup=create_inline_keyboard(['menu']))
    else:
        bot.send_message(message.chat.id, "Сессия истекла. Начните заново, выбрав 'Добавить'.",
                         reply_markup=create_inline_keyboard(['menu']))


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
                         "Список привычек пуст. Нажмите 'Добавить', чтобы создать новую привычку.",
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
    keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(text='Назад', callback_data='menu')
    keyboard.add(back_button)

    if file_path is None:
        bot.send_message(call.message.chat.id, "Нет данных для отображения графика за выбранный период.",
                         reply_markup=keyboard)
    else:
        try:
            with open(file_path, 'rb') as photo:
                bot.send_photo(call.message.chat.id, photo, reply_markup=keyboard)
            delete_file(file_path)  # Удаление файла после отправки
        except FileNotFoundError:
            logging.error(f"File not found: {file_path}", exc_info=True)
            bot.send_message(call.message.chat.id, "Ошибка при отправке графика. Попробуйте снова.",
                             reply_markup=keyboard)

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
