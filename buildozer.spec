[app]
title = App Compartir
package.name = compartirapp
package.domain = org.edgardo
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,xml
version = 0.1
requirements = python3, kivy==2.3.0, kivymd==1.1.1, pyjnius, plyer, android

# Permisos mínimos necesarios (Bluetooth no hace falta, el menú nativo lo maneja)
android.permissions = READ_EXTERNAL_STORAGE, READ_MEDIA_IMAGES, READ_MEDIA_VIDEO, READ_MEDIA_AUDIO

android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
orientation = portrait

# Para FileProvider
android.add_src = provider_paths.xml
android.gradle_dependencies = androidx.core:core:1.9.0

[buildozer]
log_level = 2
warn_on_root = 1
