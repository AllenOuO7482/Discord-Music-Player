# Standard library imports
import asyncio
import json
import os
import random
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path
import multiprocessing
import queue
import signal

# Third-party imports
import discord
import spotipy
import yt_dlp as youtube_dl
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ui import Button, View

# Local Files
from ytdl_source import ytdl_format_options, ffmpeg_options

with open('settings.json', 'r') as f:
    settings = json.load(f)

ENABLE_SPOTIFY = settings['ENABLE_SPOTIFY']
ENABLE_YOUTUBE = settings['ENABLE_YOUTUBE']
BUTTON_TIMEOUT = settings['BUTTON_TIMEOUT']

# reset music folder
for file in Path(__file__).parent.glob('*.mp3'):
    file.unlink()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='?', intents=intents)

# Add a music queue for each guild, repeat queue, and repeat song
music_queues = {}
repeat_queue = {}
repeat_song = {}

# bot ready event
@bot.event
async def on_ready():
    """
    Event handler that runs when the bot is ready and connected to Discord.
    """
    print(f'{bot.user.name} has connected to Discord!')

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
            music_queues[member.guild.id].clear()
            await voice_client.disconnect()

# join/quit command
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

# song manipulation commands
@bot.command(name='play', help='To play song or add to queue')
async def play(ctx, url):
    try:
        voice_client = ctx.message.guild.voice_client
        
        if not voice_client:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                if ctx.guild.id in music_queues:
                    music_queues[ctx.guild.id].clear() 

                voice_client = await channel.connect()
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

        guild_id = ctx.guild.id
        if guild_id not in music_queues:
            music_queues[guild_id] = deque()

        async with ctx.typing():
            if "spotify.com" in url and ENABLE_SPOTIFY:
                track_name, artist_name = get_spotify_track_info(url)
                query = f"{track_name} {artist_name}"
            elif ENABLE_YOUTUBE:
                query = url
            else:
                embed = discord.Embed(title="Error:", description=f"Unable to process {url}. Please try another URL.", color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

            # Use multiprocessing to download music and put guild_id in task_queue
            task_queue.put((query, guild_id))
            
            # Wait for the download to complete
            while True:
                try:
                    title, filename, processed_guild_id = music_queue.get_nowait()
                    if processed_guild_id == guild_id:
                        break
                    else:
                        # Put back the item if it's for a different guild
                        music_queue.put((title, filename, processed_guild_id))
                except queue.Empty:
                    await asyncio.sleep(1)  # Wait for a second before checking again

        if filename is None:
            embed = discord.Embed(title="Error:", description=f"Unable to get filename for {url}. Please try another URL.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            return

        music_queues[guild_id].append((title, filename))
        
        embed = discord.Embed(title='Added to queue:', description=title, color=discord.Color.blue())
        await ctx.send(embed=embed)

        if not voice_client.is_playing():
            await play_next(ctx)

    except Exception as e:
        if str(e) != 'Already playing audio.':
            embed = discord.Embed(title="An error occurred:", description=str(e), color=discord.Color.blue())
            await ctx.send(embed=embed)
            traceback.print_exc()

async def play_next(ctx):
    """
    Play the next song in the queue.
    
    :param ctx: The context of the command invocation
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        voice_client = ctx.voice_client
        
        current_song = music_queues[guild_id][0]
        title, filename = current_song
        print(f"\nDebug: Current queue: {music_queues[guild_id]}\nCurrent song: {title}\n")
        
        if filename is None:
            print(f"Error: Filename is None for song '{title}'")
            embed = discord.Embed(title="Error:", description=f"Unable to play '{title}'. Skipping to next song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await play_next(ctx)
            return

        try:
            absolute_filename = os.path.abspath(filename)
            print(f"Debug: Playing {absolute_filename} with FFmpeg at {settings['ffmpeg_path']}")
            player = discord.FFmpegPCMAudio(absolute_filename, **ffmpeg_options, executable=settings['ffmpeg_path'])
        
        except Exception as e:
            print(f"Error creating FFmpegPCMAudio for '{title}': {e}")
            traceback.print_exc()
            embed = discord.Embed(title="Error:", description=f"Unable to play '{title}'. Skipping to next song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await play_next(ctx)
            return
        
        def after_playing(error):
            if error:
                print(f'Player error: {error}')
                traceback.print_exc()
            
            if not repeat_song.get(guild_id, False):
                if not hasattr(ctx, 'skip_direction'):
                    ctx.skip_direction = "next"

                print(f"Debug: skip_direction: {ctx.skip_direction}")

                if repeat_queue.get(guild_id, False):
                    if ctx.skip_direction == "back":
                        # Move the played song to the end of the queue
                        played_song = music_queues[guild_id].pop()
                        music_queues[guild_id].appendleft(played_song)
                    if ctx.skip_direction == "next":
                        # Move the played song to the end of the queue
                        played_song = music_queues[guild_id].popleft()
                        music_queues[guild_id].append(played_song)
                else:
                    # Remove the played song if not in repeat queue mode
                    if ctx.skip_direction == "back":
                        music_queues[guild_id].popleft()
                        # Move the played song to the end of the queue
                        played_song = music_queues[guild_id].pop()
                        music_queues[guild_id].appendleft(played_song)
                    if ctx.skip_direction == "next":
                        music_queues[guild_id].pop()
            
            # # Use the skip direction if set, otherwise default to "next"
            # next_direction = getattr(ctx, 'skip_direction', 'next')
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        voice_client.play(player, after=after_playing)
        
        # Create buttons for pause, skip, and repeat
        pause_button = Button(label="⏸️", style=discord.ButtonStyle.primary, custom_id="pause_button")
        skip_button = Button(label="⏩️", style=discord.ButtonStyle.primary, custom_id="skip_button")
        repeat_queue_button = Button(label="Queue 🔄", style=discord.ButtonStyle.primary, custom_id="repeat_queue_button")
        repeat_song_button = Button(label="Song 🔂️", style=discord.ButtonStyle.primary, custom_id="repeat_song_button")

        async def pause_button_callback(interaction: discord.Interaction):
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.response.defer()
                await pause_resume(ctx)
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)

        async def skip_button_callback(interaction: discord.Interaction):
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.response.defer()
                await skip(ctx)
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)
        
        async def repeat_queue_button_callback(interaction: discord.Interaction):
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.response.defer()
                await repeat_queue_toggle(ctx)
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)

        async def repeat_song_button_callback(interaction: discord.Interaction):
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.response.defer()
                await repeat_song_toggle(ctx)
            else:
                embed = discord.Embed(title="You need to be in a voice channel to use this command.", color=discord.Color.blue())
                await ctx.send(embed=embed)

        pause_button.callback = pause_button_callback
        skip_button.callback = skip_button_callback
        repeat_queue_button.callback = repeat_queue_button_callback
        repeat_song_button.callback = repeat_song_button_callback

        view = View(timeout=settings['BUTTON_TIMEOUT'])
        view.add_item(pause_button)
        view.add_item(skip_button)
        view.add_item(repeat_queue_button)
        view.add_item(repeat_song_button)

        embed = discord.Embed(title='Now playing:', description=title, color=discord.Color.blue())
        await ctx.send(embed=embed, view=view)
    else:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='pause', help='Pause or resume the song')
async def pause_resume(ctx):
    """
    Command to pause the currently playing audio or resume if paused.
    
    :param ctx: The context of the command invocation
    """
    voice_client = ctx.message.guild.voice_client
    if voice_client:
        if voice_client.is_playing():
            embed = discord.Embed(title="Paused the song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
            await voice_client.pause()
        elif voice_client.is_paused():
            embed = discord.Embed(title="Resumed the song.", color=discord.Color.blue())
            await ctx.send(embed=embed)  
            await voice_client.resume()
        else:
            embed = discord.Embed(title="The bot is not playing anything at the moment.", color=discord.Color.blue())
            await ctx.send(embed=embed) 
    else:
        embed = discord.Embed(title="The bot is not connected to a voice channel.", color=discord.Color.blue())
        await ctx.send(embed=embed)

@bot.command(name='skip', help='Skip the current song')
async def skip(ctx, direction: str = "next"):
    """
    Command to skip the currently playing song.
    
    :param ctx: The context of the command invocation
    :param direction: The direction to move in the queue ("next" or "back")
    """
    # TODO "?skip back" doesn't work
    try:
        voice_client = ctx.message.guild.voice_client
        if voice_client and voice_client.is_playing():
            # Set a flag to indicate the skip direction
            ctx.skip_direction = direction
            voice_client.stop()  # This will trigger the after_playing callback
            embed = discord.Embed(title=f"Skipped {'to previous' if direction == 'back' else 'the current'} song.", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="The bot is not playing anything at the moment.", color=discord.Color.blue())
            await ctx.send(embed=embed)
    except Exception as e:
        if str(e) != 'Already playing audio.':
            embed = discord.Embed(title="An error occurred:", description=str(e), color=discord.Color.blue())
            await ctx.send(embed=embed)
            traceback.print_exc()

# queue manipulation commands
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

@bot.command(name='shuffle', help='Shuffle the current queue')
async def shuffle(ctx):
    """
    Command to shuffle the current queue.
    
    :param ctx: The context of the command invocation
    """
    def shuffle_queue(guild_id):
        if guild_id in music_queues and len(music_queues[guild_id]) > 1:
            current_song = music_queues[guild_id][0]
            rest_of_queue = list(music_queues[guild_id])[1:]
            random.shuffle(rest_of_queue)
            music_queues[guild_id] = deque([current_song] + rest_of_queue)

    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        shuffle_queue(guild_id)
        embed = discord.Embed(title="The queue has been shuffled.", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="The queue is empty.", color=discord.Color.blue())
        await ctx.send(embed=embed)

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

# repeat manipulation commands
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

# ping command
@bot.command(name='ping', help='Test bot responsiveness')
async def ping(ctx):
    """
    Command to test the bot's responsiveness and check the latency.
    
    :param ctx: The context of the command invocation
    """

    message_timestamp = ctx.message.created_at
    current_time = datetime.now(message_timestamp.tzinfo)
    time_difference = current_time - message_timestamp
    embed = discord.Embed(title='Pong!', description=f'Latency: {time_difference.total_seconds() * 1000:.2f} ms', color=discord.Color.blue())
    await ctx.send(embed=embed)

# music downloader functions
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=settings['spotify_client_id'], client_secret=settings['spotify_client_secret']))

def get_spotify_track_info(track_url):
    track_id = track_url.split("/")[-1].split("?")[0]
    track = sp.track(track_id)
    return track['name'], track['artists'][0]['name']

def download_from_youtube(query, guild_id, music_queue):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',  # Change filename format
        'ffmpeg_location': settings['ffmpeg_path'],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            if "youtube.com" in query or "youtu.be" in query:
                info_dict = ydl.extract_info(query, download=True)
            else:
                info_dict = ydl.extract_info(f"ytsearch:{query}", download=True)
                if 'entries' in info_dict:
                    info_dict = info_dict['entries'][0]
            title = info_dict.get('title', 'Unknown Title')
            filename = f"{title}.mp3"
            print(f"Debug: Downloaded music: {title}, Filename: {filename}, Guild ID: {guild_id}")
            music_queue.put((title, filename, guild_id))
        except Exception as e:
            print(f"Error downloading {query}: {e}")
            music_queue.put((query, None, guild_id))

def music_processor(task_queue, music_queue):
    while True:
        item = task_queue.get()
        if item is None:  # Poison pill to shut down the process
            break
        print(f"Debug: item: {item}")   
        query, guild_id = item
        download_from_youtube(query, guild_id, music_queue)

def shutdown_handler(signal, frame):
    """
    Handler to clean up resources when the program is terminated.
    """
    for voice_client in bot.voice_clients:
        asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop)
    bot.loop.stop()

def main():
    global task_queue, music_queue
    task_queue = multiprocessing.Queue()
    music_queue = multiprocessing.Queue()

    # Start the music processor
    process = multiprocessing.Process(target=music_processor, args=(task_queue, music_queue), daemon=True)
    process.start()

    # Example: Add tasks to the task queue
    # music_url = 'http://example.com/music.mp3'
    # task_queue.put((music_url, None))

    # title, filename, guild_id = music_queue.get()
    # print(f"Downloaded music: {title}, Filename: {filename}")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    main()
    # Run the bot using the token from the settings file
    bot.run(settings['token'])
