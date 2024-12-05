# STOLEN FROM https://github.com/wakatime/sublime-wakatime/blob/master/WakaTime.py


import json
from logging import ERROR, log, INFO, WARNING, DEBUG
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import threading
import traceback
from subprocess import PIPE
from zipfile import ZipFile



from configparser import ConfigParser, Error as ConfigParserError

from urllib.request import Request, urlopen
from urllib.error import HTTPError

is_win = platform.system() == 'Windows'
HOME_FOLDER = os.path.realpath(os.environ.get('WAKATIME_HOME') or os.path.expanduser('~'))
RESOURCES_FOLDER = os.path.join(HOME_FOLDER, '.wakatime')
CONFIG_FILE = os.path.join(HOME_FOLDER, '.wakatime.cfg')
INTERNAL_CONFIG_FILE = os.path.join(HOME_FOLDER, '.wakatime-internal.cfg')
GITHUB_RELEASES_STABLE_URL = 'https://api.github.com/repos/wakatime/wakatime-cli/releases/latest'
GITHUB_DOWNLOAD_PREFIX = 'https://github.com/wakatime/wakatime-cli/releases/download'
SETTINGS = {}
LATEST_CLI_VERSION = None
WAKATIME_CLI_LOCATION = None



def parseConfigFile(configFile):
    """Returns a configparser.SafeConfigParser instance with configs
    read from the config file. Default location of the config file is
    at ~/.wakatime.cfg.
    """

    kwargs = {'strict': False}
    configs = ConfigParser(**kwargs)
    try:
        with open(configFile, 'r', encoding='utf-8') as fh:
            try:

                configs.read_file(fh)
                return configs
            except ConfigParserError:
                log(ERROR, traceback.format_exc())
                return None
    except IOError:
        log(DEBUG, "Error: Could not read from config file {0}\n".format(configFile))
        return configs

class Popen(subprocess.Popen):
    """Patched Popen to prevent opening cmd window on Windows platform."""

    def __init__(self, *args, **kwargs):
        if is_win:
            startupinfo = kwargs.get('startupinfo')
            try:
                startupinfo = startupinfo or subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except AttributeError:
                pass
            kwargs['startupinfo'] = startupinfo
        super(Popen, self).__init__(*args, **kwargs)

class UpdateCLI(threading.Thread):
    """Non-blocking thread for downloading latest wakatime-cli from GitHub.
    """

    def run(self):
        if isCliLatest():
            print("Wakatime-cli is up to date")
            return
        print("Downloading wakatime-cli...")
        log(INFO, 'Downloading wakatime-cli...')

        if os.path.isdir(os.path.join(RESOURCES_FOLDER, 'wakatime-cli')):
            shutil.rmtree(os.path.join(RESOURCES_FOLDER, 'wakatime-cli'))

        if not os.path.exists(RESOURCES_FOLDER):
            os.makedirs(RESOURCES_FOLDER)

        try:
            url = cliDownloadUrl()
            log(DEBUG, 'Downloading wakatime-cli from {url}'.format(url=url))
            zip_file = os.path.join(RESOURCES_FOLDER, 'wakatime-cli.zip')
            download(url, zip_file)

            if isCliInstalled():
                try:
                    os.remove(getCliLocation())
                except:
                    log(DEBUG, traceback.format_exc())
            print("Extracting wakatime-cli...")
            log(INFO, 'Extracting wakatime-cli...')
            with ZipFile(zip_file) as zf:
                zf.extractall(RESOURCES_FOLDER)

            if not is_win:
                os.chmod(getCliLocation(), 509)  # 755

            try:
                os.remove(os.path.join(RESOURCES_FOLDER, 'wakatime-cli.zip'))
            except:
                log(DEBUG, traceback.format_exc())
        except:
            log(DEBUG, traceback.format_exc())

        createSymlink()
        print("Finished extracting wakatime-cli.")
        log(INFO, 'Finished extracting wakatime-cli.')


def getCliLocation():
    global WAKATIME_CLI_LOCATION

    if not WAKATIME_CLI_LOCATION:
        binary = 'wakatime-cli-{osname}-{arch}{ext}'.format(
            osname=platform.system().lower(),
            arch=architecture(),
            ext='.exe' if is_win else '',
        )
        WAKATIME_CLI_LOCATION = os.path.join(RESOURCES_FOLDER, binary)

    return WAKATIME_CLI_LOCATION


def architecture():
    arch = platform.machine() or platform.processor()
    if arch == 'armv7l':
        return 'arm'
    if arch == 'aarch64':
        return 'arm64'
    if 'arm' in arch:
        return 'arm64' if sys.maxsize > 2**32 else 'arm'
    return 'amd64' if sys.maxsize > 2**32 else '386'


def isCliInstalled():
    return os.path.exists(getCliLocation())


def isCliLatest():
    if not isCliInstalled():
        return False

    args = [getCliLocation(), '--version']
    try:
        stdout, stderr = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
    except:
        return False
    stdout = (stdout or b'') + (stderr or b'')
    localVer = extractVersion(stdout.decode('utf-8'))
    if not localVer:
        log(DEBUG, 'Local wakatime-cli version not found.')
        return False

    log(INFO, 'Current wakatime-cli version is %s' % localVer)
    log(INFO, 'Checking for updates to wakatime-cli...')

    remoteVer = getLatestCliVersion()

    if not remoteVer:
        return True

    if remoteVer == localVer:
        log(INFO, 'wakatime-cli is up to date.')
        return True

    log(INFO, 'Found an updated wakatime-cli %s' % remoteVer)
    return False


