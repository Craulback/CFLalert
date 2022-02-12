import requests
import pytz
import os
import json
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
    if app.sched_stand_toggle.get() == "Show Standings":
        app.get_labels()

def hide_window():
    root.withdraw()
    image=Image.open(cfl_ico)
    menu=(item('Show', show_window), item('Check Now', reset_and_notify), item('Exit', quit_from_tray))
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
    dt = dt.strftime('%A-%b-%d %I:%M%p').split(maxsplit=1)
    date = dt[0].replace('-', ' ')
    time = dt[1]
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
    standings = requests.get(url).json()
    stand = open("standings.json", "w")
    json.dump(standings, stand, ensure_ascii=False, indent=4)
    stand.close()

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
    global alerted_5m
    global alerted_today
    global alerted_1h
    global notify_per_game
    global alerted
    if alerted == False and len(live_now) == 1:
        reset_alerts()
        alerted = True
        teams = get_teams(live_now[0])
        date_time = live_now[0]['date_start']
        date, time = split_time(date_time)
        toast = Notification(app_id="CFL Alert", title="Game Time", 
                             msg="Live now! " + teams + " started at " + time, icon=cfl_ico, duration='long')
        toast.build().show()
    elif alerted == False and len(live_now) > 1:
        reset_alerts()
        alerted = True
        toast = Notification(app_id="CFL Alert", title="Game Time", 
                             msg="2 Live Games! Open CFL Alert for details.", icon=cfl_ico, duration='long')
        # toast.add_actions(label="Click here to open", show_window)
        toast.build().show()
    elif future_games[0]:
        if alerted == True:
            get_standings(current_year)
            alerted = False
        date_time = future_games[0]['date_start']
        teams = get_teams(future_games[0])
        date, time = split_time(date_time)
        insertion_time = parser.parse(date_time)
        difference = insertion_time - pytz.utc.localize(datetime.utcnow())
        if difference.seconds <= 300 and difference.days < 1 and alerted_5m == False:
            alerted_5m = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " starting soon! " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds <= 3600 and difference.days < 1 and alerted_1h == False:
            alerted_1h = True
            toast = Notification(app_id="CFL Alert", title="Game Time", 
                                 msg="Next game: " + teams + " today at " + time, icon=cfl_ico, duration='long')            
            toast.build().show()
        elif difference.seconds > 3600 and difference.days < 1 and alerted_today == False:
            alerted_today = True
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
    else:
        pass

def reset_alerts():
    global alerted_5m
    global alerted_1h
    global alerted_today
    global notify_per_game
    global alerted
    alerted = False
    alerted_5m = False
    alerted_1h = False
    alerted_today = False
    notify_per_game = False

def reset_and_notify():
    reset_alerts()
    gen_notification()
    if app.sched_stand_toggle.get() == "Show Standings":
        app.destroy_labels()
        app.get_labels()
    elif app.sched_stand_toggle.get() == "Show Game Time":
        app.destroy_labels()
        app.pack_standings()

