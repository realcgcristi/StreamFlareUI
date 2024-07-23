import os
import logging
import requests
import tkinter as tk
from tkinter import filedialog, messagebox
from yt_dlp import YoutubeDL
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3
from pyfiglet import figlet_format
import customtkinter as ctk
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_filename(filename):
    """Sanitize the filename by replacing invalid characters."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)

def convert_file(input_file, output_file):
    """Convert the audio/video file using ffmpeg."""
    logging.info(f"Converting {input_file} to {output_file}")
    os.system(f"ffmpeg -i \"{input_file}\" \"{output_file}\"")
    os.remove(input_file)

def get_file_size(file_path):
    """Return the size of a file in megabytes."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    return os.path.getsize(file_path) / (1024 * 1024)  # Convert bytes to megabytes

def add_metadata_to_audio(file_path, title, artist, album=None, genre=None, year=None, thumbnail_url=None):
    """Add metadata to the audio file."""
    audio = EasyID3(file_path)
    audio['title'] = title
    audio['artist'] = artist
    if album:
        audio['album'] = album
    if genre:
        audio['genre'] = genre
    if year:
        audio['date'] = year
    audio.save()

    if thumbnail_url:
        thumbnail_data = requests.get(thumbnail_url).content
        audio = ID3(file_path)
        audio['APIC'] = APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc='Cover',
            data=thumbnail_data
        )
        audio.save()

