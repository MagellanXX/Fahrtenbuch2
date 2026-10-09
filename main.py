import os
import time
import math
import sqlite3
import datetime
import webbrowser

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.recycleview import RecycleView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Color, RoundedRectangle, Line

from kivy_garden.mapview import MapView, MapMarker, MapLayer

# --- NATIVE ANDROID INTEGRATION (PYJNIUS) ---
if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method
    from android.permissions import request_permissions, Permission

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    LocationManager = autoclass('android.location.LocationManager')
    PowerManager = autoclass('android.os.PowerManager')
    Looper = autoclass('android.os.Looper')
    NotificationBuilder = autoclass('android.app.Notification$Builder')
    NotificationManager = autoclass('android.app.NotificationManager')
    NotificationChannel = autoclass('android.app.NotificationChannel')

    class NativeUpdateListener(PythonJavaClass):
        __javainterfaces__ = ['android/location/LocationListener']
        __javacontext__ = 'app'

        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        @java_method('(Landroid/location/Location;)V')
        def onLocationChanged(self, location):
            try:
                lat = float(location.getLatitude())
                lon = float(location.getLongitude())
                spd = float(location.getSpeed()) if location.hasSpeed() else -1.0
                acc = float(location.getAccuracy()) if location.hasAccuracy() else 99.0
                self.callback(lat, lon, spd, acc)
            except Exception:
                pass

        @java_method('(Ljava/lang/String;)V')
        def onProviderDisabled(self, provider):
            pass

        @java_method('(Ljava/lang/String;)V')
        def onProviderEnabled(self, provider):
            pass

        @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
        def onStatusChanged(self, provider, status, extras):
            pass

DB_FILE = os.path.join(os.path.dirname(__file__), "trips.db")

# --- SQLITE DATENBANK MIT TRANSAKTIONSSICHERHEIT ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    distance_km REAL,
                    duration_str TEXT,
                    avg_speed REAL,
                    max_speed REAL,
                    lat REAL,
                    lon REAL
                )''')
    conn.commit()
    conn.close()

def create_trip_entry(start_time, lat, lon):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    s_time = datetime.datetime.fromtimestamp(start_time).strftime("%H:%M:%S")
    c.execute('''INSERT INTO trips 
                 (date, start_time, end_time, distance_km, duration_str, avg_speed, max_speed, lat, lon)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (date_str, s_time, s_time, 0.0, "00:00:00", 0.0, 0.0, lat, lon))
    trip_id = c.lastrowid
    conn.commit()
    conn.close()
    return trip_id

def update_trip_entry(trip_id, end_time, dist_km, duration_str, avg_speed, max_speed, lat, lon):
    if not trip_id:
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    e_time = datetime.datetime.fromtimestamp(end_time).strftime("%H:%M:%S")
    c.execute('''UPDATE trips SET 
                 end_time = ?, distance_km = ?, duration_str = ?, avg_speed = ?, max_speed = ?, lat = ?, lon = ?
                 WHERE id = ?''',
              (e_time, dist_km, duration_str, avg_speed, max_speed, lat, lon, trip_id))
    conn.commit()
    conn.close()

def get_all_trips():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT date, start_time, end_time, distance_km, duration_str, avg_speed, max_speed, lat, lon FROM trips ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# --- UI KOMPONENTEN ---
class CardBox(BoxLayout):
    def __init__(self, bg_color=(0.14, 0.16, 0.20, 1), **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.padding = [12, 8]
        self.orientation = 'vertical'
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[12])

