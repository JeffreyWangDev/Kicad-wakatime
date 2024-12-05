from datetime import datetime, timedelta
import subprocess
import wakainstall
import json


wakainstall.UpdateCLI().start()
SETTINGS_FILE = 'WakaTime-kicad-settings.json'

si = subprocess.STARTUPINFO()
si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

def get_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
    except:
        settings = {"api_key": "", "folderpath": ""}
    return settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

class plugin:
    def __init__(self,):
        self.version = "1.0.0"
        self.last_sent_time = datetime.now()-timedelta(minutes=2)

    def cli_path(self):
        return wakainstall.getCliLocation()
    
    def send_heartbeat(self, file_path, api_key, project, file_saved=False):
        if (datetime.now() - self.last_sent_time) < timedelta(minutes=1):
            return
        
        cli_path = self.cli_path()
        cli_args = [
            cli_path,
            "--entity", file_path,
            "--plugin", f"0.0.0 some_editor/prob_kicad wakatime-for-all/{self.version}",  
            "--key", api_key,
            "--project", project,
            "--api-url", "https://waka.hackclub.com/api",
            "--verbose"
        ]

        if file_saved:
            cli_args.append("--write")

        print("Executing WakaTime CLI...")
        stdin = None
        inp = None
        process = subprocess.Popen(cli_args, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,startupinfo=si)
        process.communicate(input=inp)
        retcode = process.poll()
        self.last_sent_time = datetime.now()
        if retcode == 0:
            print("Heartbeat sent successfully")
            return True
        else:
            print("Error sending heartbeat")
            return False