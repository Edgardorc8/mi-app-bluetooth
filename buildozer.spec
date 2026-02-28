[app]
title = Bluetooth Directo
package.name = bluetoothdirecto
package.domain = org.edgardo
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3, kivy==2.3.0, kivymd==1.1.1, pyjnius, plyer, android

# -------------------------------------------------------------------------
# PERMISOS PARA BLUETOOTH EN TODAS LAS VERSIONES DE ANDROID
# -------------------------------------------------------------------------
# Para Android 12+ (API 31+): BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADVERTISE
# Para Android 11- (API 30-): BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION
# -------------------------------------------------------------------------
android.permissions = \
    BLUETOOTH, \
    BLUETOOTH_ADMIN, \
    BLUETOOTH_SCAN, \
    BLUETOOTH_CONNECT, \
    BLUETOOTH_ADVERTISE, \
    ACCESS_FINE_LOCATION, \
    ACCESS_COARSE_LOCATION, \
    ACCESS_BACKGROUND_LOCATION, \
    READ_EXTERNAL_STORAGE, \
    READ_MEDIA_IMAGES, \
    READ_MEDIA_VIDEO, \
    READ_MEDIA_AUDIO, \
    WRITE_EXTERNAL_STORAGE

# Para Android 12+, podemos limitar la ubicación a API < 31
# (pero incluimos todo para simplificar)

android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33

android.archs = arm64-v8a, armeabi-v7a
orientation = portrait

# Para usar FileProvider (opcional, pero recomendado)
android.add_src = provider_paths.xml
android.gradle_dependencies = androidx.core:core:1.9.0

[buildozer]
log_level = 2
warn_on_root = 1