def getLatestCliVersion():
    global LATEST_CLI_VERSION

    if LATEST_CLI_VERSION:
        return LATEST_CLI_VERSION

    configs, last_modified, last_version = None, None, None
    try:
        configs = parseConfigFile(INTERNAL_CONFIG_FILE)
        if configs:
            last_modified, last_version = lastModifiedAndVersion(configs)
    except:
        log(DEBUG, traceback.format_exc())

    try:
        headers, contents, code = request(GITHUB_RELEASES_STABLE_URL, last_modified=last_modified)

        log(DEBUG, 'GitHub API Response {0}'.format(code))

        if code == 304:
            LATEST_CLI_VERSION = last_version
            return last_version

        data = json.loads(contents.decode('utf-8'))

        ver = data['tag_name']
        log(DEBUG, 'Latest wakatime-cli version from GitHub: {0}'.format(ver))

        if configs:
            last_modified = headers.get('Last-Modified')
            if not configs.has_section('internal'):
                configs.add_section('internal')
            configs.set('internal', 'cli_version', ver)
            configs.set('internal', 'cli_version_last_modified', last_modified)
            with open(INTERNAL_CONFIG_FILE, 'w', encoding='utf-8') as fh:
                configs.write(fh)

        LATEST_CLI_VERSION = ver
        return ver
    except:
        log(DEBUG, traceback.format_exc())
        return None


def lastModifiedAndVersion(configs):
    last_modified, last_version = None, None
    if configs.has_option('internal', 'cli_version'):
        last_version = configs.get('internal', 'cli_version')
    if last_version and configs.has_option('internal', 'cli_version_last_modified'):
        last_modified = configs.get('internal', 'cli_version_last_modified')
    if last_modified and last_version and extractVersion(last_version):
        return last_modified, last_version
    return None, None


def extractVersion(text):
    pattern = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)")
    match = pattern.search(text)
    if match:
        return 'v{ver}'.format(ver=match.group(1))
    return None


def cliDownloadUrl():
    osname = platform.system().lower()
    arch = architecture()

    validCombinations = [
      'darwin-amd64',
      'darwin-arm64',
      'freebsd-386',
      'freebsd-amd64',
      'freebsd-arm',
      'linux-386',
      'linux-amd64',
      'linux-arm',
      'linux-arm64',
      'netbsd-386',
      'netbsd-amd64',
      'netbsd-arm',
      'openbsd-386',
      'openbsd-amd64',
      'openbsd-arm',
      'openbsd-arm64',
      'windows-386',
      'windows-amd64',
      'windows-arm64',
    ]
    check = '{osname}-{arch}'.format(osname=osname, arch=arch)
    if check not in validCombinations:
        reportMissingPlatformSupport(osname, arch)

    version = getLatestCliVersion()

    return '{prefix}/{version}/wakatime-cli-{osname}-{arch}.zip'.format(
        prefix=GITHUB_DOWNLOAD_PREFIX,
        version=version,
        osname=osname,
        arch=arch,
    )


def reportMissingPlatformSupport(osname, arch):
    url = 'https://api.wakatime.com/api/v1/cli-missing?osname={osname}&architecture={arch}&plugin=sublime'.format(
        osname=osname,
        arch=arch,
    )
    request(url)


def request(url, last_modified=None):
    req = Request(url)
    req.add_header('User-Agent', 'github.com/wakatime/sublime-wakatime')

    proxy = SETTINGS.get('proxy')
    if proxy:
        req.set_proxy(proxy, 'https')

    if last_modified:
        req.add_header('If-Modified-Since', last_modified)

    try:
        resp = urlopen(req)
        headers = resp.headers
        return headers, resp.read(), resp.getcode()
    except HTTPError as err:
        if err.code == 304:
            return None, None, 304

        log(DEBUG, err.read().decode())
        raise
    except IOError:
        raise


def download(url, filePath):
    req = Request(url)
    req.add_header('User-Agent', 'waka-forall')

    proxy = SETTINGS.get('proxy')
    if proxy:
        req.set_proxy(proxy, 'https')

    with open(filePath, 'wb') as fh:
        try:
            resp = urlopen(req)
            fh.write(resp.read())
        except HTTPError as err:
            if err.code == 304:
                return None, None, 304
            log(DEBUG, err.read().decode())
            raise
        except IOError:
            raise


def is_symlink(path):
    try:
        return os.is_symlink(path)
    except:
        return False


def createSymlink():
    link = os.path.join(RESOURCES_FOLDER, 'wakatime-cli')
    if is_win:
        link = link + '.exe'
    elif os.path.exists(link) and is_symlink(link):
        return  # don't re-create symlink on Unix-like platforms

    try:
        os.symlink(getCliLocation(), link)
    except:
        try:
            shutil.copy2(getCliLocation(), link)
            if not is_win:
                os.chmod(link, 509)  # 755
        except:
            log(WARNING, traceback.format_exc())


class SSLCertVerificationDisabled(object):

    def __enter__(self):
        self.original_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context

    def __exit__(self, *args, **kwargs):
        ssl._create_default_https_context = self.original_context

