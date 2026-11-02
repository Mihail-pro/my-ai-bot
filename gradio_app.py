import ctypes
import getpass
import os
import platform
import socket

import gradio as gr
import requests

API_URL = "http://127.0.0.1:8080/at_data/answer"

def content_to_text(content):
    """Gradio 6 stores message content as a list of blocks like
    [{"type": "text", "text": ...}]; older versions use a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def ask_bot(message, history):
    """
    message: last message from user
    history: list of {"role": ..., "content": ...} dicts (gradio >= 6)
    """
    all_messages = [content_to_text(msg["content"]) for msg in history]
    all_messages.append(message)
    print(len(history), message)
    try:
        response = requests.post(API_URL, json=all_messages)
        response.raise_for_status()
        data = response.json()
        print(f"response {data}") #DEBUG

        parts = data["answer"].split("</think>")
        if len(parts) > 1:
            answer = parts[1]
        else:
            answer = parts[0]

        return answer.strip()
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except ValueError:
            detail = e.response.text
        print(f"API error {e.response.status_code}: {detail}")
        return f"API error {e.response.status_code}: {detail}"
    except requests.exceptions.RequestException as e:
        print(f"Error connection to API: {e}")
        return f"Error connection to API: {e}"
    except KeyError:
        return "Error: not correct answer from server"
    except Exception as e:
        print(f"Unknown error: {e}")
        return f"Unknown error: {e}"


def get_ip_address():
    try:
        # UDP "connect" (no traffic sent) to learn the outgoing interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "unknown"


def get_total_ram_gb():
    try:
        if platform.system() == "Windows":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / 1024**3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (OSError, AttributeError, ValueError):
        return None


def get_host_meta():
    ram_gb = get_total_ram_gb()
    ram = f"{ram_gb:.1f} GB RAM" if ram_gb else "RAM: unknown"
    try:
        user = getpass.getuser()
    except OSError:
        user = "unknown"
    parts = [
        f"{user}@{socket.gethostname()} ({get_ip_address()})",
        f"{platform.system()} {platform.release()}",
        f"{os.cpu_count()} cores",
        ram,
    ]
    return " · ".join(parts)


HOST_META_CSS = """
.host-meta {
    position: fixed;
    bottom: 8px;
    left: 12px;
    font-size: 12px;
    color: var(--body-text-color-subdued, gray);
    z-index: 1000;
}
"""

with gr.Blocks(title="🔨AT AI assistant", css=HOST_META_CSS) as demo:
    gr.ChatInterface(
        fn=ask_bot,
        chatbot=gr.Chatbot(height=400, type="messages"),
        textbox=gr.Textbox(placeholder="Ask question", container=False),
        title="🔨AT AI assistant",
        description="Your helpful assistant and best friend :)",
        type="messages"
    )
    gr.HTML(f'<div class="host-meta">🖥 {get_host_meta()}</div>')

demo.launch(share=False)


'''
examples=[
        "Tell me about Allied Testing",
        "How can I contact you?",
        "What services do you offer?"
    ],
    cache_examples=False
'''