class App:

    def destroy_labels(self):
        for label in self.labels:
            label.destroy()
    
    def pack_game(self):
        self.top = Frame(root)
        self.top.pack(side=TOP)
        self.header = Label(root, textvariable=self.header_text, font=("Leelawadee UI", 22, "bold"))
        self.teams = Label(root, textvariable=self.teams_text, font=("Leelawadee UI", 20, "bold"))
        self.body = Label(root, textvariable=self.body_text, font=("Leelawadee UI", 14))
        self.header.pack(in_=self.top, side=TOP)
        self.teams.pack(in_=self.top, side=TOP)
        self.body.pack(in_=self.top, side=TOP)
        self.separator = ttk.Separator(self.top, orient='horizontal')
        self.separator.pack(in_=self.top,fill='x')
        self.labels.append(self.top)
    
    def pack_standings(self):
        with open('standings.json') as standings_file:
            standings = json.load(standings_file)
            standings_file.close()
        iid_var = 0
        self.main_frame = Frame(root)
        self.main_frame.pack(side=TOP)
        self.table_frame_w = Frame(self.main_frame)
        self.table_frame_w.pack(side=LEFT)
        self.separator = ttk.Separator(self.main_frame,orient=VERTICAL)
        self.separator.pack(in_=self.main_frame,side=RIGHT)
        self.table_frame_e = Frame(self.main_frame)
        self.table_frame_e.pack(side=RIGHT)
        self.table_w = ttk.Treeview(self.table_frame_w)
        self.table_e = ttk.Treeview(self.table_frame_e)
        self.table_w.pack(in_=self.table_frame_w,side=BOTTOM)
        self.table_e.pack(in_=self.table_frame_e,side=BOTTOM)
        self.labels.append(self.main_frame)
        
        self.title = Label(self.table_frame_w, text="Western Division",font=("Leelawadee UI", 16))
        self.title.pack(in_=self.table_frame_w, side=TOP)
        for stand in standings['data']['divisions']['west']['standings']:
            team_name = stand['abbreviation'] + " " + stand['nickname']
            position = stand['place']
            w_l_t = str(stand['wins']) + " / " + str(stand['losses']) + " / " + str(stand['ties'])
            #columns
            self.table_w['columns'] = ('position', 'team_name', 'w_l_t')
            self.table_w.column("#0", width=0, stretch=NO)
            self.table_w.column("position",anchor=CENTER, width=80)
            self.table_w.column("team_name",anchor=CENTER, width=110)
            self.table_w.column("w_l_t",anchor=CENTER, width=80)
            #headings
            self.table_w.heading("position", text="Place",anchor=CENTER)
            self.table_w.heading("team_name", text="Team",anchor=CENTER)
            self.table_w.heading("w_l_t", text="W / L / T",anchor=CENTER)
            #add data
            self.table_w.insert(parent='',index='end',iid=iid_var,text='',
                                values=(position, team_name, w_l_t))
            self.table_w.pack()
            iid_var +=1
        iid_var = 0
        self.title = Label(self.table_frame_e, text="Eastern Division",font=("Leelawadee UI", 16))
        self.title.pack(in_=self.table_frame_e, side=TOP)
        for stand in standings['data']['divisions']['east']['standings']:
            team_name = stand['abbreviation'] + " " + stand['nickname']
            position = stand['place']
            w_l_t = str(stand['wins']) + " / " + str(stand['losses']) + " / " + str(stand['ties'])
            #columns
            self.table_e['columns'] = ('position', 'team_name', 'w_l_t')
            self.table_e.column("#0", width=0, stretch=NO)
            self.table_e.column("position",anchor=CENTER, width=80)
            self.table_e.column("team_name",anchor=CENTER, width=110)
            self.table_e.column("w_l_t",anchor=CENTER, width=80)
            #headings
            self.table_e.heading("position", text="Place",anchor=CENTER)
            self.table_e.heading("team_name", text="Team",anchor=CENTER)
            self.table_e.heading("w_l_t", text="W / L / T",anchor=CENTER)
            #add data
            self.table_e.insert(parent='',index='end',iid=iid_var,text='',
                                values=(position, team_name, w_l_t))
            self.table_e.pack()
            iid_var +=1
        
    def toggle_standings(self):
        if self.sched_stand_toggle.get() == "Show Standings":
            self.destroy_labels()
            self.sched_stand_toggle.set("Show Game Time")
            self.pack_standings()
        elif self.sched_stand_toggle.get() == "Show Game Time":
            self.destroy_labels()
            self.get_labels()
            self.sched_stand_toggle.set("Show Standings")
                
    def get_labels(self):
        if len(live_now) > 0:
            self.destroy_labels()
            for game in live_now:
                header = "Live Game:"
                teams = get_teams(game)
                date_time = game['date_start']
                date, time = split_time(date_time)
                time_label = "Started at " + time
                self.header_text.set(header)
                self.teams_text.set(teams)
                self.body_text.set(time_label)
                self.pack_game()

            header = "Next Game:"
            teams = get_teams(future_games[0])
            date_time = future_games[0]['date_start']
            date, time = split_time(date_time)
            time_label = date + " at " + time
            self.header_text.set(header)
            self.teams_text.set(teams)
            self.body_text.set(time_label)
            self.pack_game()
            
        else:
            header = "Next Game:"
            teams = get_teams(future_games[0])
            date_time = future_games[0]['date_start']
            date, time = split_time(date_time)
            time_label = date + " at " + time
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
        self.bottom = Frame(root)
        self.bottom.pack(side=BOTTOM)
        self.show_standings_btn = Button(root, textvariable=self.sched_stand_toggle, command=self.toggle_standings).pack(in_=self.bottom)
        self.quit_btn = Button(root, text="Exit", command=quit_from_window).pack(in_=self.bottom, side=RIGHT)
        self.hide_btn = Button(root, text="Hide", command=hide_window).pack(in_=self.bottom, side=RIGHT)
        self.update_btn = Button(root, text="Update", command=reset_and_notify).pack(in_=self.bottom, side=RIGHT)
        self.get_labels()

if __name__ == "__main__":

    future_games = []
    live_now = []
    games = None
    notify_per_game = False
    alerted = False
    alerted_5m = False
    alerted_1h = False
    alerted_today = False
    path = Path(__file__).parent.resolve()
    cfl_ico = fr"{path}\CFL.ico"

    current_year = date.today().year
    api_key = os.environ.get('CFL_API_KEY')
    utc_time = datetime.utcnow()
    local_time = pytz.utc.localize(utc_time, is_dst=None).astimezone()
    update_games = Periodic(300,get_games())
    get_standings(current_year)

    root=Tk()
    root.title("CFL Alert")
    root.iconbitmap(cfl_ico)
    root.protocol('WM_DELETE_WINDOW', hide_window)

    app = App(root)
    notify = Periodic(60,gen_notification())
    root.resizable(False, False)
    root.mainloop()
    update_games.stop()
    notify.stop()

    #TODO
    # pretty up the GUI
    # use .json data instead of API calls in some places
    # optimize, shit takes forever to start
