# Windows encoding fix - UTF-8'i zorla
import sys
import os
import io

# Windows'ta UTF-8 encoding'i zorla
if sys.platform == 'win32':
    # Windows terminal encoding sorunlarını çöz
    try:
        # Python 3.7+ için reconfigure kullan
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        else:
            if sys.stdout.encoding != 'utf-8':
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except (AttributeError, ValueError):
        # Fallback: eski yöntem
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    
    try:
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            if sys.stderr.encoding != 'utf-8':
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except (AttributeError, ValueError):
        if sys.stderr.encoding != 'utf-8':
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    
    try:
        # stdin'i de UTF-8'e ayarla (Python 3.7+)
        if hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        # stdin için reconfigure yoksa, encoding'i environment variable ile ayarla
        pass
    
    # Environment variable ile de UTF-8'i zorla
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.status import Status
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich import box
from rich.style import Style
from rich.theme import Theme

# Basit renk şeması: Beyaz ve Kırmızımsı Turuncu (Claude style)
PRIMARY_COLOR = "white"
ACCENT_COLOR = "rgb(167,199,231)"  # Kırmızımsı turuncu (Claude style)
DIM_COLOR = "dim white"

# Rich Theme - Prompt renklerini özelleştir (tüm mor/cyan renkleri kırmızımsı turuncu yap)
# Rich'in tüm default renklerini override et
custom_theme = Theme({
    "prompt": Style(color="rgb(167,199,231)"),
    "prompt.choices": Style(color="rgb(167,199,231)"),
    "prompt.default": Style(color="rgb(167,199,231)"),
    "prompt.invalid": Style(color="rgb(167,199,231)"),
    "prompt.invalid.choice": Style(color="rgb(167,199,231)"),
    # Rich'in tüm default renklerini override et
    "repr.number": Style(color="rgb(167,199,231)"),
    "repr.str": Style(color="rgb(167,199,231)"),
    "markup.code": Style(color="rgb(167,199,231)"),
    "markup.code.attr": Style(color="rgb(167,199,231)"),
    "markup.code.keyword": Style(color="rgb(167,199,231)"),
    # Magenta ve cyan renklerini override et
    "magenta": Style(color="rgb(167,199,231)"),
    "cyan": Style(color="rgb(167,199,231)"),
    "bright_magenta": Style(color="rgb(167,199,231)"),
    "bright_cyan": Style(color="rgb(167,199,231)"),
    "blue": Style(color="rgb(167,199,231)"),
    "bright_blue": Style(color="rgb(167,199,231)")
})
import requests
import time
import subprocess
import platform
import shlex
import threading
import queue
import re
import tempfile
import glob
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Config yönetimi - agent.config'e bağımlı değil
import json
import yaml

CONFIG_DIR = Path.home() / ".neurops"
CONFIG_FILE = CONFIG_DIR / "config.json"
USER_WORKFLOWS_DIR = CONFIG_DIR / "workflows"
DEFAULT_WORKFLOWS_DIR = Path(__file__).parent / "workflows"

def ensure_config_dir():
    """Config dizinini oluştur"""
    CONFIG_DIR.mkdir(exist_ok=True)

def is_setup_completed() -> bool:
    """Setup'ın tamamlanıp tamamlanmadığını kontrol et"""
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return config_data.get("setup_completed", False)
        except:
            return False
    return False

def mark_setup_completed():
    """Setup'ı tamamlandı olarak işaretle"""
    try:
        ensure_config_dir()
        config_data = {}
        
        if CONFIG_FILE.exists():
            try:
                config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except:
                pass
        
        config_data["setup_completed"] = True
        
        CONFIG_FILE.write_text(
            json.dumps(config_data, indent=2),
            encoding="utf-8"
        )
        return True
    except:
        return False

def normalize_api_url(url: str) -> str:
    """API URL'ini normalize et - sonundaki /'yi kaldır"""
    if not url:
        return url
    url = url.strip()
    # Sonundaki /'yi kaldır
    while url.endswith('/'):
        url = url[:-1]
    return url

def save_api_url(api_url: str) -> bool:
    """
    API URL'ini config dosyasına kaydeder.
    """
    try:
        # URL'yi normalize et
        normalized_url = normalize_api_url(api_url)
        
        ensure_config_dir()
        config_data = {}
        
        if CONFIG_FILE.exists():
            try:
                config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except:
                pass
        
        config_data["api_url"] = normalized_url
        
        CONFIG_FILE.write_text(
            json.dumps(config_data, indent=2),
            encoding="utf-8"
        )
        
        # Environment variable olarak da ayarla
        os.environ["NEUROPS_API_URL"] = normalized_url
        
        return True
    except Exception as e:
        # Fallback: sadece environment variable
        normalized_url = normalize_api_url(api_url)
        os.environ["NEUROPS_API_URL"] = normalized_url
        return False

def load_api_url():
    """
    API URL'ini yükler.
    Önce environment variable'dan, sonra config dosyasından okur.
    """
    # 1. Environment variable'dan kontrol et
    api_url = os.getenv("NEUROPS_API_URL")
    if api_url and len(api_url.strip()) > 0:
        return normalize_api_url(api_url.strip())
    
    # 2. Config dosyasından oku
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            api_url = config_data.get("api_url")
            if api_url and len(str(api_url).strip()) > 0:
                api_url = str(api_url).strip()
                normalized_url = normalize_api_url(api_url)
                os.environ["NEUROPS_API_URL"] = normalized_url
                return normalized_url
        except Exception:
            pass
    
    return None

def save_hf_token(token: str) -> bool:
    """
    Hugging Face API token'ını config dosyasına kaydeder.
    """
    try:
        ensure_config_dir()
        config_data = {}
        
        if CONFIG_FILE.exists():
            try:
                config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except:
                pass
        
        config_data["hf_token"] = token
        
        CONFIG_FILE.write_text(
            json.dumps(config_data, indent=2),
            encoding="utf-8"
        )
        
        # Environment variable olarak da ayarla
        os.environ["HF_API_KEY"] = token
        
        return True
    except Exception as e:
        # Fallback: sadece environment variable
        os.environ["HF_API_KEY"] = token
        return False

def load_hf_token() -> str:
    """
    Hugging Face API token'ını yükler.
    Önce environment variable'dan, sonra config dosyasından okur.
    """
    # 1. Environment variable'dan kontrol et
    token = os.getenv("HF_API_KEY")
    if token and len(token.strip()) > 0:
        return token.strip()
    
    # 2. Config dosyasından oku
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            token = config_data.get("hf_token")
            if token and len(str(token).strip()) > 0:
                token = str(token).strip()
                os.environ["HF_API_KEY"] = token
                return token
        except:
            pass
    
    return None

