import asyncio
import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, filedialog, simpledialog

asyncio_loop = None
reader = None
writer = None
username = None
current_room = None
ip = '127.0.0.1'


async def get_messages(reader, message_widget, user_widget):
    while True:
        data = await reader.read(100)
        if not data:
            break
        message = data.decode().strip()
        print(f"received message:{message}")
        if message.startswith("Active users"):
            user_widget.config(state=tk.NORMAL)
            user_widget.delete(1.0, tk.END)
            user_widget.insert(tk.END, message + '\n')
            user_widget.config(state=tk.DISABLED)
        elif message.startswith("Available rooms:"):
            rooms = message[len("Available rooms: "):].split(", ")
            update_sidebar_with_rooms(rooms)
        else:
            message_widget.insert(tk.END, f"{message}\n")
            message_widget.see(tk.END)

async def send_message(writer, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_message = f"{username}({timestamp}): {message}"
    writer.write((full_message + '\n').encode())
    await writer.drain()

async def send_file(writer, file_path):
    full_message = f"FILE:{os.path.basename(file_path)}\n"
    writer.write(full_message.encode())
    await writer.drain()

    file_size = os.path.getsize(file_path)
    writer.write(f"{file_size}\n".encode())
    await writer.drain()

    with open(file_path, 'rb') as file:
        while chunk := file.read(1024):
            writer.write(chunk)
            await writer.drain()
    full_message = f"Finished sending file: {os.path.basename(file_path)}\n"
    writer.write(full_message.encode())
    await writer.drain()

async def register_client(ip, username, room):
    global reader, writer, current_room
    if writer:
        writer.close()
        await writer.wait_closed()
    reader, writer = await asyncio.open_connection(ip, 8888)
    writer.write(f"{username}\n".encode())
    await writer.drain()
    writer.write(f"{room}\n".encode())
    await writer.drain()

    current_room = room

    print(f"Client {username} registered in room {room}")

    asyncio.create_task(get_messages(reader, text_widget, active_users_widget))

def start_chat(ip, username, room):
    asyncio.run_coroutine_threadsafe(register_client(ip, username, room), asyncio_loop)
    root.deiconify()

async def main():
    global reader, writer
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
    asyncio.create_task(get_messages(reader, text_widget, active_users_widget))

def start_client():
    global asyncio_loop
    asyncio_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(asyncio_loop)
    asyncio_loop.run_forever()

def initial_registration():
    dialog = tk.Toplevel(root)
    dialog.title("Подключение к серверу")

    form_frame = tk.Frame(dialog, padx=10, pady=10)
    form_frame.pack(padx=10, pady=10)

    # Поле для ввода IP-адреса
    tk.Label(form_frame, text="IP адрес сервера:").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    ip_entry = tk.Entry(form_frame)
    ip_entry.insert(0, "127.0.0.1")
    ip_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

    # Поле для ввода имени пользователя
    tk.Label(form_frame, text="Имя пользователя:").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))
    username_entry = tk.Entry(form_frame)
    username_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

    # Поле для ввода названия комнаты
    tk.Label(form_frame, text="Название комнаты:").grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 5))
    room_entry = tk.Entry(form_frame)
    room_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 10))

    # Настройка растяжения по ширине
    form_frame.columnconfigure(0, weight=1)
    form_frame.columnconfigure(1, weight=1)

    def on_confirm():
        global username
        ip = ip_entry.get()
        username = username_entry.get()
        room = room_entry.get()

        if ip and username and room:
            start_chat(ip, username, room)
            dialog.destroy()

    # Кнопка подключения
    connect_button = tk.Button(form_frame, text="Подключиться", command=on_confirm, bg="#2196F3", fg="white")
    connect_button.grid(row=6, column=0, columnspan=2, pady=(10, 0))

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    position_top = int(screen_height / 2 - height / 2)
    position_left = int(screen_width / 2 - width / 2)

    window.geometry(f'{width}x{height}+{position_left}+{position_top}')

async def disconnect_client():
    global writer
    if writer:
        writer.close()
        await writer.wait_closed()
        root.destroy()

def on_disconnect_button_click():
    asyncio.run_coroutine_threadsafe(disconnect_client(), asyncio_loop)

def create_new_room():
    new_room_name = simpledialog.askstring("Новая комната", "Введите название новой комнаты:")
    if new_room_name:
        asyncio.run_coroutine_threadsafe(send_create_room_request(new_room_name), asyncio_loop)

async def send_create_room_request(new_room_name):
    writer.write(f"CREATE_ROOM:{new_room_name}\n".encode())
    await writer.drain()
    await request_available_rooms()

async def request_available_rooms():
    print("Requesting available rooms...")
    writer.write("FETCH_ROOMS\n".encode())
    await writer.drain()

def refresh_rooms():
    asyncio.run_coroutine_threadsafe(request_available_rooms(), asyncio_loop)

