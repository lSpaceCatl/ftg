from ..  import loader, utils

import io
import math
import urllib.request

from PIL import Image
from telethon.tl.types import DocumentAttributeFilename, MessageMediaPhoto

from userbot import CMD_HELP, bot
from userbot.events import register

PACK_FULL = "Чел, пак полон. 120 стикеров - предел в тележке. Пора делать новый)))"


@register(outgoing=True, pattern="^.kang")
async def kang(args):
    """ Для .kang команды требуется стикер """
    user = await bot.get_me()
    if not user.username:
        user.username = user.first_name
    message = await args.get_reply_message()
    photo = None
    emojibypass = False
    is_anim = False
    emoji = ""
    await args.edit("`Пошла родимая...`")
    if message and message.media:
        if isinstance(message.media, MessageMediaPhoto):
            photo = io.BytesIO()
            photo = await bot.download_media(message.photo, photo)
        elif "image" in message.media.document.mime_type.split('/'):
            photo = io.BytesIO()
            await bot.download_file(message.media.document, photo)
            if (DocumentAttributeFilename(file_name='sticker.webp') in
                    message.media.document.attributes):
                emoji = message.media.document.attributes[1].alt
                emojibypass = True
        elif (DocumentAttributeFilename(file_name='AnimatedSticker.tgs') in
              message.media.document.attributes):
            emoji = message.media.document.attributes[0].alt
            emojibypass = True
            is_anim = True
            photo = 1
        else:
            await args.edit("`Иди нахуй - не поддерживаю я такое`")
            return
    else:
        await args.edit("`Реплай на фото сделай для добавления стикера`")
        return

    if photo:
        splat = args.text.split()
        if not emojibypass:
            emoji = "🤨"
        pack = 1
        if len(splat) == 3:
            pack = splat[2]  
            emoji = splat[1]
        elif len(splat) == 2:
            if splat[1].isnumeric():
                pack = int(splat[1])
            else:
                emoji = splat[1]

        packname = f"a{user.id}_by_{user.username}_{pack}"
        packnick = f"@{user.username}'s pack {pack}"
        cmd = '/newpack'
        file = io.BytesIO()

        if not is_anim:
            image = await resize_photo(photo)
            file.name = "sticker.png"
            image.save(file, "PNG")
        else:
            packname += "_anim"
            packnick += " animated"
            cmd = '/newanimated'

        response = urllib.request.urlopen(
            urllib.request.Request(f'http://t.me/addstickers/{packname}'))
        htmlstr = response.read().decode("utf8").split('\n')

        if "  A <strong>Telegram</strong> user has created the <strong>Sticker&nbsp;Set</strong>." not in htmlstr:
            async with bot.conversation('Stickers') as conv:
                await conv.send_message('/addsticker')
                await conv.get_response()
                # Ensure user doesn't get spamming notifications
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.send_message(packname)
                x = await conv.get_response()
                while x.text == PACK_FULL:
                    pack += 1
                    packname = f"a{user.id}_by_{user.username}_{pack}"
                    packnick = f"@{user.username}'s userbot pack {pack}"
                    await args.edit("`Switching to Pack " + str(pack) +
                                    " due to insufficient space`")
                    await conv.send_message(packname)
                    x = await conv.get_response()
                    if x.text == "Invalid pack selected.":
                        await conv.send_message(cmd)
                        await conv.get_response()
                        await bot.send_read_acknowledge(conv.chat_id)
                        await conv.send_message(packnick)
                        await conv.get_response()
                        await bot.send_read_acknowledge(conv.chat_id)
                        if is_anim:
                            await bot.forward_messages('Stickers',
                                                       [message.id],
                                                       args.chat_id)
                        else:
                            file.seek(0)
                            await conv.send_file(file, force_document=True)
                        await conv.get_response()
                        await conv.send_message(emoji)
                        # Ensure user doesn't get spamming notifications
                        await bot.send_read_acknowledge(conv.chat_id)
                        await conv.get_response()
                        await conv.send_message("/publish")
                        if is_anim:
                            await conv.get_response()
                            await conv.send_message(f"<{packnick}>")
                        await conv.get_response()
                        await bot.send_read_acknowledge(conv.chat_id)
                        await conv.send_message("/skip")
                        await bot.send_read_acknowledge(conv.chat_id)
                        await conv.get_response()
                        await conv.send_message(packname)
                        await bot.send_read_acknowledge(conv.chat_id)
                        await conv.get_response()
                        await bot.send_read_acknowledge(conv.chat_id)
                        await args.edit(
                            f"Стикер добавлен в ахуенный пак. Пак создан сейчас. Можешь его найти [тут](t.me/addstickers/{packname})",
                            parse_mode='md')
                        return
                if is_anim:
                    await bot.forward_messages('Stickers', [message.id],
                                               args.chat_id)
                else:
                    file.seek(0)
                    await conv.send_file(file, force_document=True)
                await conv.get_response()
                await conv.send_message(emoji)
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.get_response()
                await conv.send_message('/done')
                await conv.get_response()
                await bot.send_read_acknowledge(conv.chat_id)
        else:
            await args.edit("Тут должен был быть аргемент про стикерпак и тп, но мне лень писать - крч создаю новый. Мур")
            async with bot.conversation('Stickers') as conv:
                await conv.send_message(cmd)
                await conv.get_response()
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.send_message(packnick)
                await conv.get_response()
                await bot.send_read_acknowledge(conv.chat_id)
                if is_anim:
                    await bot.forward_messages('Stickers', [message.id],
                                               args.chat_id)
                else:
                    file.seek(0)
                    await conv.send_file(file, force_document=True)
                await conv.get_response()
                await conv.send_message(emoji)
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.get_response()
                await conv.send_message("/publish")
                if is_anim:
                    await conv.get_response()
                    await conv.send_message(f"<{packnick}>")
                await conv.get_response()
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.send_message("/skip")
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.get_response()
                await conv.send_message(packname)
                await bot.send_read_acknowledge(conv.chat_id)
                await conv.get_response()
                await bot.send_read_acknowledge(conv.chat_id)

        await args.edit(
            f"Стикер добавлен. Пак тута. [Мур](t.me/addstickers/{packname})",
            parse_mode='md')


async def resize_photo(photo):
    """ Resize the given photo to 512x512 """
    image = Image.open(photo)
    maxsize = (512, 512)
    if (image.width and image.height) < 512:
        size1 = image.width
        size2 = image.height
        if image.width > image.height:
            scale = 512 / size1
            size1new = 512
            size2new = size2 * scale
        else:
            scale = 512 / size2
            size1new = size1 * scale
            size2new = 512
        size1new = math.floor(size1new)
        size2new = math.floor(size2new)
        sizenew = (size1new, size2new)
        image = image.resize(sizenew)
    else:
        image.thumbnail(maxsize)

    return image


CMD_HELP.update({
    "kang":
    ".kang\n"
    "Usage: Сделай реплай .kang на фото или стикер и он будет в твоем мяупаке"
})

CMD_HELP.update({
    "kang":
    ".kang [emoji('s)]\n"
    "Usage: Работает с  .kang и использует твой смайл для обозначения стикера."
})

CMD_HELP.update({
    "kang":
    ".kang [number]\n"
    "Usage: Стикеризация стикера/изображения по умолчанию использует 🤭 как эмоджи."
})
