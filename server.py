import asyncio

clients = {}
clients_lock = asyncio.Lock()
chat_histories = {}


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"New connection: {addr}")
    try:
        print("restart")
        username = (await reader.readline()).decode().strip()
        room = (await reader.readline()).decode().strip()

        await disconnect_user_from_previous_room(username)

        if room not in clients:
            clients[room] = []
        clients[room].append((username, writer))
        print(f"Client {username} {addr} joined the room {room}")

        await send_active_users_to_room(room)

        await send_available_rooms(writer)

        await send_chat_history_to_client(writer, room)

        while True:
            data = await reader.readline()
            if not data:
                break

            message = data.decode().strip()

            if message.startswith("FETCH_ROOMS"):
                await send_available_rooms(writer)
            elif message.startswith("CREATE_ROOM:"):
                new_room_name = message.split(":")[1].strip()
                await create_room(new_room_name)
            elif message.startswith("CHAT_HISTORY"):
                await send_chat_history_to_client(writer, room)
            elif message.startswith("FILE:"):
                await handle_file_transfer(reader, message[5:], username, room)
            else:
                print(f"{username} ({addr}) in room {room}: {message}")
                await send_message_to_room(room, f"{username}: {message}")
    except Exception as e:
        print(f"Client error {username}: {e}")
    finally:
        async with clients_lock:
            if room in clients:
                clients[room] = [client for client in clients[room] if client[1] != writer]
                if not clients[room]:
                    del clients[room]
                await send_active_users_to_room(room)

        print(f"Client {username} {addr} left the room {room}")
        writer.close()
        await writer.wait_closed()


async def send_available_rooms(writer):
    async with clients_lock:
        available_rooms = list(clients.keys())
        print(available_rooms)
        rooms_message = f"Available rooms: {', '.join(available_rooms)}\n"
        writer.write(rooms_message.encode())
        await writer.drain()


async def create_room(new_room_name):
    async with clients_lock:
        if new_room_name not in clients:
            clients[new_room_name] = []
            chat_histories[new_room_name] = []
            print(f"Room created: {new_room_name}")


async def disconnect_user_from_previous_room(username):
    global clients

    for room in clients.keys():
        for client in clients[room]:
            if client[0] == username:
                clients[room].remove(client)
                await send_active_users_to_room(room)

                await send_message_to_room(room, f"{username} has left the room.\n")

                if not clients[room]:
                    del clients[room]
                return


async def handle_file_transfer(reader, filename, username, room):
    await send_message_to_room(room, f"{username} is sending a file: {filename}")

    size_data = await reader.readline()

    try:
        file_size = int(size_data.decode().strip())
    except ValueError:
        print(f"Invalid file size received from {username}.")
        return

    with open(filename, 'wb') as f:
        bytes_received = 0
        while bytes_received < file_size:
            chunk = await reader.read(1024)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    await send_message_to_room(room, f"File received: {filename}")


async def send_active_users_to_room(room):
    if room in clients:
        active_users = [client[0] for client in clients[room]]
        message = f"Active users in {room}: {', '.join(active_users)}\n"
        for _, writer in clients[room]:
            writer.write(message.encode())
            await writer.drain()


async def send_chat_history_to_client(writer, room):
    if room in chat_histories:
        for message in chat_histories[room]:
            writer.write(f"{message}\n".encode())
            await writer.drain()


async def send_message_to_room(room, message):
    if room in clients:
        if room not in chat_histories:
            chat_histories[room] = []
        chat_histories[room].append(message)

        for username, writer in clients[room]:
            writer.write(f"{message}\n".encode())
            await writer.drain()


async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)
    addr = server.sockets[0].getsockname()
    print(f"Server works on {addr}")
    async with server:
        await server.serve_forever()


asyncio.run(main())
