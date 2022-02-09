import requests
import pytz
import os
# import json
from datetime import datetime, date
from pystray import Icon
from pathlib import Path
from dateutil import parser
from dotenv import load_dotenv
from winotify import Notification
from threading import Timer, Lock
from tkinter import *
from pystray import MenuItem as item
from PIL import Image, ImageTk

load_dotenv()

def quit_window(icon):
   icon.stop()
   root.destroy()
   
def quit_program():
   root.destroy()

def show_window(icon):
   icon.stop()
   root.after(0,root.deiconify())

def hide_window():
   root.withdraw()
   image=Image.open(cfl_ico)
   menu=(item('Show', show_window), item('Check Now', reset_and_notify), item('Exit', quit_window))
   icon=Icon("name", image, "CFL Alert", menu)
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
    url = f"http://api.cfl.ca/v1/games/{year}?key={api_key}"
    schedule = requests.get(url).json()
    return schedule

def check_for_current_game(games):
    for game in games['data']:
        status = game['event_status']
        active = status['is_active']
        if active:
            return game

def parse_time(iso_time):
    dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00')).astimezone()
    output = dt.strftime('%A-%b-%d %I:%M%p').split(maxsplit=1)
    date = output[0].replace('-', ' ')
    time = output[1]
    return date, time

def future_schedule(schedule):
    for game in schedule['data']:
        game_time = parser.parse(game['date_start'])
        if game_time > local_time:
            future_games.append(game)
            
# def fill_schedule(games):
#     scheduled_games = []
#     for game in games:
#         teams = get_teams(game)
#         date_time = game['date_start']
#         date, time = parse_time(date_time)
#         if teams and date and time:
#             details = (teams + " on " + date + " at " + time)
#             scheduled_games.append(details)
#     sched = open("sched.json", "w")
#     json.dump(scheduled_games, sched, ensure_ascii=False, indent=4)

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
    # test = open("standings.json", "w")
    # json.dump(stats, test, ensure_ascii=False, indent=4)
    # test.close()
    # print("Standings loaded")
    return stats

def get_next_game():
    global current_game
    global future_games
    if current_game:
        header = "Live Game: "
        return header, current_game
    elif not current_game and future_games:
        next_game = future_games[0]
        teams = get_teams(next_game)
        header = "Next Game: "
        return header, teams
    else:
        return "Next Game: ", "No data"

def get_games():
    global games
    games = load_data(current_year)
    future_schedule(games)
    # test2 = open("games.json", "w")
    # json.dump(games, test2, ensure_ascii=False, indent=4)
    # test2.close()
    # fill_schedule(future_games)
    # print("Data loaded")

def gen_notification():
    global notify_5m
    global notify_24h
    global notify_1h
    global alerted
    global notify_per_game
    toast = None
    if current_game and alerted == False:
        notify_per_game = False
        alerted = True
        teams = get_teams(current_game)
        toast = Notification(app_id="CFL Alert", title="Game Time", msg="Live now! " + teams, icon=cfl_ico, duration='long')
        toast.build().show()
    elif next_game:
        teams = get_teams(next_game)
        date, time = parse_time(date_time)
        insertion_time = parser.parse(date_time)
        difference = insertion_time - pytz.utc.localize(datetime.utcnow())
        if difference.seconds <= 300 and difference.days < 1 and notify_5m == False:
            notify_5m = True
            toast = Notification(app_id="CFL Alert", title="Game Time", msg="Next game: " + teams + " starting soon! " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds <= 3600 and difference.days < 1 and notify_1h == False:
            notify_1h = True
            toast = Notification(app_id="CFL Alert", title="Game Time", msg="Next game: " + teams + " today at " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds > 3600 and difference.days < 1 and notify_24h == False:
            notify_24h = True
            toast = Notification(app_id="CFL Alert", title="Game Time", msg="Next game: " + teams + " today at " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.days > 1 and notify_per_game == False:
            notify_per_game = True
            toast = Notification(app_id="CFL Alert", title="Game Time", msg="Next game: " + teams + " at " + time + " on " + date, icon=cfl_ico, duration='long')            
            toast.build().show()
        else:
            return None

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
    app.update_label()

class App:
    
    def update_label(self):
        self.headerText.set(main_header)
        self.header2Text.set(main_game)
        self.bodyText.set(time_label)
    
    def __init__(self, master):
        self.master = master

        self.headerText = StringVar()
        self.header2Text = StringVar()
        self.bodyText = StringVar()
        self.header = Label(root, textvariable=self.headerText, font=("Leelawadee UI", 22, "bold")).pack()
        self.header2 = Label(root, textvariable=self.header2Text, font=("Leelawadee UI", 20, "bold")).pack()
        self.body = Label(root, textvariable=self.bodyText, font=("Leelawadee UI", 14)).pack()
        self.bottom = Frame(root)
        self.bottom.pack(side=BOTTOM) # fill=BOTH, expand=True also options
        self.check_btn = Button(root, text="Update", command=reset_and_notify).pack(in_=self.bottom, side=RIGHT)
        self.quit_btn = Button(root, text="Exit", command=quit_program).pack(in_=self.bottom, side=RIGHT)

if __name__ == "__main__":

    future_games = []
    notify_per_game = False
    notify_5m = False
    notify_1h = False
    notify_24h = False
    alerted = False
    games = None
    path = Path(__file__).parent.resolve()
    cfl_ico = fr"{path}\CFL.ico"

    current_year = date.today().year
    api_key = os.environ.get('CFL_API_KEY')
    utc_time = datetime.utcnow()
    local_time = pytz.utc.localize(utc_time, is_dst=None).astimezone()
    update_games = Periodic(3600,get_games())
    # update_standing = Periodic(3600,get_standings(current_year))
    reset_hour = Periodic(3600,reset_notify_1h())
    reset_alert = Periodic(14400,reset_notify_current())
    reset_24 = Periodic(86400,reset_notify_24h())
    current_game = check_for_current_game(games)
    main_header, main_game = get_next_game()
    next_game = future_games[0]
    date_time = next_game['date_start']
    date, time = parse_time(date_time)
    time_label = str(date) + " at " + str(time)
    notify = Periodic(60,gen_notification())

    root=Tk()
    root.title("CFL Alert")
    root.iconbitmap(cfl_ico)

    app = App(root)
    
    update_labels = Periodic(30,app.update_label())
    
    root.protocol('WM_DELETE_WINDOW', hide_window)
    root.mainloop()
    update_games.stop()
    # update_standings.stop()
    reset_alert.stop()
    reset_hour.stop()
    reset_24.stop()
    notify.stop()
    update_labels.stop()

    #TODO
    # filter out games with --- for team
    # check for 2nd currently live game
    # do something with standings
    # pretty up the GUI
    # use .json data instead of API calls in som places
    # optimize, shit takes forever to start
