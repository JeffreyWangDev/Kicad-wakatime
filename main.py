from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import FreeSimpleGUI as sg
import os
from waka import plugin, get_settings, save_settings
from datetime import datetime
waka = plugin()

settings = get_settings()

class FileWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        sent = waka.send_heartbeat(event.src_path, settings["api_key"], settings["folderpath"].replace("\\","/").split("/")[-1], file_saved=True)
        if sent:
            window["-OUTPUT-"].update("Sent heartbeat at " + str(datetime.now()))

observer = Observer()
event_handler = FileWatcher()

def cheek_folder(folder):
    if folder == "" or folder == None:
        return False
    if not os.path.exists(folder):
        return False
    return True

layout = [[sg.Text("Folder to watch")],
          [sg.Text(settings["folderpath"], key="FILEIN")],
          [sg.Text("API KEY")],
          [sg.Input(settings["api_key"], key="APIKEY")],
          [sg.Text(key="-OUTPUT-")],
          [sg.Button("Start"), sg.Button("Stop", disabled=True), sg.Button("Select Folder"), sg.Button("Quit")]]

window = sg.Window("Wakatime for all", layout)

while True:
    event, values = window.read()
    if event == "Select Folder":
        folder = sg.popup_get_folder("Select a folder")
        if not cheek_folder(folder):
            window["-OUTPUT-"].update("Folder does not exist")
            continue
        else:
            window["FILEIN"].update(folder)
            settings["folderpath"] = folder
            save_settings(settings)

    if event == sg.WINDOW_CLOSED or event == "Quit":
        break
    if values["APIKEY"] == "":
        window["-OUTPUT-"].update("Please enter an API KEY")
        continue
    else:
        settings["api_key"] = values["APIKEY"]
        save_settings(settings)

    if event == "Start":
        try:
            if not cheek_folder(layout[1][0].DisplayText):
                window["-OUTPUT-"].update("Folder does not exist")
                continue
        except:
            window["-OUTPUT-"].update("Folder does not exist")
            continue
        window["-OUTPUT-"].update("Starting...")
        window["Start"].update(disabled=True)
        window["Stop"].update(disabled=False)
        window["Select Folder"].update(disabled=True)
        observer.schedule(event_handler, layout[1][0].DisplayText, recursive=True)
        observer.start()
    if event == "Stop":
        window["-OUTPUT-"].update("Stopped")
        window["Start"].update(disabled=False)
        window["Stop"].update(disabled=True)
        window["Select Folder"].update(disabled=False)
        observer.stop()
        observer = Observer()
        event_handler = FileWatcher()
try:
    observer.stop()
    observer.join()
except:
    pass
window.close()