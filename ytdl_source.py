import asyncio
import os
import traceback
import discord
import yt_dlp as youtube_dl
import json

# Load settings from a JSON file
with open('settings.json', 'r') as f:
    settings = json.load(f)

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