class RouteLineLayer(MapLayer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.coordinates = []

    def add_point(self, lat, lon):
        self.coordinates.append((lat, lon))
        self.reposition()

    def clear(self):
        self.coordinates = []
        self.canvas.clear()

    def reposition(self):
        if len(self.coordinates) < 2:
            self.canvas.clear()
            return

        mapview = self.parent
        pts = []
        for lat, lon in self.coordinates:
            x, y = mapview.get_window_xy_from(lat, lon, mapview.zoom)
            pts.extend([x, y])

        self.canvas.clear()
        with self.canvas:
            Color(0.9, 0.25, 0.28, 0.9)  # MagellanX Rot
            Line(points=pts, width=3.5)

class LiveTrackingMap(MapView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.zoom = 15
        self.lat = 53.33
        self.lon = 8.48
        self.current_marker = None
        self.route_layer = RouteLineLayer()
        self.add_layer(self.route_layer)

    def update_position(self, lat, lon):
        self.center_on(lat, lon)
        if not self.current_marker:
            self.current_marker = MapMarker(lat=lat, lon=lon)
            self.add_marker(self.current_marker)
        else:
            self.current_marker.lat = lat
            self.current_marker.lon = lon
        self.route_layer.add_point(lat, lon)

    def clear_route(self):
        self.route_layer.clear()
        if self.current_marker:
            self.remove_marker(self.current_marker)
            self.current_marker = None

# --- TRACKING ENGINE ---
class TrackerEngine:
    def __init__(self):
        self.is_tracking = False
        self.trip_id = None
        self.start_time = None
        self.last_lat = None
        self.last_lon = None
        self.last_loc_time = 0
        self.current_lat = 0.0
        self.current_lon = 0.0
        self.total_distance_m = 0.0
        self.current_speed_kmh = 0.0
        self.max_speed_kmh = 0.0
        self.gps_status_text = "GPS: Bereit"
        self.loc_mgr = None
        self.wake_lock = None
        self.native_listener = None
        self.poll_event = None

    def start(self):
        self.is_tracking = True
        self.start_time = time.time()
        self.total_distance_m = 0.0
        self.current_speed_kmh = 0.0
        self.max_speed_kmh = 0.0
        self.last_lat = None
        self.last_lon = None
        self.last_loc_time = 0
        self.gps_status_text = "GPS: Suche Signal..."

        self.trip_id = create_trip_entry(self.start_time, self.current_lat, self.current_lon)

        if platform == 'android':
            try:
                act = PythonActivity.mActivity

                pm = act.getSystemService(Context.POWER_SERVICE)
                self.wake_lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MagellanX:TrackerLock")
                self.wake_lock.acquire()

                channel_id = "magellanx_tracker"
                notif_mgr = act.getSystemService(Context.NOTIFICATION_SERVICE)
                channel = NotificationChannel(channel_id, "GPS Tracking Service", NotificationManager.IMPORTANCE_LOW)
                notif_mgr.createNotificationChannel(channel)
                builder = NotificationBuilder(act, channel_id)
                builder.setContentTitle("MagellanX Tracker")
                builder.setContentText("Streckenaufzeichnung laeuft...")
                builder.setSmallIcon(act.getApplicationInfo().icon)
                builder.setOngoing(True)
                notif_mgr.notify(101, builder.build())

                self.loc_mgr = act.getSystemService(Context.LOCATION_SERVICE)
                self.native_listener = NativeUpdateListener(self.process_location)

                best_loc = None
                for prov in ["gps", "network", "passive"]:
                    try:
                        if self.loc_mgr.isProviderEnabled(prov):
                            loc = self.loc_mgr.getLastKnownLocation(prov)
                            if loc and (best_loc is None or loc.getTime() > best_loc.getTime()):
                                best_loc = loc
                    except Exception:
                        pass

                if best_loc:
                    self.current_lat = float(best_loc.getLatitude())
                    self.current_lon = float(best_loc.getLongitude())
                    self.last_lat = self.current_lat
                    self.last_lon = self.current_lon
                    acc = float(best_loc.getAccuracy()) if best_loc.hasAccuracy() else 50.0
                    self.gps_status_text = f"Live GPS: ±{int(acc)}m"

                for p in ["gps", "network"]:
                    try:
                        if self.loc_mgr.isProviderEnabled(p):
                            self.loc_mgr.requestLocationUpdates(
                                p,
                                int(1000),
                                float(0.0),
                                self.native_listener,
                                Looper.getMainLooper()
                            )
                    except Exception as pe:
                        print(f"Provider {p} Fehler: {pe}")

            except Exception as e:
                self.gps_status_text = f"Sensor-Fehler: {e}"

        self.poll_event = Clock.schedule_interval(self._poll_gps, 1.0)

    def _poll_gps(self, dt):
        if not self.is_tracking or platform != 'android' or not self.loc_mgr:
            return

        best_loc = None
        for prov in ["gps", "network", "passive"]:
            try:
                if self.loc_mgr.isProviderEnabled(prov):
                    loc = self.loc_mgr.getLastKnownLocation(prov)
                    if loc:
                        if best_loc is None or loc.getTime() > best_loc.getTime():
                            best_loc = loc
            except Exception:
                pass

        if best_loc:
            t = best_loc.getTime()
            lat = float(best_loc.getLatitude())
            lon = float(best_loc.getLongitude())
            acc = float(best_loc.getAccuracy()) if best_loc.hasAccuracy() else 99.0
            spd = float(best_loc.getSpeed()) if best_loc.hasSpeed() else -1.0

            if t > self.last_loc_time:
                self.last_loc_time = t
                self.process_location(lat, lon, spd, acc)

    def stop(self):
        if not self.is_tracking:
            return
        self.is_tracking = False
        end_time = time.time()

        if self.poll_event:
            self.poll_event.cancel()
            self.poll_event = None

        if platform == 'android':
            if self.loc_mgr and self.native_listener:
                try:
                    self.loc_mgr.removeUpdates(self.native_listener)
                except Exception:
                    pass

            if self.wake_lock and self.wake_lock.isHeld():
                try:
                    self.wake_lock.release()
                except Exception:
                    pass

            try:
                act = PythonActivity.mActivity
                notif_mgr = act.getSystemService(Context.NOTIFICATION_SERVICE)
                notif_mgr.cancel(101)
            except Exception:
                pass

        stats = self.get_stats()
        update_trip_entry(self.trip_id, end_time, float(stats['dist_km']), stats['time_str'],
                          float(stats['avg_speed_kmh']), float(stats['max_speed_kmh']), self.current_lat, self.current_lon)
        self.gps_status_text = "Fahrt gespeichert!"

    @mainthread
    def process_location(self, lat, lon, speed_ms, accuracy):
        if accuracy > 80.0:
            return

        now = time.time()
        self.current_lat = lat
        self.current_lon = lon
        self.gps_status_text = f"Live GPS: ±{int(accuracy)}m"

        if self.last_lat is not None and self.last_lon is not None:
            d = self._haversine(self.last_lat, self.last_lon, lat, lon)
            if d >= 1.0:
                self.total_distance_m += d
                if speed_ms >= 0:
                    self.current_speed_kmh = speed_ms * 3.6
                else:
                    self.current_speed_kmh = d * 3.6

                if self.current_speed_kmh > self.max_speed_kmh:
                    self.max_speed_kmh = self.current_speed_kmh

                stats = self.get_stats()
                update_trip_entry(self.trip_id, now, float(stats['dist_km']), stats['time_str'],
                                  float(stats['avg_speed_kmh']), float(stats['max_speed_kmh']), self.current_lat, self.current_lon)
            else:
                self.current_speed_kmh = 0.0
        else:
            if speed_ms > 0:
                self.current_speed_kmh = speed_ms * 3.6

        self.last_lat = lat
        self.last_lon = lon

    def _haversine(self, lat1, lon1, lat2, lon2):
        r = 6371000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_stats(self):
        elapsed = (time.time() - self.start_time) if self.start_time else 0
        dist_km = self.total_distance_m / 1000.0
        avg_speed = (dist_km / (elapsed / 3600.0)) if elapsed > 0 else 0.0
        return {
            "time_str": time.strftime("%H:%M:%S", time.gmtime(elapsed)),
            "dist_km": f"{dist_km:.2f}",
            "speed_kmh": f"{self.current_speed_kmh:.1f}",
            "avg_speed_kmh": f"{avg_speed:.1f}",
            "max_speed_kmh": f"{self.max_speed_kmh:.1f}",
            "status": self.gps_status_text
        }

# --- DASHBOARD SCREEN ---
class DashboardScreen(Screen):
    def __init__(self, tracker, **kwargs):
        super().__init__(**kwargs)
        self.tracker = tracker

        root = BoxLayout(orientation='vertical', padding=14, spacing=10)
        with root.canvas.before:
            Color(0.07, 0.08, 0.11, 1)
            self.bg = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda i, v: setattr(self.bg, 'pos', v), size=lambda i, v: setattr(self.bg, 'size', v))

        nav_bar = BoxLayout(size_hint_y=0.08)
        title = Label(text="MAGELLAN-X TRACKER", font_size='18sp', bold=True, color=(0.95, 0.96, 0.98, 1))
        btn_history = Button(text="Historie ➔", size_hint_x=0.35, font_size='13sp', bold=True,
                             background_normal='', background_color=(0.2, 0.25, 0.35, 1))
        btn_history.bind(on_press=self.go_to_history)
        nav_bar.add_widget(title)
        nav_bar.add_widget(btn_history)
        root.add_widget(nav_bar)

        self.lbl_gps_status = Label(text="GPS: Bereit", font_size='11sp',
                                    color=(0.9, 0.7, 0.2, 1), size_hint_y=0.04)
        root.add_widget(self.lbl_gps_status)

        speed_card = CardBox(bg_color=(0.11, 0.14, 0.20, 1), size_hint_y=0.20, spacing=2)
        lbl_speed_title = Label(text="AKTUELLES TEMPO", font_size='11sp', bold=True, color=(0.9, 0.25, 0.28, 1), size_hint_y=0.2)
        self.val_speed = Label(text="0.0", font_size='46sp', bold=True, color=(1, 1, 1, 1), size_hint_y=0.6)
        lbl_unit = Label(text="km/h", font_size='12sp', color=(0.5, 0.55, 0.65, 1), size_hint_y=0.2)
        speed_card.add_widget(lbl_speed_title)
        speed_card.add_widget(self.val_speed)
        speed_card.add_widget(lbl_unit)
        root.add_widget(speed_card)

        self.live_map = LiveTrackingMap(size_hint_y=0.32)
        root.add_widget(self.live_map)

        grid = GridLayout(cols=2, spacing=8, size_hint_y=0.22)
        c_dist = CardBox()
        c_dist.add_widget(Label(text="DISTANZ", font_size='10sp', bold=True, color=(0.55, 0.6, 0.7, 1), size_hint_y=0.3))
        self.val_dist = Label(text="0.00 km", font_size='18sp', bold=True, color=(0.95, 0.95, 0.95, 1), size_hint_y=0.7)
        c_dist.add_widget(self.val_dist)

        c_time = CardBox()
        c_time.add_widget(Label(text="FAHRZEIT", font_size='10sp', bold=True, color=(0.55, 0.6, 0.7, 1), size_hint_y=0.3))
        self.val_time = Label(text="00:00:00", font_size='18sp', bold=True, color=(0.95, 0.95, 0.95, 1), size_hint_y=0.7)
        c_time.add_widget(self.val_time)

        c_avg = CardBox()
        c_avg.add_widget(Label(text="Ø TEMPO", font_size='10sp', bold=True, color=(0.55, 0.6, 0.7, 1), size_hint_y=0.3))
        self.val_avg = Label(text="0.0 km/h", font_size='17sp', bold=True, color=(0.95, 0.95, 0.95, 1), size_hint_y=0.7)
        c_avg.add_widget(self.val_avg)

        c_max = CardBox()
        c_max.add_widget(Label(text="MAX TEMPO", font_size='10sp', bold=True, color=(0.55, 0.6, 0.7, 1), size_hint_y=0.3))
        self.val