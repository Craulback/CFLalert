import requests
import pytz
import os
from datetime import datetime, date
from pystray import Icon
from pathlib import Path
from dateutil import parser
from dotenv import load_dotenv
from winotify import Notification
from threading import Timer, Lock
from tkinter import *
from tkinter import ttk
from pystray import MenuItem as item
from PIL import Image

load_dotenv()

def quit_from_tray(icon):
    icon.stop()
    root.destroy()

def quit_from_window():
    root.destroy()

def show_window(icon):
    icon.stop()
    root.after(0,root.deiconify())
    app.get_labels()

def hide_window():
    root.withdraw()
    image=Image.open(cfl_ico)
    menu=(item('Show', show_window), item('Check Now', reset_and_notify), item('Exit', quit_from_tray))
    icon=Icon("CFL.ico", image, "CFL Alert", menu)
    icon.run()

class Periodic(object):

    def __init__(self, interval, function, *args, **kwargs):
        self._lock = Lock()
        self._timer = None
        self.function = function
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self._stopped = True
        if kwargs.pop('autostart', True):
            self.start()

    def start(self, from_run=False):
        self._lock.acquire()
        if from_run or self._stopped:
            self._stopped = False
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self._lock.release()

    def _run(self):
        self.start(from_run=True)
        if self.function != None:
            self.function(*self.args, **self.kwargs)

    def stop(self):
        self._lock.acquire()
        self._stopped = True
        self._timer.cancel()
        self._lock.release()

def load_data(year):
    url = f"http://api.cfl.ca/v1/games/{year}?sort=date_start&key={api_key}"
    schedule = requests.get(url).json()
    return schedule

def check_live_game(games):
    global live_now
    live_now = []
    for game in games['data']:
        status = game['event_status']
        active = status['is_active']
        if active:
            live_now.append(game)

def split_time(iso_time):
    dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00')).astimezone()
    output = dt.strftime('%A-%b-%d %I:%M%p').split(maxsplit=1)
    date = output[0].replace('-', ' ')
    time = output[1]
    return date, time

def get_teams(game):
    team1 = game['team_1']
    team2 = game['team_2']
    if team1['is_at_home'] == False:
        result = team1['abbreviation'] + " @ " + team2['abbreviation']
        return result
    elif team1['is_at_home']:
        result = team2['abbreviation'] + " @ " + team1['abbreviation']
        return result
    elif team1['is_at_home'] == False and team2['is_at_home'] == False:
        result = team1['abbreviation'] + " vs " + team2['abbreviation']
        return result

def get_standings(year):
    url = f"http://api.cfl.ca/v1/standings/{year}?key={api_key}"
    stats = requests.get(url).json()
    return stats

def get_games():
    global games
    games = load_data(current_year)
    check_live_game(games)
    for game in games['data']:
        game_time = parser.parse(game['date_start'])
        team1 = (game['team_1'])
        if game_time > local_time and team1 != '---':
            future_games.append(game)

def gen_notification():
    global notify_5m
    global notify_24h
    global notify_1h
    global alerted
    global notify_per_game
    global date_time
    toast = None
    if live_now and alerted == False and len(live_now) == 1:
        notify_per_game = False
        alerted = True
        teams = get_teams(live_now[0])
        date, time = split_time(date_time)
        toast = Notification(app_id="CFL Alert", title="Game Time", 
                             msg="Live now! " + teams + " started at " + time, icon=cfl_ico, duration='long')
        toast.build().show()
    elif len(live_now) > 1 and alerted == False:
        notify_per_game = False
        alerted = True
        toast = Notification(app_id="CFL Alert", title="Game Time", 
                             msg="2 Live Games! Open CFL Alert to see details.", icon=cfl_ico, duration='long')
        # toast.add_actions(label="Click here to open", show_window)
        toast.build().show()
    elif next_game:
        teams = get_teams(next_game)
        date, time = split_time(date_time)
        insertion_time = parser.parse(date_time)
        difference = insertion_time - pytz.utc.localize(datetime.utcnow())
        if difference.seconds <= 300 and difference.days < 1 and notify_5m == False:
            notify_5m = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " starting soon! " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds <= 3600 and notify_1h == False:
            notify_1h = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " today at " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds > 3600 and difference.days < 1 and notify_24h == False:
            notify_24h = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " today at " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.days > 1 and notify_per_game == False:
            notify_per_game = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " at " + time + " on " + date, icon=cfl_ico, duration='long')
            toast.build().show()
        else:
            pass

def reset_notify_24h():
    global notify_24h
    notify_24h = False

def reset_notify_current():
    global alerted
    alerted = False
 
