# Sandesh Discord Music Bot

A feature-rich Discord music bot written in Python using discord.py and yt_dlp. Plays high-quality music from YouTube and supports playlists, volume, lyrics, and more.

## Requirements
- **Python 3.8+**
- **discord.py[voice]** — Discord bot framework with voice support
- **yt-dlp** — YouTube and media downloader for extracting audio URLs
- **python-dotenv** — For loading the Discord token from a `.env` file
- **FFmpeg** — Must be installed and available in your system PATH (for audio streaming)

### Windows: Quick Install for yt-dlp and FFmpeg
If you are on Windows and have [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) installed, you can quickly install the required system tools with:
```sh
winget install --id=yt-dlp.yt-dlp  -e
winget install ffmpeg
```

## Setup
1. **Clone the repository**
2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```
3. **Create a `.env` file** in the `Sandesh` directory with your Discord bot token:
   ```env
   DISCORD_TOKEN=your-bot-token-here
   ```
4. **Run the bot**
   ```sh
   python bot.py
   ```

## Commands
| Command                | Alias | Description                                      |
|------------------------|-------|--------------------------------------------------|
| `!join`                |       | Join your voice channel                          |
| `!play <song/URL>`     | `!p`  | Play a song by name or URL, or a playlist        |
| `!pause`               |       | Pause playback                                   |
| `!resume`              |       | Resume playback                                  |
| `!stop`                |       | Stop and clear queue                             |
| `!skip`                |       | Skip to next song                                |
| `!queue`               | `!q`  | Show queue                                       |
| `!volume <0.1-2.0>`    |       | Set playback volume                              |
| `!lyrics [song name]`  |       | Get lyrics for current or given song             |
| `!leave`               |       | Leave the voice channel                          |
| `!helpme`              |       | Show help message                                |

## Notes
- The bot will leave the voice channel when the queue is empty.
- Volume can be set per guild (server).
- Lyrics are fetched using the [lyrics.ovh](https://lyrics.ovh/) API.
- For best results, ensure FFmpeg is installed and available in your system PATH.

## Example Usage
```
!join
!p Numb Linkin Park
!queue
!skip
!volume 1.5
!lyrics
!leave
```

---

Enjoy your music! 🎶 