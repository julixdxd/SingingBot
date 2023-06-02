import discord
from discord.ext import commands
import asyncio
import youtube_dl
import yt_dlp
from youtubesearchpython import VideosSearch
import re
import random
import config
import requests
from PIL import Image
import json

TOKEN = config.TOKEN
PREFIX = "!"
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
current_track = None
current_author = None
yt_dl_opts = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
ytdl = yt_dlp.YoutubeDL(yt_dl_opts)
dynamic_commands = {}
COMMANDS_FILE = "commands.json"
EMOTE_FILE = "emotes.json"
EMOJI_FOLDER = "C:\\Users\\Julian\\Pictures\\DISCORDBOTEMOJIS"
EMOJI_FOLDER = "C:\\Users\\Julian\\Pictures\\DISCORDBOTEMOTES"
SHOWME_FILE = "showme.txt"


ffmpeg_options = {
    "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def findYT(query):
    if re.match(r"^https?:\/\/(www\.youtube\.com|youtu\.?be)\/.+$", query):
        return query
    else:
        videosSearch = VideosSearch(query, limit=1)
        result = videosSearch.result()
        link = result["result"][0]["id"]
        return "https://www.youtube.com/watch?v=" + link


def load_dynamic_commands():
    try:
        with open(COMMANDS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


dynamic_commands = load_dynamic_commands()


def load_emotes():
    try:
        with open(EMOTE_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


triggers = load_emotes()


@bot.event
async def on_ready():
    print(f"Bot is online. Logged in as {bot.user.name}")


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot and not after.channel:
        voice_client = member.guild.voice_client
        if voice_client:
            guild = voice_client.guild
            if guild.id in bot.music_queues:
                await play_next_song(guild)


@bot.command(name="join", description="Join a voice channel.")
async def join(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.move_to(channel)
    else:
        voice_client = await channel.connect()
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="leave", description="Leave the voice channel.")
async def leave(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="play", description="Play a YouTube video.")
async def play(ctx, *, query):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    try:
        channel = ctx.author.voice.channel
    except AttributeError:
        await bot_spam_channel.send("You are not in a voice channel.")
        return

    voice_client = ctx.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        voice_client = await channel.connect()

    url = findYT(query)

    if voice_client.is_playing() or voice_client.is_paused():
        server_queue = bot.music_queues.get(ctx.guild.id, [])
        server_queue.append((query, url, ctx.author))
        bot.music_queues[ctx.guild.id] = server_queue
        await bot_spam_channel.send(f"Added to the queue: {query}\n{url}")
    else:

        def after_playing(error):
            if error:
                print(f"Error playing next song: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(ctx.guild), bot.loop)

        global current_track
        current_track = url
        global current_author
        current_author = ctx.author
        player = await create_player(url)
        voice_client.play(player, after=after_playing)
        await bot_spam_channel.send(
            f"Now Playing:{current_track}  requested by {ctx.author}"
        )
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="currently_playing", description="Show what song is playing")
async def currently_playing(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_state = ctx.author.voice
    if voice_state is None:
        await bot_spam_channel.send("You are not connected to a voice channel.")
        return
    voice_channel = voice_state.channel
    if ctx.voice_client is None or ctx.voice_client.channel != voice_channel:
        await bot_spam_channel.send("The bot is not connected to a voice channel.")
        return
    if ctx.voice_client.is_playing():
        await bot_spam_channel.send(
            f"The currently playing audio is: {current_track} requested by {current_author}"
        )
    else:
        await bot_spam_channel.send("Nothing is currently playing.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="pause", description="Pause the currently playing song.")
async def pause(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await bot_spam_channel.send("Paused the current song.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="resume", description="Resume the currently playing song.")
async def resume(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await bot_spam_channel.send("Resumed the current song.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(
    name="stop", description="Stop the currently playing song and clear the queue."
)
async def stop(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()
        bot.music_queues.pop(ctx.guild.id, None)
        await bot_spam_channel.send("Stopped the current song and cleared the queue.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="skip", description="Skip the current song.")
async def skip(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await bot_spam_channel.send("Skipped the current song.")
    else:
        await bot_spam_channel.send("No song is currently playing.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


@bot.command(name="queue", description="Display the songs currently in the queue.")
async def queue(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    guild = ctx.guild
    if guild.id in bot.music_queues:
        server_queue = bot.music_queues[guild.id]
        if server_queue:
            queue_message = "Songs in queue:\n"
            for index, (query, url, _) in enumerate(server_queue, start=1):
                queue_message = f"{index}. {query} {url} \n"
                await bot_spam_channel.send(queue_message)
        else:
            await bot_spam_channel.send("The queue is currently empty.")
    else:
        await bot_spam_channel.send("The queue is currently empty.")
    if ctx.channel != bot_spam_channel:
        await ctx.message.delete()


async def create_player(url):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: ytdl.extract_info(url, download=False)
    )
    song = data["url"]

    player = discord.FFmpegPCMAudio(
        song, **ffmpeg_options, executable="G:\\ffmpeg\\bin\\ffmpeg.exe"
    )
    return player


async def create_playerVLControl(url, volume):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: ytdl.extract_info(url, download=False)
    )
    song = data["url"]
    optionsVL = {
        "before_options": f"--reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 ",
        "options": f"-vn ",
    }

    player = discord.PCMVolumeTransformer(
        discord.FFmpegPCMAudio(
            song, **optionsVL, executable="G:\\ffmpeg\\bin\\ffmpeg.exe"
        )
    )

    return player


bot.music_queues = {}  # Server-specific song queues


async def play_next_song(guild):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = guild.voice_client
    server_queue = bot.music_queues.get(guild.id, [])

    if server_queue:
        if voice_client.is_playing() or voice_client.is_paused():
            return
        (query, url, author) = server_queue[0]

        player = await create_player(url)
        global current_track
        current_track = url
        global current_author
        current_author = author
        await bot_spam_channel.send(
            f"Now Playing:{current_track} requested by {author}"
        )

        def after_playing(error):
            if error:
                print(f"Error playing next song: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(guild), bot.loop)

        voice_client.play(player, after=after_playing)
        del server_queue[0]
        bot.music_queues[guild.id] = server_queue
    else:
        print(f"Queue is empty")
        bot.music_queues.pop(guild.id, None)


@bot.command(
    name="play_now",
    description="Play a specific link immediately and continue the queue afterward.",
)
async def play_now(ctx: commands.Context, *, query):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    voice_client = ctx.guild.voice_client
    url = findYT(query)
    global current_track
    current_track = url
    global current_author
    current_author = ctx.author

    if (
        voice_client
        and voice_client.is_connected()
        and (voice_client.is_playing() or voice_client.is_paused())
    ):
        server_queue = bot.music_queues.get(ctx.guild.id, [])
        server_queue.insert(0, (query, url, ctx.author))
        bot.music_queues[ctx.guild.id] = server_queue
        voice_client.stop()

    else:
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            await bot_spam_channel.send("You are not in a voice channel.")
            return
        if not voice_client or not voice_client.is_connected():
            voice_client = await channel.connect()

            player = await create_player(url)

        def after_playing(error):
            if error:
                print(f"Error playing next song: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(ctx.guild), bot.loop)

            voice_client.play(player, after=after_playing)

        await bot_spam_channel.send(
            f"Now Playing:{current_track}  requested by {ctx.author}"
        )


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Please use a real command retor. See !help")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing args retor")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("hahaha no perms retor")
    else:
        await ctx.send("I fucked it ping JJ pls")
        print(f"{error}")


@bot.command(name="insult", description="Insult a user on the server.")
async def insult(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send("Self-insulting is not allowed.")
    else:
        with open("insult.txt", "r") as file:
            insults = file.readlines()
        insults = [insult.strip() for insult in insults if insult.strip()]
        if not insults:
            await ctx.send("No insults found.")
        else:
            insult = random.choice(insults)
            await ctx.send(f"{member.mention} is a {insult}.")


@bot.command(name="divinitywhen", description="ping all to play divinity")
async def divinitywhen(ctx):
    await ctx.send("@everyone divinity when")
    await ctx.send(
        "https://tenor.com/view/divinity-original-sin2-divinty-hop-on-divinty-divinty-now-primo-mafioso-gif-24888241"
    )


@bot.command(name="xp", description="xp")
async def xp(ctx):
    await ctx.send("HOLY XP DUMP")
    await ctx.send(
        "https://cdn.discordapp.com/attachments/1104485229474893974/1105100082640068608/xpdump.png"
    )


afk = []


@bot.command(name="shoot", description="move user to afk")
async def shoot(ctx, member: discord.Member):
    bot_spam_channel = bot.get_channel(1104485229474893974)
    afk_channel = discord.utils.get(ctx.guild.voice_channels, name="afk")
    if afk_channel is None:
        await bot_spam_channel.send("AFK voice channel not found.")
        return
    if member.voice is None:
        await bot_spam_channel.send(f"{member.display_name} is not in a voice channel.")
        return
    afk.append((member.id, member.voice.channel))

    await member.move_to(afk_channel)
    await bot_spam_channel.send(
        f"{member.display_name} has been moved to the AFK channel."
    )


@bot.command(name="unshoot", description="move self to active voicechannel")
async def unshoot(ctx):
    bot_spam_channel = bot.get_channel(1104485229474893974)

    for id, channel in afk:
        if id == ctx.author.id:
            await ctx.author.move_to(channel)
            afk.remove((id, channel))

    await bot_spam_channel.send(
        f"{ctx.author.display_name} has been moved to the active voice channel channel."
    )


@bot.command(name="add", description="Add a command dynamically.")
async def add(ctx, command_name, *, command_content):
    for command in bot.commands:
        if command_name == command.name:
            await ctx.send("Already an OG command. Can't use this bucko")
            return
    if command_name in dynamic_commands:
        await ctx.send("Already an added command. Can't use this bucko")
        return
    dynamic_commands[command_name] = command_content
    await ctx.send(f"Command '{command_name}' added dynamically.")

    with open(COMMANDS_FILE, "w", encoding="utf-8") as file:
        json.dump(dynamic_commands, file, indent=4)


@bot.command(name="edit", description="Edit a command dynamically.")
async def edit(ctx, command_name, *, command_content):
    if command_name not in dynamic_commands:
        await ctx.send("Not a dynamic command.")
        return
    dynamic_commands[command_name] = command_content
    await ctx.send(f"Command '{command_name}' updated.")

    with open(COMMANDS_FILE, "w", encoding="utf-8") as file:
        json.dump(dynamic_commands, file, indent=4)


@bot.command(name="delete", description="Delete a dynamic command.")
async def delete(ctx, command_name):
    if command_name not in dynamic_commands:
        await ctx.send("Not a dynamic command.")
        return
    del dynamic_commands[command_name]
    await ctx.send(f"Command '{command_name}' has been deleted.")

    with open(COMMANDS_FILE, "w", encoding="utf-8") as file:
        json.dump(dynamic_commands, file, indent=4)


@bot.command(name="list", description="List all dynamically added commands.")
async def list(ctx):
    commands_list = "\n".join(dynamic_commands.keys())
    await ctx.send(f"List of dynamically added commands:\n{commands_list}")


@bot.command(name="edit_emote", description="Edit an existing emote.")
async def edit_emote(ctx, trigger, *, emote_link):
    if trigger not in triggers:
        await ctx.send("Emote does not exist. Can't edit.")
        return
    triggers[trigger] = emote_link
    await ctx.send(f"Emote '{trigger}' edited successfully.")

    with open(EMOTE_FILE, "w", encoding="utf-8") as file:
        json.dump(triggers, file, indent=4)


@bot.command(name="add_emote", description="Add an emote dynamically.")
async def add_emote(ctx, trigger, *, emote_link):
    if trigger in triggers:
        await ctx.send("Already an emote. Can't use this bucko")
        return
    triggers[trigger] = emote_link
    await ctx.send(f"Command '{trigger}' added dynamically.")

    with open(EMOTE_FILE, "w", encoding="utf-8") as file:
        json.dump(triggers, file, indent=4)


@bot.command(name="delete_emote", description="Delete an existing emote.")
async def delete_emote(ctx, trigger):
    if trigger not in triggers:
        await ctx.send("Emote does not exist. Can't delete.")
        return
    del triggers[trigger]
    await ctx.send(f"Emote '{trigger}' deleted successfully.")

    with open(EMOTE_FILE, "w", encoding="utf-8") as file:
        json.dump(triggers, file, indent=4)


@bot.command(name="list_emotes", description="List all emotes")
async def list_emotes(ctx):
    triggers_list = "\n".join(triggers.keys())
    await ctx.send(f"List of dynamically added commands:\n{triggers_list}")


@bot.command(name="create_emoji", description="add emoji to server")
async def create_emoji(ctx: commands.Context, name, image_link: str):
    if not (
        image_link.endswith(".jpg")
        or image_link.endswith(".jpeg")
        or image_link.endswith(".png")
        or image_link.endswith(".webp")
    ):
        await ctx.send(f"Not a jpg or a png")
        return
    if image_link.endswith(".jpg") or image_link.endswith(".jpeg"):
        format = "JPEG"
    elif image_link.endswith(".png"):
        format = "PNG"
    elif image_link.endswith(".webp"):
        format = "png"
        file_name = f"{EMOJI_FOLDER}\\{name}.png"
        img = Image.open(requests.get(image_link, stream=True).raw).convert()
        img.save(fp=file_name, format=format)
        with open(file_name, "rb") as image:
            byte_image = image.read()
            await ctx.guild.create_custom_emoji(name=name, image=byte_image)
            return
    file_name = f"{EMOJI_FOLDER}\\{name}.{format.lower()}"
    img = Image.open(requests.get(image_link, stream=True).raw)
    img.save(fp=file_name, format=format)
    with open(file_name, "rb") as image:
        byte_image = image.read()
        await ctx.guild.create_custom_emoji(name=name, image=byte_image)


@bot.command(name="delete_emoji", description="deletes a emoji")
async def delete_emoji(ctx: commands.Context, name):
    for emoji in ctx.guild.emojis:
        if emoji.name == name:
            await emoji.delete()
            return
    await ctx.send(f"No emoji named {name} is in the list. Check your spelling :)))")


@bot.command(name="showme", description="posts random image/gif")
async def showme(ctx: commands.Context, *, name):
    lines = []
    title = name.lower()
    start_found = False
    with open(SHOWME_FILE, "r") as file:
        for line in file:
            line = line.strip()
            if title == line[:-1]:
                start_found = True
                continue
            elif line.endswith(":") and start_found:
                break
            elif start_found:
                lines.append(line)
    if lines:
        await ctx.send(random.choice(lines))
        await ctx.send(random.choice(lines))

    else:
        await ctx.send(
            f"{name} is not yet showable. Send image and gif links to JJ and pray"
        )


@bot.command(name="showme_help", description="display possible showme's")
async def showme(ctx: commands.Context):
    titles = []
    with open(SHOWME_FILE, "r") as file:
        for line in file:
            line = line.strip()
            if line.endswith(":"):
                titles.append(line[:-1])
    await ctx.send(f"possible showme's so far:\n{titles}")


@bot.command(name="memerater", description="rates your meme")
async def memerater(ctx: commands.Context):
    if ctx.author.id == 205628227559882752:
        score = random.randint(7, 10)
    else:
        score = random.randint(0, 10)
    await ctx.send(f"{score}/10 Nice Job :)))")


@bot.event
async def on_message(message):
    # Check if the message starts with the prefix and a dynamically added command
    if message.content.startswith(PREFIX):
        command_name = message.content[len(PREFIX) :].split()[0]
        for command in bot.commands:
            if command_name == command.name:
                await bot.process_commands(message)
                return

        if command_name not in dynamic_commands:
            await message.channel.send("Unknown Command retor")
            return

        else:
            command_content = dynamic_commands[command_name]
            await message.channel.send(f"{command_content}")
            for command in bot.commands:
                if command_content[1:].startswith(command.name):
                    message.content = command_content
                    print(f"processing {message}")
                    await bot.process_commands(message)
                    return
    if not message.author.bot:
        for trigger, emote in triggers.items():
            if trigger.lower() == message.content.lower():
                # Delete the triggering message
                await message.delete()
                await message.channel.send(emote)
                return


bot.run(TOKEN)
