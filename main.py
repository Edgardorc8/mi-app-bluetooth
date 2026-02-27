import os
import threading
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.list import TwoLineListItem

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    from plyer import filechooser

UUID_PUERTO_SERIE = "00001101-0000-1000-8000-00805F9B34FB"

# --- DISEÑO DE LA INTERFAZ (UI) EN FORMATO KV ---
# Esto es mucho más limpio que crearlo con Python puro.
KV_UI = '''
MDScreen:
    MDBoxLayout:
        orientation: "vertical"
        
        # Barra superior al estilo Android
        MDTopAppBar:
            title: "Envío Bluetooth"
            elevation: 4
            md_bg_color: app.theme_cls.primary_color

        # Etiqueta de estado
        MDLabel:
            id: etiqueta_estado
            text: "Estado: Desconectado"
            halign: "center"
            size_hint_y: None
            height: "50dp"
            theme_text_color: "Secondary"

        # Botón principal de escaneo
        MDRaisedButton:
            text: "BUSCAR DISPOSITIVOS EMPAREJADOS"
            pos_hint: {"center_x": .5}
            on_release: app.buscar_dispositivos()
            elevation: 2

        # Lista de dispositivos con Scroll nativo
        ScrollView:
            MDList:
                id: lista_dispositivos

        # Tarjeta inferior para la gestión de archivos
        MDCard:
            orientation: "vertical"
            size_hint: 1, None
            height: "140dp"
            padding: "15dp"
            spacing: "10dp"
            elevation: 3
            radius: [20, 20, 0, 0] # Bordes redondeados arriba
            
            MDLabel:
                id: etiqueta_archivo
                text: "Ningún archivo seleccionado"
                halign: "center"
                theme_text_color: "Hint"
                
            MDBoxLayout:
                orientation: "horizontal"
                spacing: "15dp"
                pos_hint: {"center_x": .5}
                size_hint_x: None
                width: self.minimum_width
                
                MDRectangleFlatButton:
                    text: "ELEGIR ARCHIVO"
                    on_release: app.seleccionar_archivo()
                    
                MDRaisedButton:
                    id: btn_enviar
                    text: "ENVIAR ARCHIVO"
                    disabled: True
                    md_bg_color: 0.2, 0.8, 0.2, 1 if not self.disabled else app.theme_cls.disabled_hint_text_color
                    on_release: app.iniciar_envio_archivo()
'''

class AplicacionBluetooth(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light" # Puedes cambiar a "Dark" si prefieres
        
        self.socket_bt = None
        self.flujo_salida = None
        self.ruta_archivo_seleccionado = None
        
        # Cargar la interfaz diseñada arriba
        self.pantalla = Builder.load_string(KV_UI)
        
        if platform == 'android':
            self.solicitar_permisos_android()
        else:
            self.actualizar_estado("Aviso: Esta app requiere Android.")
            
        return self.pantalla

    def actualizar_estado(self, texto):
        Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_estado, 'text', texto))

    def solicitar_permisos_android(self):
        permisos = [
            Permission.BLUETOOTH_CONNECT, Permission.BLUETOOTH_SCAN,
            Permission.ACCESS_FINE_LOCATION, Permission.READ_EXTERNAL_STORAGE, Permission.READ_MEDIA_IMAGES
        ]
        request_permissions(permisos)

    def buscar_dispositivos(self):
        if platform != 'android': return
        self.pantalla.ids.lista_dispositivos.clear_widgets()
        self.actualizar_estado("Estado: Buscando...")
        
        try:
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            adaptador = AdaptadorBluetooth.getDefaultAdapter()
            if not adaptador:
                self.actualizar_estado("Error: Sin Bluetooth")
                return
            if not adaptador.isEnabled():
                adaptador.enable()
                self.actualizar_estado("Activando Bluetooth...")
                return
                
            dispositivos = adaptador.getBondedDevices().toArray()
            if len(dispositivos) == 0:
                self.actualizar_estado("No hay dispositivos.")
                return
                
            for dispositivo in dispositivos:
                # Usamos el elemento de lista nativo de Material Design
                item = TwoLineListItem(
                    text=dispositivo.getName(),
                    secondary_text=dispositivo.getAddress(),
                    on_release=lambda x, d=dispositivo: self.iniciar_conexion(d)
                )
                self.pantalla.ids.lista_dispositivos.add_widget(item)
                
            self.actualizar_estado("Estado: Dispositivos listos")
        except Exception as error:
            self.actualizar_estado(f"Error: {str(error)}")

    def iniciar_conexion(self, dispositivo_java):
        self.actualizar_estado(f"Conectando a {dispositivo_java.getName()}...")
        threading.Thread(target=self.conectar_a_dispositivo, args=(dispositivo_java,), daemon=True).start()

    def conectar_a_dispositivo(self, dispositivo_java):
        try:
            ClaseUUID = autoclass('java.util.UUID')
            uuid = ClaseUUID.fromString(UUID_PUERTO_SERIE)
            self.socket_bt = dispositivo_java.createRfcommSocketToServiceRecord(uuid)
            
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            AdaptadorBluetooth.getDefaultAdapter().cancelDiscovery()
            
            self.socket_bt.connect()
            self.flujo_salida = self.socket_bt.getOutputStream()
            
            self.actualizar_estado(f"Conectado a: {dispositivo_java.getName()}")
            if self.ruta_archivo_seleccionado:
                Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))
        except Exception as error:
            self.actualizar_estado("Error al conectar.")
            if self.socket_bt:
                try: self.socket_bt.close()
                except: pass

    def seleccionar_archivo(self):
        if platform == 'android':
            try: filechooser.open_file(on_selection=self.al_seleccionar_archivo)
            except Exception as e: self.pantalla.ids.etiqueta_archivo.text = f"Error: {e}"
        else:
            self.al_seleccionar_archivo(["/ruta/prueba.txt"])

    def al_seleccionar_archivo(self, seleccion):
        if seleccion and len(seleccion) > 0:
            self.ruta_archivo_seleccionado = seleccion[0]
            nombre = os.path.basename(self.ruta_archivo_seleccionado)
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_archivo, 'text', nombre))
            if self.flujo_salida:
                Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))

    def iniciar_envio_archivo(self):
        if not self.ruta_archivo_seleccionado or not self.flujo_salida: return
        self.actualizar_estado("Enviando...")
        self.pantalla.ids.btn_enviar.disabled = True
        threading.Thread(target=self.hilo_enviar_archivo, daemon=True).start()

    def hilo_enviar_archivo(self):
        try:
            with open(self.ruta_archivo_seleccionado, "rb") as archivo:
                while True:
                    fragmento = archivo.read(1024)
                    if not fragmento: break
                    self.flujo_salida.write(fragmento)
            self.flujo_salida.flush()
            self.actualizar_estado("Estado: ¡Enviado con éxito!")
        except Exception as error:
            self.actualizar_estado("Error de envío.")
        finally:
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))

if __name__ == '__main__':
    AplicacionBluetooth().run()
