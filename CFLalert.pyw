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
#         date, time = split_time(date_time)
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

def get_headers():
    global live_now
    global future_games
    if live_now:
        if len(live_now) == 1:
            teams = get_teams(live_now[0])
            header = "Live Game: "
            return header, teams, None
        elif len(live_now) > 1:
            teams = get_teams(live_now[0])
            teams2 = get_teams(live_now[1])
            header = "Live Game: "
            return header, teams, teams2
    elif not live_now and future_games:
        next_game = future_games[0]
        teams = get_teams(next_game)
        header = "Next Game: "
        return header, teams, None
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
    global date_time
    toast = None
    if live_now and alerted == False and not len(live_now) == 1:
        notify_per_game = False
        alerted = True
        teams = get_teams(live_now[0])
        date, time = split_time(date_time)
        toast = Notification(app_id="CFL Alert", title="Game Time", msg="Live now! " + teams + " started at " + time, icon=cfl_ico, duration='long')
        toast.build().show()
    elif len(live_now) > 1 and alerted == False:
        notify_per_game = False
        alerted = True
        teams = get_teams(live_now[0])
        teams2 = get_teams(live_now[1])
        date, time = split_time(date_time)
        date, time2 = split_time(date_time2)
        toast = Notification(app_id="CFL Alert", title="Game Time", msg="2 Live Games! " + teams + " started at " + time + " and " + teams2 + " started at " + time2, icon=cfl_ico, duration='long')
        toast.build().show()
    elif next_game:
        teams = get_teams(next_game)
        date, time = split_time(date_time)
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

def get_time_label():
    global time_label
    global time_label2
    global date_time
    global date_time2
    if len(live_now) == 1:
        date_time = live_now[0]['date_start']
        date, time = split_time(date_time)
        time_label = "Started at " + str(time)
        app.destroy_label()
    elif len(live_now) > 1:
        date_time = live_now[0]['date_start']
        date, time = split_time(date_time)
        date_time2 = live_now[1]['date_start']
        date, time2 = split_time(date_time)
        time_label = "Started at " + str(time)
        time_label2 = "Started at " + str(time2)
        app.pack_labels()
    else:
        date_time = next_game['date_start']
        date, time = split_time(date_time)
        time_label = str(date) + " at " + str(time)
class App:

    def update_label(self):
        self.header_text.set(main_header)
        self.header2_text.set(main_teams)
        self.body_text.set(time_label)
        try:
            if self.body2.winfo_exists() == 1:
                self.header3_text.set(main_header)
                self.header4_text.set(main_teams2)
                self.body2_text.set(time_label2)
        except:
            pass

    def destroy_label(self):
        try:
            if self.body2.winfo_exists() == 1:
                self.header3.destroy()
                self.header4.destroy()
                self.body2.destroy()
        except:
            pass

    def pack_labels(self):
        self.header3 = Label(root, textvariable=self.header3_text, font=("Leelawadee UI", 22, "bold")).pack(in_=self.top, side=TOP)
        self.header4 = Label(root, textvariable=self.header4_text, font=("Leelawadee UI", 20, "bold")).pack(in_=self.top, side=TOP)
        self.body2 = Label(root, textvariable=self.body2_text, font=("Leelawadee UI", 14)).pack(in_=self.top, side=TOP)

    def __init__(self, master):
        self.master = master
        self.header_text = StringVar()
        self.header2_text = StringVar()
        self.body_text = StringVar()
        self.top = Frame(root)
        self.top.pack(side=TOP)
        self.bottom = Frame(root)
        self.bottom.pack(side=BOTTOM) # fill=BOTH, expand=True also options
        self.quit_btn = Button(root, text="Exit", command=quit_program).pack(in_=self.bottom, side=RIGHT)
        self.hide_btn = Button(root, text="Hide", command=hide_window).pack(in_=self.bottom, side=RIGHT)
        self.check_btn = Button(root, text="Update", command=reset_and_notify).pack(in_=self.bottom, side=RIGHT)
        self.header = Label(root, textvariable=self.header_text, font=("Leelawadee UI", 22, "bold")).pack(in_=self.top, side=TOP)
        self.header2 = Label(root, textvariable=self.header2_text, font=("Leelawadee UI", 20, "bold")).pack(in_=self.top, side=TOP)
        self.body = Label(root, textvariable=self.body_text, font=("Leelawadee UI", 14)).pack(in_=self.top, side=TOP)

if __name__ == "__main__":

    future_games = []
    live_now = []
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
    update_games = Periodic(300,get_games())
    # update_standing = Periodic(3600,get_standings(current_year))
    reset_hour = Periodic(3600,reset_notify_1h())
    reset_alert = Periodic(14400,reset_notify_current())
    reset_24 = Periodic(86400,reset_notify_24h())
    check_live = Periodic(300,check_live_game(games))
    main_header, main_teams, main_teams2 = get_headers()
    next_game = future_games[0]

    root=Tk()
    root.title("CFL Alert")
    root.iconbitmap(cfl_ico)

    app = App(root)
    get_time_label()
    notify = Periodic(60,gen_notification())
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
    check_live.stop()

    #TODO
    # filter out games with --- for team
    # do something with standings
    # pretty up the GUI
    # use .json data instead of API calls in som places
    # optimize, shit takes forever to start
