import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import json
from collections import deque
import random
import traceback
import os
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time

# Load settings from a JSON file
with open('settings.json', 'r') as f:
    settings = json.load(f)

ENABLE_SPOTIFY = settings['ENABLE_SPOTIFY']
ENABLE_YOUTUBE = settings['ENABLE_YOUTUBE']

# delete all .mp3 files in the current directory
for file in Path(__file__).parent.glob('*.mp3'):
    file.unlink()

# Set up Discord bot intents
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot with a command prefix and intents
bot = commands.Bot(command_prefix='?', intents=intents)

# Suppress youtube_dl bug reports
youtube_dl.utils.bug_reports_message = lambda: ''

# Configuration for youtube_dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # Bind to ipv4 since ipv6 addresses cause issues sometimes
    'force-ipv4': True,
    'preferredcodec': 'mp3',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'ffmpeg_location': settings['ffmpeg_path'],  # Added FFmpeg location
}

# FFmpeg options for audio processing
ffmpeg_options = {
    'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

# Create a youtube_dl object with the specified options
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Custom audio source class for YouTube downloads
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = data.get('filename', None)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        ytdl_opts = ytdl_format_options.copy()
        ytdl_opts['ffmpeg_location'] = settings['ffmpeg_path']
        ytdl = youtube_dl.YoutubeDL(ytdl_opts)
        
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if data is None:
                print(f"Error: Unable to extract info for {url}")
                return None

            if 'entries' in data:
                data = data['entries'][0]

            if stream:
                filename = data['url']
            else:
                filename = ytdl.prepare_filename(data)
                filename = os.path.splitext(filename)[0] + ".mp3"
                data['filename'] = filename

            absolute_filename = os.path.abspath(filename)
            print(f"Debug: Filename for {url} is {absolute_filename}") 

            if not os.path.isfile(absolute_filename):
                print(f"Error: File {absolute_filename} does not exist.")
                return None

            return cls(discord.FFmpegPCMAudio(absolute_filename, executable=settings['ffmpeg_path'], **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Error in from_url: {e}")
            traceback.print_exc()
            return None

# Assuming you have a queue implementation
class MusicQueue:
    def __init__(self):
        self.queue = deque()

    def add_to_queue(self, title, filename):
        self.queue.append((title, filename))

    def get_next(self):
        if self.queue:
            return self.queue.popleft()
        return None

# Example usage
music_queue = MusicQueue()

async def play_next_song():
    next_song = music_queue.get_next()
    if next_song:
        title, filename = next_song
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options, executable=settings['ffmpeg_path'])
        # Play the source
        # ...

# Adding a song to the queue
async def add_song_to_queue(url):
    loop = asyncio.get_event_loop()  # Get the current event loop
    source = await YTDLSource.from_url(url, loop=loop, stream=False)
    if source:
        music_queue.add_to_queue(source.title, source.filename)

# Add a music queue for each guild
music_queues = {}

# Add flags for repeat modes and a shuffle function
repeat_queue = {}
repeat_song = {}

def shuffle_queue(guild_id):
    if guild_id in music_queues and len(music_queues[guild_id]) > 1:
        current_song = music_queues[guild_id][0]
        rest_of_queue = list(music_queues[guild_id])[1:]
        random.shuffle(rest_of_queue)
        music_queues[guild_id] = deque([current_song] + rest_of_queue)

# Modify the play_next function to handle skipping
async def play_next(ctx):
    """
    Play the next song in the queue.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        voice_client = ctx.voice_client
        
        current_song = music_queues[guild_id][0]  # choose the first song in the queue, but not remove it from the queue
        title, filename = current_song
        
        if filename is None:
            print(f"Error: Filename is None for song '{title}'")
            embed = discord.Embed(title="Error:", description="Unable to play '{title}'. Skipping to next song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await play_next(ctx)
            return

        try:
            absolute_filename = os.path.abspath(filename)
            print(f"Debug: Playing {absolute_filename} with FFmpeg at {settings['ffmpeg_path']}")  # 新增的除錯訊息
            player = discord.FFmpegPCMAudio(absolute_filename, **ffmpeg_options, executable=settings['ffmpeg_path'])
        
        except Exception as e:
            print(f"Error creating FFmpegPCMAudio for '{title}': {e}")
            traceback.print_exc()
            embed = discord.Embed(title="Error:", description="Unable to play '{title}'. Skipping to next song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await play_next(ctx)
            return
        
        def after_playing(error):
            if error:
                print(f'Player error: {error}')
                traceback.print_exc()
            
            # manipulate the queue after playing
            if not repeat_song.get(guild_id, False):
                music_queues[guild_id].popleft()  # remove the played song
                if repeat_queue.get(guild_id, False):
                    # if repeat queue is enabled, add the played song to the end of the queue
                    music_queues[guild_id].append((title, filename))
            
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        voice_client.play(player, after=after_playing)
        embed = discord.Embed(title='Now playing:', description=title, color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='join', help='Joins a voice channel')
async def join(ctx):
    """
    Command to make the bot join the user's voice channel.
    
    :param ctx: The context of the command invocation
    """
    if not ctx.message.author.voice:
        embed = discord.Embed(title=f"{ctx.message.author.name} is not connected to a voice channel", color=discord.Color.blue())
        await ctx.send(embed=embed)
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.event
async def on_ready():
    """
    Event handler that runs when the bot is ready and connected to Discord.
    """
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='leave', help='To make the bot leave the voice channel')
async def leave(ctx):
    """
    Command to make the bot leave the current voice channel.
    
    :param ctx: The context of the command invocation
    """
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        embed = discord.Embed(title="The bot is not connected to a voice channel.", color=discord.Color.blue())
        await ctx.send(embed=embed)

# Spotify API verification
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=settings['spotify_client_id'], client_secret=settings['spotify_client_secret']))

def get_spotify_track_info(track_url):
    track_id = track_url.split("/")[-1].split("?")[0]
    track = sp.track(track_id)
    return track['name'], track['artists'][0]['name']

def download_from_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'ffmpeg_location': settings['ffmpeg_path'],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch:{query}"])

@bot.command(name='play', help='To play song or add to queue')
async def play(ctx, url):
    try:
        voice_client = ctx.message.guild.voice_client
        
        if not voice_client:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                voice_client = await channel.connect()
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

        if ctx.guild.id not in music_queues:
            music_queues[ctx.guild.id] = deque()

        async with ctx.typing():
            if "spotify.com" in url and ENABLE_SPOTIFY:
                track_name, artist_name = get_spotify_track_info(url)
                query = f"{track_name} {artist_name}"
                download_from_youtube(query)
                player = await YTDLSource.from_url(query, loop=bot.loop, stream=False)
            elif ENABLE_YOUTUBE:
                player = await YTDLSource.from_url(url, loop=bot.loop, stream=False)
            else:
                embed = discord.Embed(title="Error:", description=f"Unable to process {url}. Please try another URL.", color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

        if player is None:
            embed = discord.Embed(title="Error:", description=f"Unable to process {url}. Please try another URL.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            return

        if player.filename is None:
            embed = discord.Embed(title="Error:", description=f"Unable to get filename for {url}. Please try another URL.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            return

        music_queues[ctx.guild.id].append((player.title, player.filename))
        
        embed = discord.Embed(title='Added to queue:', description=player.title, color=discord.Color.blue())
        await ctx.send(embed=embed)

        if not voice_client.is_playing():
            await play_next(ctx)

    except Exception as e:
        if str(e) != 'Already playing audio.':
            embed = discord.Embed(title="An error occurred:", description=str(e), color=discord.Color.blue())
            await ctx.send(embed=embed)
            traceback.print_exc()

@bot.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    """
    Command to pause the currently playing audio.
    
    :param ctx: The context of the command invocation
    """
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_playing():
        await voice_client.pause()
    else:
        embed = discord.Embed(title="The bot is not playing anything at the moment.", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    """
    Command to resume paused audio.
    
    :param ctx: The context of the command invocation
    """
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_paused():
        await voice_client.resume()
    else:
        embed = discord.Embed(title="The bot was not playing anything before this. Use play command", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='stop', help='Stops the song')
async def stop(ctx):
    """
    Command to stop the currently playing audio.
    
    :param ctx: The context of the command invocation
    """
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_playing():
        await voice_client.stop()
    else:
        embed = discord.Embed(title="The bot is not playing anything at the moment.", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='ping', help='Test bot responsiveness')
async def ping(ctx):
    """
    Command to test the bot's responsiveness and check the latency.
    
    :param ctx: The context of the command invocation
    """

    message_timestamp = ctx.message.created_at
    current_time = time.time()
    time_difference = current_time - message_timestamp
    await ctx.send(f'Pong! Latency: {time_difference * 1000:.2f} ms')

@bot.command(name='queue', help='Show the current music queue')
async def show_queue(ctx):
    """
    Command to show the current music queue.
    
    :param ctx: The context of the command invocation
    """
    if ctx.guild.id not in music_queues or len(music_queues[ctx.guild.id]) == 0:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        queue_list = "\n".join([f"{i+1}. {song[0]}" for i, song in enumerate(music_queues[ctx.guild.id])])
        embed = discord.Embed(title="Current queue:", description=queue_list, color=discord.Color.blue())
        await ctx.send(embed=embed)

# Modify the on_voice_state_update event to use the new function
@bot.event
async def on_voice_state_update(member, before, after):
    """
    Event handler that runs when a member's voice state changes.
    Checks if the bot should disconnect from empty voice channels.
    
    :param member: The member whose voice state changed
    :param before: The voice state before the change
    :param after: The voice state after the change
    """
    voice_client = member.guild.voice_client
    if voice_client:
        if len(voice_client.channel.members) == 1:
            await voice_client.disconnect()

# Add commands for repeat queue and song modes
@bot.command(name='repeatqueue', help='Toggle repeat queue mode')
async def repeat_queue_toggle(ctx):
    """
    Command to toggle repeat queue mode.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    repeat_queue[guild_id] = not repeat_queue.get(guild_id, False)
    status = "enabled" if repeat_queue[guild_id] else "disabled"
    embed = discord.Embed(title=f"Repeat queue mode {status}", color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name='repeatsong', help='Toggle repeat song mode')
async def repeat_song_toggle(ctx):
    """
    Command to toggle repeat song mode.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    repeat_song[guild_id] = not repeat_song.get(guild_id, False)
    status = "enabled" if repeat_song[guild_id] else "disabled"
    embed = discord.Embed(title=f"Repeat song mode {status}", color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name='shuffle', help='Shuffle the current queue')
async def shuffle(ctx):
    """
    Command to shuffle the current queue.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        shuffle_queue(guild_id)
        embed = discord.Embed(title="The queue has been shuffled.", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)

# Add a skip command
@bot.command(name='skip', help='Skip the current song')
async def skip(ctx):
    """
    Command to skip the currently playing song.
    
    :param ctx: The context of the command invocation
    """
    try:
        voice_client = ctx.message.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            embed = discord.Embed(title="Skipped the current song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await play_next(ctx)
        else:
            embed = discord.Embed(title="The bot is not playing anything at the moment.", color=discord.Color.blue())
            await ctx.send(embed=embed)
    except Exception as e:
        if str(e) != 'Already playing audio.':
            embed = discord.Embed(title="An error occurred:", description=str(e), color=discord.Color.blue())
            await ctx.send(embed=embed)
            traceback.print_exc()

@bot.command(name='clear', help='Clear the current queue')
async def clear(ctx):
    """
    Command to clear the current music queue.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues:
        music_queues[guild_id].clear()
        embed = discord.Embed(title="The queue has been cleared.", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)

# Run the bot using the token from the settings file
bot.run(settings['token'])