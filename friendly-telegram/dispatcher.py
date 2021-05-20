#    Friendly Telegram Userbot
#    by GeekTG Team

import asyncio
import collections
import logging

from . import utils, main, security

ru_keys = """ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГ
        ШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ, """
en_keys = """`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{
        }ASDFGHJKL:"|ZXCVBNM<>? """


def _decrement_ratelimit(delay, data, key, severity):
	def inner():
		data[key] = max(0, data[key] - severity)

	asyncio.get_event_loop().call_later(delay, inner)


class CommandDispatcher:
	def __init__(self, modules, db, bot, testing):
		self._modules = modules
		self._db = db
		self._bot = bot
		self.security = security.SecurityManager(db, bot)
		self._testing = testing
		if not testing:
			self._ratelimit_storage_user = collections.defaultdict(int)
			self._ratelimit_storage_chat = collections.defaultdict(int)
			self._ratelimit_max_user = db.get(__name__, "ratelimit_max_user", 30)
			self._ratelimit_max_chat = db.get(__name__, "ratelimit_max_chat", 100)
		self.check_security = self.security.check

	async def init(self, client):
		await self.security.init(client)
		me = await client.get_me()
		self._me = me.id
		self._cached_username = me.username.lower() if me.username else str(me.id)

	async def _handle_ratelimit(self, message, func):
		if self._testing or await self.security.check(message, security.OWNER | security.SUDO | security.SUPPORT):
			return True
		func = getattr(func, "__func__", func)
		ret = True
		chat = self._ratelimit_storage_chat[message.chat_id]
		if message.sender_id:
			user = self._ratelimit_storage_user[message.sender_id]
			severity = (5 if getattr(func, "ratelimit", False) else 2) * ((user + chat) // 30 + 1)
			user += severity
			self._ratelimit_storage_user[message.sender_id] = user
			if user > self._ratelimit_max_user:
				ret = False
			else:
				self._ratelimit_storage_chat[message.chat_id] = chat
			_decrement_ratelimit(self._ratelimit_max_user * severity, self._ratelimit_storage_user,
			                     message.sender_id, severity)
		else:
			severity = (5 if getattr(func, "ratelimit", False) else 2) * (chat // 15 + 1)
		chat += severity
		if chat > self._ratelimit_max_chat:
			ret = False
		_decrement_ratelimit(self._ratelimit_max_chat * severity, self._ratelimit_storage_chat,
		                     message.chat_id, severity)
		return ret

	async def handle_command(self, event):
		"""Handle all commands"""
		if not hasattr(event, "message") or getattr(event.message, "message", "") == "":
			return

		# Empty string evaluates to False, so the `or` activates
		prefixes = self._db.get(main.__name__, "command_prefix", False) or ["."]
		if isinstance(prefixes, str):
			prefixes = [prefixes]  # legacy db migration
			self._db.set(main.__name__, "command_prefix", prefixes)

		prefix = None
		change = str.maketrans(ru_keys + en_keys, en_keys + ru_keys)
		for possible_prefix in prefixes:
			if event.message.message.startswith(possible_prefix):
				prefix = possible_prefix
				break
			elif event.message.message.startswith(str.translate(possible_prefix, change)):
				prefix = str.translate(possible_prefix, change)
		if prefix is None:
			return

		logging.debug("Incoming command!")
		if event.sticker or event.dice or event.audio:
			logging.debug("Ignoring invisible or potentially forwarded command.")
			return
		if event.via_bot_id:
			logging.debug("Ignoring inline bot.")
			return

		message = utils.censor(event.message)
		blacklist_chats = self._db.get(main.__name__, "blacklist_chats", [])
		whitelist_chats = self._db.get(main.__name__, "whitelist_chats", [])
		whitelist_modules = self._db.get(main.__name__, "whitelist_modules", [])
		if utils.get_chat_id(message) in blacklist_chats or (whitelist_chats and utils.get_chat_id(message) not in
		                                                     whitelist_chats):
			logging.debug("Message is blacklisted")
			return

		if message.out and len(message.message) > len(prefix) and message.message[:len(prefix) * 2] == prefix * 2 \
				and message.message != len(message.message) // len(prefix) * prefix:
			# Allow escaping commands using .'s
			entities = utils.relocate_entities(message.entities, -len(prefix), message.message)
			await message.edit(message.message[len(prefix):], parse_mode=lambda s: (s, entities or ()))
			return

		logging.debug(message)
		# Make sure we don't get confused about spaces or other stuff in the prefix
		message.message = message.message[len(prefix):]
		if not message.message:
			return  # Message is just the prefix
		utils.relocate_entities(message.entities, -len(prefix))

		command = message.message.split(maxsplit=1)[0]
		tag = command.split("@", maxsplit=1)
		if not self._testing:
			if len(tag) == 2:
				if tag[1] == "me":
					if not message.out:
						return
				elif tag[1].lower() != self._cached_username:
					return
			elif not event.is_private and not event.out:
				return
		logging.debug(tag[0])

		txt, func = self._modules.dispatch(tag[0])
		if func is not None:
			if not await self._handle_ratelimit(message, func):
				return
			if not await self.security.check(message, func):
				return
			if message.is_channel and message.is_group:
				my_id = (await message.client.get_me(True)).user_id
				if (await message.get_chat()).title.startswith(f"friendly-{my_id}-"):
					return
			message.message = txt + message.message[len(command):]
			if str(utils.get_chat_id(message)) + "." + func.__self__.__module__ in blacklist_chats:
				logging.debug("Command is blacklisted in chat")
				return
			if whitelist_modules and not (str(utils.get_chat_id(message)) + "."
			                              + func.__self__.__module__ in whitelist_modules):
				logging.debug("Command is not whitelisted in chat")
				return

			try:
				await func(message)
			except Exception as e:
				logging.exception("Command failed")
				try:
					if await self.security.check(message, security.OWNER | security.SUDO):
						txt = ("<b>Request failed! Request was</b> <code>" + utils.escape_html(message.message)
						       + "</code><b>. Please report it in the support group "
						         "(</b><code>{0}support</code><b>) along with the logs "
						         "(</b><code>{0}logs error</code><b>)</b>").format(prefix)
					else:
						txt = "<b>Sorry, something went wrong!</b>"
					await (message.edit if message.out else message.reply)(txt)
				finally:
					raise e

	async def handle_incoming(self, event):
		"""Handle all incoming messages"""
		logging.debug("Incoming message!")
		message = utils.censor(getattr(event, "message", event))
		blacklist_chats = self._db.get(main.__name__, "blacklist_chats", [])
		whitelist_chats = self._db.get(main.__name__, "whitelist_chats", [])
		whitelist_modules = self._db.get(main.__name__, "whitelist_modules", [])
		if utils.get_chat_id(message) in blacklist_chats or (whitelist_chats and utils.get_chat_id(message) not in
		                                                     whitelist_chats):
			logging.debug("Message is blacklisted")
			return
		for func in self._modules.watchers:
			if str(utils.get_chat_id(message)) + "." + func.__self__.__module__ in blacklist_chats:
				logging.debug("Command is blacklisted in chat")
				return
			if whitelist_modules and not (str(utils.get_chat_id(message)) + "."
			                              + func.__self__.__module__ in whitelist_modules):
				logging.debug("Command is not whitelisted in chat")
				return
			try:
				await func(message)
			except Exception:
				logging.exception("Error running watcher")