def reset_notify_1h():
    global notify_1h
    global notify_5m
    notify_1h = False
    notify_5m = False

def reset_once_per_game():
    global notify_per_game
    notify_per_game = False

def reset_and_notify():
    reset_once_per_game()
    reset_notify_current()
    reset_notify_24h()
    reset_notify_1h()
    gen_notification()
    app.get_labels()


class App:

    def destroy_labels(self):
        for label in self.labels:
            label.destroy()
    
    def pack_game(self):
        self.header = Label(root, textvariable=self.header_text, font=("Leelawadee UI", 22, "bold"))
        self.teams = Label(root, textvariable=self.teams_text, font=("Leelawadee UI", 20, "bold"))
        self.body = Label(root, textvariable=self.body_text, font=("Leelawadee UI", 14))
        self.header.pack(in_=self.top, side=TOP)
        self.teams.pack(in_=self.top, side=TOP)
        self.body.pack(in_=self.top, side=TOP)
        self.separator.pack(fill='x')
        self.labels.append(self.header)
        self.labels.append(self.teams)
        self.labels.append(self.body)

    def toggle_standings(self):
        if self.sched_stand_toggle.get() == "Show Standings":
            self.destroy_labels()
            self.sched_stand_toggle.set("Show Game Time")
        elif self.sched_stand_toggle.get() == "Show Game Time":
            self.destroy_labels()
            self.get_labels()
            self.sched_stand_toggle.set("Show Standings")
                
    def get_labels(self):
        global date_time
        if len(live_now) > 0:
            self.destroy_labels()
            for game in live_now:
                header = "Live Game:"
                teams = get_teams(game)
                date_time = game['date_start']
                date, time = split_time(date_time)
                time_label = "Started at " + str(time)
                self.header_text.set(header)
                self.teams_text.set(teams)
                self.body_text.set(time_label)
                self.pack_game()
        else:
            header = "Next Game:"
            teams = get_teams(next_game)
            date_time = next_game['date_start']
            date, time = split_time(date_time)
            time_label = str(date) + " at " + str(time)
            self.destroy_labels()
            self.header_text.set(header)
            self.teams_text.set(teams)
            self.body_text.set(time_label)
            self.pack_game()
    
    def __init__(self, master):
        self.labels = []
        self.master = master
        self.sched_stand_toggle = StringVar(root)
        self.sched_stand_toggle.set("Show Standings")
        self.header_text = StringVar(root)
        self.teams_text = StringVar(root)
        self.body_text = StringVar(root)
        self.separator = ttk.Separator(root, orient='horizontal')
        self.top = Frame(root)
        self.top.pack(side=TOP)
        self.bottom = Frame(root)
        self.bottom.pack(side=BOTTOM)
        self.show_standings_btn = Button(root, textvariable=self.sched_stand_toggle, command=self.toggle_standings).pack(in_=self.bottom)
        self.quit_btn = Button(root, text="Exit", command=quit_from_window).pack(in_=self.bottom, side=RIGHT)
        self.hide_btn = Button(root, text="Hide", command=hide_window).pack(in_=self.bottom, side=RIGHT)
        self.update_btn = Button(root, text="Update", command=self.get_labels).pack(in_=self.bottom, side=RIGHT)
        self.get_labels()

if __name__ == "__main__":

    future_games = []
    live_now = []
    games = None
    notify_per_game = False
    notify_5m = False
    notify_1h = False
    notify_24h = False
    alerted = False
    path = Path(__file__).parent.resolve()
    cfl_ico = fr"{path}\CFL.ico"

    current_year = date.today().year
    api_key = os.environ.get('CFL_API_KEY')
    utc_time = datetime.utcnow()
    local_time = pytz.utc.localize(utc_time, is_dst=None).astimezone()
    update_sched = Periodic(300,get_games())
    # update_standing = Periodic(3600,get_standings(current_year))
    reset_hour = Periodic(3600,reset_notify_1h())
    reset_alert = Periodic(14400,reset_notify_current())
    reset_24 = Periodic(86400,reset_notify_24h())
    next_game = future_games[0]

    root=Tk()
    root.title("CFL Alert")
    root.iconbitmap(cfl_ico)

    app = App(root)
    notify = Periodic(60,gen_notification())
    root.protocol('WM_DELETE_WINDOW', hide_window)
    root.mainloop()
    update_sched.stop()
    # update_standings.stop()
    reset_alert.stop()
    reset_hour.stop()
    reset_24.stop()
    notify.stop()

    #TODO
    # do something with standings
    # pretty up the GUI
    # use .json data instead of API calls in some places
    # optimize, shit takes forever to start