def save_settings(auto_workflow: bool = False, auto_incident: bool = False) -> bool:
    """Settings'i config dosyasına kaydeder"""
    try:
        ensure_config_dir()
        config_data = {}
        
        if CONFIG_FILE.exists():
            try:
                config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except:
                pass
        
        config_data["settings"] = {
            "auto_workflow_generation": auto_workflow,
            "auto_incident_creation": auto_incident
        }
        
        CONFIG_FILE.write_text(
            json.dumps(config_data, indent=2),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        return False

def load_settings() -> dict:
    """Settings'i config dosyasından yükler"""
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            settings = config_data.get("settings", {})
            return {
                "auto_workflow_generation": settings.get("auto_workflow_generation", False),
                "auto_incident_creation": settings.get("auto_incident_creation", False)
            }
        except:
            pass
    return {
        "auto_workflow_generation": False,
        "auto_incident_creation": False
    }

def get_user_id() -> str:
    """Kullanıcı ID'sini al (IP veya config'den)"""
    # Önce config'den kontrol et
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if config_data.get("user_id"):
                return config_data.get("user_id")
        except:
            pass
    
    # Fallback: IP adresini kullan
    import socket
    try:
        hostname = socket.gethostname()
        return f"{hostname}_{socket.gethostbyname(hostname)}"
    except:
        return "unknown"


def get_username() -> str:
    """Kullanıcı adını al"""
    if CONFIG_FILE.exists():
        try:
            config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if config_data.get("username"):
                return config_data.get("username")
        except:
            pass
    
    import getpass
    return getpass.getuser()


def get_api_headers() -> dict:
    """
    API çağrıları için header'ları döndürür.
    Token varsa header'a ekler.
    """
    headers = {"Content-Type": "application/json"}
    token = load_hf_token()
    if token:
        headers["X-HF-Token"] = token
    headers["X-User-ID"] = get_user_id()
    headers["X-Username"] = get_username()
    return headers

def check_api_connection():
    """
    API bağlantısını kontrol eder.
    Returns: (is_connected: bool, message: str)
    """
    try:
        # API URL'ini normalize et
        normalized_url = normalize_api_url(API_URL)
        res = requests.get(f"{normalized_url}/health", timeout=5)
        if res.status_code == 200:
            return True, "Connected"
        else:
            return False, f"Not Connected (Status: {res.status_code})"
    except requests.exceptions.ConnectionError:
        return False, "Not Connected (Connection error)"
    except requests.exceptions.Timeout:
        return False, "Not Connected (Timeout)"
    except Exception as e:
        return False, f"Not Connected ({str(e)[:30]})"

# API URL'ini yükle veya varsayılan kullan ve normalize et
raw_api_url = os.getenv("NEUROPS_API_URL") or load_api_url() or "http://127.0.0.1:8000"
API_URL = normalize_api_url(raw_api_url)

# Console'u UTF-8 encoding ile başlat (Windows uyumluluğu için)
if sys.platform == 'win32':
    # Windows'ta renk desteğini zorla
    # Windows Terminal ve PowerShell'de renkler çalışır
    try:
        # Windows Terminal renk desteğini aktif et
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Enable virtual terminal processing (Windows 10+)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass  # Eski Windows versiyonlarında çalışmayabilir
    
    # Rich Console'u renk desteği ile başlat
    console = Console(
        force_terminal=True,
        width=None,
        color_system="auto",  # Otomatik renk algılama
        legacy_windows=False,  # Modern Windows Terminal kullan
        no_color=False,  # Renkleri devre dışı bırakma
        highlight=False,  # Syntax highlighting'i kapat (mor/mavi renkleri kaldırır)
        theme=custom_theme  # Özel tema - Prompt renklerini değiştir
    )
else:
    console = Console(
        color_system="auto", 
        highlight=False, 
        theme=custom_theme
    )

# Rich'in Prompt.ask fonksiyonunu monkey-patch et - choices renklerini override et
_original_prompt_ask = Prompt.ask

def _patched_prompt_ask(
    prompt: str,
    *,
    console: Optional[Console] = None,
    password: bool = False,
    choices: Optional[List[str]] = None,
    default: Optional[str] = None,
    show_default: bool = True,
    show_choices: bool = True,
    **kwargs
) -> str:
    """Patched Prompt.ask - choices renklerini rgb(167,199,231) yap"""
    # Console'u kullan veya global console'u kullan
    if console is None:
        console = globals().get('console')
    
    # Orijinal fonksiyonu çağır ama console'u geç
    return _original_prompt_ask(
        prompt,
        console=console,
        password=password,
        choices=choices,
        default=default,
        show_default=show_default,
        show_choices=show_choices,
        **kwargs
    )

# Monkey-patch'i uygula
Prompt.ask = staticmethod(_patched_prompt_ask)


def get_multiline_input(prompt_text: str, end_marker: str = "END") -> str:
    """
    Multi-line input almak için özel fonksiyon.
    Kullanıcı yapıştırdığında tüm içeriği alır.
    END yazıp Enter'a basarak bitirir.
    """
    console.print(f"[bold rgb(167,199,231)]{prompt_text}[/bold rgb(167,199,231)]")
    console.print(f"[dim rgb(167,199,231)]Paste your content. Type '{end_marker}' on a new line and press Enter to finish:[/dim rgb(167,199,231)]")
    console.print()
    
    lines = []
    try:
        while True:
            try:
                line = input()
                if line.strip() == end_marker:
                    break
                lines.append(line)
            except EOFError:
                # Ctrl+D veya Ctrl+Z ile bitir
                break
            except KeyboardInterrupt:
                # Ctrl+C ile iptal
                console.print("\n[rgb(167,199,231)]Input cancelled.[/rgb(167,199,231)]")
                return ""
    except Exception:
        # Fallback: tek satır input
        return Prompt.ask(prompt_text)
    
    result = "\n".join(lines)
    return result.strip()


def get_multiline_input_simple(prompt_text: str) -> str:
    """
    Daha basit multi-line input - sadece Enter'a basınca bitirir (boş satır)
    veya Ctrl+D/Ctrl+Z ile bitirir.
    """
    console.print(f"[bold rgb(167,199,231)]{prompt_text}[/bold rgb(167,199,231)]")
    console.print("[dim rgb(167,199,231)]Paste your content. Press Enter twice or Ctrl+D/Ctrl+Z to finish:[/dim rgb(167,199,231)]")
    
    lines = []
    empty_line_count = 0
    
    try:
        while True:
            try:
                line = input()
                if not line.strip():
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        break
                else:
                    empty_line_count = 0
                    lines.append(line)
            except EOFError:
                # Ctrl+D veya Ctrl+Z ile bitir
                break
            except KeyboardInterrupt:
                # Ctrl+C ile iptal
                console.print("\n[rgb(167,199,231)]Input cancelled.[/rgb(167,199,231)]")
                return ""
    except Exception:
        # Fallback: tek satır input
        return Prompt.ask(prompt_text)
    
    result = "\n".join(lines)
    return result.strip()


def welcome_screen():
    """Basit ve temiz welcome ekranı"""
    console.clear()
    console.print("[rgb(167,199,231)]NeurOps[/rgb(167,199,231)] [dim rgb(167,199,231)]v2.0.0[/dim rgb(167,199,231)]")
    console.print("[rgb(167,199,231)]Welcome to NeurOps CLI[/rgb(167,199,231)]")
    console.print()
    console.print("[dim rgb(167,199,231)]Let's get started.[/dim rgb(167,199,231)]")
    console.print()


def prompt_with_animation(prompt_text: str, **kwargs) -> str:
    """Prompt'un yanında animasyon gösterir"""
    from rich.text import Text
    
    # Animasyonlu karakterler (rgb(167,199,231) renginde)
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    # Prompt'tan önce kısa bir animasyon göster
    for i in range(4):
        char = spinner_chars[i % len(spinner_chars)]
        animation = Text(char, style="rgb(167,199,231)")
        console.print(animation, end="\r")
        time.sleep(0.08)
    
    # Animasyonu temizle
    console.print(" " * 2, end="\r")
    
    # Prompt metninin yanına animasyonlu karakter ekle (ilk karakter)
    animated_prompt = f"[rgb(167,199,231)]{spinner_chars[0]}[/rgb(167,199,231)] {prompt_text}"
    
    # Normal prompt'u göster
    return Prompt.ask(animated_prompt, **kwargs)


def show_menu():
    """Basit ve temiz menü - margin yok, tamamen sola yaslı"""
    console.print()
    console.print("[rgb(167,199,231)]1.[/rgb(167,199,231)] Analyze Logs")
    console.print("[rgb(167,199,231)]2.[/rgb(167,199,231)] Incident Management")
    console.print("[rgb(167,199,231)]3.[/rgb(167,199,231)] Workflow Management")
    console.print()
    console.print("[rgb(167,199,231)]4.[/rgb(167,199,231)] AI Agent - Analyze Problem")
    console.print("[rgb(167,199,231)]5.[/rgb(167,199,231)] Security & Protection")
    console.print()
    console.print("[rgb(167,199,231)]6.[/rgb(167,199,231)] Team Management")
    console.print()
    console.print("[rgb(167,199,231)]7.[/rgb(167,199,231)] AI Agent - Set Token")
    console.print("[rgb(167,199,231)]8.[/rgb(167,199,231)] AI Agent - Status")
    console.print()
    console.print("[rgb(167,199,231)]9.[/rgb(167,199,231)] Monitor Terminal Output")
    console.print("[rgb(167,199,231)]10.[/rgb(167,199,231)] Full-Agent Mode")
    console.print()
    console.print("[rgb(167,199,231)]11.[/rgb(167,199,231)] Settings")
    console.print("[rgb(167,199,231)]12.[/rgb(167,199,231)] [dim rgb(167,199,231)]Exit[/dim rgb(167,199,231)]")
    console.print()
    
    # API URL ve bağlantı durumu bilgisi
    is_connected, connection_msg = check_api_connection()
    api_info = Text()
    api_info.append("API: ", style="dim rgb(167,199,231)")
    api_info.append(API_URL, style="white")
    api_info.append(" | ", style="dim white")
    if is_connected:
        api_info.append(connection_msg, style="dim rgb(167,199,231)")
    else:
        api_info.append(connection_msg, style="rgb(167,199,231)")
    console.print(api_info)


def show_security_menu():
    """Security yönetim menüsü - margin yok, tamamen sola yaslı"""
    console.print("[rgb(167,199,231)]Security & Protection[/rgb(167,199,231)]")
    console.print()
    console.print("[rgb(167,199,231)]5.1.[/rgb(167,199,231)] Security Analysis")
    console.print()
    console.print("[rgb(167,199,231)]5.2.[/rgb(167,199,231)] Generate Workflow for Event (AI)")
    console.print()
    console.print("[rgb(167,199,231)]5.3.[/rgb(167,199,231)] Security Scan")
    console.print("[rgb(167,199,231)]5.4.[/rgb(167,199,231)] Security Recommendations")
    console.print("[rgb(167,199,231)]5.5.[/rgb(167,199,231)] Security Statistics")
    console.print()
    console.print("[rgb(167,199,231)]5.6.[/rgb(167,199,231)] [dim white]Back to Main Menu[/dim white]")


def show_incident_menu():
    """Incident yönetim menüsü - margin yok, tamamen sola yaslı"""
    console.print("[rgb(167,199,231)]Incident Management[/rgb(167,199,231)]")
    console.print()
    console.print("[rgb(167,199,231)]2.1.[/rgb(167,199,231)] Report Incident")
    console.print("[rgb(167,199,231)]2.2.[/rgb(167,199,231)] List Incidents")
    console.print("[rgb(167,199,231)]2.3.[/rgb(167,199,231)] View Incident Details")
    console.print()
    console.print("[rgb(167,199,231)]2.4.[/rgb(167,199,231)] Update Incident")
    console.print("[rgb(167,199,231)]2.5.[/rgb(167,199,231)] Resolve Incident")
    console.print()
    console.print("[rgb(167,199,231)]2.6.[/rgb(167,199,231)] Generate Workflow for Incident (AI)")
    console.print("[rgb(167,199,231)]2.7.[/rgb(167,199,231)] Incident Statistics")
    console.print()
    console.print("[rgb(167,199,231)]2.8.[/rgb(167,199,231)] [dim white]Back to Main Menu[/dim white]")


def show_workflow_menu():
    """Workflow yönetim menüsü - margin yok, tamamen sola yaslı"""
    console.print("[rgb(167,199,231)]Workflow Management[/rgb(167,199,231)]")
    console.print()
    console.print("[rgb(167,199,231)]3.1.[/rgb(167,199,231)] List Workflows")
    console.print("[rgb(167,199,231)]3.2.[/rgb(167,199,231)] View Workflow Details")
    console.print()
    console.print("[rgb(167,199,231)]3.3.[/rgb(167,199,231)] AI - Generate Workflow")
    console.print()
    console.print("[rgb(167,199,231)]3.4.[/rgb(167,199,231)] Run Workflow")
    console.print("[rgb(167,199,231)]3.5.[/rgb(167,199,231)] Check Workflow Run Status")
    console.print("[rgb(167,199,231)]3.6.[/rgb(167,199,231)] List Workflow Runs")
    console.print()
    console.print("[rgb(167,199,231)]3.7.[/rgb(167,199,231)] [dim white]Back to Main Menu[/dim white]")


def show_team_menu():
    """Takım yönetim menüsü"""
    console.print("[rgb(167,199,231)]Team Management[/rgb(167,199,231)]")
    console.print()
    console.print("[rgb(167,199,231)]6.1.[/rgb(167,199,231)] Create Team")
    console.print("[rgb(167,199,231)]6.2.[/rgb(167,199,231)] Join Team")
    console.print()
    console.print("[rgb(167,199,231)]6.3.[/rgb(167,199,231)] List My Teams")
    console.print("[rgb(167,199,231)]6.4.[/rgb(167,199,231)] View Team Details")
    console.print()
    console.print("[rgb(167,199,231)]6.5.[/rgb(167,199,231)] Manage Team Members")
    console.print("[rgb(167,199,231)]6.6.[/rgb(167,199,231)] View Team Invitation")
    console.print()
    console.print("[rgb(167,199,231)]6.7.[/rgb(167,199,231)] [dim white]Back to Main Menu[/dim white]")


def check_token():
    """Token durumunu kontrol et (lokal config'den)"""
    token = load_hf_token()
    return {"token_set": bool(token), "agent_initialized": bool(token)}


def setup_tutorial():
    """İlk kurulum ve tutorial"""
    console.clear()
    console.print("[rgb(167,199,231)]Welcome to NeurOps![/rgb(167,199,231)]")
    console.print()
    console.print("Let's set up your environment:")
    console.print()
    
    # API URL Setup
    console.print("[rgb(167,199,231)]Step 1: API URL Configuration[/rgb(167,199,231)]")
    current_url = load_api_url() or "http://127.0.0.1:8000"
    console.print(f"Current API URL: [white]{current_url}[/white]")
    
    if not Confirm.ask("[dim white]Is this correct?[/dim white]", default=True):
        new_url = Prompt.ask("[bold white]Enter API URL[/bold white]", default=current_url)
        save_api_url(new_url)
        console.print("[white]API URL saved![/white]")
    else:
        if not current_url:
            new_url = Prompt.ask("[bold white]Enter API URL[/bold white]", default="http://127.0.0.1:8000")
            save_api_url(new_url)
            console.print("[white]API URL saved![/white]")
    
    console.print()
    
    # HF Token Setup
    console.print("[rgb(167,199,231)]Step 2: Hugging Face API Token[/rgb(167,199,231)]")
    console.print("To use AI features, you need a Hugging Face API token.")
    console.print("Get your token from: [link]https://huggingface.co/settings/tokens[/link]")
    console.print()
    
    if Confirm.ask("[bold white]Do you want to set your HF token now?[/bold white]", default=True):
        if sys.platform == 'win32':
            console.print("[dim white]Note: Token will be visible as you type (Windows compatibility)[/dim white]")
            token = Prompt.ask("[bold white]Enter your Hugging Face API token[/bold white]", password=False)
        else:
            token = Prompt.ask("[bold white]Enter your Hugging Face API token[/bold white]", password=True)
        
        if token:
            if save_hf_token(token):
                console.print("[white]Token saved successfully![/white]")
            else:
                console.print("[rgb(167,199,231)]Token saved to environment variable only[/rgb(167,199,231)]")
        else:
            console.print("[rgb(167,199,231)]Token not set. You can set it later from the main menu.[/rgb(167,199,231)]")
    else:
        console.print("[dim white]You can set your token later from the main menu (option 6).[/dim white]")
    
    console.print()
    
    # Tutorial
    console.print("[rgb(167,199,231)]Step 3: Quick Tutorial[/rgb(167,199,231)]")
    console.print()
    console.print("[bold white]Main Features:[/bold white]")
    console.print("  • [white]Analyze Logs[/white] - Analyze and search through logs")
    console.print("  • [white]Incident Management[/white] - Track and manage incidents")
    console.print("  • [white]Workflow Automation[/white] - Create and run automated workflows")
    console.print("  • [white]AI Problem Analysis[/white] - Get AI assistance for troubleshooting")
    console.print("  • [white]Security & Protection[/white] - Security analysis and threat detection")
    console.print()
    console.print("[dim white]Press Enter to continue...[/dim white]")
    input()
    
    # Mark setup as completed
    mark_setup_completed()
    console.print()
    console.print("[white]Setup completed![/white]")
    console.print()
    time.sleep(1)

def set_token():
    """Hugging Face API token'ını ayarla (lokal olarak sakla)"""
    console.print()
    panel = Panel(
        "[bold white]Hugging Face API Token Setup[/bold white]\n\n"
        "Get your token from: [link]https://huggingface.co/settings/tokens[/link]\n\n"
        "Your token will be stored locally and sent with each API request.",
        title="Token Configuration",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    # Windows'ta password input sorunları olabilir, önce normal input dene
    import sys
    if sys.platform == 'win32':
        # Windows'ta password input bazen donuyor, normal input kullan
        console.print("[dim white]Note: Token will be visible as you type (Windows compatibility)[/dim white]")
        token = Prompt.ask("[bold white]Enter your Hugging Face API token[/bold white]", password=False)
    else:
        # Linux/macOS'ta password input kullan
        token = Prompt.ask("[bold white]Enter your Hugging Face API token[/bold white]", password=True)
    
    if not token:
        console.print("[rgb(167,199,231)]Token cannot be empty![/rgb(167,199,231)]")
        return
    
    try:
        if save_hf_token(token):
            console.print("[white]Token saved successfully![/white]")
            console.print("[dim white]Token saved to config file (~/.neurops/config.json)[/dim white]")
            console.print("[dim white]Token will be sent with each API request[/dim white]")
        else:
            console.print("[rgb(167,199,231)] Token saved to environment variable only[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def agent_status():
    """Agent durumunu göster (lokal token durumu)"""
    token_status = check_token()
    token = load_hf_token()
    
    table = Table(
        title="[rgb(167,199,231)]Agent Status[/rgb(167,199,231)]",
        box=box.SIMPLE,
        border_style="rgb(167,199,231)",
        show_header=True,
        header_style="rgb(167,199,231)"
    )
    table.add_column("Property", style="white", width=20)
    table.add_column("Value", style="white", width=30)
    
    status_text = "ACTIVE" if token_status.get("token_set") else "INACTIVE"
    status_color = "white" if token_status.get("token_set") else "rgb(167,199,231)"
    table.add_row("Status", f"[{status_color}]{status_text}[/{status_color}]")
    
    token_text = "Yes" if token_status.get("token_set") else "No"
    token_color = "white" if token_status.get("token_set") else "rgb(167,199,231)"
    table.add_row("Token Configured", f"[{token_color}]{token_text}[/{token_color}]")
    
    if token:
        # Token'ın ilk ve son birkaç karakterini göster (güvenlik için)
        masked_token = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "***"
        table.add_row("Token Preview", f"[dim white]{masked_token}[/dim white]")
    
    table.add_row("Model", "[dim white]deepseek-ai/DeepSeek-R1[/dim white]")
    table.add_row("Token Storage", "[dim white]~/.neurops/config.json[/dim white]")
    
    console.print()
    console.print(table)
    console.print()
    
    if not token_status.get("token_set"):
        warning = Panel(
            "[rgb(167,199,231)]Token not set. Use option 6 to set your Hugging Face API token.[/rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)


def analyze_problem():
    """AI Agent ile problem analizi"""
    # Token kontrolü
    token_status = check_token()
    if not token_status.get("token_set"):
        console.print()
        warning = Panel(
            "[rgb(167,199,231)] Token not set![/rgb(167,199,231)]\n\n"
            "AI features require a Hugging Face API token.",
            title="Warning",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)
        console.print()
        
        if Confirm.ask("[rgb(167,199,231)]Would you like to set token now?[/rgb(167,199,231)]"):
            set_token()
            token_status = check_token()
            if not token_status.get("token_set"):
                console.print("[rgb(167,199,231)]Token setup failed. Cannot proceed.[/rgb(167,199,231)]")
                return
        else:
            return
    console.print()
    console.print("[rgb(167,199,231)]AI Problem Analysis[/rgb(167,199,231)]")
    console.print("[dim rgb(167,199,231)]Describe the problem you're experiencing:[/dim rgb(167,199,231)]")
    console.print()
    
    # Multi-line input için özel fonksiyon kullan
    problem = get_multiline_input_simple("[dim rgb(167,199,231)]Problem description[/dim rgb(167,199,231)]")
    
    if not problem:
        console.print("[rgb(167,199,231)]Problem description cannot be empty![/rgb(167,199,231)]")
        return
    
    # Context bilgileri iste (opsiyonel)
    context = {}
    if Confirm.ask("[rgb(167,199,231)]Do you have additional context (logs, metrics, etc.)?[/rgb(167,199,231)]"):
        console.print()
        logs = get_multiline_input_simple("[white]Paste relevant logs (optional)[/white]")
        if logs:
            context["logs"] = logs
    
    auto_apply = Confirm.ask("[rgb(167,199,231)]Auto-apply suggested solutions?[/rgb(167,199,231)]", default=False)
    
    try:
        console.print()
        
        # Loading animasyonu ile analiz
        with Status(
            "[rgb(167,199,231)]Analyzing problem with AI...[/rgb(167,199,231)]",
            spinner="dots12",
            spinner_style="rgb(167,199,231)"
        ):
            res = requests.post(
                f"{API_URL}/agent/analyze",
                json={
                    "problem_description": problem,
                    "context": context if context else None,
                    "auto_apply": auto_apply
                },
                headers=get_api_headers(),
                timeout=120  # AI analysis için daha uzun timeout
            )
        
        if res.status_code == 200:
            result = res.json()
            
            console.print()
            console.print("[rgb(167,199,231)]Analysis Complete[/rgb(167,199,231)]")
            console.print()
            
            if result.get("fallback"):
                warning = Panel(
                    "[rgb(167,199,231)]Using fallback mode (AI model not available)[/rgb(167,199,231)]",
                    border_style="white",
                    box=box.SIMPLE
                )
                console.print(warning)
                console.print()
            
            # Markdown formatında analiz
            analysis_text = result.get("analysis", "No analysis available")
            analysis_panel = Panel(
                Markdown(analysis_text),
                title="[rgb(167,199,231)]AI Analysis[/rgb(167,199,231)]",
                border_style="white",
                title_align="left",
                box=box.SIMPLE,
                padding=(0, 0)
            )
            console.print(analysis_panel)
            
            # Actions taken
            if result.get("actions_taken"):
                console.print()
                console.print("[rgb(167,199,231)]Actions Taken:[/rgb(167,199,231)]")
                for action in result["actions_taken"]:
                    console.print(f"  [white]•[/white] {action}")
            
            # Recommendations
            if result.get("recommendations"):
                console.print()
                console.print("[rgb(167,199,231)]Recommendations:[/rgb(167,199,231)]")
                for rec in result["recommendations"]:
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {rec}")
            
            # Model bilgisi
            if result.get("model"):
                console.print()
                console.print(f"[dim]Model: {result['model']}[/dim]")
        
        else:
            error_detail = res.json().get("detail", "Unknown error")
            error_panel = Panel(
                f"[rgb(167,199,231)]Analysis failed:[/rgb(167,199,231)]\n\n{error_detail}",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(error_panel)
    
    except requests.Timeout:
        error_panel = Panel(
            "[rgb(167,199,231)]Request Timeout[/rgb(167,199,231)]\n\n"
            "The AI analysis took longer than expected.\n"
            "This can happen if:\n"
            "  • The AI service is slow or overloaded\n"
            "  • Your problem description is very complex\n"
            "  • Network connection is slow\n\n"
            "[rgb(167,199,231)]Try again with a simpler description or check your connection.[/rgb(167,199,231)]",
            title="Timeout",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(Align.center(error_panel), width=80)
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def analyze_logs():
    """Log analizi"""
    console.print()
    
    # Dosya yolu veya direkt yapıştırma seçeneği
    choice = Prompt.ask(
        "[white]Choose input method[/white]",
        choices=["file", "paste"],
        default="file"
    )
    
    logs = ""
    
    if choice == "file":
        path = Prompt.ask("[white]Enter log file path[/white]")
        try:
            with Status("[rgb(167,199,231)]Reading log file...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
                with open(path, "r", encoding="utf-8") as f:
                    logs = f.read()
        except FileNotFoundError:
            console.print(f"[rgb(167,199,231)]File not found.[/rgb(167,199,231)]")
            return
        except Exception as e:
            console.print(f"[rgb(167,199,231)]Error reading file.[/rgb(167,199,231)]")
            return
    else:
        # Direkt yapıştırma
        console.print()
        logs = get_multiline_input_simple("[white]Paste your logs[/white]")
        if not logs:
            console.print("[rgb(167,199,231)]No logs provided![/rgb(167,199,231)]")
            return
    
    try:
        with Status("[rgb(167,199,231)]Analyzing logs...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(f"{API_URL}/logs/analyze", json={"logs": logs})
        
        if res.status_code == 200:
            result = res.json()
            
            console.print()
            console.print("[rgb(167,199,231)]Analysis Complete[/rgb(167,199,231)]")
            console.print()
            
            summary_panel = Panel(
                result.get('summary', 'N/A'),
                title="[rgb(167,199,231)]Analysis Summary[/rgb(167,199,231)]",
                border_style="white",
                title_align="left",
                box=box.SIMPLE
            )
            console.print(summary_panel)
            
            if result.get("critical_issues"):
                console.print()
                console.print("[rgb(167,199,231)]Critical Issues:[/rgb(167,199,231)]")
                for issue in result["critical_issues"]:
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {issue}")
            
            if result.get("recommendations"):
                console.print()
                console.print("[rgb(167,199,231)]Recommendations:[/rgb(167,199,231)]")
                for rec in result["recommendations"]:
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {rec}")
            
            # Settings kontrolü
            settings = load_settings()
            errors = result.get("errors_detected", 0)
            warnings = result.get("warnings_detected", 0)
            critical = result.get("critical_issues", [])
            
            # Auto Incident Creation
            if settings.get("auto_incident_creation") and (errors > 0 or warnings > 0 or critical):
                console.print()
                if Confirm.ask("[rgb(167,199,231)]Create incident for detected issues?[/rgb(167,199,231)]", default=True):
                    try:
                        incident_title = f"Log Analysis: {errors} errors, {warnings} warnings detected"
                        incident_desc = f"Automatically created from log analysis.\n\nErrors: {errors}\nWarnings: {warnings}\n\nSummary:\n{result.get('summary', '')}\n\nLog snippet:\n{logs[-1000:]}"
                        
                        incident_res = requests.post(
                            f"{API_URL}/incident/",
                            json={
                                "title": incident_title,
                                "description": incident_desc,
                                "severity": "high" if critical else "medium",
                                "source": "log_analysis"
                            }
                        )
                        
                        if incident_res.status_code == 200:
                            incident = incident_res.json()
                            console.print()
                            console.print(f"[rgb(167,199,231)]✓ Incident created: {incident.get('id')}[/rgb(167,199,231)]")
                    except Exception as e:
                        console.print(f"[rgb(167,199,231)]Error creating incident: {e}[/rgb(167,199,231)]")
            
            # Auto Workflow Generation (token varsa ve sorun varsa)
            token_status = check_token()
            if settings.get("auto_workflow_generation") and token_status.get("token_set") and (errors > 0 or warnings > 0):
                console.print()
                if Confirm.ask("[rgb(167,199,231)]Generate and run workflow to fix issues?[/rgb(167,199,231)]", default=True):
                    try:
                        workflow_desc = f"Fix issues detected in log analysis:\n\nErrors: {errors}\nWarnings: {warnings}\n\nSummary: {result.get('summary', '')}\n\nRecommendations: {', '.join(result.get('recommendations', [])[:3])}"
                        
                        workflow_res = requests.post(
                            f"{API_URL}/workflow/generate",
                            json={
                                "description": workflow_desc,
                                "context": {
                                    "logs": logs[-2000:],
                                    "errors": errors,
                                    "warnings": warnings,
                                    "summary": result.get('summary', '')
                                }
                            },
                            headers=get_api_headers(),
                            timeout=120
                        )
                        
                        if workflow_res.status_code == 200:
                            workflow_result = workflow_res.json()
                            workflow_name = workflow_result.get("workflow_name")
                            
                            console.print()
                            console.print(f"[rgb(167,199,231)]✓ Workflow generated: {workflow_name}[/rgb(167,199,231)]")
                            
                            # Workflow'u çalıştır
                            run_res = requests.post(
                                f"{API_URL}/workflow/run",
                                json={
                                    "workflow_name": workflow_name,
                                    "parameters": {}
                                },
                                headers=get_api_headers()
                            )
                            
                            if run_res.status_code == 200:
                                run_result = run_res.json()
                                console.print(f"[rgb(167,199,231)]✓ Workflow started: {run_result.get('run_id')}[/rgb(167,199,231)]")
                    except Exception as e:
                        console.print(f"[rgb(167,199,231)]Error generating workflow: {e}[/rgb(167,199,231)]")
        else:
            console.print(f"[rgb(167,199,231)]Error: {res.status_code}[/rgb(167,199,231)]")
    except FileNotFoundError:
        console.print(f"[rgb(167,199,231)]File not found.[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error.[/rgb(167,199,231)]")


def report_incident():
    """Incident raporlama"""
    console.print()
    title = Prompt.ask("[rgb(167,199,231)]Enter incident title[/rgb(167,199,231)]")
    description = Prompt.ask("[rgb(167,199,231)]Enter incident description[/rgb(167,199,231)]")
    severity = Prompt.ask(
        "[rgb(167,199,231)]Severity[/rgb(167,199,231)]",
        choices=["low", "medium", "high", "critical"],
        default="medium"
    )
    
    # Takım seçeneği
    team_id = None
    if Confirm.ask("[rgb(167,199,231)]Associate with a team?[/rgb(167,199,231)]", default=False):
        team_id = Prompt.ask("[rgb(167,199,231)]Enter team ID[/rgb(167,199,231)]")
    
    try:
        params = {}
        if team_id:
            params["team_id"] = team_id
        
        with Status("[rgb(167,199,231)]Reporting incident...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/incident/report",
                json={
                    "title": title,
                    "description": description,
                    "severity": severity
                },
                params=params,
                headers=get_api_headers()
            )
        
        if res.status_code == 200:
            incident = res.json()
            console.print()
            success_panel = Panel(
                f"[rgb(167,199,231)]Incident created successfully![/rgb(167,199,231)]\n\n"
                f"ID: [white]{incident.get('id')}[/white]\n"
                f"Status: [white]{incident.get('status')}[/white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            console.print(f"[rgb(167,199,231)]Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def list_incidents():
    """Incident'leri listele"""
    console.print()
    
    # Takım filtresi
    use_team = Confirm.ask("[rgb(167,199,231)]Filter by team?[/rgb(167,199,231)]", default=False)
    team_id = None
    if use_team:
        team_id = Prompt.ask("[rgb(167,199,231)]Enter team ID[/rgb(167,199,231)]")
    
    # Filtre seçenekleri
    status_filter = Prompt.ask(
        "[rgb(167,199,231)]Filter by status (optional)[/rgb(167,199,231)]",
        choices=["", "open", "in_progress", "resolved", "closed"],
        default=""
    )
    severity_filter = Prompt.ask(
        "[rgb(167,199,231)]Filter by severity (optional)[/rgb(167,199,231)]",
        choices=["", "low", "medium", "high", "critical"],
        default=""
    )
    
    try:
        params = {}
        if team_id:
            params["team_id"] = team_id
        if status_filter:
            params["status"] = status_filter
        if severity_filter:
            params["severity"] = severity_filter
        
        with Status("[rgb(167,199,231)]Fetching incidents...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/incident/", params=params, headers=get_api_headers())
        
        if res.status_code == 200:
            incidents = res.json()
            console.print()
            
            if not incidents:
                console.print("[rgb(167,199,231)]No incidents found.[/rgb(167,199,231)]")
                return
            
            table = Table(
                title="[rgb(167,199,231)]Incidents[/rgb(167,199,231)]",
                box=box.SIMPLE,
                border_style="white",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("ID", style="white", width=36)
            table.add_column("Title", style="white", width=30)
            table.add_column("Severity", style="rgb(167,199,231)", width=12)
            table.add_column("Status", style="white", width=15)
            table.add_column("Created", style="dim", width=20)
            
            status_colors = {
                "open": "red",
                "in_progress": "yellow",
                "resolved": "green",
                "closed": "dim"
            }
            
            severity_icons = {
                "low": "[white]LOW[/white]",
                "medium": "[rgb(167,199,231)]MEDIUM[/rgb(167,199,231)]",
                "high": "[rgb(167,199,231)]HIGH[/rgb(167,199,231)]",
                "critical": "[rgb(167,199,231)]CRITICAL[/rgb(167,199,231)]"
            }
            
            for incident in incidents:
                inc_id = incident.get('id', 'N/A')[:8] + '...'
                title = incident.get('title', 'N/A')[:28] + '...' if len(incident.get('title', '')) > 28 else incident.get('title', 'N/A')
                severity = incident.get('severity', 'N/A')
                status = incident.get('status', 'N/A')
                created = incident.get('created_at', 'N/A')[:19] if incident.get('created_at') else 'N/A'
                
                severity_display = f"{severity_icons.get(severity, severity)}"
                status_display = f"[{status_colors.get(status, 'white')}]{status}[/{status_colors.get(status, 'white')}]"
                
                table.add_row(inc_id, title, severity_display, status_display, created)
            
            console.print(table)
        else:
            console.print(f"[rgb(167,199,231)]Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def view_incident():
    """Incident detaylarını görüntüle"""
    console.print()
    incident_id = Prompt.ask("[rgb(167,199,231)]Enter incident ID[/rgb(167,199,231)]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching incident details...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/incident/{incident_id}")
        
        if res.status_code == 200:
            incident = res.json()
            console.print()
            
            # Status icon
            status = incident.get('status', 'unknown')
            status_icons = {
                'open': '[rgb(167,199,231)]OPEN[/rgb(167,199,231)]',
                'in_progress': '[rgb(167,199,231)]IN PROGRESS[/rgb(167,199,231)]',
                'resolved': '[rgb(167,199,231)]RESOLVED[/rgb(167,199,231)]',
                'closed': '[dim white]CLOSED[/dim white]'
            }
            
            # Severity icon
            severity = incident.get('severity', 'unknown')
            
            info_text = f"[rgb(167,199,231)]ID:[/rgb(167,199,231)] {incident.get('id')}\n"
            info_text += f"[rgb(167,199,231)]Title:[/rgb(167,199,231)] {incident.get('title')}\n"
            info_text += f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {incident.get('description')}\n"
            info_text += f"[rgb(167,199,231)]Severity:[/rgb(167,199,231)] {severity.upper()}\n"
            info_text += f"[rgb(167,199,231)]Status:[/rgb(167,199,231)] {status.upper()}\n"
            info_text += f"[rgb(167,199,231)]Created:[/rgb(167,199,231)] {incident.get('created_at')}\n"
            info_text += f"[rgb(167,199,231)]Updated:[/rgb(167,199,231)] {incident.get('updated_at')}\n"
            
            if incident.get('resolved_at'):
                info_text += f"[rgb(167,199,231)]Resolved:[/rgb(167,199,231)] {incident.get('resolved_at')}\n"
            if incident.get('assigned_to'):
                info_text += f"[rgb(167,199,231)]Assigned To:[/rgb(167,199,231)] {incident.get('assigned_to')}\n"
            if incident.get('resolution'):
                info_text += f"[rgb(167,199,231)]Resolution:[/rgb(167,199,231)] {incident.get('resolution')}\n"
            
            # Generated workflow bilgisi
            if incident.get('metadata') and incident.get('metadata').get('generated_workflow'):
                workflow_name = incident.get('metadata').get('generated_workflow')
                info_text += f"\n[rgb(167,199,231)]Generated Workflow:[/rgb(167,199,231)] [white]{workflow_name}[/white]"
            
            info_panel = Panel(
                info_text,
                border_style="white",
                box=box.SIMPLE
            )
            console.print(info_panel)
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)]Incident '{incident_id}' not found[/rgb(167,199,231)]")
        else:
            console.print(f"[rgb(167,199,231)]Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def update_incident():
    """Incident'i güncelle"""
    console.print()
    incident_id = Prompt.ask("[rgb(167,199,231)]Enter incident ID[/rgb(167,199,231)]")
    
    # Önce incident'i getir
    try:
        res = requests.get(f"{API_URL}/incident/{incident_id}")
        if res.status_code != 200:
            console.print(f"[rgb(167,199,231)]Incident not found[/rgb(167,199,231)]")
            return
        incident = res.json()
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")
        return
    
    console.print()
    console.print(f"[dim]Current incident: {incident.get('title')}[/dim]")
    console.print()
    
    # Güncelleme seçenekleri
    update_data = {}
    
    if Confirm.ask("[rgb(167,199,231)]Update status?[/rgb(167,199,231)]", default=False):
        new_status = Prompt.ask(
            "[white]New status[/white]",
            choices=["open", "in_progress", "resolved", "closed"],
            default=incident.get('status', 'open')
        )
        update_data["status"] = new_status
    
    if Confirm.ask("[rgb(167,199,231)]Update description?[/rgb(167,199,231)]", default=False):
        new_description = get_multiline_input_simple("[white]New description[/white]")
        if new_description:
            update_data["description"] = new_description
    
    if Confirm.ask("[rgb(167,199,231)]Add/Update resolution?[/rgb(167,199,231)]", default=False):
        resolution = get_multiline_input_simple("[white]Resolution[/white]")
        if resolution:
            update_data["resolution"] = resolution
    
    if Confirm.ask("[rgb(167,199,231)]Assign to someone?[/rgb(167,199,231)]", default=False):
        assigned_to = Prompt.ask("[white]Assign to (username/email)[/white]")
        if assigned_to:
            update_data["assigned_to"] = assigned_to
    
    if not update_data:
        console.print("[rgb(167,199,231)]No updates provided.[/rgb(167,199,231)]")
        return
    
    try:
        with Status("[rgb(167,199,231)]Updating incident...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.patch(
                f"{API_URL}/incident/{incident_id}",
                json=update_data
            )
        
        if res.status_code == 200:
            updated_incident = res.json()
            console.print()
            success_panel = Panel(
                f"[white]Incident updated successfully![/white]\n\n"
                f"Status: [white]{updated_incident.get('status')}[/white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def resolve_incident():
    """Incident'i çöz"""
    console.print()
    incident_id = Prompt.ask("[white]Enter incident ID[/white]")
    
    # Resolution açıklaması (opsiyonel)
    resolution = None
    if Confirm.ask("[rgb(167,199,231)]Add resolution description?[/rgb(167,199,231)]", default=False):
        resolution = get_multiline_input_simple("[white]Resolution[/white]")
    
    try:
        with Status("[rgb(167,199,231)]Resolving incident...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/incident/{incident_id}/resolve",
                json={"resolution": resolution} if resolution else {}
            )
        
        if res.status_code == 200:
            resolved_incident = res.json()
            console.print()
            success_panel = Panel(
                f"[white]Incident resolved successfully![/white]\n\n"
                f"Status: [white]{resolved_incident.get('status')}[/white]\n"
                f"Resolved at: [white]{resolved_incident.get('resolved_at')}[/white]",
                title="Success",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def generate_workflow_for_incident():
    """Incident için AI ile workflow oluştur"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Generate Workflow for Incident[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]AI will analyze the incident and create a custom remediation workflow.[/rgb(167,199,231)]",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    incident_id = Prompt.ask("[rgb(167,199,231)]Enter incident ID[/rgb(167,199,231)]")
    
    auto_run = Confirm.ask(
        "[rgb(167,199,231)]Automatically run the generated workflow?[/rgb(167,199,231)]",
        default=False
    )
    
    try:
        with Status("[rgb(167,199,231)]AI is analyzing incident and generating workflow...[/rgb(167,199,231)]", spinner="dots12", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/incident/{incident_id}/generate-workflow",
                params={"auto_run": str(auto_run).lower()},
                timeout=120  # AI generation için daha uzun timeout
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            
            auto_run_msg = f"[rgb(167,199,231)]Workflow will be executed automatically[/rgb(167,199,231)]" if result.get('auto_run') else "[dim]You can run the workflow manually from the Workflow Management menu[/dim]"
            
            success_panel = Panel(
                f"[white]Workflow generated successfully![/white]\n\n"
                f"Workflow Name: [white]{result.get('workflow_name')}[/white]\n"
                f"Incident ID: [white]{result.get('incident_id')}[/white]\n"
                f"Auto Run: [white]{'Yes' if result.get('auto_run') else 'No'}[/white]\n\n"
                f"{auto_run_msg}",
                title="Success",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
            
            if result.get('workflow_name'):
                console.print()
                if Confirm.ask("[white]View the generated workflow?[/white]", default=True):
                    # Workflow'u göster
                    try:
                        wf_res = requests.get(f"{API_URL}/workflow/{result.get('workflow_name')}")
                        if wf_res.status_code == 200:
                            workflow = wf_res.json()
                            console.print()
                            workflow_panel = Panel(
                                f"[white]Name:[/white] {workflow.get('name')}\n"
                                f"[white]Description:[/white] {workflow.get('description', 'N/A')}\n"
                                f"[white]Steps:[/white] {len(workflow.get('steps', []))}",
                                title="[bold white]Generated Workflow[/bold white]",
                                border_style="white",
                                box=box.SIMPLE
                            )
                            console.print(workflow_panel)
                    except:
                        pass
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)] Incident '{incident_id}' not found[/rgb(167,199,231)]")
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def incident_stats():
    """Incident istatistiklerini göster"""
    try:
        with Status("[rgb(167,199,231)]Fetching incident statistics...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/incident/stats/summary")
        
        if res.status_code == 200:
            stats = res.json()
            console.print()
            
            table = Table(
                title="[bold white]Incident Statistics[/bold white]",
                box=box.SIMPLE,
                border_style="white",
                show_header=True,
                header_style="bold red"
            )
            table.add_column("Metric", style="white", width=25)
            table.add_column("Value", style="white", width=20)
            
            table.add_row("Total Incidents", str(stats.get('total', 0)))
            table.add_row("Active", f"[rgb(167,199,231)]{stats.get('active', 0)}[/rgb(167,199,231)]")
            table.add_row("Open", f"[rgb(167,199,231)]{stats.get('open', 0)}[/rgb(167,199,231)]")
            table.add_row("In Progress", f"[rgb(167,199,231)]{stats.get('in_progress', 0)}[/rgb(167,199,231)]")
            table.add_row("Resolved", f"[white]{stats.get('resolved', 0)}[/white]")
            
            console.print(table)
            
            # By severity
            if stats.get('by_severity'):
                console.print()
                severity_table = Table(
                    title="[bold white]By Severity[/bold white]",
                    box=box.SIMPLE,
                    border_style="white",
                    show_header=True,
                    header_style="bold red"
                )
                severity_table.add_column("Severity", style="white", width=20)
                severity_table.add_column("Count", style="white", width=15)
                
                for severity, count in stats.get('by_severity', {}).items():
                    severity_table.add_row(severity.upper(), str(count))
                
                console.print(severity_table)
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


# Team Management Functions
def create_team():
    """Takım oluştur"""
    console.print()
    name = Prompt.ask("[rgb(167,199,231)]Enter team name[/rgb(167,199,231)]")
    description = Prompt.ask("[rgb(167,199,231)]Enter team description (optional)[/rgb(167,199,231)]", default="")
    
    try:
        with Status("[rgb(167,199,231)]Creating team...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/team/create",
                json={"name": name, "description": description if description else None},
                headers=get_api_headers()
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            success_panel = Panel(
                f"[rgb(167,199,231)]Team created successfully![/rgb(167,199,231)]\n\n"
                f"Team ID: [white]{result.get('team_id')}[/white]\n"
                f"Invitation ID: [white]{result.get('invitation_id')}[/white]\n"
                f"Invitation Password: [white]{result.get('invitation_password')}[/white]\n\n"
                f"[bold rgb(167,199,231)]⚠️ IMPORTANT: Save the invitation ID and password![/bold rgb(167,199,231)]\n"
                f"[dim]Share these with team members to join.[/dim]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def join_team():
    """Takıma katıl"""
    console.print()
    invitation_id = Prompt.ask("[rgb(167,199,231)]Enter invitation ID[/rgb(167,199,231)]")
    password = Prompt.ask("[rgb(167,199,231)]Enter invitation password[/rgb(167,199,231)]", password=True)
    username = Prompt.ask("[rgb(167,199,231)]Enter your username[/rgb(167,199,231)]", default=get_username())
    
    try:
        with Status("[rgb(167,199,231)]Joining team...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/team/join",
                json={
                    "team_id": invitation_id,
                    "password": password,
                    "username": username
                },
                headers=get_api_headers()
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            success_panel = Panel(
                f"[rgb(167,199,231)]Successfully joined team![/rgb(167,199,231)]\n\n"
                f"Team: [white]{result.get('team_name')}[/white]\n"
                f"Team ID: [white]{result.get('team_id')}[/white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def list_my_teams():
    """Kullanıcının takımlarını listele"""
    console.print()
    try:
        with Status("[rgb(167,199,231)]Fetching teams...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/team/", headers=get_api_headers())
        
        if res.status_code == 200:
            teams = res.json()
            console.print()
            
            if not teams:
                console.print("[rgb(167,199,231)]No teams found. Create a team or join one![/rgb(167,199,231)]")
                return
            
            table = Table(
                title="[rgb(167,199,231)]My Teams[/rgb(167,199,231)]",
                box=box.SIMPLE,
                border_style="white",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("Team Name", style="white", width=30)
            table.add_column("Role", style="rgb(167,199,231)", width=15)
            table.add_column("Members", style="white", width=10)
            table.add_column("Created", style="dim", width=20)
            
            for team in teams:
                role_colors = {
                    "owner": "bold white",
                    "admin": "white",
                    "member": "dim white",
                    "viewer": "dim"
                }
                role_style = role_colors.get(team.get('role', '').lower(), "white")
                table.add_row(
                    team.get('name', 'N/A'),
                    f"[{role_style}]{team.get('role', 'N/A').upper()}[/{role_style}]",
                    str(team.get('member_count', 0)),
                    team.get('created_at', 'N/A')[:10] if team.get('created_at') else 'N/A'
                )
            
            console.print(table)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def view_team_details():
    """Takım detaylarını göster"""
    console.print()
    team_id = Prompt.ask("[rgb(167,199,231)]Enter team ID[/rgb(167,199,231)]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching team details...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/team/{team_id}", headers=get_api_headers())
        
        if res.status_code == 200:
            team = res.json()
            console.print()
            
            info_text = f"[rgb(167,199,231)]Name:[/rgb(167,199,231)] {team.get('name')}\n"
            info_text += f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {team.get('description', 'N/A')}\n"
            info_text += f"[rgb(167,199,231)]Created:[/rgb(167,199,231)] {team.get('created_at')}\n"
            info_text += f"[rgb(167,199,231)]Members:[/rgb(167,199,231)] {len(team.get('members', []))}\n\n"
            
            # Members list
            if team.get('members'):
                info_text += "[rgb(167,199,231)]Members:[/rgb(167,199,231)]\n"
                for member in team.get('members', []):
                    info_text += f"  - [white]{member.get('username')}[/white] ([rgb(167,199,231)]{member.get('role')}[/rgb(167,199,231)])\n"
            
            info_panel = Panel(
                info_text,
                border_style="white",
                box=box.SIMPLE
            )
            console.print(info_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def manage_team_members():
    """Takım üyelerini yönet"""
    console.print()
    team_id = Prompt.ask("[rgb(167,199,231)]Enter team ID[/rgb(167,199,231)]")
    
    # Önce takım üyelerini listele
    try:
        res = requests.get(f"{API_URL}/team/{team_id}/members", headers=get_api_headers())
        if res.status_code != 200:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
            return
        
        members = res.json()
        console.print()
        console.print("[rgb(167,199,231)]Current Team Members:[/rgb(167,199,231)]")
        table = Table(box=box.SIMPLE, border_style="white", show_header=True, header_style="rgb(167,199,231)")
        table.add_column("Username", style="white")
        table.add_column("Role", style="rgb(167,199,231)")
        table.add_column("Joined", style="dim")
        
        for member in members:
            table.add_row(
                member.get('username', 'N/A'),
                member.get('role', 'N/A'),
                member.get('joined_at', 'N/A')[:10] if member.get('joined_at') else 'N/A'
            )
        console.print(table)
        console.print()
        
        action = Prompt.ask(
            "[rgb(167,199,231)]Choose action[/rgb(167,199,231)]",
            choices=["add", "remove", "update", "back"],
            default="back"
        )
        
        if action == "add":
            user_id = Prompt.ask("[rgb(167,199,231)]Enter user ID to add[/rgb(167,199,231)]")
            username = Prompt.ask("[rgb(167,199,231)]Enter username[/rgb(167,199,231)]")
            role = Prompt.ask(
                "[rgb(167,199,231)]Role[/rgb(167,199,231)]",
                choices=["member", "admin", "viewer"],
                default="member"
            )
            
            res = requests.post(
                f"{API_URL}/team/{team_id}/members",
                params={"username": username, "user_id": user_id, "role": role},
                headers=get_api_headers()
            )
            if res.status_code == 200:
                console.print("[rgb(167,199,231)]Member added successfully![/rgb(167,199,231)]")
            else:
                error_detail = res.json().get('detail', 'Unknown error')
                console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
        
        elif action == "remove":
            user_id = Prompt.ask("[rgb(167,199,231)]Enter user ID to remove[/rgb(167,199,231)]")
            res = requests.delete(f"{API_URL}/team/{team_id}/members/{user_id}", headers=get_api_headers())
            if res.status_code == 200:
                console.print("[rgb(167,199,231)]Member removed successfully![/rgb(167,199,231)]")
            else:
                error_detail = res.json().get('detail', 'Unknown error')
                console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
        
        elif action == "update":
            user_id = Prompt.ask("[rgb(167,199,231)]Enter user ID to update[/rgb(167,199,231)]")
            role = Prompt.ask(
                "[rgb(167,199,231)]New role[/rgb(167,199,231)]",
                choices=["member", "admin", "viewer"],
                default="member"
            )
            res = requests.put(
                f"{API_URL}/team/{team_id}/members/{user_id}",
                json={"role": role},
                headers=get_api_headers()
            )
            if res.status_code == 200:
                console.print("[rgb(167,199,231)]Member updated successfully![/rgb(167,199,231)]")
            else:
                error_detail = res.json().get('detail', 'Unknown error')
                console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def view_team_invitation():
    """Takım davet bilgilerini göster"""
    console.print()
    team_id = Prompt.ask("[rgb(167,199,231)]Enter team ID[/rgb(167,199,231)]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching invitation details...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/team/{team_id}/invitation", headers=get_api_headers())
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            info_panel = Panel(
                f"[rgb(167,199,231)]Team Invitation Details[/rgb(167,199,231)]\n\n"
                f"Team: [white]{result.get('team_name')}[/white]\n"
                f"Invitation ID: [white]{result.get('invitation_id')}[/white]\n\n"
                f"[dim]Share the invitation ID and password with team members.[/dim]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(info_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)]Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)]Error: {e}[/rgb(167,199,231)]")


def security_analysis():
    """Güvenlik analizi"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Security Analysis[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]Analyze logs, network traffic, and system metrics for security threats.[/rgb(167,199,231)]",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    # Input seçenekleri
    choice = Prompt.ask(
        "[rgb(167,199,231)]Choose input method[/rgb(167,199,231)]",
        choices=["logs", "file", "paste"],
        default="logs"
    )
    
    logs_content = ""
    network_traffic = None
    
    if choice == "file":
        path = Prompt.ask("[rgb(167,199,231)]Enter log file path[/rgb(167,199,231)]")
        try:
            with Status("[rgb(167,199,231)]Reading file...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
                with open(path, "r", encoding="utf-8") as f:
                    logs_content = f.read()
        except FileNotFoundError:
            console.print(f"[rgb(167,199,231)] File not found: {path}[/rgb(167,199,231)]")
            return
        except Exception as e:
            console.print(f"[rgb(167,199,231)] Error reading file: {e}[/rgb(167,199,231)]")
            return
    elif choice == "paste":
        logs_content = get_multiline_input_simple("[rgb(167,199,231)]Paste logs/network traffic[/rgb(167,199,231)]")
    else:
        # Komut çalıştır
        command = Prompt.ask("[rgb(167,199,231)]Enter command to get logs[/rgb(167,199,231)]", default="")
        if command:
            try:
                is_windows = platform.system() == "Windows"
                if is_windows:
                    process = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                else:
                    cmd_parts = shlex.split(command)
                    process = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                logs_content = process.stdout + process.stderr
            except Exception as e:
                console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")
                return
    
    if not logs_content:
        console.print("[rgb(167,199,231)] No content provided![/rgb(167,199,231)]")
        return
    
    try:
        with Status("[rgb(167,199,231)]Analyzing security threats...[/rgb(167,199,231)]", spinner="dots12", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/security/analyze",
                json={
                    "logs": logs_content,
                    "network_traffic": network_traffic
                },
                headers=get_api_headers(),
                timeout=30
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            
            # Security Score
            score = result.get('security_score', 100)
            score_color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
            
            score_panel = Panel(
                f"[bold {score_color}]Security Score: {score:.1f}/100[/bold {score_color}]\n"
                f"[white]Threats Detected:[/white] {result.get('threats_detected', 0)}\n"
                f"[white]Threat Level:[/white] {result.get('threat_level', 'low').upper()}\n"
                f"[white]Vulnerabilities:[/white] {len(result.get('vulnerabilities', []))}",
                title="[bold white]Security Analysis Results[/bold white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(score_panel)
            
            # Threats
            threats = result.get('threats', [])
            if threats:
                console.print()
                console.print("[rgb(167,199,231)]Threats Detected:[/rgb(167,199,231)]")
                for threat in threats[:10]:  # İlk 10 threat
                    threat_type = threat.get('type', 'unknown')
                    level = threat.get('level', 'low')
                    level_colors = {
                        'critical': 'red',
                        'high': 'yellow',
                        'medium': 'yellow',
                        'low': 'dim'
                    }
                    color = level_colors.get(level, 'white')
                    console.print(f"  [{color}]•[/{color}] [{color}]{level.upper()}[/{color}] {threat_type}: {threat.get('line', '')[:80]}")
            
            # Vulnerabilities
            vulnerabilities = result.get('vulnerabilities', [])
            if vulnerabilities:
                console.print()
                console.print("[rgb(167,199,231)]Vulnerabilities:[/rgb(167,199,231)]")
                for vuln in vulnerabilities:
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {vuln}")
            
            # Recommendations
            recommendations = result.get('recommendations', [])
            if recommendations:
                console.print()
                console.print("[rgb(167,199,231)]Recommendations:[/rgb(167,199,231)]")
                for rec in recommendations:
                    console.print(f"  [white]•[/white] {rec}")
            
            # Summary
            console.print()
            summary_panel = Panel(
                result.get('summary', 'Analysis completed'),
                title="[bold white]Summary[/bold white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(summary_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def report_security_event():
    """Güvenlik olayı raporla"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Report Security Event[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]Report a security incident or threat detection.[/rgb(167,199,231)]",
        title="Security Event",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    event_type = Prompt.ask(
        "[rgb(167,199,231)]Event Type[/rgb(167,199,231)]",
        choices=["intrusion_attempt", "malware_detected", "suspicious_activity", 
                 "unauthorized_access", "data_breach", "ddos_attack", "phishing", 
                 "vulnerability", "other"],
        default="suspicious_activity"
    )
    
    threat_level = Prompt.ask(
        "[rgb(167,199,231)]Threat Level[/rgb(167,199,231)]",
        choices=["low", "medium", "high", "critical"],
        default="medium"
    )
    
    title = Prompt.ask("[rgb(167,199,231)]Event Title[/rgb(167,199,231)]")
    description = get_multiline_input_simple("[rgb(167,199,231)]Description[/rgb(167,199,231)]")
    
    source_ip = Prompt.ask("[rgb(167,199,231)]Source IP (optional)[/rgb(167,199,231)]", default="")
    target_resource = Prompt.ask("[rgb(167,199,231)]Target Resource (optional)[/rgb(167,199,231)]", default="")
    
    # Critical/High threat level için otomatik workflow oluşturma seçeneği
    auto_create_workflow = False
    if threat_level in ["critical", "high"]:
        auto_create_workflow = Confirm.ask(
            "[rgb(167,199,231)]Auto-generate remediation workflow?[/rgb(167,199,231)]",
            default=False
        )
    
    try:
        with Status("[rgb(167,199,231)]Reporting security event...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/security/events",
                params={"auto_create_workflow": str(auto_create_workflow).lower()},
                json={
                    "event_type": event_type,
                    "threat_level": threat_level,
                    "title": title,
                    "description": description,
                    "source_ip": source_ip if source_ip else None,
                    "target_resource": target_resource if target_resource else None
                }
            )
        
        if res.status_code == 200:
            event = res.json()
            console.print()
            
            # Workflow oluşturuldu mu kontrol et
            workflow_name = None
            if event.get('metadata') and event.get('metadata').get('generated_workflow'):
                workflow_name = event.get('metadata').get('generated_workflow')
            
            success_msg = f"[white]Security event reported successfully![/white]\n\n"
            success_msg += f"Event ID: [white]{event.get('id')}[/white]\n"
            success_msg += f"Threat Level: [white]{event.get('threat_level', '').upper()}[/white]"
            
            if workflow_name:
                success_msg += f"\n\n[rgb(167,199,231)]AI Generated Workflow:[/rgb(167,199,231)] [white]{workflow_name}[/white]"
            
            success_panel = Panel(
                success_msg,
                title="Success",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def list_security_events():
    """Güvenlik olaylarını listele"""
    console.print()
    
    threat_level_filter = Prompt.ask(
        "[white]Filter by threat level (optional)[/white]",
        choices=["", "low", "medium", "high", "critical"],
        default=""
    )
    
    status_filter = Prompt.ask(
        "[white]Filter by status (optional)[/white]",
        choices=["", "detected", "investigating", "resolved", "false_positive"],
        default=""
    )
    
    try:
        params = {}
        if threat_level_filter:
            params["threat_level"] = threat_level_filter
        if status_filter:
            params["status"] = status_filter
        
        with Status("[rgb(167,199,231)]Fetching security events...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/security/events", params=params)
        
        if res.status_code == 200:
            events = res.json()
            console.print()
            
            if not events:
                console.print("[rgb(167,199,231)]No security events found.[/rgb(167,199,231)]")
                return
            
            table = Table(
                title="[rgb(167,199,231)]Security Events[/rgb(167,199,231)]",
                box=box.SIMPLE,
                border_style="rgb(167,199,231)",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("ID", style="white", width=36)
            table.add_column("Type", style="white", width=20)
            table.add_column("Threat Level", style="rgb(167,199,231)", width=15)
            table.add_column("Title", style="white", width=25)
            table.add_column("Status", style="white", width=15)
            table.add_column("Detected", style="dim", width=20)
            
            threat_colors = {
                "critical": "red",
                "high": "yellow",
                "medium": "yellow",
                "low": "dim"
            }
            
            for event in events:
                event_id = event.get('id', 'N/A')[:8] + '...'
                event_type = event.get('event_type', 'N/A').replace('_', ' ').title()
                threat_level = event.get('threat_level', 'N/A')
                title = event.get('title', 'N/A')[:23] + '...' if len(event.get('title', '')) > 23 else event.get('title', 'N/A')
                status = event.get('status', 'N/A')
                detected = event.get('detected_at', 'N/A')[:19] if event.get('detected_at') else 'N/A'
                
                threat_color = threat_colors.get(threat_level, 'white')
                threat_display = f"[{threat_color}]{threat_level.upper()}[/{threat_color}]"
                
                table.add_row(event_id, event_type, threat_display, title, status, detected)
            
            console.print(table)
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def view_security_event():
    """Güvenlik olayı detaylarını görüntüle"""
    console.print()
    event_id = Prompt.ask("[white]Enter security event ID[/white]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching event details...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/security/events/{event_id}")
        
        if res.status_code == 200:
            event = res.json()
            console.print()
            
            threat_level = event.get('threat_level', 'unknown')
            threat_colors = {
                "critical": "red",
                "high": "yellow",
                "medium": "yellow",
                "low": "dim"
            }
            threat_color = threat_colors.get(threat_level, 'white')
            
            info_text = f"[white]ID:[/white] {event.get('id')}\n"
            info_text += f"[white]Type:[/white] {event.get('event_type', 'N/A').replace('_', ' ').title()}\n"
            info_text += f"[white]Threat Level:[/white] [{threat_color}]{threat_level.upper()}[/{threat_color}]\n"
            info_text += f"[white]Title:[/white] {event.get('title')}\n"
            info_text += f"[white]Description:[/white] {event.get('description')}\n"
            info_text += f"[white]Status:[/white] {event.get('status', 'N/A')}\n"
            info_text += f"[white]Detected:[/white] {event.get('detected_at')}\n"
            
            if event.get('resolved_at'):
                info_text += f"[white]Resolved:[/white] {event.get('resolved_at')}\n"
            if event.get('source_ip'):
                info_text += f"[white]Source IP:[/white] {event.get('source_ip')}\n"
            if event.get('target_resource'):
                info_text += f"[white]Target:[/white] {event.get('target_resource')}\n"
            
            # Generated workflow bilgisi
            if event.get('metadata') and event.get('metadata').get('generated_workflow'):
                workflow_name = event.get('metadata').get('generated_workflow')
                info_text += f"\n[rgb(167,199,231)]Generated Workflow:[/rgb(167,199,231)] [white]{workflow_name}[/white]"
            
            info_panel = Panel(
                info_text,
                title="[bold white]Security Event Details[/bold white]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(info_panel)
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)] Security event '{event_id}' not found[/rgb(167,199,231)]")
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def generate_workflow_for_security_event():
    """Security event için AI ile workflow oluştur"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Generate Workflow for Security Event[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]AI will analyze the security event and create a custom remediation workflow.[/rgb(167,199,231)]",
        border_style="rgb(167,199,231)",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    event_id = Prompt.ask("[rgb(167,199,231)]Enter security event ID[/rgb(167,199,231)]")
    
    auto_run = Confirm.ask(
        "[rgb(167,199,231)]Automatically run the generated workflow?[/rgb(167,199,231)]",
        default=False
    )
    
    try:
        with Status("[rgb(167,199,231)]AI is analyzing event and generating workflow...[/rgb(167,199,231)]", spinner="dots12", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/security/events/{event_id}/generate-workflow",
                params={"auto_run": str(auto_run).lower()},
                timeout=120  # AI generation için daha uzun timeout
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            
            auto_run_msg = f"[rgb(167,199,231)]Workflow will be executed automatically[/rgb(167,199,231)]" if result.get('auto_run') else "[dim]You can run the workflow manually from the Workflow Management menu[/dim]"
            
            success_panel = Panel(
                f"[rgb(167,199,231)]Workflow generated successfully![/rgb(167,199,231)]\n\n"
                f"Workflow Name: [rgb(167,199,231)]{result.get('workflow_name')}[/rgb(167,199,231)]\n"
                f"Event ID: [rgb(167,199,231)]{result.get('event_id')}[/rgb(167,199,231)]\n"
                f"Auto Run: [rgb(167,199,231)]{'Yes' if result.get('auto_run') else 'No'}[/rgb(167,199,231)]\n\n"
                f"{auto_run_msg}",
                border_style="rgb(167,199,231)",
                box=box.SIMPLE
            )
            console.print(success_panel)
            
            if result.get('workflow_name'):
                console.print()
                if Confirm.ask("[rgb(167,199,231)]View the generated workflow?[/rgb(167,199,231)]", default=True):
                    # Workflow'u göster
                    try:
                        wf_res = requests.get(f"{API_URL}/workflow/{result.get('workflow_name')}")
                        if wf_res.status_code == 200:
                            workflow = wf_res.json()
                            console.print()
                            workflow_panel = Panel(
                                f"[rgb(167,199,231)]Name:[/rgb(167,199,231)] {workflow.get('name')}\n"
                                f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {workflow.get('description', 'N/A')}\n"
                                f"[rgb(167,199,231)]Steps:[/rgb(167,199,231)] {len(workflow.get('steps', []))}",
                                title="[bold rgb(167,199,231)]Generated Workflow[/bold rgb(167,199,231)]",
                                border_style="rgb(167,199,231)",
                                box=box.SIMPLE
                            )
                            console.print(workflow_panel)
                    except:
                        pass
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)] Security event '{event_id}' not found[/rgb(167,199,231)]")
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def security_scan():
    """Güvenlik taraması başlat"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Security Scan[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]Perform a security scan to detect vulnerabilities and threats.[/rgb(167,199,231)]",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    scan_type = Prompt.ask(
        "[rgb(167,199,231)]Scan Type[/rgb(167,199,231)]",
        choices=["quick", "full", "custom"],
        default="quick"
    )
    
    target = Prompt.ask("[rgb(167,199,231)]Target (optional)[/rgb(167,199,231)]", default="")
    
    try:
        with Status("[rgb(167,199,231)]Starting security scan...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.post(
                f"{API_URL}/security/scan",
                json={
                    "scan_type": scan_type,
                    "target": target if target else None
                }
            )
        
        if res.status_code == 200:
            scan = res.json()
            console.print()
            success_panel = Panel(
                f"[rgb(167,199,231)]Security scan started![/rgb(167,199,231)]\n\n"
                f"Scan ID: [rgb(167,199,231)]{scan.get('scan_id')}[/rgb(167,199,231)]\n"
                f"Type: [rgb(167,199,231)]{scan.get('scan_type')}[/rgb(167,199,231)]\n"
                f"Status: [rgb(167,199,231)]{scan.get('status')}[/rgb(167,199,231)]\n\n"
                f"[dim rgb(167,199,231)]Use option 5.5 to check scan results.[/dim rgb(167,199,231)]",
                title="Success",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(success_panel)
            
            # Scan sonuçlarını bekle (opsiyonel)
            if Confirm.ask("[rgb(167,199,231)]Wait for scan to complete?[/rgb(167,199,231)]", default=False):
                console.print()
                console.print("[dim rgb(167,199,231)]Waiting for scan to complete...[/dim rgb(167,199,231)]")
                time.sleep(3)  # Simüle edilmiş tarama için bekle
                
                # Sonuçları getir
                scan_res = requests.get(f"{API_URL}/security/scan/{scan.get('scan_id')}")
                if scan_res.status_code == 200:
                    scan_result = scan_res.json()
                    console.print()
                    result_panel = Panel(
                        f"[rgb(167,199,231)]Scan Results:[/rgb(167,199,231)]\n"
                        f"[rgb(167,199,231)]Vulnerabilities Found:[/rgb(167,199,231)] {scan_result.get('vulnerabilities_found', 0)}\n"
                        f"[rgb(167,199,231)]Threats Found:[/rgb(167,199,231)] {scan_result.get('threats_found', 0)}\n"
                        f"[rgb(167,199,231)]Status:[/rgb(167,199,231)] {scan_result.get('status', 'N/A')}",
                        border_style="white",
                        box=box.SIMPLE
                    )
                    console.print(result_panel)
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def security_recommendations():
    """Güvenlik önerilerini göster"""
    try:
        with Status("[rgb(167,199,231)]Fetching security recommendations...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/security/recommendations")
        
        if res.status_code == 200:
            recommendations = res.json()
            console.print()
            
            if not recommendations:
                console.print("[rgb(167,199,231)]No recommendations available.[/rgb(167,199,231)]")
                return
            
            for rec in recommendations:
                priority = rec.get('priority', 'low')
                priority_colors = {
                    'critical': 'red',
                    'high': 'yellow',
                    'medium': 'yellow',
                    'low': 'dim'
                }
                color = priority_colors.get(priority, 'white')
                
                rec_panel = Panel(
                    f"[rgb(167,199,231)]Title:[/rgb(167,199,231)] {rec.get('title', 'Recommendation')}\n"
                    f"[rgb(167,199,231)]Category:[/rgb(167,199,231)] {rec.get('category', 'N/A').title()}\n"
                    f"[rgb(167,199,231)]Priority:[/rgb(167,199,231)] [{color}]{priority.upper()}[/{color}]\n"
                    f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {rec.get('description', 'N/A')}\n\n"
                    + "\n".join([f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {item}" for item in rec.get('action_items', [])]),
                    border_style="white",
                    box=box.SIMPLE
                )
                console.print(rec_panel)
                console.print()
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def security_stats():
    """Güvenlik istatistiklerini göster"""
    try:
        with Status("[rgb(167,199,231)]Fetching security statistics...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/security/stats/summary")
        
        if res.status_code == 200:
            stats = res.json()
            console.print()
            
            table = Table(
                title="[rgb(167,199,231)]Security Statistics[/rgb(167,199,231)]",
                box=box.SIMPLE,
                border_style="rgb(167,199,231)",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("Metric", style="rgb(167,199,231)", width=25)
            table.add_column("Value", style="rgb(167,199,231)", width=20)
            
            table.add_row("Total Events", str(stats.get('total_events', 0)))
            table.add_row("Total Scans", str(stats.get('total_scans', 0)))
            table.add_row("Critical Events", f"[rgb(167,199,231)]{stats.get('critical_events', 0)}[/rgb(167,199,231)]")
            table.add_row("High Events", f"[rgb(167,199,231)]{stats.get('high_events', 0)}[/rgb(167,199,231)]")
            table.add_row("Active Threats", f"[rgb(167,199,231)]{stats.get('active_threats', 0)}[/rgb(167,199,231)]")
            
            console.print(table)
            
            # By threat level
            if stats.get('by_threat_level'):
                console.print()
                threat_table = Table(
                    title="[rgb(167,199,231)]By Threat Level[/rgb(167,199,231)]",
                    box=box.SIMPLE,
                    border_style="rgb(167,199,231)",
                    show_header=True,
                    header_style="rgb(167,199,231)"
                )
                threat_table.add_column("Threat Level", style="rgb(167,199,231)", width=20)
                threat_table.add_column("Count", style="rgb(167,199,231)", width=15)
                
                for level, count in stats.get('by_threat_level', {}).items():
                    threat_table.add_row(level.upper(), str(count))
                
                console.print(threat_table)
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def list_workflows():
    """Workflow'ları listele"""
    try:
        with Status("[rgb(167,199,231)]Fetching workflows...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/workflow/")
        
        if res.status_code == 200:
            workflows = res.json()
            console.print()
            
            if not workflows:
                console.print("[rgb(167,199,231)]No workflows found.[/rgb(167,199,231)]")
                return
            
            table = Table(
                title="[bold white]Available Workflows[/bold white]",
                box=box.SIMPLE,
                border_style="white",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("Name", style="rgb(167,199,231)", width=25)
            table.add_column("Description", style="rgb(167,199,231)", width=30)
            table.add_column("Steps", style="rgb(167,199,231)", width=10)
            table.add_column("Source", style="dim rgb(167,199,231)", width=15)
            
            for wf in workflows:
                name = wf.get("name", "N/A")
                desc = wf.get("description", "No description") or "No description"
                steps = wf.get("steps_count", 0)
                source = "File" if wf.get("file") else "Registered"
                table.add_row(name, desc[:40] + "..." if len(desc) > 40 else desc, str(steps), source)
            
            console.print(table)
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def view_workflow():
    """Workflow detaylarını görüntüle"""
    console.print()
    wf_name = Prompt.ask("[rgb(167,199,231)]Enter workflow name[/rgb(167,199,231)]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching workflow details...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/workflow/{wf_name}")
        
        if res.status_code == 200:
            workflow = res.json()
            console.print()
            
            # Workflow bilgileri
            triggers = workflow.get('triggers') or []
            triggers_str = ', '.join(triggers) if triggers else 'None'
            info_panel = Panel(
                f"[bold rgb(167,199,231)]Workflow: {workflow.get('name')}[/bold rgb(167,199,231)]\n"
                f"[rgb(167,199,231)]Name:[/rgb(167,199,231)] {workflow.get('name')}\n"
                f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {workflow.get('description', 'No description') or 'No description'}\n"
                f"[rgb(167,199,231)]Steps:[/rgb(167,199,231)] {len(workflow.get('steps', []))}\n"
                f"[rgb(167,199,231)]Triggers:[/rgb(167,199,231)] {triggers_str}\n"
                f"[rgb(167,199,231)]Timeout:[/rgb(167,199,231)] {workflow.get('timeout', 'Not set')}",
                border_style="white",
                padding=(0, 0),
                box=box.SIMPLE
            )
            console.print(info_panel)
            
            # Steps tablosu
            if workflow.get('steps'):
                console.print()
                steps_table = Table(
                    title="[bold rgb(167,199,231)]Workflow Steps[/bold rgb(167,199,231)]",
                    box=box.SIMPLE,
                    border_style="white",
                    show_header=True,
                    header_style="rgb(167,199,231)"
                )
                steps_table.add_column("#", style="rgb(167,199,231)", width=5)
                steps_table.add_column("Action", style="rgb(167,199,231)", width=20)
                steps_table.add_column("Service/Command", style="rgb(167,199,231)", width=25)
                steps_table.add_column("Timeout", style="dim rgb(167,199,231)", width=10)
                steps_table.add_column("Retry", style="dim rgb(167,199,231)", width=10)
                
                for idx, step in enumerate(workflow.get('steps', []), 1):
                    action = step.get('action', 'N/A')
                    service = step.get('service') or step.get('command') or 'N/A'
                    timeout = str(step.get('timeout', 'N/A'))
                    retry = str(step.get('retry', 'N/A'))
                    steps_table.add_row(str(idx), action, service, timeout, retry)
                
                console.print(steps_table)
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)] Workflow '{wf_name}' not found[/rgb(167,199,231)]")
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def check_workflow_status():
    """Workflow run durumunu kontrol et"""
    console.print()
    run_id = Prompt.ask("[rgb(167,199,231)]Enter workflow run ID[/rgb(167,199,231)]")
    
    try:
        with Status("[rgb(167,199,231)]Fetching run status...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/workflow/runs/{run_id}")
        
        if res.status_code == 200:
            run = res.json()
            console.print()
            
            # Status icon
            status = run.get('status', 'unknown')
            status_icons = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '[rgb(167,199,231)]COMPLETED[/rgb(167,199,231)]',
                'failed': '',
                'cancelled': '🚫'
            }
            icon = status_icons.get(status, '❓')
            
            status_panel = Panel(
                f"[rgb(167,199,231)]Run ID:[/rgb(167,199,231)] {run.get('id')}\n"
                f"[rgb(167,199,231)]Workflow:[/rgb(167,199,231)] {run.get('workflow_name')}\n"
                f"[rgb(167,199,231)]Status:[/rgb(167,199,231)] {icon} {status.upper()}\n"
                f"[rgb(167,199,231)]Started:[/rgb(167,199,231)] {run.get('started_at')}\n"
                f"[rgb(167,199,231)]Completed:[/rgb(167,199,231)] {run.get('completed_at', 'N/A')}\n"
                f"[rgb(167,199,231)]Steps Executed:[/rgb(167,199,231)] {len(run.get('steps_executed', []))}\n"
                + (f"[rgb(167,199,231)]Error:[/rgb(167,199,231)] {run.get('error')}\n" if run.get('error') else ""),
                title=f"[bold rgb(167,199,231)]Workflow Run Status[/bold rgb(167,199,231)]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(status_panel)
            
            # Steps executed
            if run.get('steps_executed'):
                console.print()
                console.print("[rgb(167,199,231)]Executed Steps:[/rgb(167,199,231)]")
                for step in run.get('steps_executed', []):
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {step}")
            
            # Output
            if run.get('output'):
                console.print()
                console.print("[rgb(167,199,231)]📤 Output:[/rgb(167,199,231)]")
                import json
                console.print(json.dumps(run.get('output'), indent=2))
        elif res.status_code == 404:
            console.print(f"[rgb(167,199,231)] Run ID '{run_id}' not found[/rgb(167,199,231)]")
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def list_workflow_runs():
    """Workflow run'larını listele"""
    console.print()
    workflow_name = Prompt.ask("[rgb(167,199,231)]Filter by workflow name (optional)[/rgb(167,199,231)]", default="")
    status_filter = Prompt.ask(
        "[rgb(167,199,231)]Filter by status (optional)[/rgb(167,199,231)]",
        choices=["", "pending", "running", "completed", "failed", "cancelled"],
        default=""
    )
    
    try:
        params = {}
        if workflow_name:
            params["workflow_name"] = workflow_name
        if status_filter:
            params["status"] = status_filter
        
        with Status("[rgb(167,199,231)]Fetching workflow runs...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/workflow/runs", params=params)
        
        if res.status_code == 200:
            runs = res.json()
            console.print()
            
            if not runs:
                console.print("[rgb(167,199,231)]No workflow runs found.[/rgb(167,199,231)]")
                return
            
            table = Table(
                title="[bold rgb(167,199,231)]Workflow Runs[/bold rgb(167,199,231)]",
                box=box.SIMPLE,
                border_style="white",
                show_header=True,
                header_style="rgb(167,199,231)"
            )
            table.add_column("Run ID", style="rgb(167,199,231)", width=36)
            table.add_column("Workflow", style="rgb(167,199,231)", width=20)
            table.add_column("Status", style="rgb(167,199,231)", width=12)
            table.add_column("Started", style="dim rgb(167,199,231)", width=20)
            table.add_column("Completed", style="dim rgb(167,199,231)", width=20)
            
            status_icons = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '[rgb(167,199,231)]COMPLETED[/rgb(167,199,231)]',
                'failed': '',
                'cancelled': '🚫'
            }
            
            for run in runs:
                run_id = run.get('id', 'N/A')[:8] + '...'
                workflow = run.get('workflow_name', 'N/A')
                status = run.get('status', 'unknown')
                icon = status_icons.get(status, '❓')
                started = run.get('started_at', 'N/A')[:19] if run.get('started_at') else 'N/A'
                completed = run.get('completed_at', 'N/A')[:19] if run.get('completed_at') else 'N/A'
                table.add_row(run_id, workflow, f"{icon} {status}", started, completed)
            
            console.print(table)
        else:
            console.print(f"[rgb(167,199,231)] Error: {res.status_code}[/rgb(167,199,231)]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def generate_workflow_ai():
    """AI ile workflow oluşturma"""
    # Token kontrolü
    token_status = check_token()
    if not token_status.get("token_set"):
        console.print()
        warning = Panel(
            "[rgb(167,199,231)]Warning:[/rgb(167,199,231)]\n"
            "[rgb(167,199,231)] Token not set![/rgb(167,199,231)]"
            "[rgb(167,199,231)]AI workflow generation requires a Hugging Face API token.[/rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)
        console.print()
        
        if Confirm.ask("[rgb(167,199,231)]Would you like to set token now?[/rgb(167,199,231)]"):
            set_token()
            token_status = check_token()
            if not token_status.get("token_set"):
                console.print("[rgb(167,199,231)] Token setup failed. Cannot proceed.[/rgb(167,199,231)]")
                return
        else:
            return
    
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]AI Workflow Generator[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]Describe what you want your workflow to do in natural language.[/rgb(167,199,231)]\n"
        "[dim rgb(167,199,231)]Example: 'Restart nginx service, then check if it's running'[/dim rgb(167,199,231)]\n"
        "[dim rgb(167,199,231)]         'Deploy my app: build, test, and deploy to production'[/dim rgb(167,199,231)]",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    # Workflow açıklaması al
    description = get_multiline_input_simple("[rgb(167,199,231)]Describe your workflow[/rgb(167,199,231)]")
    
    if not description:
        console.print("[rgb(167,199,231)] Workflow description cannot be empty![/rgb(167,199,231)]")
        return
    
    # Context (opsiyonel)
    context = {}
    if Confirm.ask("[rgb(167,199,231)]Do you have additional context (platform, services, etc.)?[/rgb(167,199,231)]", default=False):
        console.print()
        context_input = get_multiline_input_simple("[rgb(167,199,231)]Additional context[/rgb(167,199,231)]")
        if context_input:
            context["notes"] = context_input
    
    try:
        console.print()
        
        # Loading animasyonu ile workflow oluştur
        with Status(
            "[rgb(167,199,231)]Generating workflow with AI...[/rgb(167,199,231)]",
            spinner="dots12",
            spinner_style="rgb(167,199,231)"
        ):
            res = requests.post(
                f"{API_URL}/workflow/generate",
                json={
                    "description": description,
                    "context": context if context else None
                },
                headers=get_api_headers(),
                timeout=120  # AI generation için daha uzun timeout
            )
        
        if res.status_code == 200:
            result = res.json()
            console.print()
            console.print("[rgb(167,199,231)]Workflow Generated Successfully![/rgb(167,199,231)]")
            console.print()
            
            # Workflow bilgileri
            info_panel = Panel(
                f"[rgb(167,199,231)]Name:[/rgb(167,199,231)] {result.get('workflow_name')}\n"
                f"[rgb(167,199,231)]Message:[/rgb(167,199,231)] {result.get('message')}",
                border_style="rgb(167,199,231)",
                box=box.SIMPLE
            )
            console.print(info_panel)
            
            # YAML içeriğini göster
            yaml_content = result.get('yaml_content', '')
            if yaml_content:
                console.print()
                yaml_panel = Panel(
                    yaml_content,
                    title="[bold rgb(167,199,231)]Generated YAML[/bold rgb(167,199,231)]",
                    border_style="white",
                    box=box.SIMPLE,
                    padding=(0, 0)
                )
                console.print(yaml_panel)
            
            # Workflow detayları
            workflow_def = result.get('workflow_definition', {})
            if workflow_def.get('steps'):
                console.print()
                console.print("[rgb(167,199,231)]Workflow Steps:[/rgb(167,199,231)]")
                for idx, step in enumerate(workflow_def.get('steps', []), 1):
                    action = step.get('action', 'N/A')
                    service = step.get('service') or step.get('command') or 'N/A'
                    console.print(f"  [white]{idx}.[/white] {action}: {service}")
            
            # Dosyaya kaydetme seçeneği
            console.print()
            if Confirm.ask("[rgb(167,199,231)]Save workflow to file?[/rgb(167,199,231)]", default=True):
                workflow_name = result.get('workflow_name', 'generated_workflow')
                filename = f"{workflow_name}.yml"
                
                # Kullanıcı workflow dizinine kaydet (~/.neurops/workflows/)
                ensure_user_workflows_dir()
                filepath = USER_WORKFLOWS_DIR / filename
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(yaml_content)
                    console.print(f"[rgb(167,199,231)]Workflow saved to: {filepath}[/rgb(167,199,231)]")
                    console.print(f"[dim rgb(167,199,231)]This workflow is now available in your local workflows directory.[/dim rgb(167,199,231)]")
                except Exception as e:
                    console.print(f"[rgb(167,199,231)] Error saving file: {e}[/rgb(167,199,231)]")
        
        else:
            error_detail = res.json().get('detail', 'Unknown error')
            error_panel = Panel(
                f"[rgb(167,199,231)] Workflow generation failed:[/rgb(167,199,231)]\n\n{error_detail}",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(error_panel)
    
    except requests.Timeout:
        error_panel = Panel(
            "[rgb(167,199,231)] Request Timeout[/rgb(167,199,231)]\n\n"
            "The AI workflow generation took longer than 2 minutes.\n"
            "This can happen if:\n"
            "  • The AI service is slow or overloaded\n"
            "  • Your description is very complex\n"
            "  • Network connection is slow\n\n"
            "[rgb(167,199,231)]Try again with a simpler description or check your connection.[/rgb(167,199,231)]",
            title="Timeout",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(Align.center(error_panel), width=80)
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def execute_workflow_step_local(step: dict) -> dict:
    """
    Workflow step'ini kullanıcının lokal terminalinde çalıştırır.
    """
    result = {
        "action": step.get("action"),
        "status": "completed",
        "output": None,
        "error": None
    }
    
    try:
        is_windows = platform.system() == "Windows"
        action = step.get("action")
        
        if action == "run_command":
            # Command field'ını kontrol et - farklı isimlerle de gelebilir
            command = step.get("command") or step.get("cmd") or step.get("execute")
            if not command:
                # Step'in tüm içeriğini göster (debug için)
                console.print(f"[rgb(167,199,231)] Step data: {step}[/rgb(167,199,231)]")
                result["status"] = "failed"
                result["error"] = f"Command not specified in step. Step has fields: {list(step.keys())}. This workflow may have been generated incorrectly. Please regenerate it using 'AI - Generate Workflow'."
                return result
            
            try:
                console.print(f"[dim]Executing: {command}[/dim]")
                
                if is_windows:
                    process = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 300,
                        check=False
                    )
                else:
                    cmd_parts = shlex.split(command)
                    process = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 300,
                        check=False
                    )
                
                if process.stdout:
                    console.print(f"[white]Output:[/white]\n{process.stdout}")
                if process.stderr:
                    console.print(f"[rgb(167,199,231)]Stderr:[/rgb(167,199,231)]\n{process.stderr}")
                
                result["output"] = {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode
                }
                
                if process.returncode != 0:
                    result["status"] = "failed"
                    result["error"] = f"Command failed with return code {process.returncode}"
                    console.print(f"[rgb(167,199,231)] Command failed (exit code: {process.returncode})[/rgb(167,199,231)]")
                else:
                    console.print(f"[white]Command completed successfully[/white]")
                
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["error"] = f"Command timed out after {step.get('timeout') or 300} seconds"
                console.print(f"[rgb(167,199,231)] Command timed out[/rgb(167,199,231)]")
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error executing command: {str(e)}"
                console.print(f"[rgb(167,199,231)] Error: {str(e)}[/rgb(167,199,231)]")
        
        elif action == "stop_service":
            service = step.get("service")
            if not service:
                result["status"] = "failed"
                result["error"] = "Service name not specified"
                return result
            
            try:
                console.print(f"[dim]Stopping service: {service}[/dim]")
                
                if is_windows:
                    cmd = f"net stop {service}"
                    process = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                else:
                    cmd_parts = ["systemctl", "stop", service]
                    process = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                
                if process.stdout:
                    console.print(process.stdout)
                if process.stderr:
                    console.print(f"[rgb(167,199,231)]{process.stderr}[/rgb(167,199,231)]")
                
                result["output"] = {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode
                }
                
                if process.returncode != 0:
                    result["status"] = "failed"
                    result["error"] = f"Failed to stop service: {process.stderr}"
                    console.print(f"[rgb(167,199,231)] Failed to stop service[/rgb(167,199,231)]")
                else:
                    console.print(f"[white]Service {service} stopped successfully[/white]")
                    
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["error"] = "Service stop timed out"
                console.print(f"[rgb(167,199,231)] Service stop timed out[/rgb(167,199,231)]")
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error stopping service: {str(e)}"
                console.print(f"[rgb(167,199,231)] Error: {str(e)}[/rgb(167,199,231)]")
        
        elif action == "start_service":
            service = step.get("service")
            if not service:
                result["status"] = "failed"
                result["error"] = "Service name not specified"
                return result
            
            try:
                console.print(f"[dim]Starting service: {service}[/dim]")
                
                if is_windows:
                    cmd = f"net start {service}"
                    process = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                else:
                    cmd_parts = ["systemctl", "start", service]
                    process = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                
                if process.stdout:
                    console.print(process.stdout)
                if process.stderr:
                    console.print(f"[rgb(167,199,231)]{process.stderr}[/rgb(167,199,231)]")
                
                result["output"] = {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode
                }
                
                if process.returncode != 0:
                    result["status"] = "failed"
                    result["error"] = f"Failed to start service: {process.stderr}"
                    console.print(f"[rgb(167,199,231)] Failed to start service[/rgb(167,199,231)]")
                else:
                    console.print(f"[white]Service {service} started successfully[/white]")
                    
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["error"] = "Service start timed out"
                console.print(f"[rgb(167,199,231)] Service start timed out[/rgb(167,199,231)]")
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error starting service: {str(e)}"
                console.print(f"[rgb(167,199,231)] Error: {str(e)}[/rgb(167,199,231)]")
        
        elif action == "restart_service":
            service = step.get("service")
            if not service:
                result["status"] = "failed"
                result["error"] = "Service name not specified"
                return result
            
            try:
                console.print(f"[dim]Restarting service: {service}[/dim]")
                
                if is_windows:
                    stop_cmd = f"net stop {service}"
                    start_cmd = f"net start {service}"
                    
                    stop_process = subprocess.run(
                        stop_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                    
                    if stop_process.returncode == 0:
                        start_process = subprocess.run(
                            start_cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=step.get("timeout") or 60,
                            check=False
                        )
                        process = start_process
                    else:
                        process = stop_process
                else:
                    cmd_parts = ["systemctl", "restart", service]
                    process = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=step.get("timeout") or 60,
                        check=False
                    )
                
                if process.stdout:
                    console.print(process.stdout)
                if process.stderr:
                    console.print(f"[rgb(167,199,231)]{process.stderr}[/rgb(167,199,231)]")
                
                result["output"] = {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "returncode": process.returncode
                }
                
                if process.returncode != 0:
                    result["status"] = "failed"
                    result["error"] = f"Failed to restart service: {process.stderr}"
                    console.print(f"[rgb(167,199,231)] Failed to restart service[/rgb(167,199,231)]")
                else:
                    console.print(f"[white]Service {service} restarted successfully[/white]")
                    
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["error"] = "Service restart timed out"
                console.print(f"[rgb(167,199,231)] Service restart timed out[/rgb(167,199,231)]")
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error restarting service: {str(e)}"
                console.print(f"[rgb(167,199,231)] Error: {str(e)}[/rgb(167,199,231)]")
        
        else:
            result["status"] = "failed"
            result["error"] = f"Unknown action type: {action}"
            console.print(f"[rgb(167,199,231)] Unknown action: {action}[/rgb(167,199,231)]")
    
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        console.print(f"[rgb(167,199,231)] Error: {str(e)}[/rgb(167,199,231)]")
    
    return result


def run_workflow():
    """Workflow çalıştırma - lokal terminalde"""
    console.print()
    
    # Önce workflow'ları listele
    try:
        res = requests.get(f"{API_URL}/workflow/")
        if res.status_code == 200:
            workflows = res.json()
            if workflows:
                console.print("[rgb(167,199,231)]Available workflows:[/rgb(167,199,231)]")
                for wf in workflows[:10]:  # İlk 10'unu göster
                    console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {wf.get('name')}")
                console.print()
    except:
        pass
    
    wf_name = Prompt.ask("[rgb(167,199,231)]Enter workflow name[/rgb(167,199,231)]")
    
    # Workflow tanımını backend'den al
    try:
        with Status("[rgb(167,199,231)]Loading workflow...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            res = requests.get(f"{API_URL}/workflow/{wf_name}")
        
        if res.status_code != 200:
            error_detail = res.json().get('detail', 'Unknown error') if res.status_code != 404 else "Workflow not found"
            console.print(f"[rgb(167,199,231)] Error: {error_detail}[/rgb(167,199,231)]")
            return
        
        workflow = res.json()
        
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error loading workflow: {e}[/rgb(167,199,231)]")
        return
    
    # Workflow bilgilerini göster
    console.print()
    info_panel = Panel(
        f"[bold rgb(167,199,231)]Workflow:[/bold rgb(167,199,231)]\n"
        f"[rgb(167,199,231)]Name:[/rgb(167,199,231)] {workflow.get('name')}\n"
        f"[rgb(167,199,231)]Description:[/rgb(167,199,231)] {workflow.get('description', 'No description') or 'No description'}\n"
        f"[rgb(167,199,231)]Steps:[/rgb(167,199,231)] {len(workflow.get('steps', []))}",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(Align.center(info_panel), width=80)
    console.print()
    
    # Onay iste
    if not Confirm.ask("[rgb(167,199,231)]Run this workflow in your local terminal?[/rgb(167,199,231)]", default=True):
        console.print("[rgb(167,199,231)]Workflow execution cancelled.[/rgb(167,199,231)]")
        return
    
    console.print()
    console.print("[rgb(167,199,231)]🚀 Executing workflow steps...[/rgb(167,199,231)]")
    console.print()
    
    # Her step'i lokal olarak çalıştır
    steps = workflow.get('steps', [])
    executed_steps = []
    failed = False
    
    # Debug: Step'leri kontrol et
    if not steps:
        console.print("[rgb(167,199,231)] No steps found in workflow![/rgb(167,199,231)]")
        return
    
    for idx, step in enumerate(steps, 1):
        # Step'in tüm içeriğini debug için göster (sadece ilk seferde)
        if idx == 1:
            console.print(f"[dim rgb(167,199,231)]Debug: First step content: {step}[/dim rgb(167,199,231)]")
        
        step_name = step.get('action', 'unknown')
        service_or_cmd = step.get('service') or step.get('command') or 'N/A'
        
        console.print()
        step_header = Panel(
            f"[rgb(167,199,231)]Step {idx}/{len(steps)}: {step_name}[/rgb(167,199,231)]\n"
            f"[dim rgb(167,199,231)]{service_or_cmd}[/dim rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(step_header)
        console.print()
        
        # Step'i çalıştır
        step_result = execute_workflow_step_local(step)
        executed_steps.append({
            "step": idx,
            "action": step_name,
            "result": step_result
        })
        
        # Hata varsa durdur
        if step_result["status"] == "failed":
            failed = True
            console.print()
            error_panel = Panel(
                f"[rgb(167,199,231)] Step {idx} failed![/rgb(167,199,231)]\n\n"
                f"[bold rgb(167,199,231)]Error:[/bold rgb(167,199,231)] {step_result.get('error', 'Unknown error')}\n\n"
                f"[rgb(167,199,231)]Workflow execution stopped.[/rgb(167,199,231)]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(error_panel)
            break
        
        # Kısa bir bekleme (opsiyonel)
        if idx < len(steps):
            time.sleep(0.5)
    
    # Sonuç özeti
    console.print()
    if failed:
        result_panel = Panel(
            f"[rgb(167,199,231)] Workflow execution failed[/rgb(167,199,231)]\n\n"
            f"Completed steps: {len([s for s in executed_steps if s['result']['status'] == 'completed'])}/{len(steps)}",
            border_style="white",
            box=box.SIMPLE
        )
    else:
        result_panel = Panel(
            f"[rgb(167,199,231)]Workflow completed successfully![/rgb(167,199,231)]\n\n"
            f"Executed {len(executed_steps)}/{len(steps)} steps",
            border_style="white",
            box=box.SIMPLE
        )
    console.print(Align.center(result_panel), width=80)


def show_settings_menu():
    """Settings menüsü"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Settings[/rgb(167,199,231)]\n\n"
        "[rgb(167,199,231)]Configure automatic actions for terminal monitoring and log analysis.[/rgb(167,199,231)]",
        border_style="white",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    settings = load_settings()
    
    # Mevcut ayarları göster
    console.print("[rgb(167,199,231)]Current Settings:[/rgb(167,199,231)]")
    console.print(f"  Auto Workflow Generation: [rgb(167,199,231)]{'Enabled' if settings['auto_workflow_generation'] else 'Disabled'}[/rgb(167,199,231)]")
    console.print(f"  Auto Incident Creation: [rgb(167,199,231)]{'Enabled' if settings['auto_incident_creation'] else 'Disabled'}[/rgb(167,199,231)]")
    console.print()
    
    # Log dosyalarını göster
    if Confirm.ask("[rgb(167,199,231)]View log file locations?[/rgb(167,199,231)]", default=False):
        show_log_file_locations()
        console.print()
    
    # Auto Workflow Generation
    auto_workflow = Confirm.ask(
        "[rgb(167,199,231)]Auto-generate and run workflows when issues detected in terminal?[/rgb(167,199,231)]",
        default=settings['auto_workflow_generation']
    )
    
    # Auto Incident Creation
    auto_incident = Confirm.ask(
        "[rgb(167,199,231)]Auto-create incidents when issues detected in logs?[/rgb(167,199,231)]",
        default=settings['auto_incident_creation']
    )
    
    # Kaydet
    if save_settings(auto_workflow, auto_incident):
        console.print()
        console.print("[rgb(167,199,231)]Settings saved successfully![/rgb(167,199,231)]")
    else:
        console.print()
        console.print("[rgb(167,199,231)]Error saving settings[/rgb(167,199,231)]")
    
    console.print()


def show_log_file_locations():
    """Log dosyalarının konumlarını göster"""
    console.print()
    console.print("[rgb(167,199,231)]📁 Log File Locations[/rgb(167,199,231)]")
    console.print()
    
    # Temp dizinini bul
    temp_dir = tempfile.gettempdir()
    console.print(f"[rgb(167,199,231)]Temporary directory:[/rgb(167,199,231)] [white]{temp_dir}[/white]")
    console.print()
    
    # Neurops log dosyalarını bul
    import glob
    log_patterns = [
        os.path.join(temp_dir, "neurops_terminal_*.log"),
        os.path.join(temp_dir, "neurops_agent_*.log"),
        os.path.join(temp_dir, "neurops_fix_*.sh"),
    ]
    
    all_logs = []
    for pattern in log_patterns:
        all_logs.extend(glob.glob(pattern))
    
    if all_logs:
        console.print("[rgb(167,199,231)]Found log files:[/rgb(167,199,231)]")
        console.print()
        
        table = Table(
            box=box.SIMPLE,
            border_style="white",
            show_header=True,
            header_style="rgb(167,199,231)"
        )
        table.add_column("File", style="white", width=60)
        table.add_column("Size", style="rgb(167,199,231)", width=15)
        table.add_column("Modified", style="dim", width=20)
        
        # Dosyaları tarihe göre sırala (en yeni önce)
        all_logs.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        
        for log_file in all_logs[:20]:  # En fazla 20 dosya göster
            if os.path.exists(log_file):
                size = os.path.getsize(log_file)
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024*1024):.1f} MB"
                mtime = os.path.getmtime(log_file)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                table.add_row(log_file, size_str, mtime_str)
        
        console.print(table)
        console.print()
        console.print(f"[dim]Showing {min(len(all_logs), 20)} of {len(all_logs)} files[/dim]")
    else:
        console.print("[rgb(167,199,231)]No log files found in temporary directory.[/rgb(167,199,231)]")
        console.print("[rgb(167,199,231)]Log files are created when you use terminal monitoring features.[/rgb(167,199,231)]")
    
    console.print()
    console.print("[rgb(167,199,231)]💡 Tip: Log files are stored in your system's temporary directory.[/rgb(167,199,231)]")
    console.print(f"[dim]On macOS: Usually /var/folders/... or /tmp[/dim]")
    console.print(f"[dim]On Linux: Usually /tmp[/dim]")
    console.print(f"[dim]On Windows: Usually C:\\Users\\...\\AppData\\Local\\Temp[/dim]")


def monitor_terminal_output():
    """Terminal output'unu anlık olarak izle ve log analizi yap"""
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]Terminal Monitor[/rgb(167,199,231)]\n"
        "[dim rgb(167,199,231)]Monitor a command's output in real-time and analyze logs for issues.[/dim rgb(167,199,231)]\n"
        "[dim rgb(167,199,231)]The AI will analyze the output and alert you if problems are detected.[/dim rgb(167,199,231)]",
        border_style="white",
        padding=(0, 0),
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    
    # Token kontrolü
    token_status = check_token()
    if not token_status.get("token_set"):
        console.print()
        warning = Panel(
            "[rgb(167,199,231)]Warning:[/rgb(167,199,231)]\n"
            "[rgb(167,199,231)] Token not set![/rgb(167,199,231)]\n\n"
            "[rgb(167,199,231)]AI analysis requires a Hugging Face API token.[/rgb(167,199,231)]\n"
            "[rgb(167,199,231)]Basic log analysis will still work, but AI insights won't be available.[/rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)
        console.print()
        if not Confirm.ask("[rgb(167,199,231)]Continue without AI analysis?[/rgb(167,199,231)]", default=True):
            return
    
    # Komut seçimi
    choice = Prompt.ask(
        "[rgb(167,199,231)]Choose input method[/rgb(167,199,231)]",
        choices=["command", "file", "stdin", "terminal"],
        default="command"
    )
    
    log_buffer = []
    analysis_interval = 5  # Her 5 saniyede bir analiz
    last_analysis_time = time.time()
    
    def analyze_logs_async(logs_text: str):
        """Log'ları asenkron olarak analiz et"""
        try:
            # Önce basit analiz
            res = requests.post(
                f"{API_URL}/logs/analyze",
                json={"logs": logs_text},
                timeout=10
            )
            
            if res.status_code == 200:
                result = res.json()
                errors = result.get("errors_detected", 0)
                warnings = result.get("warnings_detected", 0)
                critical = result.get("critical_issues", [])
                
                if errors > 0 or warnings > 0 or critical:
                    console.print()
                    alert_panel = Panel(
                        f"[rgb(167,199,231)]Issues Detected![/rgb(167,199,231)]\n\n"
                        f"Errors: [rgb(167,199,231)]{errors}[/rgb(167,199,231)]\n"
                        f"Warnings: [rgb(167,199,231)]{warnings}[/rgb(167,199,231)]\n"
                        + (f"Critical Issues: {len(critical)}\n" if critical else ""),
                        border_style="white",
                        box=box.SIMPLE
                    )
                    console.print(alert_panel)
                    
                    if critical:
                        console.print("[rgb(167,199,231)]Critical Issues:[/rgb(167,199,231)]")
                        for issue in critical[:3]:
                            console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {issue[:100]}")
                    
                    if result.get("recommendations"):
                        console.print()
                        console.print("[rgb(167,199,231)]Recommendations:[/rgb(167,199,231)]")
                        for rec in result.get("recommendations", [])[:3]:
                            console.print(f"  [rgb(167,199,231)]•[/rgb(167,199,231)] {rec}")
                
                # Settings kontrolü
                settings = load_settings()
                
                # Auto Incident Creation (loglarda sorun varsa)
                if settings.get("auto_incident_creation") and (errors > 0 or warnings > 0 or critical):
                    try:
                        incident_title = f"Log Analysis: {errors} errors, {warnings} warnings detected"
                        incident_desc = f"Automatically created from log analysis.\n\nErrors: {errors}\nWarnings: {warnings}\n\nLog snippet:\n{logs_text[-1000:]}"
                        
                        incident_res = requests.post(
                            f"{API_URL}/incident/",
                            json={
                                "title": incident_title,
                                "description": incident_desc,
                                "severity": "high" if critical else "medium",
                                "source": "log_analysis"
                            }
                        )
                        
                        if incident_res.status_code == 200:
                            incident = incident_res.json()
                            console.print()
                            console.print(f"[rgb(167,199,231)]✓ Incident created: {incident.get('id')}[/rgb(167,199,231)]")
                    except:
                        pass
                
                # AI analizi ve Auto Workflow (token varsa)
                if token_status.get("token_set") and (errors > 0 or warnings > 0):
                    try:
                        # Auto workflow generation ayarı kontrol et
                        auto_workflow = settings.get("auto_workflow_generation", False)
                        
                        ai_res = requests.post(
                            f"{API_URL}/agent/analyze",
                            json={
                                "problem_description": f"Analyze these logs for issues:\n\n{logs_text[-2000:]}",
                                "context": {"logs": logs_text[-2000:]},
                                "auto_apply": False
                            },
                            headers=get_api_headers(),
                            timeout=90  # Log analizi için daha uzun timeout
                        )
                        
                        if ai_res.status_code == 200:
                            ai_result = ai_res.json()
                            if ai_result.get("analysis") and not ai_result.get("fallback"):
                                console.print()
                                ai_panel = Panel(
                                    Markdown(ai_result.get("analysis", "")[:500]),
                                    title="[bold white]AI Analysis[/bold white]",
                                    border_style="white",
                                    box=box.SIMPLE
                                )
                                console.print(ai_panel)
                                
                                # Auto workflow generation
                                if auto_workflow:
                                    console.print()
                                    if Confirm.ask("[rgb(167,199,231)]Generate and run workflow automatically?[/rgb(167,199,231)]", default=True):
                                        try:
                                            workflow_desc = f"Fix issues detected in logs:\n\n{ai_result.get('analysis', '')[:500]}\n\nLog context:\n{logs_text[-1000:]}"
                                            
                                            workflow_res = requests.post(
                                                f"{API_URL}/workflow/generate",
                                                json={
                                                    "description": workflow_desc,
                                                    "context": {"logs": logs_text[-1000:], "analysis": ai_result.get("analysis", "")}
                                                },
                                                headers=get_api_headers(),
                                                timeout=120
                                            )
                                            
                                            if workflow_res.status_code == 200:
                                                workflow_result = workflow_res.json()
                                                workflow_name = workflow_result.get("workflow_name")
                                                
                                                console.print()
                                                console.print(f"[rgb(167,199,231)]✓ Workflow generated: {workflow_name}[/rgb(167,199,231)]")
                                                
                                                # Workflow'u çalıştır
                                                run_res = requests.post(
                                                    f"{API_URL}/workflow/run",
                                                    json={
                                                        "workflow_name": workflow_name,
                                                        "parameters": {}
                                                    },
                                                    headers=get_api_headers()
                                                )
                                                
                                                if run_res.status_code == 200:
                                                    run_result = run_res.json()
                                                    console.print(f"[rgb(167,199,231)]✓ Workflow started: {run_result.get('run_id')}[/rgb(167,199,231)]")
                                        except Exception as e:
                                            console.print(f"[rgb(167,199,231)]Error generating workflow: {e}[/rgb(167,199,231)]")
                    except:
                        pass  # AI analizi başarısız olursa sessizce devam et
            
        except Exception as e:
            pass  # Analiz hatası olursa sessizce devam et
    
    if choice == "command":
        # Komut çalıştır ve output'unu izle
        command = Prompt.ask("[white]Enter command to monitor[/white]")
        
        if not command:
            console.print("[rgb(167,199,231)] Command cannot be empty![/rgb(167,199,231)]")
            return
        
        console.print()
        console.print("[white]🚀 Starting command execution...[/white]")
        console.print(f"[dim]Command: {command}[/dim]")
        console.print()
        console.print("[rgb(167,199,231)]Monitoring output (Press Ctrl+C to stop)...[/rgb(167,199,231)]")
        console.print()
        
        is_windows = platform.system() == "Windows"
        
        try:
            if is_windows:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            else:
                cmd_parts = shlex.split(command)
                process = subprocess.Popen(
                    cmd_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            
            # Output'u oku ve göster
            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                
                # Satırı göster
                console.print(line.rstrip())
                log_buffer.append(line.rstrip())
                
                # Son 100 satırı tut (çok büyümesin)
                if len(log_buffer) > 100:
                    log_buffer.pop(0)
                
                # Belirli aralıklarla analiz et
                current_time = time.time()
                if current_time - last_analysis_time >= analysis_interval:
                    if log_buffer:
                        logs_text = "\n".join(log_buffer[-50:])  # Son 50 satırı analiz et
                        # Thread'de analiz et (blocking olmasın)
                        threading.Thread(
                            target=analyze_logs_async,
                            args=(logs_text,),
                            daemon=True
                        ).start()
                    last_analysis_time = current_time
            
            # Process bitti, son analiz
            if log_buffer:
                logs_text = "\n".join(log_buffer)
                analyze_logs_async(logs_text)
            
            console.print()
            console.print(f"[white]Command completed (exit code: {process.returncode})[/white]")
            
        except KeyboardInterrupt:
            console.print()
            console.print("[rgb(167,199,231)] Monitoring stopped by user[/rgb(167,199,231)]")
            if 'process' in locals():
                process.terminate()
        except Exception as e:
            console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")
    
    elif choice == "file":
        # Dosyadan oku ve izle (tail -f benzeri)
        filepath = Prompt.ask("[white]Enter log file path[/white]")
        
        if not os.path.exists(filepath):
            console.print(f"[rgb(167,199,231)] File not found: {filepath}[/rgb(167,199,231)]")
            return
        
        console.print()
        console.print(f"[white]📄 Monitoring file: {filepath}[/white]")
        console.print("[rgb(167,199,231)]Press Ctrl+C to stop...[/rgb(167,199,231)]")
        console.print()
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Dosyanın sonuna git
                f.seek(0, 2)
                
                while True:
                    line = f.readline()
                    if line:
                        console.print(line.rstrip())
                        log_buffer.append(line.rstrip())
                        
                        if len(log_buffer) > 100:
                            log_buffer.pop(0)
                        
                        # Analiz et
                        current_time = time.time()
                        if current_time - last_analysis_time >= analysis_interval:
                            if log_buffer:
                                logs_text = "\n".join(log_buffer[-50:])
                                threading.Thread(
                                    target=analyze_logs_async,
                                    args=(logs_text,),
                                    daemon=True
                                ).start()
                            last_analysis_time = current_time
                    else:
                        time.sleep(0.5)  # Yeni satır beklerken bekle
                        
        except KeyboardInterrupt:
            console.print()
            console.print("[rgb(167,199,231)] Monitoring stopped by user[/rgb(167,199,231)]")
        except Exception as e:
            console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")
    
    elif choice == "stdin":
        # Standart input'tan oku
        console.print()
        console.print("[white]📥 Reading from stdin (paste logs, press Ctrl+D/Ctrl+Z to finish)[/white]")
        console.print()
        
        try:
            while True:
                line = input()
                console.print(line)
                log_buffer.append(line)
                
                if len(log_buffer) > 100:
                    log_buffer.pop(0)
                
                # Analiz et
                current_time = time.time()
                if current_time - last_analysis_time >= analysis_interval:
                    if log_buffer:
                        logs_text = "\n".join(log_buffer[-50:])
                        threading.Thread(
                            target=analyze_logs_async,
                            args=(logs_text,),
                            daemon=True
                        ).start()
                    last_analysis_time = current_time
                    
        except (EOFError, KeyboardInterrupt):
            console.print()
            console.print("[rgb(167,199,231)] Input finished[/rgb(167,199,231)]")
            if log_buffer:
                logs_text = "\n".join(log_buffer)
                analyze_logs_async(logs_text)
    
    elif choice == "terminal":
        # Açık terminal penceresini izle
        console.print()
        console.print("[white]🖥️  Open Terminal Monitor[/white]")
        console.print()
        console.print("[rgb(167,199,231)]Monitor output from an already open terminal window.[/rgb(167,199,231)]")
        console.print()
        
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            # Windows için
            console.print("[rgb(167,199,231)]Windows: Please run this command in your open terminal:[/rgb(167,199,231)]")
            console.print()
            temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log', prefix='neurops_terminal_')
            temp_file.close()
            script_file = temp_file.name
            console.print(f"[white]Get-Content -Path '{script_file}' -Wait -Tail 0[/white]")
            console.print()
            console.print("[rgb(167,199,231)]Then redirect your command output to this file:[/rgb(167,199,231)]")
            console.print(f"[white]YourCommand 2>&1 | Tee-Object -FilePath '{script_file}' -Append[/white]")
            console.print()
            if not Confirm.ask("[rgb(167,199,231)]Ready to monitor? (Make sure you've started the command above)[/rgb(167,199,231)]", default=True):
                return
        else:
            # Unix/Linux/macOS için
            console.print("[rgb(167,199,231)]To monitor an open terminal window:[/rgb(167,199,231)]")
            console.print()
            console.print("[white]1. Go to your open terminal window[/white]")
            console.print("[white]2. Run this command in that terminal:[/white]")
            console.print()
            
            # Geçici dosya oluştur
            temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log', prefix='neurops_terminal_')
            temp_file.close()
            script_file = temp_file.name
            
            # macOS'ta -f seçeneği yok
            if platform.system() == "Darwin":  # macOS
                console.print(f"[white]script -q {script_file}[/white]")
                console.print()
                console.print("[dim]Note: On macOS, use 'script -q' (without -f option)[/dim]")
            else:
                console.print(f"[white]script -q -f {script_file}[/white]")
            
            console.print()
            console.print("[rgb(167,199,231)]3. Now run your commands in that terminal - output will appear here[/rgb(167,199,231)]")
            console.print()
            console.print(f"[rgb(167,199,231)]Log file location:[/rgb(167,199,231)]")
            console.print(f"[white]{script_file}[/white]")
            console.print()
            
            if not Confirm.ask("[rgb(167,199,231)]Have you run 'script' command in your terminal?[/rgb(167,199,231)]", default=True):
                return
        
        console.print()
        console.print("[white]📄 Monitoring terminal output...[/white]")
        console.print("[rgb(167,199,231)]Press Ctrl+C to stop monitoring[/rgb(167,199,231)]")
        console.print()
        
        try:
            # Dosyayı izle (hem Windows hem Unix için aynı mantık)
            # Dosya oluşturulana kadar bekle
            max_wait = 30  # 30 saniye bekle (kullanıcının script komutunu çalıştırması için zaman)
            waited = 0
            console.print("[rgb(167,199,231)]Waiting for log file to be created...[/rgb(167,199,231)]")
            while not os.path.exists(script_file) and waited < max_wait:
                time.sleep(1)
                waited += 1
                if waited % 5 == 0:
                    console.print(f"[dim]Still waiting... ({waited}/{max_wait} seconds)[/dim]")
            
            if not os.path.exists(script_file):
                console.print()
                console.print(f"[rgb(167,199,231)]⚠️  Log file not created yet.[/rgb(167,199,231)]")
                console.print(f"[rgb(167,199,231)]Make sure you ran the command in your open terminal:[/rgb(167,199,231)]")
                if is_windows:
                    console.print(f"[white]YourCommand 2>&1 | Tee-Object -FilePath '{script_file}' -Append[/white]")
                else:
                    if platform.system() == "Darwin":  # macOS
                        console.print(f"[white]script -q {script_file}[/white]")
                    else:
                        console.print(f"[white]script -q -f {script_file}[/white]")
                console.print()
                if not Confirm.ask("[rgb(167,199,231)]Continue waiting?[/rgb(167,199,231)]", default=True):
                    return
            
            # Dosyayı izle
            console.print()
            console.print("[white]✅ Log file found! Monitoring terminal output...[/white]")
            console.print()
            
            last_size = 0
            if os.path.exists(script_file):
                last_size = os.path.getsize(script_file)  # Mevcut içeriği atla, sadece yeni içeriği izle
            
            with open(script_file, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    try:
                        if not os.path.exists(script_file):
                            time.sleep(0.5)
                            continue
                        
                        # Dosya boyutunu kontrol et
                        current_size = os.path.getsize(script_file)
                        if current_size > last_size:
                            # Yeni içerik var, oku
                            f.seek(last_size)
                            new_content = f.read()
                            if new_content:
                                lines = new_content.split('\n')
                                for line in lines:
                                    if line.strip():
                                        # script komutu bazı kontrol karakterleri ekler, temizle
                                        line_clean = line.rstrip()
                                        # ANSI escape kodlarını temizle
                                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                                        line_clean = ansi_escape.sub('', line_clean)
                                        
                                        if line_clean.strip():
                                            console.print(line_clean)
                                            log_buffer.append(line_clean)
                                            
                                            if len(log_buffer) > 100:
                                                log_buffer.pop(0)
                                            
                                            # Analiz et
                                            current_time = time.time()
                                            if current_time - last_analysis_time >= analysis_interval:
                                                if log_buffer:
                                                    logs_text = "\n".join(log_buffer[-50:])
                                                    threading.Thread(
                                                        target=analyze_logs_async,
                                                        args=(logs_text,),
                                                        daemon=True
                                                    ).start()
                                                last_analysis_time = current_time
                            last_size = current_size
                        time.sleep(0.1)  # 100ms bekle (daha responsive)
                    except (IOError, OSError) as e:
                        # Dosya henüz oluşturulmamış veya silinmiş
                        time.sleep(0.5)
                        continue
                    except Exception as e:
                        # Diğer hatalar
                        time.sleep(0.5)
                        continue
        
        except KeyboardInterrupt:
            console.print()
            console.print("[rgb(167,199,231)] Monitoring stopped by user[/rgb(167,199,231)]")
            console.print(f"[dim]Log file saved at: {script_file}[/dim]")
            console.print("[rgb(167,199,231)]Your terminal window will continue running normally.[/rgb(167,199,231)]")
            if is_windows:
                console.print("[rgb(167,199,231)]To stop redirecting, just stop running commands with Tee-Object.[/rgb(167,199,231)]")
            else:
                console.print("[rgb(167,199,231)]To stop script, type 'exit' in your terminal.[/rgb(167,199,231)]")
        except Exception as e:
            console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")
            console.print(f"[dim]Log file: {script_file}[/dim]")


def full_agent_mode():
    """Full-Agent Mode: Terminal çıktısını izle ve hataları otomatik düzelt"""
    console.print()
    console.print("[white]Full-Agent Mode[/white]")
    console.print()
    console.print("[rgb(167,199,231)]This mode monitors a terminal window and automatically fixes errors.[/rgb(167,199,231)]")
    console.print("[rgb(167,199,231)]When an error is detected, the agent will fix it automatically.[/rgb(167,199,231)]")
    console.print()
    
    # Token kontrolü
    token_status = check_token()
    if not token_status.get("token_set"):
        console.print()
        warning = Panel(
            "[rgb(167,199,231)]Warning:[/rgb(167,199,231)]\n"
            "[rgb(167,199,231)] AI Agent token not set![/rgb(167,199,231)]\n\n"
            "[rgb(167,199,231)]Full-Agent Mode requires a Hugging Face API token.[/rgb(167,199,231)]\n"
            "[rgb(167,199,231)]Please set your token first (option 7).[/rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)
        console.print()
        return
    
    # Terminal penceresi seçimi
    console.print("[rgb(167,199,231)]Step 1: Set up terminal monitoring[/rgb(167,199,231)]")
    console.print()
    
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        console.print("[rgb(167,199,231)]Windows: Please run this command in your terminal:[/rgb(167,199,231)]")
        console.print()
        temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log', prefix='neurops_agent_')
        temp_file.close()
        script_file = temp_file.name
        console.print(f"[white]YourCommand 2>&1 | Tee-Object -FilePath '{script_file}' -Append[/white]")
        console.print()
    else:
        console.print("[rgb(167,199,231)]Please run this command in your terminal window:[/rgb(167,199,231)]")
        console.print()
        temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log', prefix='neurops_agent_')
        temp_file.close()
        script_file = temp_file.name
        
        # macOS'ta -f seçeneği yok, sadece -q kullan
        if platform.system() == "Darwin":  # macOS
            console.print(f"[white]script -q {script_file}[/white]")
            console.print()
            console.print("[dim]Note: On macOS, use 'script -q' (without -f option)[/dim]")
        else:
            # Linux'ta -f ile kullan
            console.print(f"[white]script -q -f {script_file}[/white]")
        
        console.print()
        console.print(f"[rgb(167,199,231)]Log file location:[/rgb(167,199,231)]")
        console.print(f"[white]{script_file}[/white]")
        console.print()
    
    if not Confirm.ask("[rgb(167,199,231)]Have you run the command in your terminal?[/rgb(167,199,231)]", default=True):
        return
    
    console.print()
    console.print("[white]Full-Agent Mode Active[/white]")
    console.print("[rgb(167,199,231)]Monitoring terminal output and fixing errors automatically...[/rgb(167,199,231)]")
    console.print("[rgb(167,199,231)]Press Ctrl+C to stop[/rgb(167,199,231)]")
    console.print()
    
    log_buffer = []
    analysis_interval = 2  # Her 2 saniyede bir kontrol et
    last_analysis_time = time.time()
    last_size = 0
    current_directory = None
    error_count = 0
    processed_errors = set()  # İşlenen hataların unique string'leri (logda kalsa bile tekrar işlenmesin)
    fixed_files = {}  # Düzeltilen dosyaları takip et (file_path -> timestamp)
    ai_request_in_progress = False  # AI isteği devam ediyor mu? (cevap gelene kadar true)
    last_command = None  # Son çalıştırılan komut (yeniden başlatma için)
    last_command_time = None  # Son komutun çalıştırılma zamanı
    
    def detect_command_in_output(output_text: str) -> Optional[str]:
        """Log çıktısından son çalıştırılan komutu tespit et"""
        # Yaygın komut pattern'leri (daha esnek pattern'ler)
        command_patterns = [
            r'(python3?\s+[^\s\n]+\.py(?:\s+[^\n]*)?)',  # python script.py [args]
            r'(python3?\s+[^\s\n]+(?:\s+[^\n]*)?)',  # python -m module [args]
            r'(node\s+[^\s\n]+\.js(?:\s+[^\n]*)?)',  # node script.js [args]
            r'(node\s+[^\s\n]+(?:\s+[^\n]*)?)',  # node --version, node index.js, vb.
            r'(npm\s+(?:run|start|test|build|install|dev)[^\n]*)',  # npm run/start/test/build/install/dev
            r'(npm\s+[^\s\n]+[^\n]*)',  # npm install package, npm run script, vb.
            r'(yarn\s+[^\n]*)',  # yarn komutları
            r'(go\s+run\s+[^\n]*)',  # go run
            r'(cargo\s+(?:run|build|test)[^\n]*)',  # cargo run/build/test
            r'(ruby\s+[^\s\n]+\.rb[^\n]*)',  # ruby script.rb
            r'(perl\s+[^\s\n]+\.pl[^\n]*)',  # perl script.pl
            r'(bash\s+[^\s\n]+\.sh[^\n]*)',  # bash script.sh
            r'(sh\s+[^\s\n]+\.sh[^\n]*)',  # sh script.sh
            r'(\.\/[^\s\n]+[^\n]*)',  # ./executable [args]
        ]
        
        # Tüm satırları kontrol et (komutlar genellikle en son çalıştırılır)
        lines = output_text.split('\n')
        
        # Ters sırada kontrol et (en son komutu bul)
        for line in reversed(lines):
            line_clean = line.strip()
            if not line_clean:
                continue
            
            # Prompt karakterlerini atla (örn: $, >, #)
            if line_clean.startswith('$') or line_clean.startswith('>') or line_clean.startswith('#'):
                line_clean = line_clean[1:].strip()
            
            # Script komutu çıktılarını atla
            if 'Script started' in line_clean or 'Script done' in line_clean:
                continue
            
            # Komut pattern'lerini kontrol et
            for pattern in command_patterns:
                match = re.search(pattern, line_clean, re.IGNORECASE)
                if match:
                    command = match.group(1).strip()
                    # Boş komut değilse ve sadece prompt değilse
                    if command and len(command) > 3 and not command.startswith('cd '):
                        # Komutun geçerli olduğunu kontrol et (sadece whitespace değilse)
                        if command.strip() and not command.strip().startswith('#'):
                            return command
        
        return None
    
    def restart_command(command: str, working_dir: Optional[str] = None) -> bool:
        """Komutu yeniden başlat - script komutunun çalıştığı terminale komut gönder"""
        try:
            console.print()
            console.print(f"[rgb(167,199,231)]Restarting command:[/rgb(167,199,231)] [white]{command}[/white]")
            if working_dir:
                console.print(f"[rgb(167,199,231)]Working directory:[/rgb(167,199,231)] [white]{working_dir}[/white]")
            console.print()
            
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                if working_dir:
                    full_command = f'cd /d "{working_dir}" && {command}'
                else:
                    full_command = command
                
                # Windows'ta arka planda çalıştır
                subprocess.Popen(
                    full_command,
                    shell=True,
                    cwd=working_dir if working_dir else None,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                )
            else:
                # macOS/Linux'ta script komutunun çalıştığı terminale komut göndermek için
                if platform.system() == "Darwin":  # macOS
                    if working_dir:
                        full_command = f'cd "{working_dir}" && {command}'
                    else:
                        full_command = command
                    
                    # macOS'ta script komutunun çalıştığı terminale komut göndermek için
                    # Script komutunun çalıştığı terminali bulmak için:
                    # 1. Script komutunun çalıştığı terminalin title'ını veya process'ini bul
                    # 2. O terminale komut gönder
                    # En pratik çözüm: Tüm terminal pencerelerini kontrol et ve script komutunun çalıştığı terminali bul
                    # Script komutunun çalıştığı terminal genellikle "script" kelimesini içerir
                    
                    # AppleScript ile script komutunun çalıştığı terminali bul ve o terminale komut gönder
                    # Eğer bulamazsak, aktif terminale gönder
                    escaped_command = full_command.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
                    applescript = f'''
                    tell application "Terminal"
                        set foundWindow to false
                        repeat with w in windows
                            try
                                set windowTitle to name of w
                                if windowTitle contains "script" or windowTitle contains "{os.path.basename(script_file)}" then
                                    set foundWindow to true
                                    do script "{escaped_command}" in w
                                    exit repeat
                                end if
                            end try
                        end repeat
                        if not foundWindow then
                            -- Script komutunun çalıştığı terminal bulunamadı, aktif terminale gönder
                            do script "{escaped_command}" in front window
                        end if
                    end tell
                    '''
                    subprocess.run(['osascript', '-e', applescript], check=False)
                else:
                    # Linux için
                    if working_dir:
                        full_command = f'cd "{working_dir}" && {command}'
                    else:
                        full_command = command
                    
                    # Linux'ta da komutu direkt çalıştır
                    subprocess.Popen(
                        full_command,
                        shell=True,
                        cwd=working_dir if working_dir else None,
                        executable='/bin/bash'
                    )
            
            console.print(f"[rgb(167,199,231)]Command restarted![/rgb(167,199,231)]")
            console.print()
            return True
            
        except Exception as e:
            console.print(f"[rgb(167,199,231)]Error restarting command: {e}[/rgb(167,199,231)]")
            return False
    
    def detect_error_in_output(output_text: str) -> Optional[Dict[str, Any]]:
        """Çıktıda hata tespit et"""
        # Yaygın hata pattern'leri
        error_patterns = [
            # Syntax hataları (öncelikli - önce bunları kontrol et)
            # Python'un standart hata formatı: File "path", line X -> SyntaxError: message
            # re.DOTALL modunda . zaten \n ile eşleşir, bu yüzden \n kullanmaya gerek yok
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?SyntaxError:.*", "syntax_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?IndentationError:.*", "syntax_error"),
            # Alternatif format: SyntaxError: message -> File "path", line X
            (r"SyntaxError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "syntax_error"),
            (r"IndentationError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "syntax_error"),
            # Daha genel syntax hata pattern'leri
            (r"SyntaxError.*?File ['\"]([^'\"]+)['\"].*?line (\d+)", "syntax_error"),
            (r"IndentationError.*?File ['\"]([^'\"]+)['\"].*?line (\d+)", "syntax_error"),
            (r"SyntaxError:.*?invalid syntax.*?File ['\"]([^'\"]+)['\"].*?line (\d+)", "syntax_error"),
            (r"SyntaxError:.*?unexpected EOF.*?File ['\"]([^'\"]+)['\"].*?line (\d+)", "syntax_error"),
            (r"SyntaxError:.*?was never closed.*?File ['\"]([^'\"]+)['\"].*?line (\d+)", "syntax_error"),
            # Python Runtime Hataları (AttributeError, NameError, TypeError, vb.)
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?AttributeError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?NameError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?TypeError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?ValueError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?KeyError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?IndexError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?ZeroDivisionError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?FileNotFoundError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?PermissionError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?OSError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?IOError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?UnboundLocalError:.*", "runtime_error"),
            (r"File ['\"]([^'\"]+\.py)['\"].*?line (\d+).*?RuntimeError:.*", "runtime_error"),
            # Alternatif format: Error: message -> File "path", line X
            (r"AttributeError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "runtime_error"),
            (r"NameError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "runtime_error"),
            (r"TypeError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "runtime_error"),
            (r"ValueError:.*?File ['\"]([^'\"]+\.py)['\"].*?line (\d+)", "runtime_error"),
            # Modül hataları
            (r"ModuleNotFoundError.*?No module named ['\"]([^'\"]+)['\"]", "module_not_found"),
            (r"ImportError.*?No module named ['\"]([^'\"]+)['\"]", "module_not_found"),
            (r"ImportError.*?cannot import name.*?from ['\"]([^'\"]+)['\"]", "module_not_found"),
            (r"PackageNotFoundError.*?Could not find.*?package.*?['\"]([^'\"]+)['\"]", "package_not_found"),
            (r"opencv.*?not found", "opencv_not_found"),
            (r"cv2.*?not found", "opencv_not_found"),
            (r"pip.*?not found", "pip_not_found"),
            (r"command not found.*?['\"]([^'\"]+)['\"]", "command_not_found"),
            (r"Error.*?([A-Za-z0-9_-]+).*?not found", "generic_not_found"),
        ]
        
        for pattern, error_type in error_patterns:
            match = re.search(pattern, output_text, re.IGNORECASE | re.DOTALL)
            if match:
                if error_type in ["syntax_error", "runtime_error"]:
                    # Syntax veya runtime hatası için dosya yolu ve satır numarasını al
                    file_path = match.group(1) if match.groups() else None
                    line_num = match.group(2) if len(match.groups()) > 1 else None
                    
                    return {
                        "error_type": error_type,
                        "file_path": file_path,
                        "line_number": int(line_num) if line_num and line_num.isdigit() else None,
                        "error_text": match.group(0),
                        "full_output": output_text[-1000:]  # Hatalar için daha fazla context
                    }
                else:
                    # Diğer hata türleri
                    module_name = match.group(1) if match.groups() else None
                    if error_type == "opencv_not_found" or (module_name and module_name == "cv2"):
                        module_name = "cv2"  # cv2 olarak işaretle, fix_error_with_ai'de opencv-python'a çevrilecek
                    elif error_type == "module_not_found" and module_name:
                        # Modül adını olduğu gibi bırak, fix_error_with_ai'de dönüştürülecek
                        pass
                    
                    return {
                        "error_type": error_type,
                        "module_name": module_name,
                        "error_text": match.group(0),
                        "full_output": output_text[-500:]  # Son 500 karakter
                    }
        
        return None
    
    def fix_syntax_error(error_info: Dict[str, Any], working_dir: Optional[str] = None) -> bool:
        """Syntax veya runtime hatasını AI ile düzelt ve dosyaya yaz"""
        file_path = error_info.get('file_path')
        line_number = error_info.get('line_number')
        error_text = error_info.get('error_text', '')
        full_output = error_info.get('full_output', '')
        
        if not file_path:
            console.print("[rgb(167,199,231)]Could not determine file path from error[/rgb(167,199,231)]")
            return False
        
        # Dosya yolunu düzelt (relative path ise working_dir ile birleştir)
        if not os.path.isabs(file_path) and working_dir:
            file_path = os.path.join(working_dir, file_path)
        
        # Normalize path
        file_path = os.path.normpath(file_path)
        
        # Bu dosya daha önce düzeltildi mi kontrol et
        if file_path in fixed_files:
            # Dosya düzeltildikten sonra değişmiş mi kontrol et
            try:
                current_mtime = os.path.getmtime(file_path)
                if current_mtime <= fixed_files[file_path]:
                    # Dosya düzeltildikten sonra değişmemiş, yeni hata gelene kadar bekle
                    return False
            except:
                pass
        
        if not os.path.exists(file_path):
            console.print(f"[rgb(167,199,231)]File not found: {file_path}[/rgb(167,199,231)]")
            return False
        
        try:
            # Dosyayı oku
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            error_type = error_info.get('error_type', 'syntax_error')
            error_name = "Runtime error" if error_type == "runtime_error" else "Syntax error"
            
            console.print()
            console.print(f"[rgb(167,199,231)]Detected {error_name.lower()} in:[/rgb(167,199,231)] [white]{file_path}[/white]")
            if line_number:
                console.print(f"[rgb(167,199,231)]Line:[/rgb(167,199,231)] [white]{line_number}[/white]")
            console.print()
            
            # AI'ya gönder - daha detaylı ve net prompt
            error_type_name = "runtime error" if error_info.get('error_type') == "runtime_error" else "syntax error"
            
            problem_desc = f"""You are a Python code fixer. Fix the {error_type_name} in the following Python code.

ERROR DETAILS:
- File: {file_path}
- Line: {line_number if line_number else 'Unknown'}
- Error message: {error_text}

FULL ERROR OUTPUT:
{full_output[:800]}

CURRENT CODE (with error):
{file_content}

INSTRUCTIONS:
1. Identify the exact {error_type_name} in the code
2. Fix ONLY the error - do not change the logic or functionality unnecessarily
3. Return the COMPLETE corrected code
4. Do NOT include any explanations, comments, or markdown formatting
5. Return ONLY the Python code, nothing else

IMPORTANT: Return the entire fixed file content, not just the fixed line.
"""
            
            # Progress bar ile AI isteği gönder
            with Progress(
                SpinnerColumn(),
                TextColumn("[rgb(167,199,231)]Analyzing with AI...[/rgb(167,199,231)]"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                task = progress.add_task("", total=100)
                
                # AI isteğini thread'de çalıştır
                import threading
                ai_response = [None]
                ai_exception = [None]
                
                def make_request():
                    try:
                        ai_response[0] = requests.post(
                            f"{API_URL}/agent/analyze",
                            json={
                                "problem_description": problem_desc,
                                "context": {
                                    "error_type": "syntax_error",
                                    "file_path": file_path,
                                    "line_number": line_number,
                                    "error_text": error_text
                                },
                                "auto_apply": False
                            },
                            headers=get_api_headers(),
                            timeout=180
                        )
                    except Exception as e:
                        ai_exception[0] = e
                
                # Request thread'ini başlat
                request_thread = threading.Thread(target=make_request, daemon=True)
                request_thread.start()
                
                # Progress bar'ı güncelle
                elapsed = 0
                while request_thread.is_alive():
                    time.sleep(0.1)
                    elapsed += 0.1
                    # Progress'i simüle et (0-90% arası)
                    progress_value = min(90, int(elapsed * 2))
                    progress.update(task, completed=progress_value)
                
                # Thread bitene kadar bekle
                request_thread.join()
                
                # Son %10'u tamamla
                progress.update(task, completed=100)
                
                if ai_exception[0]:
                    raise ai_exception[0]
                
                ai_res = ai_response[0]
            
            if ai_res.status_code == 200:
                ai_result = ai_res.json()
                analysis = ai_result.get("analysis", "")
                
                # Kod düzeltme işlemi için progress bar
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[rgb(167,199,231)]Processing fixed code...[/rgb(167,199,231)]"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=console
                ) as progress:
                    task = progress.add_task("", total=100)
                    
                    # AI'dan düzeltilmiş kodu çıkar
                    progress.update(task, completed=10)
                    fixed_code = analysis
                    
                    # Markdown code block'larını temizle
                    progress.update(task, completed=30)
                    if "```python" in fixed_code:
                        # ```python ile başlayan blokları bul
                        parts = fixed_code.split("```python")
                        if len(parts) > 1:
                            fixed_code = parts[1].split("```")[0]
                    elif "```" in fixed_code:
                        # Genel ``` blokları
                        parts = fixed_code.split("```")
                        if len(parts) > 1:
                            # İlk ``` bloğunu al (genellikle kod bloğu)
                            fixed_code = parts[1]
                            if "```" in fixed_code:
                                fixed_code = fixed_code.split("```")[0]
                    
                    # Başta/sonda boşlukları ve gereksiz açıklamaları temizle
                    progress.update(task, completed=50)
                    fixed_code = fixed_code.strip()
                    
                    # Eğer hala açıklama içeriyorsa, sadece kod kısmını al
                    # Python kodunun başlangıcını bul (import, def, class, #! gibi)
                    lines = fixed_code.split('\n')
                    code_start = 0
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        # Python kodunun başlangıcı olabilecek satırlar
                        if stripped and (stripped.startswith('#!') or 
                                       stripped.startswith('import ') or 
                                       stripped.startswith('from ') or
                                       stripped.startswith('def ') or
                                       stripped.startswith('class ') or
                                       stripped.startswith('"""') or
                                       stripped.startswith("'''") or
                                       (stripped[0].isalpha() and not stripped.startswith('Here') and not stripped.startswith('The') and not stripped.startswith('This'))):
                            code_start = i
                            break
                    
                    progress.update(task, completed=70)
                    if code_start > 0:
                        fixed_code = '\n'.join(lines[code_start:])
                    
                    # Son kontrol: eğer çok kısa ise veya Python kodu gibi görünmüyorsa, orijinal analizi kullan
                    if fixed_code and len(fixed_code) > 50:  # Minimum uzunluk kontrolü
                        # Dosyaya yaz
                        progress.update(task, completed=90)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_code)
                        
                        progress.update(task, completed=100)
                        
                        # Düzeltilen dosyayı kaydet
                        fixed_files[file_path] = os.path.getmtime(file_path)
                        
                        error_type = error_info.get('error_type', 'syntax_error')
                        error_name = "Runtime error" if error_type == "runtime_error" else "Syntax error"
                        
                        console.print()
                        console.print(f"[rgb(167,199,231)]{error_name} fixed! File updated: {file_path}[/rgb(167,199,231)]")
                        console.print()
                        return True
                    else:
                        progress.update(task, completed=100)
                        console.print()
                        console.print("[rgb(167,199,231)]AI did not return valid code. Manual fix required.[/rgb(167,199,231)]")
                        return False
            else:
                console.print()
                console.print(f"[rgb(167,199,231)]AI analysis failed with status {ai_res.status_code}[/rgb(167,199,231)]")
                return False
                
        except Exception as e:
            console.print()
            console.print(f"[rgb(167,199,231)]Error fixing syntax: {e}[/rgb(167,199,231)]")
            return False
    
    def fix_error_with_ai(error_info: Dict[str, Any], working_dir: Optional[str] = None) -> Optional[str]:
        """AI ile hatayı düzelt - önce basit fix'leri dene, sonra AI'ya git"""
        error_type = error_info.get('error_type')
        module_name = error_info.get('module_name')
        
        # Syntax ve runtime hataları için özel işlem (kod düzeltme gerektirir)
        if error_type in ["syntax_error", "runtime_error"]:
            # Syntax veya runtime hatasını düzelt (dosyaya yazılır, komut döndürülmez)
            success = fix_syntax_error(error_info, working_dir)
            return "FIXED" if success else None  # Hata düzeltildi, komut döndürülmez
        
        # Basit hatalar için direkt fix komutları (AI'ya gitmeden)
        if error_type in ["module_not_found", "package_not_found", "opencv_not_found"]:
            if module_name:
                # Python modülü için pip paket adını tahmin et
                package_name = module_name
                if module_name.startswith("cv2"):
                    package_name = "opencv-python"
                elif module_name.startswith("PIL"):
                    package_name = "Pillow"
                elif module_name.startswith("sklearn"):
                    package_name = "scikit-learn"
                elif module_name.startswith("yaml"):
                    package_name = "pyyaml"
                elif module_name.startswith("bs4"):
                    package_name = "beautifulsoup4"
                elif module_name.startswith("lxml"):
                    package_name = "lxml"
                elif module_name.startswith("requests"):
                    package_name = "requests"
                elif module_name.startswith("numpy"):
                    package_name = "numpy"
                elif module_name.startswith("pandas"):
                    package_name = "pandas"
                elif module_name.startswith("matplotlib"):
                    package_name = "matplotlib"
                
                # Direkt fix komutu döndür (AI'ya gitmeden)
                return f"pip install {package_name}"
        
        # Daha karmaşık hatalar için AI'ya git
        try:
            error_desc = f"Error detected: {error_info.get('error_text', 'Unknown error')}"
            if module_name:
                error_desc += f"\nMissing module/package: {module_name}"
            
            context = {
                "error_type": error_type,
                "module_name": module_name,
                "working_directory": working_dir,
                "output": error_info.get('full_output', '')
            }
            
            console.print("[dim]🤔 Analyzing error with AI (this may take a moment)...[/dim]")
            
            # AI'ya sor - timeout süresini artır
            ai_res = requests.post(
                f"{API_URL}/agent/analyze",
                json={
                    "problem_description": f"Fix this error automatically:\n\n{error_desc}\n\nContext: {context}",
                    "context": context,
                    "auto_apply": False
                },
                headers=get_api_headers(),
                timeout=120  # 60 saniyeden 120 saniyeye çıkarıldı
            )
            
            if ai_res.status_code == 200:
                ai_result = ai_res.json()
                analysis = ai_result.get("analysis", "")
                
                # AI'dan komut çıkar (pip install gibi)
                if "pip install" in analysis.lower():
                    # pip install komutunu bul
                    pip_match = re.search(r"pip install\s+([^\s\n]+)", analysis, re.IGNORECASE)
                    if pip_match:
                        package = pip_match.group(1)
                        return f"pip install {package}"
                
                # Eğer module_name varsa, direkt pip install dene
                if module_name:
                    return f"pip install {module_name}"
            
            return None
        except requests.exceptions.Timeout:
            console.print("[dim]AI analysis timed out. Using fallback fix...[/dim]")
            # Timeout olursa basit fix'i dene
            if module_name:
                package_name = module_name
                if module_name.startswith("cv2"):
                    package_name = "opencv-python"
                elif module_name.startswith("PIL"):
                    package_name = "Pillow"
                elif module_name.startswith("sklearn"):
                    package_name = "scikit-learn"
                return f"pip install {package_name}"
            return None
        except Exception as e:
            console.print(f"[dim]AI analysis error: {e}[/dim]")
            console.print("[dim]Using fallback fix...[/dim]")
            # Hata olursa basit fix'i dene
            if module_name:
                package_name = module_name
                if module_name.startswith("cv2"):
                    package_name = "opencv-python"
                elif module_name.startswith("PIL"):
                    package_name = "Pillow"
                elif module_name.startswith("sklearn"):
                    package_name = "scikit-learn"
                return f"pip install {package_name}"
            return None
    
    def execute_fix_command(command: str, working_dir: Optional[str] = None) -> bool:
        """Düzeltme komutunu mevcut terminal üzerinden çalıştır ve çıktıları gerçek zamanlı göster"""
        try:
            console.print()
            console.print(f"[rgb(167,199,231)]Executing fix command:[/rgb(167,199,231)] [white]{command}[/white]")
            if working_dir:
                console.print(f"[rgb(167,199,231)]Working directory:[/rgb(167,199,231)] [white]{working_dir}[/white]")
            console.print()
            console.print("[rgb(167,199,231)]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/rgb(167,199,231)]")
            console.print()
            
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                # Windows için PowerShell komutu
                if working_dir:
                    # Önce dizine git, sonra komutu çalıştır
                    full_command = f'cd /d "{working_dir}" && {command}'
                else:
                    full_command = command
                
                # Komutu gerçek zamanlı çıktı ile çalıştır
                process = subprocess.Popen(
                    full_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=working_dir if working_dir else None
                )
            else:
                # macOS/Linux için bash ile çalıştır
                if working_dir:
                    # Önce dizine git, sonra komutu çalıştır
                    full_command = f'cd "{working_dir}" && {command}'
                else:
                    full_command = command
                
                # Komutu gerçek zamanlı çıktı ile çalıştır
                process = subprocess.Popen(
                    full_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=working_dir if working_dir else None,
                    executable='/bin/bash'
                )
            
            # Gerçek zamanlı çıktı oku ve göster
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_line = output.strip()
                    if output_line:
                        # Çıktıyı direkt terminale yazdır
                        console.print(f"[white]{output_line}[/white]")
                        output_lines.append(output_line)
            
            # Process'in bitmesini bekle
            return_code = process.poll()
            
            console.print()
            console.print("[rgb(167,199,231)]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/rgb(167,199,231)]")
            
            if return_code == 0:
                console.print()
                console.print("[rgb(167,199,231)]Fix command completed successfully![/rgb(167,199,231)]")
                return True
            else:
                console.print()
                console.print(f"[rgb(167,199,231)]Fix command failed with exit code {return_code}[/rgb(167,199,231)]")
                return False
                
        except Exception as e:
            console.print()
            console.print(f"[rgb(167,199,231)]Error executing fix: {e}[/rgb(167,199,231)]")
            return False
    
    # Dosyayı izle
    try:
        # Dosya oluşturulana kadar bekle
        max_wait = 30
        waited = 0
        while not os.path.exists(script_file) and waited < max_wait:
            time.sleep(1)
            waited += 1
        
        if not os.path.exists(script_file):
            console.print(f"[rgb(167,199,231)]Log file not created. Make sure you ran the command.[/rgb(167,199,231)]")
            return
        
        # Mevcut içeriği atla
        if os.path.exists(script_file):
            last_size = os.path.getsize(script_file)
        
        console.print("[white]Monitoring started![/white]")
        console.print()
        
        with open(script_file, 'r', encoding='utf-8', errors='ignore') as f:
            while True:
                try:
                    if not os.path.exists(script_file):
                        time.sleep(0.5)
                        continue
                    
                    current_size = os.path.getsize(script_file)
                    if current_size > last_size:
                        # Yeni içerik var
                        f.seek(last_size)
                        new_content = f.read()
                        if new_content:
                            lines = new_content.split('\n')
                            for line in lines:
                                if line.strip():
                                    # ANSI escape kodlarını temizle
                                    line_clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line.rstrip())
                                    
                                    if line_clean.strip():
                                        console.print(f"[dim]{line_clean}[/dim]")
                                        log_buffer.append(line_clean)
                                        
                                        # Çalışma dizinini tespit et (cd komutlarından)
                                        cd_match = re.search(r'cd\s+([^\s\n]+)', line_clean, re.IGNORECASE)
                                        if cd_match:
                                            current_directory = cd_match.group(1)
                                        
                                        # Komut tespiti - log_buffer'dan son çalıştırılan komutu tespit et
                                        # Son 20 satırı kontrol et (komutlar genellikle hata öncesinde görünür)
                                        recent_lines_for_command = log_buffer[-20:] if len(log_buffer) >= 20 else log_buffer
                                        recent_output_for_command = "\n".join(recent_lines_for_command) + "\n" + line_clean
                                        detected_command = detect_command_in_output(recent_output_for_command)
                                        if detected_command:
                                            last_command = detected_command
                                            last_command_time = time.time()
                                        
                                        # Hata tespiti - son birkaç satırı birlikte kontrol et (syntax hataları çok satırlı olabilir)
                                        # Son 10 satırı birleştir ve kontrol et
                                        recent_lines = log_buffer[-10:] if len(log_buffer) >= 10 else log_buffer
                                        recent_output = "\n".join(recent_lines) + "\n" + line_clean
                                        
                                        error_info = detect_error_in_output(recent_output)
                                        if error_info:
                                            # KRİTİK: AI isteği devam ediyorsa HİÇBİR ŞEY YAPMA
                                            if ai_request_in_progress:
                                                continue
                                            
                                            error_type = error_info.get('error_type')
                                            file_path = error_info.get('file_path')
                                            line_number = error_info.get('line_number', '')
                                            error_text = error_info.get('error_text', '')[:150]  # İlk 150 karakter
                                            
                                            # Dosya yolunu normalize et
                                            if file_path:
                                                if not os.path.isabs(file_path) and current_directory:
                                                    file_path = os.path.normpath(os.path.join(current_directory, file_path))
                                                else:
                                                    file_path = os.path.normpath(file_path)
                                            
                                            # Hatanın unique string'ini oluştur (hash YOK, direkt string)
                                            error_key = f"{error_type}|||{file_path or ''}|||{line_number}|||{error_text}"
                                            
                                            # Bu hata daha önce işlendi mi? (LOGDA KALSA BİLE TEKRAR İŞLEME)
                                            if error_key in processed_errors:
                                                continue  # Bu hata zaten işlendi, LOGDA KALSA BİLE TEKRAR İŞLEME
                                            
                                            # HEMEN İŞARETLE - LOGDA KALSA BİLE TEKRAR İŞLENMESİN
                                            processed_errors.add(error_key)  # Set'e ekle
                                            ai_request_in_progress = True  # API İSTEĞİ BAŞLADI
                                            
                                            error_count += 1
                                            console.print()
                                            
                                            # Syntax ve runtime hataları için özel mesaj
                                            if error_type in ["syntax_error", "runtime_error"]:
                                                error_name = "Runtime Error" if error_type == "runtime_error" else "Syntax Error"
                                                console.print(f"[rgb(167,199,231)]{error_name} #{error_count} detected:[/rgb(167,199,231)]")
                                                console.print(f"[white]{error_text[:200]}[/white]")
                                                console.print()
                                                
                                                # Hatayı AI ile düzelt
                                                try:
                                                    result = fix_error_with_ai(error_info, current_directory)
                                                    if result == "FIXED":
                                                        console.print(f"[rgb(167,199,231)]{error_name.lower()} fixed automatically![/rgb(167,199,231)]")
                                                        
                                                        # Hata düzeltildi, komutu yeniden başlat
                                                        if last_command and last_command_time:
                                                            # Son komut 30 saniye içinde çalıştırıldıysa yeniden başlat
                                                            if time.time() - last_command_time < 30:
                                                                console.print()
                                                                console.print(f"[rgb(167,199,231)]Error fixed! Restarting command...[/rgb(167,199,231)]")
                                                                restart_command(last_command, current_directory)
                                                                # Komut yeniden başlatıldı, zamanı güncelle
                                                                last_command_time = time.time()
                                                except Exception as e:
                                                    console.print(f"[dim]Error during fix: {e}[/dim]")
                                                finally:
                                                    # CEVAP GELDİ - ARTIK YENİ İSTEK GÖNDERİLEBİLİR
                                                    ai_request_in_progress = False
                                            else:
                                                console.print(f"[rgb(167,199,231)]Error #{error_count} detected: {error_info.get('error_text', 'Unknown')[:200]}[/rgb(167,199,231)]")
                                                
                                                # AI ile düzeltme komutu al
                                                fix_command = fix_error_with_ai(error_info, current_directory)
                                                
                                                if fix_command:
                                                    console.print(f"[white]Fixing: {fix_command}[/white]")
                                                    
                                                    # Düzeltme komutunu çalıştır
                                                    if execute_fix_command(fix_command, current_directory):
                                                        console.print(f"[rgb(167,199,231)]Fix command executed successfully[/rgb(167,199,231)]")
                                                        
                                                        # Hata düzeltildi, komutu yeniden başlat
                                                        if last_command and last_command_time:
                                                            # Son komut 30 saniye içinde çalıştırıldıysa yeniden başlat
                                                            if time.time() - last_command_time < 30:
                                                                console.print()
                                                                console.print(f"[rgb(167,199,231)]Error fixed! Restarting command...[/rgb(167,199,231)]")
                                                                restart_command(last_command, current_directory)
                                                                # Komut yeniden başlatıldı, zamanı güncelle
                                                                last_command_time = time.time()
                                                    else:
                                                        console.print(f"[rgb(167,199,231)]Failed to execute fix command[/rgb(167,199,231)]")
                                                else:
                                                    console.print(f"[rgb(167,199,231)]Could not determine fix command[/rgb(167,199,231)]")
                                            
                                            console.print()
                                        
                                        if len(log_buffer) > 200:
                                            log_buffer.pop(0)
                            
                            # Periyodik analiz
                            current_time = time.time()
                            if current_time - last_analysis_time >= analysis_interval:
                                if log_buffer:
                                    # Son 100 satırı analiz et
                                    recent_output = "\n".join(log_buffer[-100:])
                                    error_info = detect_error_in_output(recent_output)
                                    if error_info:
                                        # Hata zaten yukarıda işlendi, tekrar işleme
                                        pass
                                last_analysis_time = current_time
                        
                        last_size = current_size
                    
                    time.sleep(0.1)  # 100ms bekle
                
                except (IOError, OSError):
                    time.sleep(0.5)
                    continue
                except Exception as e:
                    console.print(f"[dim]Error: {e}[/dim]")
                    time.sleep(0.5)
                    continue
    
    except KeyboardInterrupt:
        console.print()
        console.print("[rgb(167,199,231)] Full-Agent Mode stopped[/rgb(167,199,231)]")
        console.print(f"[rgb(167,199,231)]Total errors detected and fixed: {error_count}[/rgb(167,199,231)]")
        console.print(f"[dim]Log file: {script_file}[/dim]")
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")


def configure_api_url():
    """API URL'ini yapılandır"""
    global API_URL
    
    console.print()
    panel = Panel(
        "[rgb(167,199,231)]API Server Configuration[/rgb(167,199,231)]\n\n"
        "Enter the URL of your Neurops API server.\n"
        "Example: https://api.neurops.dev or http://localhost:8000",
        title="API Configuration",
        border_style="rgb(167,199,231)",
        box=box.SIMPLE
    )
    console.print(panel)
    console.print()
    console.print(f"[dim]Current API URL: {API_URL}[/dim]")
    console.print()
    
    new_url = Prompt.ask(
        "[white]Enter API URL[/white]",
        default=API_URL
    )
    
    if not new_url:
        console.print("[rgb(167,199,231)] API URL cannot be empty![/rgb(167,199,231)]")
        return
    
    # URL formatını kontrol et
    if not new_url.startswith(("http://", "https://")):
        console.print("[rgb(167,199,231)] Adding http:// prefix...[/rgb(167,199,231)]")
        new_url = f"http://{new_url}"
    
    # Test connection
    try:
        with Status("[rgb(167,199,231)]Testing connection...[/rgb(167,199,231)]", spinner="dots", spinner_style="rgb(167,199,231)"):
            normalized_test_url = normalize_api_url(new_url)
            res = requests.get(f"{normalized_test_url}/health", timeout=5)
        
        if res.status_code == 200:
            console.print("[white]Connection successful![/white]")
            
            # API URL'ini kaydet (normalize edilmiş hali)
            normalized_url = normalize_api_url(new_url)
            if save_api_url(normalized_url):
                API_URL = normalized_url
                os.environ["NEUROPS_API_URL"] = normalized_url
                console.print("[white]API URL saved successfully![/white]")
            else:
                console.print("[rgb(167,199,231)] Could not save to config file, but using for this session.[/rgb(167,199,231)]")
                normalized_url = normalize_api_url(new_url)
                API_URL = normalized_url
        else:
            console.print(f"[rgb(167,199,231)] Server responded with status {res.status_code}, but URL saved.[/rgb(167,199,231)]")
            normalized_url = normalize_api_url(new_url)
            if save_api_url(normalized_url):
                API_URL = normalized_url
                os.environ["NEUROPS_API_URL"] = normalized_url
    except requests.exceptions.ConnectionError:
        console.print("[rgb(167,199,231)] Could not connect to server. URL saved anyway.[/rgb(167,199,231)]")
        normalized_url = normalize_api_url(new_url)
        if save_api_url(normalized_url):
            API_URL = normalized_url
            os.environ["NEUROPS_API_URL"] = normalized_url
    except Exception as e:
        console.print(f"[rgb(167,199,231)] Error: {e}[/rgb(167,199,231)]")
        console.print("[rgb(167,199,231)] URL not saved.[/rgb(167,199,231)]")


def ensure_user_workflows_dir():
    """Kullanıcı workflow dizinini oluştur"""
    USER_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def load_default_workflows():
    """Default workflow'ları backend'e kaydet"""
    if not DEFAULT_WORKFLOWS_DIR.exists():
        return
    
    try:
        for workflow_file in DEFAULT_WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow_data = yaml.safe_load(f)
                
                # Backend'e kaydet
                res = requests.post(
                    f"{API_URL}/workflow/register",
                    json=workflow_data,
                    timeout=5
                )
                if res.status_code in [200, 201]:
                    console.print(f"[dim rgb(167,199,231)]Loaded default workflow: {workflow_data.get('name')}[/dim rgb(167,199,231)]")
            except Exception as e:
                # Sessizce devam et, default workflow yükleme kritik değil
                pass
    except Exception:
        # Sessizce devam et
        pass


def main():
    """Ana fonksiyon"""
    global API_URL
    
    # Konsolu temizle
    console.clear()
    
    # Kullanıcı workflow dizinini oluştur
    ensure_user_workflows_dir()
    
    # Setup kontrolü - eğer tamamlanmamışsa tutorial göster
    if not is_setup_completed():
        setup_tutorial()
        console.clear()
    
    welcome_screen()
    
    # İlk çalıştırmada default workflow'ları yükle (sessizce)
    try:
        load_default_workflows()
    except:
        pass
    
    # API bağlantı kontrolü ve bilgilendirme
    is_connected, connection_msg = check_api_connection()
    if not is_connected:
        console.print()
        warning = Panel(
            f"[rgb(167,199,231)]Connection Error[/rgb(167,199,231)]\n\n"
            f"API URL: [white]{API_URL}[/white]\n"
            f"Status: [rgb(167,199,231)]{connection_msg}[/rgb(167,199,231)]\n\n",
            border_style="white",
            box=box.SIMPLE,
            padding=(0, 0),
            title_align="left"
        )
        console.print(warning)
        console.print()
    
    # Token durumunu kontrol et ve göster
    token_status = check_token()
    if not token_status.get("token_set"):
        warning = Panel(
            "[rgb(167,199,231)]  AI Agent token not set. Use option 6 to enable AI features.[/rgb(167,199,231)]",
            border_style="white",
            box=box.SIMPLE
        )
        console.print(warning)
        console.print()
    
    while True:
        show_menu()
        console.print()
        choice = prompt_with_animation(
            "[rgb(167,199,231)]Enter choice[/rgb(167,199,231)]",
            console=console
        )
        
        if choice == "1":
            analyze_logs()
        elif choice == "2":
            # Incident submenu
            while True:
                show_incident_menu()
                console.print()
                inc_choice = prompt_with_animation(
                    "[rgb(167,199,231)]Enter choice[/rgb(167,199,231)]",
                    choices=["2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8"],
                    default="2.8",
                    console=console
                )
                
                if inc_choice == "2.1":
                    report_incident()
                elif inc_choice == "2.2":
                    list_incidents()
                elif inc_choice == "2.3":
                    view_incident()
                elif inc_choice == "2.4":
                    update_incident()
                elif inc_choice == "2.5":
                    resolve_incident()
                elif inc_choice == "2.6":
                    generate_workflow_for_incident()
                elif inc_choice == "2.7":
                    incident_stats()
                elif inc_choice == "2.8":
                    break
                
                console.print()
                time.sleep(0.5)
        elif choice == "3":
            # Workflow submenu
            while True:
                show_workflow_menu()
                console.print()
                wf_choice = prompt_with_animation(
                    "[rgb(167,199,231)]Enter choice[/rgb(167,199,231)]",
                    choices=["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"],
                    default="3.7",
                    console=console
                )
                
                if wf_choice == "3.1":
                    list_workflows()
                elif wf_choice == "3.2":
                    view_workflow()
                elif wf_choice == "3.3":
                    generate_workflow_ai()
                elif wf_choice == "3.4":
                    run_workflow()
                elif wf_choice == "3.5":
                    check_workflow_status()
                elif wf_choice == "3.6":
                    list_workflow_runs()
                elif wf_choice == "3.7":
                    break
                
                console.print()
                time.sleep(0.5)
        elif choice == "4":
            analyze_problem()
        elif choice == "5":
            # Security submenu
            while True:
                show_security_menu()
                console.print()
                sec_choice = prompt_with_animation(
                    "[rgb(167,199,231)]Enter choice[/rgb(167,199,231)]",
                    choices=["5.1", "5.2", "5.3", "5.4", "5.5", "5.6"],
                    default="5.6",
                    console=console
                )
                
                if sec_choice == "5.1":
                    security_analysis()
                elif sec_choice == "5.2":
                    generate_workflow_for_security_event()
                elif sec_choice == "5.3":
                    security_scan()
                elif sec_choice == "5.4":
                    security_recommendations()
                elif sec_choice == "5.5":
                    security_stats()
                elif sec_choice == "5.6":
                    break
                
                console.print()
                time.sleep(0.5)
        elif choice == "6":
            # Team submenu
            while True:
                show_team_menu()
                console.print()
                team_choice = prompt_with_animation(
                    "[rgb(167,199,231)]Enter choice[/rgb(167,199,231)]",
                    choices=["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7"],
                    default="6.7",
                    console=console
                )
                
                if team_choice == "6.1":
                    create_team()
                elif team_choice == "6.2":
                    join_team()
                elif team_choice == "6.3":
                    list_my_teams()
                elif team_choice == "6.4":
                    view_team_details()
                elif team_choice == "6.5":
                    manage_team_members()
                elif team_choice == "6.6":
                    view_team_invitation()
                elif team_choice == "6.7":
                    break
                
                console.print()
                time.sleep(0.5)
        elif choice == "7":
            set_token()
        elif choice == "8":
            agent_status()
        elif choice == "9":
            monitor_terminal_output()
        elif choice == "10":
            full_agent_mode()
        elif choice == "11":
            show_settings_menu()
        elif choice == "12":
            console.print()
            goodbye = Panel(
                "[rgb(167,199,231)]Thank you for using Neurops CLI![/rgb(167,199,231)]\n"
                "[dim rgb(167,199,231)]Goodbye! 👋[/dim rgb(167,199,231)]",
                border_style="white",
                box=box.SIMPLE
            )
            console.print(Align.center(goodbye), width=80)
            console.print()
            break
        
        console.print()  # Boş satır
        time.sleep(0.5)  # Kısa bir bekleme


if __name__ == "__main__":
    main()
