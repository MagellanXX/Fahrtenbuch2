[app]
title = Fahrtenbuch GPS
package.name = fahrtenbuch
package.domain = org.gpstracker.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

# Keine externen Garden/C-Plugins, die den Compiler sprengen:
requirements = python3,kivy==2.3.0,plyer

orientation = portrait
fullscreen = 0
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,INTERNET

# Stabile Android SDK/NDK Einstellungen
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a

# ZWINGEND: Verhindert, dass Buildozer den unfertigen Python 3.14 Master zieht!
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1