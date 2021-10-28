import os
from functools import reduce
from tempfile import NamedTemporaryFile
from gtts import gTTS
from flask import abort, request, Flask
from pydub import AudioSegment
import telebot

BACKGROUND_START = AudioSegment.from_mp3('background_start.mp3')
BACKGROUND_MIDDLE = AudioSegment.from_mp3('background_middle.mp3')
BACKGROUND_END = AudioSegment.from_mp3('background_end.mp3')
POSITION = 1000

DOMAIN = os.environ['BOT_DOMAIN']
KEY = os.environ['BOT_KEY']
WEBHOOK_URL_BASE = "https://{}:{}".format(DOMAIN, '443')
WEBHOOK_URL_PATH = "/{}/".format(KEY)
bot = telebot.TeleBot(KEY, threaded=False)
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH)
app = Flask(__name__)


def generate_speech(text: str, output_path: str):
    """Генерация текста гуглодевочкой"""
    obj = gTTS(text=text, lang='ru', slow=False)
    obj.save(output_path)


def overlay(input_path: str, output_path: str):
    """Накладывает текст на минус из Кривого Зеркала"""
    lyrics = AudioSegment.from_mp3(input_path)
    first_part_single = BACKGROUND_START
    first_part_double = BACKGROUND_START.append(BACKGROUND_MIDDLE)
    if len(lyrics) + POSITION > len(first_part_double):
        middle_parts_amount = \
            (len(lyrics) + POSITION - len(first_part_double)) // len(BACKGROUND_MIDDLE)
        if middle_parts_amount > 0:
            first_part = first_part_double.append(
                reduce(lambda a, b: a.append(b),
                       [BACKGROUND_MIDDLE] * middle_parts_amount)
            )
        else:
            first_part = first_part_double
        position = POSITION
    elif len(lyrics) + POSITION > len(first_part_single):
        first_part = first_part_single
        position = POSITION
    else:
        first_part = first_part_single
        position = len(first_part_single - 1)
    delta = len(lyrics) + position - len(first_part)
    if delta > 0:
        first_part = first_part.append(AudioSegment.silent(delta + 100)).fade_out(1000)
    first_part = first_part.overlay(lyrics, position=position)
    res = first_part.append(BACKGROUND_END)
    res.export(output_path)


def make_song(text: str, output_path: str):
    with NamedTemporaryFile(suffix='.mp3') as lyrics_file:
        generate_speech(text, lyrics_file.name)
        overlay(lyrics_file.name, output_path)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Частушки, бесплатно без СМС и регистрации. Нужно скинуть текст")


@bot.message_handler(func=lambda message: True)
def send_song(message):
    with NamedTemporaryFile(suffix='.mp3') as f:
        make_song(message.text, f.name)
        bot.send_audio(audio=open(f.name, 'rb'), chat_id=message[-1].chat.id)


@app.route('/', methods=['GET', 'HEAD'])
def index():
    return 'ok'


@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)