def download_youtube(link, output_dir, file_format, custom_filename=None, user_agent=None, proxy=None, download_subtitles=False, log_callback=None):
    """Download a YouTube link with retries and additional options."""
    ydl_opts = {
        'format': 'bestaudio/best' if file_format in ['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus'] else 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(output_dir, 'temp.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'progress_hooks': [lambda d: log_callback(d)],
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': file_format, 'preferredquality': '192'}] if file_format in ['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus'] else [],
        'proxy': proxy,
        'headers': {'User-Agent': user_agent} if user_agent else {},
        'subtitleslangs': ['en'] if download_subtitles else []
    }
    
    temp_ext = 'webm' if file_format in ['mp4', 'mkv', 'avi', 'mov', 'flv', 'wmv', '3gp'] else file_format
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            video_title = info_dict.get('title', 'Unknown Title')
            video_uploader = info_dict.get('uploader', 'Unknown Uploader')
            thumbnail_url = info_dict.get('thumbnail')

            temp_file = os.path.join(output_dir, f'temp.{temp_ext}')
            final_filename = sanitize_filename(custom_filename) if custom_filename else sanitize_filename(f"{video_title}.{file_format}")
            final_file = os.path.join(output_dir, final_filename)

            if not os.path.exists(temp_file):
                raise FileNotFoundError(f"Temporary file {temp_file} does not exist.")

            os.rename(temp_file, final_file)
            
            if file_format in ['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus']:
                add_metadata_to_audio(final_file, video_title, video_uploader, thumbnail_url=thumbnail_url)

            return final_file

    except FileNotFoundError as fnf_error:
        logging.error(f"Failed to find temporary file: {fnf_error}")
        raise
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        raise

def show_log_window():
    """Create and show a new window for logs and progress."""
    log_window = ctk.CTkToplevel(root)
    log_window.title("Log and Progress")

    # Calculate main window position
    main_window_x = root.winfo_x()
    main_window_y = root.winfo_y()
    main_window_width = root.winfo_width()
    main_window_height = root.winfo_height()

    # Calculate log window position
    screen_width = log_window.winfo_screenwidth()
    screen_height = log_window.winfo_screenheight()

    log_window_width = 600
    log_window_height = 400

    log_window_x = main_window_x + main_window_width + 10
    log_window_y = main_window_y

    # Adjust position if the log window is out of screen bounds
    if log_window_x + log_window_width > screen_width:
        log_window_x = main_window_x - log_window_width - 10

    log_window.geometry(f"{log_window_width}x{log_window_height}+{log_window_x}+{log_window_y}")

    # Display ASCII art and welcome message
    ascii_art = generate_ascii_art()
    ascii_label = ctk.CTkLabel(log_window, text=ascii_art, font=("Courier", 12), justify=tk.LEFT, anchor="w")
    ascii_label.pack(pady=10)

    welcome_text = ("Welcome to the log of StreamFlare, here is everything that happens in the background when you\n download a YouTube video/audio/whatever format you want.\n")
    welcome_label = ctk.CTkLabel(log_window, text=welcome_text, font=("Courier", 10), justify=tk.LEFT, anchor="w")
    welcome_label.pack(pady=10)

    # Add a text widget for log and progress
    log_text = tk.Text(log_window, wrap=tk.WORD, height=15, width=80, font=("Courier", 12))
    log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Add a scrollbar
    scrollbar = tk.Scrollbar(log_window, command=log_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=scrollbar.set)

    # Redirect logging output to the text widget
    class LogHandler(logging.Handler):
        def __init__(self, text_widget):
            super().__init__()
            self.text_widget = text_widget

        def emit(self, record):
            log_entry = self.format(record)
            self.text_widget.insert(tk.END, log_entry + '\n')
            self.text_widget.see(tk.END)

    log_handler = LogHandler(log_text)
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(log_handler)

    # Show progress updates
    log_text.insert(tk.END, "Log window initialized.\n")
    log_text.insert(tk.END, "You can see download progress and logs here.\n")
    log_text.insert(tk.END, "If you get an error please report it to me on Discord (user: cgcristi) or on GitHub Issues at https://github.com/CristiGitHubber/StreamFlareUI/issues")

    return log_text

def generate_ascii_art():
    """Generate ASCII art for StreamFlare."""
    return figlet_format("StreamFlare", font='small')

def download_thread(link, file_format, output_dir, custom_filename, user_agent, proxy, open_after_download, download_subtitles, log_text):
    """Run the download process in a separate thread."""
    try:
        def log_callback(d):
            """Update log text widget based on progress data."""
            if d['status'] == 'downloading':
                log_text.insert(tk.END, f"Downloading: {d['_percent_str']} {d['_eta_str']}\n")
                log_text.see(tk.END)
            elif d['status'] == 'finished':
                log_text.insert(tk.END, "Download finished.\n")
                log_text.see(tk.END)
        
        final_file = download_youtube(
            link, output_dir, file_format, custom_filename, user_agent, proxy, download_subtitles, log_callback
        )
        log_text.insert(tk.END, f"Downloaded and saved as {final_file}\n")
        log_text.see(tk.END)

        if open_after_download:
            os.system(f'start {final_file}')
    
    except Exception as e:
        log_text.insert(tk.END, f"Error occurred: {e}\n")
        log_text.see(tk.END)

def start_download(link_entry, format_var, output_dir_entry, filename_entry, user_agent_entry, proxy_entry, open_after_download_var, download_subtitles_var):
    """Start the download process based on user inputs."""
    link = link_entry.get()
    file_format = format_var.get()
    output_dir = output_dir_entry.get()
    custom_filename = filename_entry.get() or None
    user_agent = user_agent_entry.get()
    proxy = proxy_entry.get()
    open_after_download = open_after_download_var.get()
    download_subtitles = download_subtitles_var.get()

    if not link or not file_format or not output_dir:
        messagebox.showerror("Error", "Please fill in all required fields.")
        return

    log_text = show_log_window()
    threading.Thread(target=download_thread, args=(link, file_format, output_dir, custom_filename, user_agent, proxy, open_after_download, download_subtitles, log_text), daemon=True).start()

root = ctk.CTk()

root.title("StreamFlare")
root.geometry("763x532")

frame = ctk.CTkFrame(root)
frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

# ASCII Art in the main window
ascii_art = generate_ascii_art()
ascii_label = ctk.CTkLabel(frame, text=ascii_art, font=("Courier", 12), justify=tk.LEFT, anchor="w")
ascii_label.grid(row=0, columnspan=2, padx=10, pady=10)

# Format Selection
ctk.CTkLabel(frame, text="Select Format:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
format_var = tk.StringVar(value='mp4')
format_menu = ctk.CTkOptionMenu(frame, variable=format_var, values=['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus', 'mp4', 'mkv', 'avi', 'webm', 'mov', 'flv', 'wmv', '3gp'])
format_menu.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

# YouTube Link
ctk.CTkLabel(frame, text="YouTube Link:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
link_entry = ctk.CTkEntry(frame, placeholder_text="e.g., https://www.youtube.com/watch?v=abc123")
link_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

# Output Directory
ctk.CTkLabel(frame, text="Output Directory:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
output_dir_entry = ctk.CTkEntry(frame, placeholder_text="e.g., C:/Users/YourName/Downloads")
output_dir_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

# Custom Filename
ctk.CTkLabel(frame, text="Custom Filename (Optional):").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
filename_entry = ctk.CTkEntry(frame, placeholder_text="e.g., my_video.mp4")
filename_entry.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

# User-Agent
ctk.CTkLabel(frame, text="User-Agent (Optional):").grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
user_agent_entry = ctk.CTkEntry(frame, placeholder_text="e.g., Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
user_agent_entry.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

# Proxy URL
ctk.CTkLabel(frame, text="Proxy URL (Optional):").grid(row=6, column=0, padx=10, pady=5, sticky=tk.W)
proxy_entry = ctk.CTkEntry(frame, placeholder_text="e.g., http://127.0.0.1:8080")
proxy_entry.grid(row=6, column=1, padx=10, pady=5, sticky="ew")

# Open After Download
ctk.CTkLabel(frame, text="Open After Download:").grid(row=7, column=0, padx=10, pady=5, sticky=tk.W)
open_after_download_var = tk.BooleanVar()
open_after_download_check = ctk.CTkCheckBox(frame, variable=open_after_download_var, text="")
open_after_download_check.grid(row=7, column=1, padx=10, pady=5, sticky=tk.W)

# Download Subtitles
ctk.CTkLabel(frame, text="Download Subtitles:").grid(row=8, column=0, padx=10, pady=5, sticky=tk.W)
download_subtitles_var = tk.BooleanVar()
download_subtitles_check = ctk.CTkCheckBox(frame, variable=download_subtitles_var, text="")
download_subtitles_check.grid(row=8, column=1, padx=10, pady=5, sticky=tk.W)

# Download Button
download_button = ctk.CTkButton(frame, text="Download", command=lambda: start_download(link_entry, format_var, output_dir_entry, filename_entry, user_agent_entry, proxy_entry, open_after_download_var, download_subtitles_var))
download_button.grid(row=9, column=0, padx=10, pady=20, sticky="ew")

# Log/Progress Button
log_button = ctk.CTkButton(frame, text="Show Log", command=show_log_window)
log_button.grid(row=9, column=1, padx=10, pady=20, sticky="ew")

# Adjust UI elements to fit the window size
frame.columnconfigure(1, weight=1)
frame.rowconfigure(1, weight=1)
frame.rowconfigure(2, weight=1)
frame.rowconfigure(3, weight=1)
frame.rowconfigure(4, weight=1)
frame.rowconfigure(5, weight=1)
frame.rowconfigure(6, weight=1)
frame.rowconfigure(7, weight=1)
frame.rowconfigure(8, weight=1)
frame.rowconfigure(9, weight=1)

root.mainloop()
