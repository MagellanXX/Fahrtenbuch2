[app]

# (str) Title of your application
title = MagellanX Tracker

# (str) Package name
package.name = fahrtenbuch

# (str) Package domain (needed for android packaging)
package.domain = org.gpstracker.app

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 0.4

# (list) Application requirements
# mapview benoetigt requests, urllib3, certifi fuer den Online-Download der Kartenkacheln
requirements = python3,kivy==2.3.0,pyjnius,requests,urllib3,certifi,mapview

# (str) Presplash of the application
presplash.filename = presplash.png

# (str) Icon of the application
icon.filename = icon.png

# (str) Supported orientation
orientation = portrait

# (bool) Fullscreen
fullscreen = 0

# (list) Permissions
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,INTERNET,WAKE_LOCK,FOREGROUND_SERVICE,POST_NOTIFICATIONS

# (int) Target Android API
android.api = 33

# (int) Minimum API
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (int) Android NDK API
android.ndk_api = 21

# (bool) Accept SDK license
android.accept_sdk_license = True

# (list) Architectures
android.archs = arm64-v8a

# (str) The branch to use for python-for-android
p4a.branch = release-2024.01.21

# (bool) Allow backup
android.allow_backup = True

[buildozer]

log_level = 2
warn_on_root = 1