def update_sidebar_with_rooms(rooms):
    chat_listbox.delete(0, tk.END)
    for room in rooms:
        chat_listbox.insert(tk.END, room)

def sidebar(frame):
    sidebar_frame = tk.Frame(frame, width=200)
    sidebar_frame.pack(side="left", fill="y")

    global chat_listbox
    chat_listbox = tk.Listbox(sidebar_frame)
    chat_listbox.pack(fill="both", expand=True)

    def clear_chat_frame():
        text_widget.delete(1.0, tk.END)

    def on_chat_select(event):
        global current_room
        selected_room = chat_listbox.get(chat_listbox.curselection())
        if selected_room != current_room:
            clear_chat_frame()
            asyncio.run_coroutine_threadsafe(register_client(ip, username, selected_room), asyncio_loop)

    chat_listbox.bind('<<ListboxSelect>>', on_chat_select)
    create_room_button = tk.Button(sidebar_frame, text="Создать комнату", command=create_new_room, bg="#2196F3", fg="white")
    create_room_button.pack(pady=(5, 10))

    update_rooms_info_button = tk.Button(sidebar_frame, text="Обновить комнаты", command=refresh_rooms, bg="#2196F3", fg="white")
    update_rooms_info_button.pack(pady=(5, 10))

def clear_placeholder(event):
    if entry_widget.get() == "Введите ваше сообщение...":
        entry_widget.delete(0, "end")
        entry_widget.config(fg="black")

def restore_placeholder(event):
    if entry_widget.get() == "":
        entry_widget.insert(0, "Введите ваше сообщение...")
        entry_widget.config(fg="grey")

def on_send_button_click():
    message = entry_widget.get()
    entry_widget.delete(0, tk.END)
    if message:
        asyncio.run_coroutine_threadsafe(send_message(writer, message), asyncio_loop)

def on_send_file_button_click():
    file_path = filedialog.askopenfilename()
    if file_path:
        asyncio.run_coroutine_threadsafe(send_file(writer, file_path), asyncio_loop)

def update_main_frame_layout():
    global main_frame, text_widget, entry_widget, active_users_widget, chat_listbox, input_frame

    main_frame = tk.Frame(root)
    main_frame.pack(padx=10, pady=10)

    # Создание боковой панели
    sidebar(main_frame)

    # Секция "Активные пользователи"
    active_users_frame = tk.LabelFrame(main_frame, text="Активные пользователи", padx=10, pady=10)
    active_users_frame.pack(fill="x", padx=5)
    active_users_widget = tk.Text(active_users_frame, height=1, wrap=tk.WORD, bg="#f0f0f0", fg="black", state=tk.DISABLED)
    active_users_widget.pack(fill="x")

    # Секция чата
    chat_frame = tk.LabelFrame(main_frame, text="Сообщения чата", padx=10, pady=10)
    chat_frame.pack(fill="both", expand=True)
    text_widget = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, height=15, bg="#ffffff", fg="black")
    text_widget.pack(fill="both", expand=True)

    # Поле ввода сообщений
    input_frame = tk.Frame(main_frame)
    input_frame.pack(padx=5)

    entry_widget = tk.Entry(input_frame)
    entry_widget.pack(side="left", fill="x", expand=True)
    if entry_widget.get() == "":
        entry_widget.insert(0, "Введите ваше сообщение...")
        entry_widget.config(fg="grey")

    # Обработчики для поля ввода
    entry_widget.bind("<FocusIn>", clear_placeholder)
    entry_widget.bind("<FocusOut>", restore_placeholder)
    entry_widget.bind("<Return>", lambda event: on_send_button_click())

    # Кнопка "Отправить"
    send_button = tk.Button(input_frame, text="Отправить", command=on_send_button_click, bg="#2196F3", fg="white")
    send_button.pack(side="right", padx=(5, 0))

    # Кнопка "Отправить файл"
    send_file_button = tk.Button(input_frame, text="Отправить файл", command=lambda: on_send_file_button_click(), bg="#2196F3", fg="white")
    send_file_button.pack(side="right", padx=(5, 0))

    # Секция для кнопки отключения
    disconnect_frame = tk.Frame(main_frame)
    disconnect_frame.pack(pady=(5, 0))
    disconnect_button = tk.Button(disconnect_frame, text="Отключиться", command=on_disconnect_button_click, bg="#2196F3", fg="#ffffff")
    disconnect_button.pack(side="right")

root = tk.Tk()
root.geometry("800x450")
root.title("Чат-клиент")
center_window(root, 800, 450)
root.withdraw()

# Создание основного интерфейса
update_main_frame_layout()

# Запуск начального окна регистрации
initial_registration()

# Запуск фонового потока для asyncio
client_thread = threading.Thread(target=start_client, daemon=True)
client_thread.start()

# Обработка закрытия окна
root.protocol("WM_DELETE_WINDOW", lambda: asyncio.run_coroutine_threadsafe(disconnect_client(), asyncio_loop))

# Запуск основного цикла приложения
root.mainloop()
