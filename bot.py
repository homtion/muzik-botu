import os
import sys
import shutil
from collections import deque
import discord
from discord.ext import commands
import yt_dlp

# --- WINDOWS / LINUX UYUMLULUĞU ---
ffmpeg_bin_path = r'C:\ffmpeg\bin'
if os.path.exists(ffmpeg_bin_path):
    os.environ['PATH'] = ffmpeg_bin_path + os.pathsep + os.environ['PATH']

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

queue = deque()
current_song = None
volume = 0.02
is_looping = False

@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yaptı')
    activity = discord.Activity(type=discord.ActivityType.listening, name="/yardım")
    await bot.change_presence(activity=activity)
    await bot.tree.sync()
    print("Slash komutlar senkronize edildi")

class MusicButtons(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    @discord.ui.button(label="Geri", style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
    
    @discord.ui.button(label="Duraklat", style=discord.ButtonStyle.blurple)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Duraklatıldı", ephemeral=True, delete_after=2)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Geç", style=discord.ButtonStyle.blurple)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("Geçildi", ephemeral=True, delete_after=2)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Döngü", style=discord.ButtonStyle.blurple)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global is_looping
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        is_looping = not is_looping
        status = "Açık" if is_looping else "Kapalı"
        await interaction.response.send_message(f"Döngü: {status}", ephemeral=True, delete_after=2)
    
    @discord.ui.button(label="Durdur", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            queue.clear()
            await interaction.response.send_message("Bağlantı Kesildi", ephemeral=True, delete_after=2)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Devam Et", style=discord.ButtonStyle.green)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("Devam Ediliyor", ephemeral=True, delete_after=2)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.blurple)
    async def playlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        
        if not queue:
            await interaction.response.send_message("Şarkı Listesi Boş", ephemeral=True)
            return
        
        liste = "\n".join([f"{i}. {title}" for i, (url, title) in enumerate(queue, 1)])
        embed = discord.Embed(title="Şarkı Listesi", description=liste, color=discord.Color.blue())
        embed.set_footer(text=f"Toplam {len(queue)} şarkı")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="yardım", description="Bot komutlarını gösterir")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Yardım Merkezi",
        description="Lütfen aşağıdan bilgi almak istediğiniz kategoriyi seçin.",
        color=discord.Color.green()
    )
    
    embed.add_field(name="/play <şarkı>", value="Şarkı oynat", inline=False)
    embed.add_field(name="/pause", value="Durakla", inline=False)
    embed.add_field(name="/resume", value="Devam et", inline=False)
    embed.add_field(name="/skip", value="Geç", inline=False)
    embed.add_field(name="/liste", value="Şarkı listesini gör", inline=False)
    embed.add_field(name="/stop", value="Durdur", inline=False)
    embed.add_field(name="/volume <0-100>", value="Ses seviyesini ayarla", inline=False)
    embed.add_field(name="/durum <metin>", value="Bot durumu ayarla", inline=False)
    embed.add_field(name="/restart", value="Yeniden başlat", inline=False)
    
    embed.set_footer(text="Müzik Botu v1.0")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="play", description="Şarkı oynat")
async def play(interaction: discord.Interaction, şarkı: str):
    global current_song
    
    await interaction.response.defer()
    
    if not interaction.user.voice:
        await interaction.followup.send("Ses kanalına katıl!")
        return
    
    channel = interaction.user.voice.channel
    
    if interaction.guild.voice_client is None:
        voice = await channel.connect()
    else:
        voice = interaction.guild.voice_client
    
    embed = discord.Embed(title="Şarkı Aranıyor", description=f"'{şarkı}' aranıyor...", color=discord.Color.blue())
    msg = await interaction.followup.send(embed=embed)
    
    ydl_opts = {'format': 'bestaudio/best', 'quiet': False, 'socket_timeout': 30, 'http_headers': {'User-Agent': 'Mozilla/5.0'}}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{şarkı}", download=False)
            url = info['entries'][0]['url']
            title = info['entries'][0]['title']
        
        queue.append((url, title))
        
        embed = discord.Embed(title="Şarkı Listeye Eklendi", description=title, color=discord.Color.green())
        await msg.edit(embed=embed)
        
        if not voice.is_playing():
            await play_next(voice, interaction)
    except Exception as e:
        embed = discord.Embed(title="Hata", description=str(e)[:100], color=discord.Color.red())
        await msg.edit(embed=embed)

async def play_next(voice, interaction):
    global current_song
    
    if queue:
        url, title = queue.popleft()
        current_song = title
        
        ffmpeg_exe = shutil.which("ffmpeg") or "ffmpeg"
        
        raw_source = discord.FFmpegPCMAudio(
            url, 
            executable=ffmpeg_exe, 
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        )
        source = discord.PCMVolumeTransformer(raw_source, volume=volume)
        
        voice.play(source, after=lambda e: bot.loop.create_task(play_next(voice, interaction)))
        
        embed = discord.Embed(title="MÜZIK PANELİ", description=title, color=discord.Color.purple())
        embed.add_field(name="İstek Sahibi", value=interaction.user.mention, inline=True)
        embed.add_field(name="Şarkı Listesi", value=f"{len(queue)} şarkı", inline=True)
        
        view = MusicButtons(interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="pause", description="Müziği duraklat")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("Duraklatıldı")
    else:
        await interaction.response.send_message("Müzik oynatılmıyor")

@bot.tree.command(name="resume", description="Müziği devam et")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("Devam Ediliyor")
    else:
        await interaction.response.send_message("Duraklatılmış müzik yok")

@bot.tree.command(name="skip", description="Sonraki şarkıya geç")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Geçildi")
    else:
        await interaction.response.send_message("Müzik oynatılmıyor")

@bot.tree.command(name="liste", description="Şarkı listesini göster")
async def show_queue(interaction: discord.Interaction):
    if not queue:
        embed = discord.Embed(title="Şarkı Listesi Boş", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        return
    
    liste = "\n".join([f"{i}. {title}" for i, (url, title) in enumerate(queue, 1)])
    embed = discord.Embed(title="Şarkı Listesi", description=liste, color=discord.Color.blue())
    embed.set_footer(text=f"Toplam {len(queue)} şarkı")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Botu durdur")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        queue.clear()
        await interaction.response.send_message("Bağlantı Kesildi")
    else:
        await interaction.response.send_message("Bot ses kanalında değil")

@bot.tree.command(name="volume", description="Ses seviyesini ayarla (0-100)")
async def set_volume(interaction: discord.Interaction, level: int):
    global volume
    
    if level < 0 or level > 100:
        embed = discord.Embed(title="Hata", description="Ses 0-100 arasında olmalı!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    volume = level / 100
    
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = volume
    
    embed = discord.Embed(title="Ses Ayarlandı", description=f"Ses {level}% olarak ayarlandı", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="durum", description="Bota durum mesajı ekle")
async def set_status(interaction: discord.Interaction, metin: str):
    activity = discord.Activity(type=discord.ActivityType.listening, name=metin)
    await bot.change_presence(activity=activity)
    embed = discord.Embed(title="Durum Güncellendi", description=f"Durum: {metin}", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="restart", description="Botu yeniden başlat")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("Yeniden başlatılıyor...")
    os.execl(sys.executable, sys.executable, *sys.argv)

token = os.getenv('DISCORD_TOKEN')
bot.run(token)